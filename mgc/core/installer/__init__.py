"""
安装流程模块包

用途：
- 实现MirginCipher的安装流程
- 包括用户须知确认、密钥输入、密钥保存、账户创建、权限设置等功能
- 确保系统能够安全、可靠地完成初始化配置

模块列表：
- user_notice: 用户须知确认模块
- auto_key_generator: 1.5.3 新增：随机生成 personal_key + weight
- migrate_key_saver: 迁移密钥文件保存模块
- env_factor_generator: 初始环境因子采集与加密存储模块
- root_key_encryptor: 根密钥硬件加密存储模块
- migration_account_creator: 迁移授权账号创建模块
- daily_account_generator: 设备日常账号生成模块
"""

from .user_notice import UserNotice, UserNoticeError
from .auto_key_generator import AutoKeyGenerator
from .migrate_key_saver import MigrateKeySaver, MigrateKeySaveError
from .env_factor_generator import EnvFactorGenerator, EnvFactorGeneratorError
from .root_key_encryptor import RootKeyEncryptor, RootKeyEncryptorError
from .migration_account_creator import MigrationAccountCreator, MigrationAccountCreatorError
from .daily_account_generator import DailyAccountGenerator, DailyAccountGeneratorError

__all__ = [
    "UserNotice",
    "UserNoticeError",
    "AutoKeyGenerator",
    "MigrateKeySaver",
    "MigrateKeySaveError",
    "EnvFactorGenerator",
    "EnvFactorGeneratorError",
    "RootKeyEncryptor",
    "RootKeyEncryptorError",
    "MigrationAccountCreator",
    "MigrationAccountCreatorError",
    "DailyAccountGenerator",
    "DailyAccountGeneratorError",
]
