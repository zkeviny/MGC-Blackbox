"""bootstrap.py — 1.5.1 Sprint 2.5 phase3 精简版（约 100 行）。

启动方式：python -m mgc.bootstrap

启动流程：
1. 从 stdin 读取 ScriptExecutionContext JSON（payload）
2. 装 subprocess_adapter（patched_run，拦截业务代码的 subprocess.run）
3. 设置 __file__ / sys.argv
4. 读 user_script 源码 → compile → exec（in-memory，不落盘）
5. 退出（exit code = user_script 的 exit code）

设计要点：
- 单进程 bootstrap：每个 root / child 脚本各启动一个 bootstrap 子进程
- 上下文通过 stdin 传递（不进 env，避免 env 泄露）
- in-memory exec：不落盘、不落库
- patched_run 自己 Popen 子进程跑被调脚本（不通过 mgc 主进程）
"""

import json
import logging
import os
import sys
import time
import traceback
from typing import Any, Dict, Optional

from mgc.runtime import EXIT_OK, EXIT_USER_EXCEPTION, EXIT_INTERNAL_ERROR
from mgc.runtime.workflow_registry import ScriptExecutionContext

logger = logging.getLogger(__name__)


# 缓存 stdin 原始 payload（patched_run 构造孙进程 payload 时不需要再次读 stdin）
_STDIN_RAW_PAYLOAD: Optional[Dict[str, Any]] = None


def read_context_from_stdin() -> ScriptExecutionContext:
    """从 stdin 读取 ScriptExecutionContext JSON。

    payload 包含：
    - ctx 全部字段（通过 ScriptExecutionContext.from_dict）
    - root_source：明文脚本源码（bootstrap 内 exec 用）
    - mgc_api_port + mgc_api_token：bootstrap 内 patched_run HTTP 调主进程用

    ★ phase5+ Win 修复：强制 UTF-8 解码，与终端 locale 解耦
      Win 下 PYTHONIOENCODING=utf-8 不影响 subprocess.Popen text=True 默认编码（跟随 locale），
      子进程写入 payload 用 cp936 时根按 UTF-8 解码会炸 UnicodeDecodeError。
      MGC 内部协议应强制 UTF-8，参照 PM 测试报告（2026-09-19）。
    """
    global _STDIN_RAW_PAYLOAD
    raw_bytes = sys.stdin.buffer.read()
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(
            f"bootstrap: stdin is not valid UTF-8: {e}. "
            "MGC 内部协议要求 UTF-8 编码。"
        ) from e
    if not raw:
        raise ValueError("bootstrap: empty stdin")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"bootstrap: invalid JSON: {e}") from e
    _STDIN_RAW_PAYLOAD = data
    return ScriptExecutionContext.from_dict(data)


def _read_stdin_payload() -> Optional[Dict[str, Any]]:
    """返回 read_context_from_stdin 时缓存的原始 dict。"""
    return _STDIN_RAW_PAYLOAD


def exec_user_script(context: ScriptExecutionContext) -> int:
    """执行 user_script 源码（in-memory，不落盘）。"""
    stdin_data = _read_stdin_payload()
    root_source = stdin_data.get("root_source") if stdin_data else None

    if not root_source:
        logger.error("bootstrap: root_source is missing in stdin payload")
        return EXIT_USER_EXCEPTION

    # logical_file = diff_3（如 "script/加车数据.py"），
    # 业务代码用 __file__ 解 Path(__file__).parent / "config.py" 时会自然得到 diff_3 形式
    logical_file = context.diff_3 or context.module_file or "<mgc_inproc>"
    logger.info(
        f"bootstrap: in-memory exec, logical __file__={logical_file}, "
        f"script_len={len(root_source)}"
    )

    # 构造 user_globals（注入 __file__）
    user_globals = {
        "__name__": "__main__",
        "__file__": logical_file,
    }

    # sys.argv[0] 设置（业务代码可能用 sys.argv[0] 读自己路径）
    argv0 = logical_file
    ext02 = context.ext02 or ""
    try:
        ext02_args = json.loads(ext02) if isinstance(ext02, str) and ext02.strip() else []
        if isinstance(ext02_args, list):
            sys.argv = [argv0] + [str(a) for a in ext02_args]
        else:
            sys.argv = [argv0]
    except (json.JSONDecodeError, ValueError, TypeError):
        sys.argv = [argv0]

    # compile + exec
    try:
        code = compile(root_source, logical_file, "exec")
        exec(code, user_globals)
        return EXIT_OK
    except SystemExit as e:
        # SystemExit.code 可以是 int / str / None
        # - None 或 0 → 正常退出
        # - int (非零) → 异常退出，返回该 code
        # - str / 其他 → 视为异常退出（返回 EXIT_USER_EXCEPTION）
        if e.code is None or e.code == 0:
            return EXIT_OK
        if isinstance(e.code, int):
            return e.code
        return EXIT_USER_EXCEPTION
    except BaseException as e:
        traceback.print_exc()
        logger.exception(
            f"bootstrap: user_script raised {type(e).__name__}: {e}"
        )
        return EXIT_USER_EXCEPTION


def main() -> int:
    """bootstrap 主入口（精简版）。"""
    # phase5：sealed import hook 安装引用（用于 finally 清理）
    sealed_finder = None
    try:
        # 1. 读 context（含 root_source / mgc_api_port/token）
        context = read_context_from_stdin()
        payload = _read_stdin_payload()
        context.started_at = time.time()

        # 1.5 phase6+：装 patched_run（拦截业务代码的 subprocess.run）
        from mgc.runtime.subprocess_adapter import install_subprocess_adapter
        mgc_api_port = payload.get("mgc_api_port")
        mgc_api_token = payload.get("mgc_api_token") or payload.get("internal_token")
        # phase4 方案C：读 internal_token（patched_run HTTP unseal RPC 鉴权用）
        internal_token = payload.get("internal_token", "") or ""
        install_subprocess_adapter(
            context,
            mgc_api_port=mgc_api_port,
            mgc_api_token=mgc_api_token,
            internal_token=internal_token,
        )

        # 2.5 phase5+：装 sealed import hook（拦截业务代码的 import / from-import）
        #   - 与 patched_run 并存：subprocess 写法走 patched_run，import 写法走 hook
        #   - 完全复用 phase4 unseal_for_child RPC + internal_token 鉴权
        #   - 仅在 ext08.calls 含 import/from_import 时实际生效（白名单内才拦截）
        from mgc.runtime.sealed_import_hook import install_sealed_import_hook
        sealed_finder = install_sealed_import_hook(
            context=context,
            mgc_api_port=mgc_api_port,
            mgc_api_token=mgc_api_token,
            internal_token=internal_token,
        )

        # 3. exec user_script（in-memory）
        exit_code = exec_user_script(context)
        return exit_code

    except SystemExit as e:
        # bootstrap 里也会发生 SystemExit（例如 sys.exit 在业务代码里）
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise
    except BaseException as e:
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        logger.exception(f"bootstrap: fatal error: {e}")
        return EXIT_INTERNAL_ERROR
    finally:
        # phase5：清理 sealed import hook（避免污染后续 exec / 子进程退出）
        if sealed_finder is not None:
            try:
                from mgc.runtime.sealed_import_hook import uninstall_sealed_import_hook
                uninstall_sealed_import_hook(sealed_finder)
            except Exception as cleanup_err:
                logger.warning(
                    f"bootstrap: failed to uninstall sealed_import_hook: {cleanup_err}"
                )


if __name__ == "__main__":
    sys.exit(main())
