"""
脚本执行服务模块

功能：
- 脚本内存加载执行
- 子进程管理
- 返回执行结果
- v1.4 新增：ext02 严格 JSON 解析（结构化 argv list）+ split fallback

依赖：
- subprocess
- json
"""

import json
import os
import subprocess
import sys
import threading
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from mgc.utils.log_utils import logger

if TYPE_CHECKING:
    from mgc.runtime.workflow_registry import ScriptExecutionContext


class ScriptExecutorError(Exception):
    """脚本执行异常"""
    pass


def parse_ext02_args(ext02: Optional[str]) -> Tuple[List[str], bool]:
    """
    严格 JSON 解析 ext02 字段。

    数据契约：ext02 字段 = 序列化后的 argv JSON 数组字符串。
    运行时：若 json.loads() 成功且结果是 list of str，则直接传给脚本；
    否则 fallback 到 ext02.split()（1.4.9 向后兼容）。

    入参：
        ext02: 从 DB 读出的 ext02 字符串

    出参：
        (args_list, use_split_fallback)
        - args_list: 解析后的 argv list
        - use_split_fallback: 是否走了 split() fallback

    异常：
        无（所有 JSON 异常都 fallback 到 split()）
    """
    if not ext02:
        return [], False

    # 唯一判定条件：严格 JSON 解析
    try:
        parsed = json.loads(ext02)
        if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
            # ✅ 成功解析为 list of str
            return parsed, False
        else:
            # JSON 解析成功但不是 list of str（如 {"k":"v"} 或 [1, 2]）
            # fallback 到 split 原始字符串
            return ext02.split(), True
    except (json.JSONDecodeError, ValueError, TypeError):
        # ✅ 任何异常都 fallback 到 split
        return ext02.split(), True


def get_split_fallback_hint(ext02: Optional[str]) -> Optional[str]:
    """
    新增：判断是否走 split fallback，返回提示文本。

    入参：
        ext02: 落库的 ext02 字符串

    出参：
        - None：JSON list 格式（无 fallback）
        - 英文提示：字符串格式（走 split fallback）
    """
    if not ext02:
        return None
    _, use_split_fallback = parse_ext02_args(ext02)
    if use_split_fallback:
        return "ext02 in legacy string format; re-save the script to upgrade to structured argv list (recommended)"
    return None


class ScriptExecutorService:
    """脚本执行服务"""

    def __init__(self):
        """初始化脚本执行服务"""
        self._processes: Dict[int, subprocess.Popen] = {}
        self.task_results: Dict[str, dict] = {}

    def execute_script(
        self,
        script_content: str,
        ext01: str,
        ext02: Optional[str] = None
    ) -> Dict[str, any]:
        """
        执行脚本

        入参：
            script_content: 脚本内容（已解密）
            ext01: 启动命令（如 "python -c"）
            ext02: 运行参数（可选）

        出参：
            {
                "pid": 子进程id,
                "status": "success"/"failed",
                "error": 错误信息（如有）
            }

        异常：
            ScriptExecutorError: 执行失败时抛出
        """
        try:
            from mgc.utils.log_utils import logger
            from mgc.utils.log_utils import safe_ext_repr
            # 1.5.1 task2：终端脱敏，仅改显示文本，业务字段 ext01/ext02 在内存中仍为原文
            # （subprocess.Popen / parse_ext02_args / DB 落库都继续用原值）。
            logger.info(
                f"ScriptExecutorService.execute_script called: "
                f"ext01={safe_ext_repr(ext01, key='ext01')}, "
                f"ext02={safe_ext_repr(ext02, key='ext02')}, "
                f"script_len={len(script_content) if script_content else 0}"
            )
        except:
            pass

        try:
            if not ext01:
                return {
                    "status": "failed",
                    "error": "ext01 (启动命令) is required"
                }

            # 1.5.1 BUG-D：之前在 ext02 非空且 ext01 不含 -c 时自动追加 "-c"，
            # 触发 Python -c 模式下后续位置参数（args_list）被忽略的 bug。
            # 统一改为：永远用 stdin 传脚本源码，args 通过 cmd_parts 传给子进程，
            # 与 phase3 新路径（subprocess_adapter）的 Popen + stdin 模式保持一致。
            cmd_parts = ext01.split() if ext01 else []
            args_list, use_split_fallback = parse_ext02_args(ext02)
            if args_list:
                cmd_parts.extend(args_list)
            use_stdin = bool(script_content)

            if use_stdin:
                process = subprocess.Popen(
                    cmd_parts,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                # Send script content via stdin (non-blocking)
                process.stdin.write(script_content.encode('utf-8'))
                process.stdin.close()
            else:
                process = subprocess.Popen(
                    cmd_parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                # Non-blocking: start and return immediately

            # Return immediately after starting process (non-blocking)
            result = {"pid": process.pid, "status": "started"}
            # v1.4 新增：返回 split fallback 标志
            if use_split_fallback and ext02:
                result["hint"] = get_split_fallback_hint(ext02)
            return result

        except FileNotFoundError as e:
            return {
                "status": "failed",
                "error": f"Command not found: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }

    def execute_script_async(self, request_key: str, script_content: str, ext01: str, ext02: str = None):
        """
        异步执行脚本

        参数：
            request_key: 请求内容key（info_type + info_owner + diff_1/2/3）
            script_content: 脚本内容
            ext01: 启动命令
            ext02: 运行时参数
        """
        def run_in_background():
            result = self.execute_script(script_content, ext01, ext02)
            self.task_results[request_key] = result

        thread = threading.Thread(target=run_in_background)
        thread.start()

    # ============================================================
    # phase3 新增：execute_script_ctx（启动 bootstrap 子进程，fire-and-forget）
    # ============================================================

    def execute_script_ctx(
        self,
        ctx: "ScriptExecutionContext",
        *,
        script_content: str,
    ) -> Dict[str, any]:
        """启动 bootstrap 执行脚本（fire-and-forget，立即返回 pid）。

        关键设计：
        - script_content 必填（主进程已解密 + unseal 后的真明文）
        - payload 含 root_source + mgc_api_port + mgc_api_token
        - 立即返回 pid，主进程不阻塞

        Args:
            ctx: ScriptExecutionContext（含 ext08 / all_records 等元数据）
            script_content: 解密后的脚本源码（明文）

        Returns:
            {pid, status: "started"} 或 {status: "failed", error}
        """
        # 1.5.2 hotfix：Popen 不传 cwd，继承主进程 cwd（绝对路径，永远存在）。
        # 原因：sealed pkg 的 diff_3 目录前缀（如 "script/"）是虚拟的，磁盘上不存在；
        # 推导 cwd 会导致 Popen FileNotFoundError。

        logger.info(
            f"execute_script_ctx: ctx.diff_3={ctx.diff_3}, "
            f"script_content_len={len(script_content) if script_content else 0}"
        )
        if not script_content:
            return {"status": "failed", "error": "execute_script_ctx: script_content is required"}

        # 构造 stdin payload（JSON）
        try:
            payload = self._build_ctx_payload(ctx, script_content)
            payload_json = json.dumps(payload, ensure_ascii=False)
        except Exception as e:
            return {"status": "failed", "error": f"execute_script_ctx: payload build failed: {e}"}

        # 启动 bootstrap 子进程
        try:
            process = subprocess.Popen(
                # 1.5.4 Linux 修复：不用硬编码 "python"（Linux 仅有 python3，
                # 会 FileNotFoundError 导致 mgc_run 全部失败）。sys.executable
                # = 启动 MGC 的解释器，保证子进程依赖环境与主进程一致。
                [sys.executable, "-m", "mgc.bootstrap"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # ★ phase5+ Win 修复：即使当前是字节模式也保留（Popen 默认按 locale 编 stdin）
                #   当前代码用 payload_json.encode("utf-8") 写字节，但 Popen 默认 locale 编码在 Win=cp936，
                #   如果将来某处误用 text=True 会触发 PM 测试报告（2026-09-19）的 UnicodeDecodeError。
                #   此处显式声明 encoding 与终端 locale 解耦（防御性）。
                # 1.5.2 hotfix：不传 cwd，继承主进程 cwd（绝对路径，永远存在）
                encoding="utf-8",
            )
        except FileNotFoundError as e:
            return {
                "status": "failed",
                "error": f"execute_script_ctx: interpreter not found: {e}",
            }
        except Exception as e:
            return {"status": "failed", "error": f"execute_script_ctx: Popen failed: {e}"}

        # 喂 stdin payload
        # ★ phase5+ Win 修复：Popen 带 encoding="utf-8" 已是文本模式，
        #   stdin.write 只接受 str（bytes 会 TypeError，触发 PM 测试 2026-09-19
        #   的 mgc_run "Error: failed"）。文本层按 utf-8 编码后落到管线的
        #   字节流与 bootstrap 读侧 buffer.read().decode("utf-8") 配对。
        try:
            process.stdin.write(payload_json)
            process.stdin.close()
        except Exception as e:
            try:
                process.kill()
            except Exception:
                pass
            try:
                process.wait()
            except Exception:
                pass
            return {"status": "failed", "error": f"execute_script_ctx: stdin write failed: {e}"}

        # fire-and-forget：立即返回 pid
        # 但为了诊断，启动 daemon 线程异步读取 stderr 并检测早期异常
        self._start_stderr_drain(process, ctx.diff_3)

        return {"pid": process.pid, "status": "started"}

    def _start_stderr_drain(self, process, diff_3: str) -> None:
        """异步读取 stderr 并在子进程退出时记录（fire-and-forget 诊断用）。

        fire-and-forget 设计下，子进程的 stdout/stderr 没人 read，会被丢弃。
        本方法启动 daemon 线程异步读取 stderr（不阻塞主进程），
        在子进程退出时记录关键错误。
        """
        def _drain():
            try:
                # phase5+ Win 修复：Popen 带 encoding="utf-8" 后 stderr.read()
                #   返回 str（此前是 bytes），统一归一为 str 再记日志
                stderr_text = ""
                try:
                    stderr_text = process.stderr.read()
                    if isinstance(stderr_text, bytes):
                        stderr_text = stderr_text.decode(
                            "utf-8", errors="replace"
                        )
                except Exception as read_err:
                    logger.error(
                        f"bootstrap[{diff_3}] stderr read error: {read_err}"
                    )

                # 即使 stderr 空也 dump 全部可用信息
                poll_result = process.poll()
                returncode = poll_result if poll_result is not None else process.wait()

                # phase6 收尾：DEBUG-bootstrap-drain 降级为 logger.debug()，
                # 并隐藏 stderr 内容（避免 args 透传 / 子进程内部 print 出现在主进程日志里）。
                # 仅保留字段名 + 长度，触发可见条件：MGC_LOG_LEVEL=DEBUG。
                logger.debug(
                    f"[bootstrap-drain] diff_3={diff_3}, "
                    f"returncode={returncode}, "
                    f"stderr_len={len(stderr_text)}"
                )
                if stderr_text:
                    # 1.5.2 hotfix：stderr 内容降级为 DEBUG（不在 mgc 终端打印）。
                    # 业务脚本可能把秘钥/敏感信息 print 到 stderr，必须避免落到 INFO/ERROR
                    # 级别以免泄露到终端或日志聚合平台。stderr 原文保留在
                    # ~/.mgc/logs/child_stderr/<diff_3>.<pid>.stderr 等独立文件中供排错。
                    # 只有 returncode != 0 且 stderr 内容提示致命错误时，再升为 ERROR
                    # 但仅记录 stderr 长度+前 200 字符截断，避免敏感数据泄露。
                    if returncode and returncode != 0:
                        logger.error(
                            f"bootstrap[{diff_3}] exited with code={returncode}, "
                            f"stderr_len={len(stderr_text)}, "
                            f"stderr_preview={stderr_text[:200]!r}"
                        )
                    else:
                        logger.debug(
                            f"bootstrap[{diff_3}] stderr_len={len(stderr_text)} "
                            f"(content not logged to avoid sensitive data leak)"
                        )
                if returncode != 0:
                    logger.error(
                        f"bootstrap[{diff_3}] exited with code={returncode}"
                    )
            except Exception as e:
                logger.error(f"bootstrap[{diff_3}] stderr drain failed: {e}")

        thread = threading.Thread(target=_drain, daemon=True)
        thread.start()

    def _build_ctx_payload(
        self,
        ctx: "ScriptExecutionContext",
        script_content: str,
    ) -> Dict[str, any]:
        """构造 bootstrap stdin payload。

        payload 包含：
        - ctx 全部字段（通过 to_dict）
        - root_source：明文脚本源码（bootstrap 内 exec 用）
        - mgc_api_port + mgc_api_token：bootstrap 内 patched_run HTTP 调主进程用
        """
        payload = ctx.to_dict()
        payload["root_source"] = script_content
        # mgc_api_port / token 通过 sensitive_service 单例注入（如果在主进程）
        # 通过环境变量或敏感服务单例传递
        from mgc.core.mgc_service.script_execution_service import ScriptExecutionService
        # 注意：这里 ScriptExecutionService 是单例（在 sensitive_service 内）
        # 通过 service 自身的 _mgc_api_port / _mgc_api_token 字段
        sensitive_service = getattr(self, "_sensitive_service_ref", None)
        if sensitive_service and hasattr(sensitive_service, "script_execution_service"):
            svc = sensitive_service.script_execution_service
            payload["mgc_api_port"] = svc._mgc_api_port
            payload["mgc_api_token"] = svc._mgc_api_token
            # phase4 方案C：注入 internal_token（patched_run HTTP unseal 鉴权用）
            payload["internal_token"] = svc._internal_token
        else:
            # 兜底：尝试从全局拿
            payload["mgc_api_port"] = None
            payload["mgc_api_token"] = None
            payload["internal_token"] = None
        return payload

    def get_task_result(self, request_key: str) -> dict:
        """
        获取任务结果

        参数：
            request_key: 请求内容key

        返回：
            任务结果字典
        """
        return self.task_results.get(request_key, {"status": "not_found"})

    def get_process(self, pid: int) -> Optional[subprocess.Popen]:
        """
        获取进程

        入参：
            pid: 进程ID

        出参：
            Popen对象或None
        """
        return self._processes.get(pid)

    def is_running(self, pid: int) -> bool:
        """
        检查进程是否在运行

        入参：
            pid: 进程ID

        出参：
            bool: 是否在运行
        """
        process = self._processes.get(pid)
        if process is None:
            return False
        return process.poll() is None