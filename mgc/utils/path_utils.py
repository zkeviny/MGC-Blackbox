"""路径处理工具 (v1.0 核心)

用途：
- 提供项目所有路径的统一获取接口。
- 封装路径转换、目录创建等常用操作。

规范：
- 所有业务代码应通过本模块的函数获取路径，而不是直接从 path_config 导入。
"""

from mgc.config.path_config import (
    PROJECT_ROOT, SECRETS_DIR, QUERY_LIST_DIR, DATABASE_DIR, LOG_DIR, TEMP_DIR,
    CUSTOMER_SECRETS_FILE, MIGRATION_KEY_FILE, QUERY_LIST_FILE, QUERY_LIST_BACKUP_DIR, DB_FILE, DB_DIR,
    APP_LOG_FILE, ERROR_LOG_FILE,
    get_relative_path as config_get_relative_path,
    get_absolute_path as config_get_absolute_path,
    ensure_directories as config_ensure_directories
)
from pathlib import Path

# --- 核心工具函数 ---

def get_relative_path(absolute_path):
    """获取相对于项目根目录的路径"""
    return config_get_relative_path(absolute_path)

def get_absolute_path(relative_path):
    """根据相对路径获取绝对路径"""
    return config_get_absolute_path(relative_path)

def ensure_directories():
    """确保存储目录存在"""
    config_ensure_directories()

# --- v1.0 目录路径获取 --- 

def get_secrets_dir():
    """获取密钥目录 (secrets/) 的绝对路径"""
    return str(SECRETS_DIR)

def get_query_list_dir():
    """获取查询清单目录 (query_list/) 的绝对路径"""
    return str(QUERY_LIST_DIR)

def get_database_dir():
    """获取数据库目录 (database/) 的绝对路径"""
    return str(DATABASE_DIR)

def get_logs_dir():
    """获取日志目录 (logs/) 的绝对路径"""
    return str(LOG_DIR)

# --- v1.0 文件路径获取 ---

def get_customer_secrets_file():
    """获取用户密钥文件 (customer_secrets.md) 的绝对路径"""
    return str(CUSTOMER_SECRETS_FILE)

def get_migration_key_file():
    """获取迁移密钥文件 (.txt) 的绝对路径"""
    return str(MIGRATION_KEY_FILE)

def get_query_list_file():
    """获取查询清单文件 (query_list.json) 的绝对路径"""
    return str(QUERY_LIST_FILE)

def get_query_list_backup_dir():
    """获取查询清单备份目录 (query_list/backup/) 的绝对路径"""
    return str(QUERY_LIST_BACKUP_DIR)

def get_db_dir():
    """获取MySQL数据库目录 (mgc_black_box/) 的绝对路径"""
    return str(DB_DIR)


def get_user_dir():
    """获取用户数据目录（与数据库目录相同）"""
    return get_db_dir()

def get_db_file():
    """获取数据库文件 (mgc_black_box.db) 的绝对路径"""
    return str(DB_FILE)

def get_app_log_file():
    """获取应用日志文件 (app.log) 的绝对路径"""
    return str(APP_LOG_FILE)

def get_error_log_file():
    """获取错误日志文件 (error.log) 的绝对路径"""
    return str(ERROR_LOG_FILE)

# --- 兼容性保留函数 (将被废弃) ---

def get_storage_dir():
    """(兼容保留，后续可弃用) 获取存储目录路径。在 v1.0 中，数据被分散到更具体的目录。"""
    # v1.0 中没有统一的 storage 目录，这里可以返回根目录或特定子目录，取决于兼容逻辑
    return str(PROJECT_ROOT)

def get_encrypted_dir():
    """(兼容保留，后续可弃用) 获取加密文件目录路径。v1.0 的数据存储在 database/ 中。"""
    return get_database_dir()

def get_keys_dir():
    """(兼容保留，后续可弃用) 获取密钥目录路径。v1.0 中应使用 get_secrets_dir()。"""
    return get_secrets_dir()


# --- 文件操作工具函数 ---

def file_exists(file_path):
    """
    检查文件是否存在

    Args:
        file_path: 文件路径（绝对路径或相对路径）

    Returns:
        bool: 文件是否存在

    Raises:
        TypeError: 文件路径类型错误
    """
    if not isinstance(file_path, (str, Path)):
        raise TypeError("文件路径必须是字符串或Path对象")
    try:
        abs_path = get_absolute_path(file_path)
        return Path(abs_path).exists()
    except Exception as e:
        raise IOError(f"检查文件是否存在失败: {e}")


def read_file(file_path):
    """
    读取文件内容

    Args:
        file_path: 文件路径（绝对路径或相对路径）

    Returns:
        str: 文件内容

    Raises:
        FileNotFoundError: 文件不存在
        IOError: 读取失败
        TypeError: 文件路径类型错误
    """
    if not isinstance(file_path, (str, Path)):
        raise TypeError("文件路径必须是字符串或Path对象")
    try:
        abs_path = get_absolute_path(file_path)
        with open(abs_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"文件不存在: {abs_path}")
    except Exception as e:
        raise IOError(f"读取文件失败: {e}")


def write_file(file_path, content):
    """
    写入文件内容

    Args:
        file_path: 文件路径（绝对路径或相对路径）
        content: 文件内容

    Raises:
        IOError: 写入失败
        TypeError: 文件路径类型错误
    """
    if not isinstance(file_path, (str, Path)):
        raise TypeError("文件路径必须是字符串或Path对象")
    if not isinstance(content, str):
        raise TypeError("文件内容必须是字符串")
    try:
        abs_path = get_absolute_path(file_path)
        # newline="" 禁止 Windows 下自动转成 CRLF，保持内容与源一致
        with open(abs_path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
    except Exception as e:
        raise IOError(f"写入文件失败: {e}")


def clear_root_credentials():
    """
    清除root权限相关变量及临时凭证文件

    说明：
    - 不删除root用户账户（DROP USER root）
    - 仅清除root权限相关的临时变量和凭证文件
    - 符合架构文档要求：初始化后清空root权限相关变量及临时文件

    参考文档：document\architecture_framework.md#L120-L125

    Raises:
        IOError: 清除失败
    """
    try:
        temp_dir = Path(get_temp_dir())
        if temp_dir.exists():
            for file in temp_dir.glob("temp_root_*"):
                try:
                    file.unlink()
                except Exception as e:
                    raise IOError(f"删除临时凭证文件失败: {file}, 错误: {e}")
    except Exception as e:
        raise IOError(f"清除root凭证失败: {e}")


def get_temp_dir():
    """获取临时目录 (temp/) 的绝对路径"""
    return str(TEMP_DIR)

