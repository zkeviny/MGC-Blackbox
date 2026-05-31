"""用户设置模块 (v1.0)

用途：
- 统一管理用户偏好设置
- 防护模式开关
"""

import json
import os
from pathlib import Path

USER_SETTINGS_FILE = "config/user_settings.json"


def _get_settings_path():
    from mgc.config.path_config import RUNTIME_ROOT
    return RUNTIME_ROOT / USER_SETTINGS_FILE


def get_protection_mode() -> bool:
    """获取防护模式状态"""
    path = _get_settings_path()
    if not path.exists():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("protection_mode", False)
    except Exception:
        return False


def set_protection_mode(enabled: bool) -> bool:
    """设置防护模式状态"""
    path = _get_settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "protection_mode": enabled,
            "#": "DO NOT manually modify this setting. Changing protection_mode manually will cause the program to fail to start. Use the official interface or WebUI to toggle this setting."
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception:
        return False
