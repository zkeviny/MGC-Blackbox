"""
MGC 升级 API 路由模块

提供：
- GET /api/update/info - 检查是否有可用更新
- POST /api/update/start - 启动更新流程
- GET /api/update/status - 查询更新状态
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("mgc.presentation.webui.update_router")

router = APIRouter(prefix="/api/update", tags=["update"])


# 更新状态（进程级）
_update_state = {
    "status": "idle",  # idle | updating | completed | failed
    "target_version": "",
    "started_at": 0.0,
    "error": ""
}


# MGC 主进程端口
MGC_MAIN_API_PORT = 57219


class UpdateStartRequest(BaseModel):
    target_version: str


@router.get("/info")
async def get_update_info():
    """
    检查是否有可用更新
    """
    try:
        from mgc.core.mgc_service.update_service import UpdateService
        service = UpdateService()
        info = service.check_for_updates()
        return info.to_dict()
    except Exception as e:
        logger.error(f"Check update failed: {e}")
        try:
            from mgc import __version__
            return {
                "has_update": False,
                "current_version": __version__,
                "latest_version": __version__,
                "upgrade_command": f"pip install mgc-blackbox=={__version__} --upgrade",
                "pypi_url": "https://pypi.org/project/mgc-blackbox/"
            }
        except Exception:
            raise HTTPException(status_code=500, detail=f"Update check failed: {str(e)}")


@router.post("/start")
async def start_update(data: UpdateStartRequest):
    """
    启动更新流程

    流程（完全复用 stop mgc 按钮的逻辑）：
    1. 写 updating.flag 标记文件
    2. 启动 update_worker 子进程（DETACHED_PROCESS，独立进程）
    3. 异步调用 POST 57219/api/mgc/service/stop（与 stop 按钮同一端点）
       → MGC 主进程会 os._exit(0) 终止整个 Python 进程
       → WebUI 线程也一起被关闭
       → update_worker 不受影响（独立进程）
    """
    global _update_state

    target_version = data.target_version
    if not target_version:
        raise HTTPException(status_code=400, detail="target_version is required")

    if _update_state["status"] == "updating":
        return {
            "status": "updating",
            "target_version": _update_state["target_version"]
        }

    try:
        # 1. 写标记文件
        from mgc.config.path_config import get_runtime_root
        data_dir = Path(get_runtime_root())
        flag_file = data_dir / "updating.flag"
        flag_file.parent.mkdir(parents=True, exist_ok=True)
        flag_file.write_text(target_version, encoding="utf-8")

        # 2. 启动 update_worker 子进程（完全独立的进程）
        worker_cmd = [
            sys.executable, "-m", "mgc.update_worker",
            target_version, str(flag_file)
        ]

        logger.info(f"Starting update_worker: {' '.join(worker_cmd)}")

        if sys.platform == "win32":
            # CREATE_NO_WINDOW gives update_worker a HIDDEN console so
            # descendant subprocesses (pip) inherit it instead of
            # spawning new visible console windows. Mirrors the fix
            # in update_worker.launch_new_mgc().
            subprocess.Popen(
                worker_cmd,
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
                worker_cmd,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )

        # 3. 更新状态
        _update_state["status"] = "updating"
        _update_state["target_version"] = target_version
        _update_state["started_at"] = time.time()

        # 4. 后台线程调用主进程 stop（与 stop mgc 按钮完全相同的逻辑）
        #    用后台线程避免阻塞 WebUI 事件循环
        import threading

        def call_main_stop():
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{MGC_MAIN_API_PORT}/api/mgc/service/stop",
                    method="POST"
                )
                # 10 秒超时足够主进程完成 stop（内部 sleep 3s + 退出）
                urllib.request.urlopen(req, timeout=10)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
                # 进程退出后连接失败是预期的
                logger.info(f"Main process stop response: {e}")

        # 等 3 秒确保浏览器有足够时间加载 /installing 页并发起首次
        # 轮询（/api/mgc/proxy/status），再调用主进程 stop，避免 fetch 竞态
        def delayed_stop():
            time.sleep(3)
            call_main_stop()

        threading.Thread(target=delayed_stop, daemon=True).start()

        return {
            "status": "updating",
            "target_version": target_version
        }

    except Exception as e:
        logger.error(f"Start update failed: {e}")
        _update_state["status"] = "failed"
        _update_state["error"] = str(e)
        raise HTTPException(status_code=500, detail=f"Start update failed: {str(e)}")


@router.get("/status")
async def get_update_status():
    """
    查询更新状态
    """
    try:
        from mgc.config.path_config import get_runtime_root
        data_dir = Path(get_runtime_root())
        flag_file = data_dir / "updating.flag"
        is_updating_flag = flag_file.exists()
    except Exception:
        is_updating_flag = False

    return {
        "status": _update_state["status"],
        "target_version": _update_state["target_version"],
        "is_updating_flag": is_updating_flag
    }
