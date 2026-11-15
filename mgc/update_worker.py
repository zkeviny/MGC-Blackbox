"""
MGC 升级 Worker 模块（简化版）

作为独立进程运行，负责：
1. 等待 MGC 主进程退出（端口 57219 释放）
2. 调用 pip install 升级（15 秒超时）
3. 拉起新的 mgc 主进程（不等端口就绪）
4. 清理标记文件
5. 自我终止

使用：
    python -m mgc.update_worker <target_version> <flag_file_path>
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path


# MGC 主进程 API 端口
MGC_MAIN_API_PORT = 57219

# 探测参数
INITIAL_WAIT = 3      # 初始等待 3 秒
PROBE_INTERVAL = 3    # 每次探测间隔 3 秒
MAX_PROBES = 3        # 最多探测 3 次

# pip install 超时（秒）
PIP_INSTALL_TIMEOUT = 15


def is_port_open(port: int) -> bool:
    """检查端口是否开放（True 表示有进程在监听）"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def wait_for_main_process_exit() -> bool:
    """
    等待 MGC 主进程退出（端口 57219 释放）

    Returns:
        True: 主进程已退出
        False: 连续 MAX_PROBES 次都未退出
    """
    print(f"[update_worker] Initial wait {INITIAL_WAIT}s...", flush=True)
    time.sleep(INITIAL_WAIT)

    print(f"[update_worker] Checking if MGC main ({MGC_MAIN_API_PORT}) has exited...", flush=True)

    for i in range(MAX_PROBES):
        if not is_port_open(MGC_MAIN_API_PORT):
            print(f"[update_worker] MGC main has exited (probe {i+1}/{MAX_PROBES})", flush=True)
            return True
        print(f"[update_worker] MGC main still running (probe {i+1}/{MAX_PROBES})", flush=True)
        time.sleep(PROBE_INTERVAL)

    print(f"[update_worker] MGC main did not exit after {MAX_PROBES} probes, aborting", flush=True)
    return False


def run_pip_install(target_version: str) -> bool:
    """
    执行 pip install 升级

    Returns:
        True: 成功
        False: 失败或超时
    """
    print(f"[update_worker] Running: pip install mgc-blackbox=={target_version} --upgrade (timeout={PIP_INSTALL_TIMEOUT}s)", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install",
             f"mgc-blackbox=={target_version}", "--upgrade"],
            timeout=PIP_INSTALL_TIMEOUT
        )
        if result.returncode == 0:
            print("[update_worker] pip install completed successfully", flush=True)
            return True
        else:
            print(f"[update_worker] pip install failed with exit code {result.returncode}", flush=True)
            return False
    except subprocess.TimeoutExpired:
        print(f"[update_worker] pip install timeout after {PIP_INSTALL_TIMEOUT}s", flush=True)
        return False
    except Exception as e:
        print(f"[update_worker] pip install error: {e}", flush=True)
        return False


def launch_new_mgc():
    """拉起新的 MGC 主进程（不等端口就绪）"""
    print("[update_worker] Launching new mgc main process...", flush=True)
    try:
        if sys.platform == "win32":
            # Use CREATE_NO_WINDOW instead of DETACHED_PROCESS:
            # - DETACHED_PROCESS = process has NO console at all
            #   → child subprocesses (wmic/powershell/whoami etc.)
            #     have nothing to inherit → Windows creates NEW visible
            #     console window for each → black flash
            # - CREATE_NO_WINDOW = process has a HIDDEN console
            #   → child subprocesses inherit the hidden console →
            #     no new visible window → no flash
            subprocess.Popen(
                [sys.executable, "-m", "mgc"],
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.CREATE_NO_WINDOW
                ),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )
        else:
            subprocess.Popen(
                [sys.executable, "-m", "mgc"],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )
        print("[update_worker] New mgc launched (not waiting for ready)", flush=True)
    except Exception as e:
        print(f"[update_worker] Failed to launch new mgc: {e}", flush=True)


def cleanup_flag(flag_file: str):
    """清理标记文件"""
    try:
        Path(flag_file).unlink(missing_ok=True)
        print(f"[update_worker] Flag removed: {flag_file}", flush=True)
    except Exception as e:
        print(f"[update_worker] Failed to remove flag: {e}", flush=True)


def main(target_version: str, flag_file: str):
    """update_worker 主函数"""
    print(f"[update_worker] === Starting ===", flush=True)
    print(f"[update_worker] target_version: {target_version}", flush=True)
    print(f"[update_worker] flag_file: {flag_file}", flush=True)

    try:
        # 1. 等待主进程退出
        if not wait_for_main_process_exit():
            cleanup_flag(flag_file)
            print("[update_worker] Aborting due to main process not exiting", flush=True)
            os._exit(1)

        # 2. 升级
        if not run_pip_install(target_version):
            cleanup_flag(flag_file)
            print("[update_worker] Aborting due to pip install failure", flush=True)
            os._exit(1)

        # 3. 拉起新 mgc
        launch_new_mgc()

        # 4. 清理标记
        cleanup_flag(flag_file)

        # 5. 等待 60 秒后自我终止（给用户/系统缓冲时间）
        print(f"[update_worker] Installation completed, waiting 60s before exit...", flush=True)
        time.sleep(60)
        print("[update_worker] === Done, exiting ===", flush=True)
        os._exit(0)

    except Exception as e:
        print(f"[update_worker] Unexpected error: {e}", flush=True)
        try:
            cleanup_flag(flag_file)
        except Exception:
            pass
        os._exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m mgc.update_worker <target_version> <flag_file>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
