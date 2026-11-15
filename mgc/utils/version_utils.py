"""版本读取工具 (v1.0)

用途：
- 提供版本号统一读取接口。
- 优先级：metadata.json -> VERSION -> 硬编码fallback

依赖：
- 无外部依赖
"""

import os
import json
from pathlib import Path

_VERSION_FALLBACK = "1.6.0"


def _get_version_from_metadata(project_root: Path) -> str:
    """从metadata.json读取版本（打包后生成）"""
    metadata_paths = [
        project_root / "metadata.json",
        project_root / "dist-info" / "metadata.json",
    ]
    for metadata_path in metadata_paths:
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("version", "")
            except Exception:
                pass
    return ""


def _get_version_from_file(project_root: Path) -> str:
    """从VERSION文件读取版本"""
    version_file = project_root / "VERSION"
    if version_file.exists():
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""


def get_version() -> str:
    """获取版本号

    优先级：
    1. metadata.json（打包后生成）
    2. VERSION文件（本地开发）
    3. 硬编码fallback
    """
    project_root = Path(__file__).parent.parent.parent

    version = _get_version_from_metadata(project_root)
    if version:
        return version

    version = _get_version_from_file(project_root)
    if version:
        return version

    return _VERSION_FALLBACK