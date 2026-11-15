r"""
迁移授权账号创建模块

用途：
- 创建固定账号mgc_env_access，密码=迁移密钥
- 权限仅为：为新设备创建并授权只读账号
- 不参与日常运行、不接触业务数据
- 复用优先级12的MySQL操作模块

参考文档：
- document/1.0细节需求文档/迁移密钥+根密钥处理方案.md

限制条件：
- 必须使用src/config/path_config.py中定义的相对路径
- 所有IO操作必须捕获异常
- mgc_env_access账号权限仅为新设备创建并授权只读账号
- 迁移密钥仅在创建mgc_env_access账号时进入内存，使用后立即清空
- 迁移密钥不参与加密过程
"""

import logging
from typing import Optional

from mgc.config.i18n_config import get_exception_message, Messages

logger = logging.getLogger(__name__)


class MigrationAccountCreatorError(Exception):
    """迁移授权账号创建异常"""
    pass


class MigrationAccountCreator:
    """迁移授权账号创建类"""
    
    MIGRATION_ACCOUNT_NAME = "mgc_env_access"
    
    def __init__(self):
        """初始化迁移授权账号创建类"""
        pass
    
    def create_migration_account(self, migrate_key: str, db_handler, salts: dict = None) -> bool:
        """
        创建迁移授权账号
        
        功能：
        - 创建固定账号mgc_env_access
        - 密码设置为迁移密钥
        - 授予创建账号和授权只读权限
        
        入参：
            migrate_key: 迁移密钥
            db_handler: 数据库处理器
            salts: 动态盐字典（可选，若不传则使用默认值）
        
        出参：
            bool: 创建成功返回True
        
        异常：
            MigrationAccountCreatorError: 创建失败时抛出
        """
        try:
            if not migrate_key:
                raise MigrationAccountCreatorError(get_exception_message(Messages.MigrationAccountCreator, "MIGRATE_KEY_CANNOT_BE_EMPTY"))
            
            if self._account_exists(db_handler):
                raise MigrationAccountCreatorError(get_exception_message(Messages.MigrationAccountCreator, "ACCOUNT_ALREADY_EXISTS", account_name=self.MIGRATION_ACCOUNT_NAME))
            
            self._create_account(migrate_key, db_handler, salts)
            
            self._grant_permissions(db_handler)
            
            if db_handler.database_type != "sqlcipher":
                logger.debug(f"迁移授权账号{self.MIGRATION_ACCOUNT_NAME}创建成功")
            
            return True
        except Exception as e:
            error_msg = f"创建迁移授权账号失败: {str(e)}"
            logger.error(error_msg)
            raise MigrationAccountCreatorError(get_exception_message(Messages.MigrationAccountCreator, "CREATE_MIGRATION_ACCOUNT_FAILED", error=str(e)))
        finally:
            migrate_key = None
    
    def _account_exists(self, db_handler) -> bool:
        """
        检查账号是否已存在
        
        入参：
            db_handler: 数据库处理器
        
        出参：
            True表示已存在，False表示不存在
        """
        try:
            if db_handler.database_type == "sqlcipher":
                return False
            else:
                query_sql = f"SELECT COUNT(*) as count FROM mysql.user WHERE user = '{self.MIGRATION_ACCOUNT_NAME}'"
                result = db_handler.execute_query(query_sql)
                if result and result[0]['count'] > 0:
                    return True
            
            return False
        except Exception as e:
            logger.debug(f"Failed to check account existence: {str(e)}")
            return False
    
    def _create_account(self, migrate_key: str, db_handler, salts: dict = None) -> None:
        """
        创建账号
        
        入参：
            migrate_key: 迁移密钥
            db_handler: 数据库处理器
            salts: 动态盐字典（可选）
        
        异常：
            MigrationAccountCreatorError: 创建失败时抛出
        """
        try:
            if db_handler.database_type == "sqlcipher":
                from mgc.domain.crypto_layer.credential_generator import generate_migration_credentials
                if salts is None:
                    raise MigrationAccountCreatorError("SQLCipher 模式需要动态盐，请传入 salts 参数")
                migration_account, migration_password = generate_migration_credentials(migrate_key, salts)
                logger.debug("SQLCipher mode: Migration credentials generated")
            else:
                create_sql = f"CREATE USER '{self.MIGRATION_ACCOUNT_NAME}'@'%' IDENTIFIED BY %s"
                db_handler.execute_update(create_sql, (migrate_key,))
                logger.debug(f"账号{self.MIGRATION_ACCOUNT_NAME}创建成功")
        except Exception as e:
            error_msg = f"创建账号失败: {str(e)}"
            logger.error(error_msg)
            raise MigrationAccountCreatorError(get_exception_message(Messages.MigrationAccountCreator, "CREATE_ACCOUNT_FAILED", error=str(e)))
    
    def _grant_permissions(self, db_handler) -> None:
        """
        授予权限
        
        功能：
        - 授予创建账号权限
        - 授予授权只读mgc_system_env表权限
        - 不授予其他任何权限
        
        入参：
            db_handler: 数据库处理器
        
        异常：
            MigrationAccountCreatorError: 授权失败时抛出
        """
        try:
            if db_handler.database_type == "sqlcipher":
                logger.debug("SQLCipher mode: Application-layer authentication, no database-layer authorization required")
            else:
                database_name = self._get_database_name(db_handler)
                grant_create_sql = f"GRANT CREATE USER ON *.* TO '{self.MIGRATION_ACCOUNT_NAME}'@'%'"
                db_handler.execute_update(grant_create_sql)
                grant_grant_sql = f"GRANT SELECT ON `{database_name}`.mgc_system_env TO '{self.MIGRATION_ACCOUNT_NAME}'@'%'"
                db_handler.execute_update(grant_grant_sql)
                flush_sql = "FLUSH PRIVILEGES"
                db_handler.execute_update(flush_sql)
                logger.debug(f"账号{self.MIGRATION_ACCOUNT_NAME}权限授予成功")
        except Exception as e:
            error_msg = f"授予权限失败: {str(e)}"
            logger.error(error_msg)
            raise MigrationAccountCreatorError(get_exception_message(Messages.MigrationAccountCreator, "GRANT_PERMISSIONS_FAILED", error=str(e)))
    
    def _get_database_name(self, db_handler) -> str:
        """
        获取数据库名
        
        入参：
            db_handler: 数据库处理器
        
        出参：
            数据库名
        """
        try:
            from config.enum_config import ConfigDefaults
            return ConfigDefaults.DATABASE_NAME
        except Exception as e:
            logger.debug(f"Failed to get database name: {str(e)}")
            return "mgc_black_box"
    
    def verify_migration_account(self, db_handler) -> bool:
        """
        验证迁移授权账号是否存在
        
        入参：
            db_handler: 数据库处理器
        
        出参：
            True表示存在，False表示不存在
        """
        try:
            return self._account_exists(db_handler)
        except Exception as e:
            logger.debug(f"Migration authorization account verification failed: {str(e)}")
            return False
    
    def delete_migration_account(self, db_handler) -> bool:
        """
        删除迁移授权账号
        
        功能：
        - 删除mgc_env_access账号
        - 用于卸载或重置时清理
        
        入参：
            db_handler: 数据库处理器
        
        出参：
            True表示成功，False表示失败
        """
        try:
            if not self._account_exists(db_handler):
                logger.debug(f"Account {self.MIGRATION_ACCOUNT_NAME} does not exist, no need to delete")
                return True
            
            drop_sql = f"DROP USER '{self.MIGRATION_ACCOUNT_NAME}'@'%'"
            db_handler.execute_update(drop_sql)
            
            # 刷新权限
            flush_sql = "FLUSH PRIVILEGES"
            db_handler.execute_update(flush_sql)
            
            logger.debug(f"账号{self.MIGRATION_ACCOUNT_NAME}删除成功")
            return True
        except Exception as e:
            error_msg = f"删除迁移授权账号失败: {str(e)}"
            logger.error(error_msg)
            return False
