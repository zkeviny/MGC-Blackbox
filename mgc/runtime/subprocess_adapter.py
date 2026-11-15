"""Subprocess Adapter — 1.5.1 Sprint 2.5 phase3 精简版。

职责：在 bootstrap 子进程内拦截业务代码的 subprocess.run，调 HTTP 拿明文后
       自己 Popen "python -m mgc.bootstrap" 跑被调脚本，communicate 拿 stdout，
       构造 _MgCompletedProcess 返回业务代码。

关键设计：
- bootstrap 内 patched_run 自己 Popen 子进程（不通过 mgc 主进程）
- HTTP /sensitive/get 拿明文（主进程空闲时立即响应）
- 不依赖主进程同步等孙进程
- 业务代码 0 改动（subprocess.run 写法完全不变）

限制：
- 仅支持同 owner + 同 diff_1 + 同 diff_2 的脚本互相调用
- 不支持跨 folder 调用
- 不支持跨 owner 调用
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from mgc.runtime.errors import MgcSecurityViolation

logger = logging.getLogger(__name__)


# ============================================================
# _MgCompletedProcess — 模拟 subprocess.CompletedProcess
# ============================================================

class _MgCompletedProcess:
    """模拟 subprocess.CompletedProcess，对外暴露相同接口。"""

    def __init__(self, args, returncode, stdout, stderr):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def check_returncode(self):
        if self.returncode != 0:
            raise subprocess.CalledProcessError(
                self.returncode, self.args, self.stdout, self.stderr
            )


# ============================================================
# SubprocessAdapter — 拦截 + HTTP 拿明文 + 自己 Popen bootstrap
# ============================================================

class SubprocessAdapter:
    """subprocess.run monkey-patch。

    在 bootstrap 子进程内拦截 subprocess.run 调用：
    1. 解析 cmd_list 拿 target_diff_3
    2. 校验 5+1 授权（精确匹配 all_records 中的 script records）
    3. HTTP /sensitive/get 拿被调脚本明文
    4. 自己 Popen "python -m mgc.bootstrap" 跑被调脚本
    5. communicate 等子进程跑完
    6. 构造 _MgCompletedProcess 返回业务代码

    不受管脚本 → fallback 到真实 subprocess.run
    """

    def __init__(
        self,
        context,
        mgc_api_port: Optional[int],
        mgc_api_token: Optional[str],
        internal_token: Optional[str] = None,
    ):
        """
        Args:
            context: ScriptExecutionContext（当前 root 脚本的 ctx）
            mgc_api_port: mgc 主进程 HTTP 端口（patched_run 调 /sensitive/get 用）
            mgc_api_token: mgc 主进程 HTTP token
            internal_token: phase4 方案C：内部 RPC token（调 /sensitive/unseal_for_child 用）
                与 mgc_api_token 隔离，仅在 mgc 子进程内有效
        """
        self.context = context
        self.mgc_api_port = mgc_api_port
        self.mgc_api_token = mgc_api_token
        self.internal_token = internal_token or ""
        # 5+1 授权集合（精确匹配）
        self._managed = self._build_managed_index(context.all_records)

    @staticmethod
    def _build_managed_index(all_records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """构造 target_diff_3 -> record 的精确匹配索引（仅 script 类型）。"""
        index = {}
        for r in all_records or []:
            if r.get("info_type") == "script":
                diff_3 = r.get("diff_3")
                if diff_3:
                    index[diff_3] = r
        return index

    # ---------- 公开接口 ----------

    def patched_run(self, cmd, *args, **kwargs):
        """subprocess.run 的 monkey-patch。"""
        import sys
        is_managed = self._is_managed(cmd) if isinstance(cmd, (list, tuple)) else False
        # phase6 收尾：移除 DBG-patched_run 直接 print（曾暴露 cmd、managed_keys、脚本名列表）
        # 改用 logger.debug，仅记录字段名 + 长度，不打印 cmd / keys 内容。
        logger.debug(
            f"[patched_run] is_managed={is_managed}, "
            f"managed_keys_count={len(self._managed)}, "
            f"cmd0_len={len(cmd[0]) if isinstance(cmd, (list, tuple)) and cmd else 0}"
        )
        logger.info(
            f"patched_run INTERCEPT: cmd={cmd if not isinstance(cmd, (list, tuple)) else cmd[:3]}"
        )
        if isinstance(cmd, (list, tuple)) and is_managed:
            return self._execute_via_bootstrap(cmd, *args, **kwargs)
        # Unmanaged script → fall back to the real subprocess.run.
        logger.info(
            f"patched_run FALLBACK to real subprocess.run: cmd={cmd if not isinstance(cmd, (list, tuple)) else cmd[:3]}"
        )
        return _real_subprocess_run(cmd, *args, **kwargs)

    # ---------- 内部：判定 + 解析 ----------

    def _is_managed(self, cmd_list: List[str]) -> bool:
        """判定 cmd 是否为受管的受控脚本调用。

        判定条件：
        - cmd_list[0] 是 python/python3
        - cmd_list[1] 是路径（如 script/config.py）
        - 该路径在 _managed 中精确命中（业务代码写 Path(__file__).parent / "x.py"
          时，__file__ = logical_diff_3，所以 parent + /x.py 也是合法 diff_3 形式）

        Basename fallback:
        Business code commonly computes an absolute path via
        `Path(__file__).resolve().parent / "x.py"`, but the database stores
        logical diff_3 paths. When the exact match fails, fall back to a
        UNIQUE basename match against _managed:
        - 0 matches → unmanaged (fall back to real subprocess.run)
        - 1 match  → managed; patched_run takes over
        - 2+ matches → unmanaged (ambiguous — prefer false-negative over false-positive)
        """
        if not cmd_list or len(cmd_list) < 2:
            return False
        # 第 1 个参数应该是 python 解释器
        exe = cmd_list[0]
        if not isinstance(exe, str):
            return False
        base = os.path.basename(exe).lower()
        # Normalize "python.exe" / "python3.exe" on Win to "python" / "python3"
        # so the interpreter check works cross-platform.
        if base.endswith(".exe"):
            base = base[:-4]
        if base not in ("python", "python3") and not base.startswith("python"):
            return False
        # 第 2 个参数是被调脚本路径
        target = cmd_list[1]
        if not isinstance(target, str):
            return False
        # Normalize path separators (backslash → forward slash) so
        # _managed index lookups and stored diff_3 (always POSIX) match.
        target = self._normalize_path(target)
        # Exact match against _managed.
        if target in self._managed:
            return True
        # Fall back to unique basename match when the absolute path
        # (from Path(__file__).resolve()) cannot be located exactly.
        return self._basename_unique_match(target)

    def _basename_unique_match(self, target: str) -> bool:
        """Unique-basename fallback against _managed.

        Args:
            target: 归一化后的 cmd_list[1]（POSIX 风格）

        Returns:
            True  - 唯一命中 self._managed 的某条 diff_3
            False - 0 命中或多命中（歧义）
        """
        # 取 target 的 basename（去掉路径前缀）
        target_basename = os.path.basename(target)
        if not target_basename:
            return False
        hits: List[str] = []
        for managed_diff_3 in self._managed.keys():
            if os.path.basename(managed_diff_3) == target_basename:
                hits.append(managed_diff_3)
        if len(hits) == 1:
            # Debug log records only field names + length; do not print diff_3.
            logger.debug(
                f"_basename_unique_match: target_basename matched 1 entry, "
                f"hits_count={len(hits)}"
            )
            return True
        return False

    @staticmethod
    def _normalize_path(p: str) -> str:
        """跨平台路径归一化（统一 POSIX `/` 分隔符）。

        业务代码在 Win 上写 `Path(__file__).parent / "config.py"` 会得到
        "script\\\\config.py"（反斜杠）。但 _managed 索引和数据库存的
        diff_3 都是 POSIX 风格 "script/config.py"。需要归一化比对。

        同时兼容业务代码传绝对路径 vs 存储的相对路径（diff_3 形式）。
        """
        if not p:
            return p
        # 反斜杠 → 正斜杠
        normalized = p.replace("\\", "/")
        # 去掉前导 "./"
        if normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized

    def _resolve_target(self, cmd_list: List[str]) -> Optional[str]:
        """从 cmd_list 解析 target_diff_3。

        策略：
        1. 精确匹配（与存储的 diff_3 完全一致），跨平台路径风格归一化
        2. 精确匹配失败时，fallback 到 basename 唯一命中
        """
        if len(cmd_list) < 2:
            return None
        target = self._normalize_path(cmd_list[1])
        if target in self._managed:
            return target
        # Basename-unique fallback when the caller passed an absolute path.
        # Returns the matched diff_3 so downstream _authorize /
        # _execute_via_bootstrap can use the logical diff_3 to dispatch.
        target_basename = os.path.basename(target)
        if not target_basename:
            return None
        hits: List[str] = []
        for managed_diff_3 in self._managed.keys():
            if os.path.basename(managed_diff_3) == target_basename:
                hits.append(managed_diff_3)
        if len(hits) == 1:
            return hits[0]
        # 0 or multiple matches (ambiguous) → return None (fall back to real subprocess.run).
        return None

    def _authorize(self, cmd_list: List[str], target_diff_3: str) -> bool:
        """5+1 授权校验（精确匹配 + 同 owner + ext08.calls 包含 target）。"""
        if target_diff_3 not in self._managed:
            logger.warning(
                f"_authorize failed: {target_diff_3} not in managed index"
            )
            return False

        target_record = self._managed[target_diff_3]

        # 5+1：同 owner + 同 diff_1 + 同 diff_2
        if target_record.get("info_owner") != self.context.info_owner:
            logger.warning(
                f"_authorize failed: owner mismatch: "
                f"{target_record.get('info_owner')} vs {self.context.info_owner}"
            )
            return False
        if target_record.get("diff_1") != self.context.diff_1:
            logger.warning(
                f"_authorize failed: diff_1 mismatch: "
                f"{target_record.get('diff_1')} vs {self.context.diff_1}"
            )
            return False
        if target_record.get("diff_2") != self.context.diff_2:
            logger.warning(
                f"_authorize failed: diff_2 mismatch: "
                f"{target_record.get('diff_2')} vs {self.context.diff_2}"
            )
            return False

        # ext08.calls 应包含该 target（静态授权）
        ext08 = self.context.ext08 or {}
        calls = ext08.get("calls", [])
        for c in calls:
            if isinstance(c, dict) and c.get("target_diff_3") == target_diff_3:
                return True
        # 如果 root 没有 ext08.calls（如 is_dependency=True），跳过此校验
        # （fall back to exact match only）
        if not calls:
            return True
        logger.warning(
            f"_authorize failed: target_diff_3={target_diff_3} not in ext08.calls"
        )
        return False

    # ---------- 内部：执行被调脚本 ----------

    def _execute_via_bootstrap(
        self,
        cmd_list: List[str],
        *,
        timeout: Optional[float] = None,
        **kwargs,
    ):
        """拦截后：HTTP 拿明文 + 自己 Popen bootstrap + communicate 拿 stdout。"""
        target_diff_3 = self._resolve_target(cmd_list)
        if not target_diff_3:
            # Unmanaged or path mismatch → fall back to the real subprocess.run.
            return _real_subprocess_run(cmd_list, timeout=timeout, **kwargs)

        # 5+1 授权校验
        if not self._authorize(cmd_list, target_diff_3):
            raise MgcSecurityViolation(
                target=target_diff_3,
                reason="not authorized by 5+1",
            )

        # Step 1: HTTP /sensitive/get 拿被调脚本明文
        plaintext = self._http_get_plaintext(target_diff_3)
        if not plaintext:
            logger.warning(
                f"patched_run: failed to get plaintext for {target_diff_3}, "
                f"fallback to real subprocess.run"
            )
            return _real_subprocess_run(cmd_list, timeout=timeout, **kwargs)

        # Step 2: 解析业务代码传的 args（cmd[2:] 跳过 [python, target_path]）
        business_args = cmd_list[2:]

        # Step 2.5: 从 all_records 查找孙进程自己的 ext08
        #   孙进程需要知道自己的调用图（caller_ext08_calls），否则 import hook / subprocess 拦截
        #   的 4.4 校验（NOT_IN_CALLS）会失败。
        #   这里只读 records，不依赖主进程查库（主进程繁忙时避免 RT 增加）。
        child_ext08: Dict[str, Any] = {}
        for r in (self.context.all_records or []):
            r_diff = r.get("diff_3")
            if r_diff == target_diff_3:
                raw_ext08 = r.get("ext08")
                # DB 返回的 ext08 可能是 JSON 字符串或 dict
                if isinstance(raw_ext08, str):
                    try:
                        child_ext08 = json.loads(raw_ext08)
                    except Exception:
                        child_ext08 = {}
                elif isinstance(raw_ext08, dict):
                    child_ext08 = raw_ext08
                else:
                    child_ext08 = {}
                if not isinstance(child_ext08, dict):
                    child_ext08 = {}
                break
        # phase6 收尾：移除 DBG-child-ext08 直接 print，改用 logger.debug（仅长度）

        # Step 3: Popen "python -m mgc.bootstrap" 跑被调脚本
        try:
            payload = json.dumps({
                "info_owner": self.context.info_owner,
                "diff_1": self.context.diff_1,
                "diff_2": self.context.diff_2,
                "diff_3": target_diff_3,
                "ext02": json.dumps(business_args),
                # ★ phase6 fix: 合并孙进程自己的 ext08（含 calls）+ is_dependency 标记
                #   这样孙进程能用自己的 callgraph 通过主进程 4.4 校验
                "ext08": {"is_dependency": True, **child_ext08},
                "root_source": plaintext,
                "mgc_api_port": self.mgc_api_port,
                "mgc_api_token": self.mgc_api_token,
                "parent_execution_id": self.context.execution_id,
                # ★ phase6 fix: 传递 internal_token（不是 mgc_api_token）给孙进程
                #   internal_token 用于 unseal_for_child RPC 鉴权，必须用同一个 token
                "internal_token": self.internal_token,
                # === 1.5.2 hotfix: 透传 all_records 给孙进程 ===
                #   PM 用例 7.6 follow-up：D→C→A 场景下，C 进程的 _managed 索引为空
                #   导致 C 内 patched_run _is_managed("config_a.py") 返回 False，
                #   fallback 到真实 subprocess.run，最终 Python 解释器找不到 config_a.py（cwd 问题）。
                #   根因：D 启动 C 的 payload 没传 all_records，C bootstrap 启动后
                #   ScriptExecutionContext.from_dict 拿到 all_records=[]（默认）。
                #   修复：把 D 的 context.all_records（pkg 内所有 record）传给 C，
                #   C 的 SubprocessAdapter._managed 就能正确构建，patched_run 正确拦截。
                "all_records": list(self.context.all_records or []),
            }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"patched_run: payload build failed: {e}")
            return _real_subprocess_run(cmd_list, timeout=timeout, **kwargs)

        try:
            # ★ phase6 DEBUG: 把孙进程 stderr 重定向到独立文件
            #   避免 daemon 线程被 _start_stderr_drain 在子进程退出时
            #   读到空 buffer（stdout/stderr 未刷）的 race condition。
            import os, tempfile
            debug_dir = os.path.expanduser("~/.mgc/logs/child_stderr")
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f"{target_diff_3.replace('/', '_')}_pid{os.getpid()}.log")
            debug_stderr = open(debug_file, "w", encoding="utf-8")
            # 1.5.2 hotfix：不传 cwd，继承当前进程 cwd（绝对路径）。
            # 原因同 execute_script_ctx：sealed pkg 脚本虚拟目录不存在，传 cwd 会 Popen 失败。
            process = subprocess.Popen(
                # 1.5.4 Linux 修复：同 execute_script_ctx，禁用硬编码 "python"
                # （Linux 仅有 python3），改用启动当前进程的解释器。
                [sys.executable, "-m", "mgc.bootstrap"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=debug_stderr,  # ★ 写到独立文件，避免 daemon race condition
                text=True,
                # ★ phase5+ Win 修复：显式 UTF-8，与终端 locale 解耦
                #   Win locale=cp936 时 Popen 默认会用 cp936 编 stdin/stdout，
                #   与 bootstrap 端 PYTHONIOENCODING=utf-8 解码错位 → UnicodeDecodeError
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"patched_run: Popen bootstrap failed: {e}")
            return _MgCompletedProcess(
                args=cmd_list,
                returncode=-1,
                stdout="",
                stderr=f"[mgc] patched_run: Popen bootstrap failed: {e}",
            )

        try:
            stdout, stderr = process.communicate(input=payload, timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except Exception:
                pass
            stdout, stderr = process.communicate()
            return _MgCompletedProcess(
                args=cmd_list,
                returncode=-1,
                stdout=stdout,
                stderr=(stderr or "") + "\n[mgc] patched_run: timeout",
            )
        except Exception as e:
            logger.error(f"patched_run: communicate failed: {e}")
            try:
                process.kill()
            except Exception:
                pass
            return _MgCompletedProcess(
                args=cmd_list,
                returncode=-1,
                stdout="",
                stderr=f"[mgc] patched_run: communicate failed: {e}",
            )

        return _MgCompletedProcess(
            args=cmd_list,
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr,
        )
        # phase6 收尾：移除 DBG-patched_run-result 直接 print
        # （曾暴露 returncode、stdout/stderr 长度、stderr 内容前 500 字符）
        # —— 改为仅记录字段名 + 长度
        logger.debug(
            f"[patched_run-result] target={target_diff_3}, "
            f"rc={process.returncode}, "
            f"stdout_len={len(stdout)}, "
            f"stderr_len={len(stderr)}"
        )

    # ---------- 内部：HTTP 拿明文 ----------

    def _http_get_plaintext(self, target_diff_3: str) -> Optional[str]:
        """通过 HTTP /sensitive/unseal_for_child 拿被调脚本明文（phase4 方案C）。

        主进程空闲时立即响应（fire-and-forget execute_script_ctx 已返回 pid）。
        使用 internal_token 鉴权（与 mgc_api_token 隔离），主进程 unseal 后返回真明文。

        5+1 校验由主进程 unseal_for_child handler 强制执行（同 owner + diff_1 + diff_2 +
        ext08.calls 包含 target），即使 internal_token 泄露也受 5+1 约束。
        """
        if not self.mgc_api_port or not self.mgc_api_token:
            logger.error(
                "patched_run: mgc_api_port / mgc_api_token not set, "
                "cannot fetch plaintext"
            )
            return None
        if not self.internal_token:
            logger.error(
                "patched_run: internal_token not set, "
                "cannot call /sensitive/unseal_for_child"
            )
            return None

        try:
            import requests  # noqa: F401
        except ImportError:
            logger.error("patched_run: 'requests' library not available")
            return None

        # 提取 caller_ext08.calls（callgraph 静态授权）
        ext08 = self.context.ext08 or {}
        if not isinstance(ext08, dict):
            ext08 = {}
        caller_calls = ext08.get("calls", []) if isinstance(ext08.get("calls"), list) else []

        try:
            resp = requests.post(
                f"http://127.0.0.1:{self.mgc_api_port}/api/mgc/sensitive/unseal_for_child",
                headers={
                    "X-MGC-Token": self.mgc_api_token,
                    "X-MGC-Internal-Token": self.internal_token,
                    "Content-Type": "application/json",
                },
                json={
                    # caller 身份（来自 ScriptExecutionContext，bootstrap payload 已含完整 5 字段）
                    "caller_info_owner": self.context.info_owner,
                    "caller_diff_1": self.context.diff_1 or "",
                    "caller_diff_2": self.context.diff_2 or "",
                    "caller_ext08_calls": caller_calls,
                    # ★ phase5+ Win 修复：补传 target 完整 5 字段，让主进程用 4 字段主键精确查 target
                    #   （与 sealed_import_hook.py loader._unseal_via_rpc 修复一致）
                    #   subprocess 形态下被调脚本必须在 caller 同 diff_2 包内
                    "target_info_type": "script",
                    "target_info_owner": self.context.info_owner or "",
                    "target_diff_1": self.context.diff_1 or "",
                    "target_diff_2": self.context.diff_2 or "",
                    "target_diff_3": target_diff_3,
                },
                timeout=30,
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("code") != 200:
                logger.warning(
                    f"patched_run: /sensitive/unseal_for_child returned code={body.get('code')} "
                    f"msg={body.get('msg')}"
                )
                return None
            data = body.get("data")
            if isinstance(data, str):
                # 主进程 unseal 后直接返回真明文 Python 源码
                return data if data else None
            if isinstance(data, dict):
                return data.get("plain_text") or data.get("content") or ""
            return None
        except Exception as e:
            logger.error(f"patched_run: HTTP unseal_for_child failed: {e}")
            return None


# ============================================================
# 模块级：real subprocess.run + install/uninstall
# ============================================================

_real_subprocess_run = subprocess.run


def install_subprocess_adapter(
    context,
    mgc_api_port: Optional[int] = None,
    mgc_api_token: Optional[str] = None,
    internal_token: Optional[str] = None,
):
    """安装 SubprocessAdapter（monkey-patch subprocess.run）。

    通常在 bootstrap.main() 启动时调用。
    """
    adapter = SubprocessAdapter(
        context=context,
        mgc_api_port=mgc_api_port,
        mgc_api_token=mgc_api_token,
        internal_token=internal_token,
    )
    subprocess.run = adapter.patched_run
    logger.info(
        f"subprocess_adapter installed: managed={len(adapter._managed)}, "
        f"port={mgc_api_port}"
    )
    return adapter


def uninstall_subprocess_adapter():
    """卸载 SubprocessAdapter（恢复 subprocess.run）。"""
    subprocess.run = _real_subprocess_run
    logger.info("subprocess_adapter uninstalled")
