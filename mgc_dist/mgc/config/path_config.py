"""路径配置模块 (v1.0 核心)

用途：
- 统一管理项目的所有相对路径和绝对路径。
- 提供跨环境部署的路径处理能力。
- 确保所有文件操作使用相对路径，避免硬编码绝对路径。

规范：
- 所有路径变量必须通过此模块统一定义和获取。
- 路径定义严格遵守 architecture_framework.md 中的规范。
"""

import os
import platform
import sys
from pathlib import Path

# ========== 路径定义 ==========
# 仓库根目录（开发环境）
REPO_ROOT = Path(__file__).parent.parent.parent.absolute()

# 源代码根目录 = src/
# 注意：__file__ 在 src/config/path_config.py，所以 parent.parent 才是 src/
SRC_ROOT = Path(__file__).parent.parent.absolute()

# 运行时根目录
# 统一使用 ~/.mgc/ 作为根目录（所有平台一致）
# 优先级：环境变量 > 默认（统一使用 ~/.mgc/）
_mgc_runtime_env = os.environ.get('MGC_RUNTIME_ROOT')
if _mgc_runtime_env:
    RUNTIME_ROOT = Path(_mgc_runtime_env)
else:
    RUNTIME_ROOT = Path.home() / ".mgc"
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)

# ========== 目录定义 ==========
# 源代码内资源目录（打包后可用）
SRC_DIR = SRC_ROOT

# 运行时目录（使用 RUNTIME_ROOT）
SECRETS_DIR = RUNTIME_ROOT / "secrets"
QUERY_LIST_DIR = RUNTIME_ROOT / "query_list"
DATABASE_DIR = RUNTIME_ROOT / "database"
LOG_DIR = RUNTIME_ROOT / "logs"
SKILLS_DIR = RUNTIME_ROOT / "skills"
DOCS_DIR = RUNTIME_ROOT / "docs"

PROJECT_ROOT = RUNTIME_ROOT

# ========== 日志文件 ==========
APP_LOG_FILE = LOG_DIR / "app.log"
ERROR_LOG_FILE = LOG_DIR / "error.log"

# 临时目录
TEMP_DIR = REPO_ROOT / "temp"

# ========== Skills 文件 ==========
HEARTBEAT_STATS_FILE = SKILLS_DIR / "heartbeat_stats.json"
VERSION_CACHE_FILE = SKILLS_DIR / "version_cache.json"


# --- v1.0 核心文件路径 --- 

# 密钥文件
CUSTOMER_SECRETS_FILE = SECRETS_DIR / "customer_secrets.md"
MIGRATION_KEY_FILE = SECRETS_DIR / "个人密钥用于环境变更认证和动态盐加密需慎重保管.txt"
MGC_MIGRATION_KEY_FILE = PROJECT_ROOT / "MGC迁移密钥请妥善保管丢失后无法迁移.txt"

# 查询清单文件
QUERY_LIST_FILE = QUERY_LIST_DIR / "query_list.json"

# 查询清单备份目录
QUERY_LIST_BACKUP_DIR = QUERY_LIST_DIR / "backup"

# MySQL 数据库目录 (架构文档要求：../database/mgc_black_box/)
DB_DIR = DATABASE_DIR / "mgc_black_box"

# 数据库文件 (SQLite 示例, MySQL 则为连接配置)
DB_FILE = DB_DIR / "mgc_black_box.db"


# 确保存储目录存在
def ensure_directories():
    """在应用启动时，确保存储数据的核心目录都已创建"""
    for directory in [SECRETS_DIR, QUERY_LIST_DIR, DATABASE_DIR, LOG_DIR, DB_DIR, TEMP_DIR, SKILLS_DIR]:
        directory.mkdir(exist_ok=True, parents=True)

# 获取相对路径
def get_relative_path(absolute_path):
    """获取相对于项目根目录的路径"""
    return str(Path(absolute_path).relative_to(PROJECT_ROOT))

# 获取绝对路径
def get_absolute_path(relative_path):
    """根据相对路径获取绝对路径"""
    return str(PROJECT_ROOT / relative_path)

# 获取日志文件路径
def get_log_file(log_type="app"):
    """获取日志文件路径"""
    if log_type == "app":
        return str(APP_LOG_FILE)
    elif log_type == "error":
        return str(ERROR_LOG_FILE)
    else:
        return str(APP_LOG_FILE)

# 获取迁移密钥文件路径
def get_migrate_key_file():
    """获取迁移密钥文件路径"""
    return str(MGC_MIGRATION_KEY_FILE)
