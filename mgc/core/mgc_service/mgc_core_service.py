"""
MGC核心服务模块

功能：
- 启动MGC核心服务，监听本地回环端口（127.0.0.1:57219）
- 停止MGC核心服务
- 重启MGC核心服务
- 获取服务状态
- 检查端口是否可用

依赖：
- FastAPI（轻量级、高性能、异步支持）
- uvicorn（ASGI服务器）
- src/config/enum_config.py（枚举配置）
- src/config/path_config.py（路径配置）
"""

import asyncio
import socket
from typing import Dict, Optional
from fastapi import FastAPI
import uvicorn

from mgc.config.enum_config import ServiceStatus, UpdateLevel
from mgc.config.i18n_config import get_exception_message, Messages
from mgc.utils.log_utils import get_logger


logger = get_logger(__name__)


class MGCCoreServiceError(Exception):
    """MGC核心服务异常"""
    pass


class MGCCoreService:
    """MGC核心服务"""

    def __init__(self, port: int = 57219, update_service=None):
        """
        初始化MGC核心服务

        入参：
            port: 监听端口，默认57219
            update_service: 版本更新服务实例（可选）
        """
        self.port = port
        self.app = FastAPI(
            title="MirginCipher Core Service",
            docs_url=None,
            redoc_url=None,
            openapi_url=None
        )
        self.server: Optional[uvicorn.Server] = None
        self._initialized = False
        self._device_id = ""
        self.update_service = update_service

    def include_router(self, router):
        """
        注册路由到FastAPI应用

        入参：
            router: FastAPI路由对象
        """
        self.app.include_router(router)

    async def start(self) -> bool:
        """
        启动MGC核心服务

        功能：
        - 检查端口是否可用
        - 启动FastAPI应用
        - 监听本地回环端口

        出参：
            bool: True表示启动成功，False表示启动失败

        异常：
            MGCCoreServiceError: 启动失败时抛出
        """
        try:
            if not self.check_port_available(self.port):
                raise MGCCoreServiceError(get_exception_message(Messages.MGCCoreService, "PORT_ALREADY_IN_USE", port=self.port))

            config = uvicorn.Config(
                app=self.app,
                host="127.0.0.1",
                port=self.port,
                log_level="info",
                access_log=False,
                loop="asyncio"
            )
            self.server = uvicorn.Server(config)

            import threading
            server_thread = threading.Thread(target=self.server.run, daemon=True)
            server_thread.start()
            self._initialized = True

            import time
            time.sleep(0.5)

            # 等待服务真正启动
            await asyncio.sleep(0.5)

            # 启动时版本检查和心跳
            if self.update_service:
                try:
                    version_check = self.update_service.check_version()
                    if version_check["status"] == "success":
                        if version_check["update_level"] == UpdateLevel.REQUIRED.value:
                            logger.warning(f"Required update available: {version_check['remote_version']}")
                        elif version_check["update_level"] == UpdateLevel.RECOMMENDED.value:
                            logger.info(f"Recommended update available: {version_check['remote_version']}")
                except Exception as e:
                    logger.error(f"Version check failed: {str(e)}")
                
                try:
                    self.update_service.send_heartbeat()
                except Exception as e:
                    logger.error(f"Heartbeat failed: {str(e)}")

            return True

        except Exception as e:
            raise MGCCoreServiceError(get_exception_message(Messages.MGCCoreService, "START_MGC_CORE_SERVICE_FAILED"))

    async def stop(self) -> bool:
        """
        停止MGC核心服务

        功能：
        - 停止接收新请求
        - 等待正在处理的请求完成
        - 关闭端口监听
        - 清理资源

        出参：
            bool: True表示停止成功，False表示停止失败

        异常：
            MGCCoreServiceError: 停止失败时抛出
        """
        try:
            if self.server:
                self.server.should_exit = True
                await asyncio.sleep(3)
                self.server = None

            self._initialized = False
            import os
            os._exit(0)
            return True

        except Exception as e:
            raise MGCCoreServiceError(get_exception_message(Messages.MGCCoreService, "STOP_MGC_CORE_SERVICE_FAILED"))

    async def restart(self) -> bool:
        """
        重启MGC核心服务

        功能：
        - 先停止服务
        - 再启动服务

        出参：
            bool: True表示重启成功，False表示重启失败

        异常：
            MGCCoreServiceError: 重启失败时抛出
        """
        try:
            await self.stop()
            await asyncio.sleep(1)
            return await self.start()

        except Exception as e:
            raise MGCCoreServiceError(get_exception_message(Messages.MGCCoreService, "RESTART_MGC_CORE_SERVICE_FAILED"))

    def get_status(self) -> Dict[str, any]:
        """
        获取服务状态

        功能：
        - 检查服务是否运行
        - 检查是否已初始化
        - 获取设备ID
        - 获取监听端口

        出参：
            dict: 服务状态信息
            {
                "status": "running/stopped",
                "initialized": true/false,
                "device_id": "xxx",
                "port": 57219
            }
        """
        status = "running" if self._initialized else "stopped"

        return {
            "status": status,
            "initialized": self._initialized,
            "device_id": self._device_id,
            "port": self.port
        }

    def check_port_available(self, port: int) -> bool:
        """
        检查端口是否可用

        功能：
        - 检查端口是否被占用
        - 返回端口可用状态

        入参：
            port: 端口号

        出参：
            bool: True表示端口可用，False表示端口被占用

        phase7 #9: 采用方案 A+B
          A. bind + SO_REUSEADDR → 覆盖 TIME_WAIT 残留
          B. bind 失败时降级为 connect 精确诊断是否真有 LISTEN
        """
        # A: bind with SO_REUSEADDR（覆盖 TIME_WAIT 残留）
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            pass

        # B: bind 失败 → connect 精确诊断
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(("127.0.0.1", port))
                return False  # connect 成功 → 真有进程在 LISTEN
        except (OSError, socket.timeout):
            return False  # bind 失败 + connect 失败 → 罕见情况

    def set_initialized(self, initialized: bool):
        """
        设置初始化状态

        入参：
            initialized: 初始化状态
        """
        self._initialized = initialized

    def set_device_id(self, device_id: str):
        """
        设置设备ID

        入参：
            device_id: 设备ID
        """
        self._device_id = device_id

    def get_app(self) -> FastAPI:
        """
        获取FastAPI应用实例

        出参：
            FastAPI: FastAPI应用实例
        """
        return self.app
