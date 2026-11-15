"""
状态查询模块

功能：
- 提供运行状态查询
- 提供设备信息查询
- 提供日志查询

依赖：
- src/core/mgc_service/mgc_core_service.py（MGC核心服务）
- src/config/path_config.py（路径配置）
"""

import os
from typing import Dict, List, Optional

from mgc.config.path_config import get_log_file
from mgc.config.i18n_config import get_exception_message, Messages


class StatusServiceError(Exception):
    """状态查询异常"""
    pass


class StatusService:
    """状态查询服务"""

    def __init__(self, mgc_core_service):
        """
        初始化状态查询服务

        入参：
            mgc_core_service: MGC核心服务实例
        """
        self.mgc_core_service = mgc_core_service
        self.log_file = get_log_file()

    def get_status(self) -> Dict[str, any]:
        """
        获取运行状态

        功能：
        - 检查服务是否运行
        - 检查是否已初始化
        - 获取设备ID
        - 获取监听端口

        出参：
            dict: 运行状态信息
            {
                "status": "running/stopped",
                "initialized": true/false,
                "device_id": "xxx",
                "port": 57219
            }

        异常：
            StatusServiceError: 查询失败时抛出
        """
        try:
            status_info = self.mgc_core_service.get_status()

            return {
                "status": status_info['status'],
                "initialized": status_info['initialized'],
                "device_id": status_info['device_id'],
                "port": status_info['port']
            }

        except Exception as e:
            raise StatusServiceError(get_exception_message(Messages.StatusService, "GET_RUNNING_STATUS_FAILED"))

    def get_device(self) -> Dict[str, any]:
        """
        获取设备信息

        功能：
        - 从数据库读取设备ID
        - 检查是否已绑定

        出参：
            dict: 设备信息
            {
                "device_id": "xxx",
                "bind_agent_uuid": "xxx",
                "initialized": true/false
            }

        异常：
            StatusServiceError: 查询失败时抛出
        """
        try:
            status_info = self.mgc_core_service.get_status()

            return {
                "device_id": status_info['device_id'],
                "bind_agent_uuid": "",
                "initialized": status_info['initialized']
            }

        except Exception as e:
            raise StatusServiceError(get_exception_message(Messages.StatusService, "GET_DEVICE_INFO_FAILED"))

    def get_log(self, limit: int = 100) -> List[str]:
        """
        获取日志

        功能：
        - 读取日志文件
        - 解析日志内容
        - 返回日志列表
        - 支持条数限制

        入参：
            limit: 返回条数限制

        出参：
            list: 日志列表

        异常：
            StatusServiceError: 查询失败时抛出
        """
        try:
            if not os.path.exists(self.log_file):
                return []

            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if limit > 0:
                lines = lines[-limit:]

            return [line.strip() for line in lines if line.strip()]

        except Exception as e:
            raise StatusServiceError(get_exception_message(Messages.StatusService, "GET_LOGS_FAILED"))
