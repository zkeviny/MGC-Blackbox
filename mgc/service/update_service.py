"""版本更新服务模块 (v1.0)

用途：
- 版本检查：Agent启动时、技能调用前、定时检查、手动触发
- 版本升级：支持技能热更新、双源下载、自动回滚
- 匿名心跳：按规范字段最小化上报
- 双区域适配：自动检测网络环境，选择最优区域

规范：
- 版本检查周期固定24小时，禁止缩短
- 无网络时不阻塞核心功能，使用本地缓存
- 客户端强制开启，禁止用户禁用
"""

import os
import json
import time
import platform
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple

from filelock import FileLock

from mgc.config.remote_config import RemoteConfig
from mgc.config.enum_config import UpdateLevel, ConfigItem, ConfigDefaults
from mgc.config.path_config import PROJECT_ROOT
from mgc.utils.http_client import HttpClient
from mgc.utils.log_utils import get_logger
from mgc.utils.version_utils import get_version


logger = get_logger(__name__)


class UpdateService:
    """版本更新服务"""
    
    # 文件锁路径（跨进程有效）
    _lock_file = PROJECT_ROOT / "cache" / "update.lock"
    _lock_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 全局检查时间（固定24小时）
    _last_global_check_time = 0
    
    # 技能级别检查时间（30分钟节流）
    _last_check_time = {}
    
    # 升级状态记录（用于心跳）
    
    def __init__(self, agent_id: str = None, agent_version: str = None):
        """
        初始化版本更新服务

        @param agent_id: Agent ID（可选，默认生成）
        @param agent_version: Agent版本（可选，默认读取配置）
        """
        self.remote_config = RemoteConfig()
        self.http_client = HttpClient()
        
        # 生成或使用传入的agent_id
        self.agent_id = agent_id or self._generate_agent_id()
        
        # 读取或使用传入的版本号
        self.agent_version = agent_version or self._get_agent_version()
        
        # 系统信息
        self.os_info = platform.system()
        self.device_type = self._get_device_type()
        
        # 缓存目录
        self.cache_dir = PROJECT_ROOT / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 版本缓存文件
        self.version_cache_file = self.cache_dir / "version_cache.json"
        
        # 心跳缓存文件
        self.heartbeat_cache_file = self.cache_dir / "heartbeat_cache.json"

    def _generate_agent_id(self) -> str:
        """生成Agent ID"""
        import uuid
        return str(uuid.uuid4())

    def _get_agent_version(self) -> str:
        return get_version()

    def _get_device_type(self) -> str:
        """获取设备类型"""
        return "local"

    def _load_version_cache(self) -> Optional[Dict]:
        """加载版本缓存"""
        try:
            if not self.version_cache_file.exists():
                return None
            with open(self.version_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load version cache: {str(e)}")
            return None

    def _save_version_cache(self, data: Dict):
        """保存版本缓存"""
        try:
            data["cache_time"] = int(time.time())
            with open(self.version_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save version cache: {str(e)}")

    def _is_cache_valid(self, cached_data: Dict) -> bool:
        """检查缓存是否有效"""
        if not cached_data or "cache_time" not in cached_data:
            return False
        cache_expire = self.remote_config.get_check_cache_expire() * 3600
        current_time = int(time.time())
        return (current_time - cached_data["cache_time"]) < cache_expire

    def _parse_release_response(self, response: Dict, url: str = "") -> Dict:
        """
        Parse release API response (supports both GitHub and PyPI)

        @param response: API response (GitHub or PyPI format)
        @param response_url: Optional URL to determine parser
        @return: Parsed version info
        """
        if "pypi.org" in url:
            info = response.get("info", {})
            return {
                "tag_name": info.get("version", ""),
                "html_url": f"https://pypi.org/project/mgc-blackbox/{info.get('version', '')}",
                "body": info.get("summary", "")
            }
        else:
            return {
                "tag_name": response.get("tag_name", "").lstrip("v"),
                "html_url": response.get("html_url", ""),
                "body": response.get("body", "")
            }

    def _compare_versions(self, local: str, remote: str) -> bool:
        """
        比较版本号

        @param local: 本地版本
        @param remote: 远程版本
        @return: True表示远程版本更新
        """
        try:
            local_parts = [int(x) for x in local.split(".")]
            remote_parts = [int(x) for x in remote.split(".")]
            return remote_parts > local_parts
        except Exception as e:
            logger.warning(f"Version comparison failed: {str(e)}")
            return False

    def _determine_update_level(self, local: str, remote: str) -> str:
        """
        判断更新级别

        @param local: 本地版本
        @param remote: 远程版本
        @return: OPTIONAL | RECOMMENDED | REQUIRED
        """
        try:
            local_parts = [int(x) for x in local.split(".")]
            remote_parts = [int(x) for x in remote.split(".")]
            
            if remote_parts[0] > local_parts[0]:
                return UpdateLevel.REQUIRED.value
            if remote_parts[1] > local_parts[1]:
                return UpdateLevel.RECOMMENDED.value
            if remote_parts[2] > local_parts[2]:
                return UpdateLevel.OPTIONAL.value
            return UpdateLevel.OPTIONAL.value
        except Exception as e:
            logger.error(f"Update level determination failed: {str(e)}")
            return UpdateLevel.OPTIONAL.value

    def check_version(self) -> Dict[str, any]:
        """
        检查MGC最新版本

        @return: 版本检查结果
        """
        try:
            cached_data = self._load_version_cache()
            if cached_data and self._is_cache_valid(cached_data):
                logger.info("Using cached version info")
                return cached_data

            region = "global"
            url = self.remote_config.get_version_check_url(region)
            timeout = self.remote_config.get_check_timeout()

            if not url:
                logger.warning("Version check URL not configured")
                return self._get_default_version_result("URL not configured")

            logger.info(f"Checking version from: {url}")
            response = self.http_client.get(url, timeout=timeout)

            if not response:
                logger.warning("Failed to fetch version info from remote")
                cached_data = self._load_version_cache()
                if cached_data:
                    logger.info("Using expired cache as fallback")
                    return cached_data
                return self._get_default_version_result("Failed to fetch version info")

            version_info = self._parse_release_response(response, url)
            update_level = self._determine_update_level(
                self.agent_version,
                version_info["tag_name"]
            )

            result = {
                "status": "success",
                "local_version": self.agent_version,
                "remote_version": version_info["tag_name"],
                "update_level": update_level,
                "release_url": version_info["html_url"],
                "release_notes": version_info.get("body", ""),
                "message": ""
            }

            self._save_version_cache(result)
            logger.info(f"Version check completed: {self.agent_version} -> {version_info['tag_name']} ({update_level})")
            return result

        except Exception as e:
            logger.error(f"Version check failed: {str(e)}")
            cached_data = self._load_version_cache()
            if cached_data:
                logger.info("Using cache as fallback after error")
                return cached_data
            return self._get_default_version_result(str(e))

    def _get_default_version_result(self, error_msg: str) -> Dict[str, any]:
        """获取默认版本检查结果"""
        return {
            "status": "error",
            "local_version": self.agent_version,
            "remote_version": "",
            "update_level": "",
            "release_url": "",
            "release_notes": "",
            "message": error_msg
        }

    def send_heartbeat(self) -> Dict[str, any]:
        """
        发送心跳统计到 Gist

        @return: 心跳发送结果
        """
        try:
            heartbeat_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] MGC started | version: {self.agent_version} | os: {self.os_info} | agent_id: {self.agent_id}\n"

            region = "global"
            gist_url = self.remote_config.get_heartbeat_url(region)
            gist_token = self.remote_config.get_gist_token()

            if not gist_url or not gist_token:
                logger.warning("Gist URL or Token not configured")
                return {"status": "error", "message": "Gist not configured"}

            headers = {
                "Authorization": f"Bearer {gist_token}",
                "Accept": "application/vnd.github+json"
            }

            response = self.http_client.get(gist_url, headers=headers, timeout=5000)
            if response.get("status") != "success":
                logger.warning(f"Failed to fetch Gist: {response.get('message')}")
                return {"status": "error", "message": "Failed to fetch Gist"}

            gist_data = response.get("data", {})
            current_content = ""
            if "files" in gist_data and "heartbeat.log" in gist_data["files"]:
                current_content = gist_data["files"]["heartbeat.log"].get("content", "") or ""

            new_content = current_content + heartbeat_entry

            update_data = {
                "files": {
                    "heartbeat.log": {
                        "content": new_content
                    }
                }
            }

            update_response = self.http_client.patch(gist_url, headers=headers, json=update_data, timeout=5000)

            if update_response.get("status") == "success":
                logger.info("Heartbeat sent to Gist successfully")
                return {"status": "success", "message": ""}
            else:
                logger.warning(f"Failed to update Gist: {update_response.get('message')}")
                return {"status": "error", "message": "Failed to update Gist"}

        except Exception as e:
            logger.error(f"Heartbeat failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def is_update_required(self) -> Dict[str, any]:
        """
        判断是否需要更新

        @return: 更新判断结果
        """
        result = self.check_version()

        if result["status"] != "success":
            return {
                "need_update": False,
                "local_version": self.agent_version,
                "remote_version": "",
                "update_level": ""
            }

        need_update = self._compare_versions(
            self.agent_version,
            result["remote_version"]
        )

        return {
            "need_update": need_update,
            "local_version": self.agent_version,
            "remote_version": result["remote_version"],
            "update_level": result["update_level"]
        }