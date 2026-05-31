"""远程配置管理模块 (v1.0)

用途：
- 加载和解析 config/remote_config.yaml 配置文件
- 提供远程服务地址的动态读取（无硬编码）
- 支持双区域配置（china/global）和主备双源

规范：
- 所有远程服务地址通过此模块动态读取
- 禁止硬编码任何域名或地址
"""

import yaml
import os
from typing import Dict, Optional, Tuple
from pathlib import Path


class RemoteConfig:
    """远程配置管理（双区域支持，主备双源）"""
    
    VALID_REGIONS = ("china", "global")
    
    def __init__(self, config_path: str = None):
        """
        初始化远程配置
        
        @param config_path: 配置文件路径，默认使用项目根目录下的 config/remote_config.yaml
        """
        if config_path is None:
            project_root = Path(__file__).parent.parent.absolute()
            config_path = project_root / "config" / "remote_config.yaml"
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            if not self.config_path.exists():
                return self._get_default_config()
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or self._get_default_config()
        except Exception:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置结构"""
        return {
            "remote": {
                "region": {"auto_detect": True, "manual_region": "china"},
                "china": {
                    "registry": {"primary": "", "secondary": ""},
                    "heartbeat": {"url": "", "timeout": 3},
                    "log": {"error_url": "", "timeout": 3}
                },
                "global": {
                    "registry": {"primary": "", "secondary": ""},
                    "heartbeat": {"url": "", "timeout": 3},
                    "log": {"error_url": "", "timeout": 3}
                }
            },
            "check": {"cache_expire": 24, "cycle": 12, "timeout": 3},
            "upgrade": {
                "max_retry": 3, "retry_interval": 2,
                "max_package_size": 500, "batch_limit": 3
            }
        }
    
    def get_registry_urls(self, region: str) -> Tuple[str, str]:
        """
        获取注册表URL（主源、备源）
        
        @param region: 区域（china/global）
        @return: (primary_url, secondary_url)
        """
        if region not in self.VALID_REGIONS:
            region = "china"
        registry = self.config.get("remote", {}).get(region, {}).get("registry", {})
        return (
            registry.get("primary", ""),
            registry.get("secondary", "")
        )
    
    def get_heartbeat_url(self, region: str) -> str:
        """
        获取心跳URL
        
        @param region: 区域（china/global）
        @return: 心跳上报地址
        """
        if region not in self.VALID_REGIONS:
            region = "china"
        return self.config.get("remote", {}).get(region, {}).get("heartbeat", {}).get("url", "")
    
    def get_heartbeat_timeout(self, region: str) -> int:
        """
        获取心跳超时时间（秒）

        @param region: 区域（china/global）
        @return: 超时秒数
        """
        if region not in self.VALID_REGIONS:
            region = "china"
        return self.config.get("remote", {}).get(region, {}).get("heartbeat", {}).get("timeout", 3)

    def get_version_check_url(self, region: str) -> str:
        """
        获取版本检查URL

        @param region: 区域（china/global）
        @return: 版本检查地址
        """
        if region not in self.VALID_REGIONS:
            region = "china"
        return self.config.get("remote", {}).get(region, {}).get("version_check", {}).get("url", "")

    def get_gist_token(self) -> str:
        """
        获取 Gist Token

        @return: Gist 个人访问令牌
        """
        return self.config.get("gist_token", "")
    
    def get_log_url(self, region: str) -> str:
        """
        获取日志上报URL
        
        @param region: 区域（china/global）
        @return: 日志上报地址
        """
        if region not in self.VALID_REGIONS:
            region = "china"
        return self.config.get("remote", {}).get(region, {}).get("log", {}).get("error_url", "")
    
    def is_auto_detect_region(self) -> bool:
        """
        是否自动检测区域
        
        @return: True=自动检测，False=使用手动指定
        """
        return self.config.get("remote", {}).get("region", {}).get("auto_detect", True)
    
    def get_manual_region(self) -> str:
        """
        获取手动指定区域
        
        @return: 区域标识（china/global）
        """
        region = self.config.get("remote", {}).get("region", {}).get("manual_region", "china")
        return region if region in self.VALID_REGIONS else "china"
    
    def get_check_cache_expire(self) -> int:
        """
        获取缓存有效期（小时）
        
        @return: 缓存有效期小时数
        """
        return self.config.get("check", {}).get("cache_expire", 24)
    
    def get_check_cycle(self) -> int:
        """
        获取定时检查周期（小时）
        
        @return: 检查周期小时数
        """
        return self.config.get("check", {}).get("cycle", 12)
    
    def get_check_timeout(self) -> int:
        """
        获取远程请求超时（秒）
        
        @return: 超时秒数
        """
        return self.config.get("check", {}).get("timeout", 3)
    
    def get_upgrade_max_retry(self) -> int:
        """
        获取下载最大重试次数
        
        @return: 最大重试次数
        """
        return self.config.get("upgrade", {}).get("max_retry", 3)
    
    def get_upgrade_retry_interval(self) -> int:
        """
        获取重试间隔（秒）
        
        @return: 重试间隔秒数
        """
        return self.config.get("upgrade", {}).get("retry_interval", 2)
    
    def get_max_package_size(self) -> int:
        """
        获取单技能包最大体积（MB）
        
        @return: 最大体积MB
        """
        return self.config.get("upgrade", {}).get("max_package_size", 500)
    
    def get_batch_limit(self) -> int:
        """
        获取单次批量升级最大技能数
        
        @return: 最大技能数
        """
        return self.config.get("upgrade", {}).get("batch_limit", 3)
