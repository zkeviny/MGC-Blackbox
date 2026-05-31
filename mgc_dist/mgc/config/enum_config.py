"""
枚举值词典定义
统一管理系统中使用的常量和枚举值

功能：
- 定义系统中使用的所有枚举类型
- 提供统一的常量定义
- 确保枚举值有统一的定义和出处
"""

from enum import Enum
from mgc.utils.compat import StrEnum


class OperationType(StrEnum):
    """操作类型枚举"""
    INIT = "INIT"
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"
    QUERY = "query"
    STORE = "store"
    CHANGE_ROOT_KEY = "CHANGE_ROOT_KEY"


class OperationResult(StrEnum):
    """操作结果枚举"""
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


class ConfigItem(StrEnum):
    """配置项枚举"""
    ENTERPRISE_TABLE_MODE = "ENTERPRISE_TABLE_MODE"
    TASK_VALIDATE_SWITCH = "TASK_VALIDATE_SWITCH"
    DATABASE_NAME = "DATABASE_NAME"
    ENV_MIGRATION = "ENV_MIGRATION"
    KEEP_ROOT_ACCOUNT = "KEEP_ROOT_ACCOUNT"
    STARTUP_ENV_CHECK = "STARTUP_ENV_CHECK"
    LOCAL_UI_SESSION_VALIDATE = "LOCAL_UI_SESSION_VALIDATE"
    EXTERNAL_ENV_CONFIRM = "EXTERNAL_ENV_CONFIRM"
    AES256_ENCRYPT = "AES256_ENCRYPT"
    AES_256_ENABLE = "AES_256_ENABLE"
    SINGLE_INFO_UNIT = "SINGLE_INFO_UNIT"
    
    # 版本更新配置
    SKILL_UPDATE_TRIGGER_STRATEGY = "SKILL_UPDATE_TRIGGER_STRATEGY"
    ENABLE_HOT_UPDATE = "ENABLE_HOT_UPDATE"
    ENABLE_ROLLBACK = "ENABLE_ROLLBACK"
    DUAL_DOWNLOAD_SOURCE = "DUAL_DOWNLOAD_SOURCE"
    
    # 查询清单与日志配置
    QUERY_LIST_ENABLED = "QUERY_LIST_ENABLED"
    LOG_SYSTEM_ENABLED = "LOG_SYSTEM_ENABLED"
    LOG_RETENTION_DAYS = "LOG_RETENTION_DAYS"
    
    # 系统级Agent配置
    SYSTEM_AGENT_UUID = "SYSTEM_AGENT_UUID"
    SYSTEM_AGENT_WHITELIST = "SYSTEM_AGENT_WHITELIST"


class ConfigDefaults:
    """配置项默认值"""
    ENTERPRISE_TABLE_MODE = False
    TASK_VALIDATE_SWITCH = False
    DATABASE_NAME = "mgc_black_box"
    ENV_MIGRATION = False
    KEEP_ROOT_ACCOUNT = False
    STARTUP_ENV_CHECK = False
    LOCAL_UI_SESSION_VALIDATE = False
    EXTERNAL_ENV_CONFIRM = False
    AES256_ENCRYPT = False
    AES_256_ENABLE = True
    SINGLE_INFO_UNIT = True
    
    # 版本更新配置默认值
    SKILL_UPDATE_TRIGGER_STRATEGY = ["agent_start", "skill_call", "scheduled", "manual"]
    ENABLE_HOT_UPDATE = True
    ENABLE_ROLLBACK = True
    DUAL_DOWNLOAD_SOURCE = True
    
    # 查询清单与日志配置默认值
    QUERY_LIST_ENABLED = True
    LOG_SYSTEM_ENABLED = True
    LOG_RETENTION_DAYS = 30
    
    # 系统级Agent配置默认值
    SYSTEM_AGENT_UUID = "system-scheduler"
    SYSTEM_AGENT_WHITELIST = [
        "system-scheduler",
        "system-admin"
    ]


class CryptoAlgorithm(StrEnum):
    """加密算法枚举"""
    SHA256 = "SHA256"
    AES256 = "AES256"
    RSA = "RSA"
    SM4 = "SM4"


class UpdateLevel(StrEnum):
    """版本控制枚举"""
    OPTIONAL = "OPTIONAL"
    RECOMMENDED = "RECOMMENDED"
    REQUIRED = "REQUIRED"


class InstallSource(StrEnum):
    """安装来源枚举"""
    DIALOG = "DIALOG"
    COMMAND = "COMMAND"


class DatabaseType(StrEnum):
    """数据库类型枚举"""
    MYSQL = "mysql"
    SQLCIPHER = "sqlcipher"


class ServiceStatus(StrEnum):
    """服务状态枚举"""
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    STARTING = "STARTING"
    STOPPING = "STOPPING"
