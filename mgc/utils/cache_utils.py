"""缓存工具模块

用途：
- 管理输入缓存，用于IO操作失败时保存输入数据
- 提供缓存文件的创建、读取和清理功能
- 支持缓存过期自动清理

依赖：
- src.config.path_config.TEMP_DIR

未来演进：
- 可扩展支持更多缓存策略
- 可添加缓存加密功能
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from mgc.config.path_config import TEMP_DIR

# 缓存目录
CACHE_DIR = TEMP_DIR / "input_cache"

# 缓存保留时间（秒）：7天
CACHE_RETENTION_DAYS = 7 * 24 * 60 * 60

# 最大缓存文件数量
MAX_CACHE_FILES = 100


def ensure_cache_dir():
    """确保缓存目录存在"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def save_input_cache(
    input_type: str,
    content: str,
    error_message: str,
    source_path: Optional[str] = None
) -> str:
    """保存输入缓存

    Args:
        input_type: 输入类型（file/text）
        content: 原始输入内容
        error_message: 错误信息
        source_path: 源文件路径（如果是文件输入）

    Returns:
        str: 缓存文件路径
    """
    ensure_cache_dir()

    # 清理过期缓存
    clean_expired_cache()

    # 生成缓存文件名
    timestamp = int(time.time())
    cache_filename = f"cache_{timestamp}_{input_type}.json"
    cache_path = CACHE_DIR / cache_filename

    # 构建缓存数据
    cache_data = {
        "timestamp": timestamp,
        "input_type": input_type,
        "content": content,
        "error_message": error_message,
        "source_path": source_path
    }

    # 写入缓存文件
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        return str(cache_path)
    except Exception as e:
        # 缓存写入失败，不影响主流程
        print(f"Warning: Failed to save cache: {e}")
        return ""


def load_input_cache(cache_path: str) -> Optional[Dict[str, Any]]:
    """加载输入缓存

    Args:
        cache_path: 缓存文件路径

    Returns:
        Optional[Dict[str, Any]]: 缓存数据，如果加载失败则返回None
    """
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load cache: {e}")
        return None


def clean_expired_cache():
    """清理过期缓存文件"""
    if not CACHE_DIR.exists():
        return

    current_time = time.time()
    expired_files = []

    # 找出过期文件
    for cache_file in CACHE_DIR.glob("cache_*.json"):
        try:
            file_stat = cache_file.stat()
            file_age = current_time - file_stat.st_mtime

            if file_age > CACHE_RETENTION_DAYS:
                expired_files.append(cache_file)
        except Exception:
            continue

    # 删除过期文件
    for expired_file in expired_files:
        try:
            expired_file.unlink()
        except Exception:
            continue

    # 如果缓存文件数量超过限制，删除最旧的文件
    cache_files = sorted(
        CACHE_DIR.glob("cache_*.json"),
        key=lambda f: f.stat().st_mtime
    )

    while len(cache_files) > MAX_CACHE_FILES:
        try:
            cache_files[0].unlink()
            cache_files.pop(0)
        except Exception:
            break


def get_all_cache_files() -> list:
    """获取所有缓存文件列表

    Returns:
        list: 缓存文件路径列表
    """
    if not CACHE_DIR.exists():
        return []

    return list(CACHE_DIR.glob("cache_*.json"))
