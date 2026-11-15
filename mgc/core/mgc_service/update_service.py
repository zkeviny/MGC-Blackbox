"""
MGC 升级检查服务

功能：
- 从 PyPI 查询最新版本
- 比较当前版本与最新版本
- 提供升级信息（version code、upgrade command、PyPI 链接）

依赖：
- requests（HTTP 请求）
- mgc.__version__（当前版本）
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger("mgc.core.mgc_service.update_service")


class UpdateServiceError(Exception):
    """升级服务异常"""
    pass


@dataclass
class UpdateInfo:
    """升级信息数据类"""
    has_update: bool
    current_version: str
    latest_version: str
    upgrade_command: str
    pypi_url: str

    def to_dict(self) -> dict:
        return asdict(self)


# PyPI 包名（与 setup.py / pyproject.toml 一致）
PYPI_PACKAGE_NAME = "mgc-blackbox"
PYPI_API_URL = f"https://pypi.org/pypi/{PYPI_PACKAGE_NAME}/json"


def _parse_version_tuple(version_str: str) -> tuple:
    """
    安全解析版本号字符串为元组

    修复 'int() with base 10: ''' 错误：遇到空字符串或非法字符时返回 (0, 0, 0)
    """
    if not version_str or not isinstance(version_str, str):
        return (0, 0, 0)
    try:
        # 去掉可能的 'v' 前缀和预发布标签
        clean = version_str.strip().lstrip('v')
        # 提取主版本号（去掉 -alpha, +build 等后缀）
        for sep in ['-', '+']:
            if sep in clean:
                clean = clean.split(sep)[0]
        parts = clean.split('.')
        # 补齐为 3 段
        nums = []
        for p in parts[:3]:
            try:
                nums.append(int(p))
            except (ValueError, AttributeError):
                nums.append(0)
        while len(nums) < 3:
            nums.append(0)
        return tuple(nums)
    except Exception:
        return (0, 0, 0)


def _get_latest_version_from_pypi(timeout: float = 5.0) -> Optional[str]:
    """
    从 PyPI JSON API 查询最新版本

    Returns:
        最新版本字符串，失败时返回 None
    """
    try:
        req = urllib.request.Request(
            PYPI_API_URL,
            headers={"Accept": "application/json", "User-Agent": "MGC-Blackbox/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("info", {}).get("version")
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to fetch latest version from PyPI: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching PyPI version: {e}")
        return None


class UpdateService:
    """升级检查服务"""

    def __init__(self):
        """初始化升级服务"""
        # 延迟导入避免循环依赖
        from mgc import __version__ as current_version
        self.current_version = current_version

    def check_for_updates(self) -> UpdateInfo:
        """
        检查是否有可用更新

        Returns:
            UpdateInfo: 升级信息
        """
        latest_version = _get_latest_version_from_pypi()

        if not latest_version:
            # 网络失败：返回无更新状态（不影响主流程）
            logger.info("PyPI check failed, assume no update")
            return UpdateInfo(
                has_update=False,
                current_version=self.current_version,
                latest_version=self.current_version,
                upgrade_command=self._build_upgrade_command(self.current_version),
                pypi_url=f"https://pypi.org/project/{PYPI_PACKAGE_NAME}/"
            )

        current_tuple = _parse_version_tuple(self.current_version)
        latest_tuple = _parse_version_tuple(latest_version)

        has_update = latest_tuple > current_tuple

        target_version = latest_version if has_update else self.current_version

        return UpdateInfo(
            has_update=has_update,
            current_version=self.current_version,
            latest_version=latest_version,
            upgrade_command=self._build_upgrade_command(target_version),
            pypi_url=f"https://pypi.org/project/{PYPI_PACKAGE_NAME}/{latest_version}/"
        )

    def _build_upgrade_command(self, version: str) -> str:
        """构建 pip install 升级命令"""
        return f"pip install {PYPI_PACKAGE_NAME}=={version} --upgrade"
