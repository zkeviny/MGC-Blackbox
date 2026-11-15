"""
迁移授权模块

功能：
- 提供设备迁移授权功能
- 支持迁移密钥管理
- 支持迁移密钥修改
- 支持迁移密钥路径查询

依赖：
- src/core/installer/migration_account_creator.py（迁移账号创建）
- src/core/installer/migrate_key_saver.py（迁移密钥保存）
- src/config/path_config.py（路径配置）
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

from mgc.config.path_config import get_migrate_key_file
from mgc.config.i18n_config import get_exception_message, Messages
from mgc.core.installer.migration_account_creator import MigrationAccountCreator
from mgc.core.installer.migrate_key_saver import MigrateKeySaver


class MigrateServiceError(Exception):
    """迁移授权异常"""
    pass


class MigrateService:
    """迁移授权服务"""

    def __init__(self, database_handler=None):
        """初始化迁移授权服务
        
        入参：
            database_handler: 数据库处理器（可选）
        """
        self.database_handler = database_handler
        self.migrate_key_file = get_migrate_key_file()
        self.migrate_key_saver = MigrateKeySaver()
        self.migration_account_creator = MigrationAccountCreator()

    def authorize_migration(self, migrate_key: str) -> dict:
        """
        设备迁移授权

        功能：
        - 接收迁移密钥
        - 验证迁移密钥是否正确
        - SQLCipher模式：解密获取初始环境密文1

        入参：
            migrate_key: 迁移密钥

        出参：
            dict: 授权结果
            {
                "success": True,
                "message": "迁移授权成功",
                "initial_env_ciphertext_1": str
            }

        异常：
            MigrateServiceError: 授权失败时抛出
        """
        try:
            if not migrate_key:
                raise MigrateServiceError(get_exception_message(Messages.MigrateService, "MIGRATION_KEY_CANNOT_BE_EMPTY"))

            if not self.verify_migrate_key(migrate_key):
                raise MigrateServiceError(get_exception_message(Messages.MigrateService, "MIGRATION_KEY_VERIFICATION_FAILED"))

            # Check if SQLCipher mode
            db_type = None
            if self.database_handler:
                db_type = getattr(self.database_handler, 'database_type', None)
            
            result_data = {"success": True, "message": "Migration authorized"}
            
            # SQLCipher mode: perform migration decryption
            if db_type == "sqlcipher":
                initial_env_ciphertext_1 = self._decrypt_initial_env_ciphertext(migrate_key)
                result_data["initial_env_ciphertext_1"] = initial_env_ciphertext_1
                logger.debug("SQLCipher migration decryption successful")

            return result_data

        except MigrateServiceError:
            raise
        except Exception as e:
            raise MigrateServiceError(get_exception_message(Messages.MigrateService, "DEVICE_MIGRATION_AUTHORIZATION_FAILED"))

    def _decrypt_initial_env_ciphertext(self, migrate_key: str) -> str:
        """
        解密获取初始环境密文1
        
        功能：
        - 生成迁移密钥密文1
        - 拆分迁移虚拟账户和密码
        - 从 mgc_info_1 查询初始环境密文3
        - 首次AES解密得到初始环境密文1
        
        入参：
            migrate_key: 迁移密钥明文
            
        出参：
            str: 初始环境密文1
            
        异常：
            MigrateServiceError: 解密失败时抛出
        """
        try:
            from mgc.domain.crypto_layer.sha256_core import sha256_hash
            from mgc.domain.crypto_layer.credential_generator import aes_decrypt
            
            if not self.database_handler:
                raise MigrateServiceError("数据库处理器未初始化")
            
            # Step 1: generate migration key hash
            migrate_key_hash = sha256_hash(migrate_key)
            
            # Step 2: split migration account and password
            migration_account = migrate_key_hash[:32]
            migration_password = migrate_key_hash[32:]
            
            # Step 3: query initial env ciphertext from mgc_info_1
            query_sql = """SELECT info_plaintext FROM mgc_info_1 
                WHERE diff_1 = 'MIGRATION_DATA' 
                AND extract_account = ? 
                AND extract_password = ?"""
            
            result = self.database_handler.execute_query(
                query_sql, 
                (migration_account, migration_password)
            )
            
            if not result or len(result) == 0:
                raise MigrateServiceError(get_exception_message(Messages.MigrateService, "MIGRATION_KEY_VERIFICATION_FAILED"))
            
            initial_env_ciphertext_3 = result[0]['info_plaintext']
            
            # Step 4: first AES decrypt
            initial_env_ciphertext_1 = aes_decrypt(initial_env_ciphertext_3, migrate_key_hash)
            
            return initial_env_ciphertext_1
            
        except MigrateServiceError:
            raise
        except Exception as e:
            logger.debug(f"Failed to decrypt initial environment cipher: {e}")
            raise MigrateServiceError(get_exception_message(Messages.MigrateService, "DEVICE_MIGRATION_AUTHORIZATION_FAILED"))

    def modify_migrate_key(self, old_migrate_key: str, new_migrate_key: str) -> bool:
        """
        修改迁移密钥

        功能：
        - 验证旧迁移密钥
        - 保存新迁移密钥
        - 更新迁移密钥文件

        入参：
            old_migrate_key: 旧迁移密钥
            new_migrate_key: 新迁移密钥

        出参：
            bool: True表示修改成功，False表示修改失败

        异常：
            MigrateServiceError: 修改失败时抛出
        """
        try:
            if not old_migrate_key or not new_migrate_key:
                raise MigrateServiceError(get_exception_message(Messages.MigrateService, "MIGRATION_KEY_CANNOT_BE_EMPTY"))

            if not self.verify_migrate_key(old_migrate_key):
                raise MigrateServiceError(get_exception_message(Messages.MigrateService, "OLD_MIGRATION_KEY_VERIFICATION_FAILED"))

            self.migrate_key_saver.save_migrate_key(new_migrate_key)

            return True

        except MigrateServiceError:
            raise
        except Exception as e:
            raise MigrateServiceError(get_exception_message(Messages.MigrateService, "MODIFY_MIGRATION_KEY_FAILED"))

    def get_migrate_key_path(self) -> str:
        """
        获取迁移密钥保存路径

        出参：
            str: 迁移密钥保存路径
        """
        return self.migrate_key_file

    def verify_migrate_key(self, migrate_key: str) -> bool:
        """
        验证迁移密钥

        功能：
        - 读取迁移密钥文件
        - 比对迁移密钥
        - 返回验证结果

        入参：
            migrate_key: 迁移密钥

        出参：
            bool: True表示验证通过，False表示验证失败

        异常：
            MigrateServiceError: 验证失败时抛出
        """
        try:
            if not migrate_key:
                return False

            if not os.path.exists(self.migrate_key_file):
                raise MigrateServiceError(get_exception_message(Messages.MigrateService, "MIGRATION_KEY_FILE_DOES_NOT_EXIST"))

            with open(self.migrate_key_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "Migration Key:" in content:
                saved_key = content.split("Migration Key:")[1].strip().split("\n")[0]
            else:
                saved_key = content.strip()

            return saved_key == migrate_key

        except FileNotFoundError:
            raise MigrateServiceError(get_exception_message(Messages.MigrateService, "MIGRATION_KEY_FILE_DOES_NOT_EXIST"))
        except Exception as e:
            raise MigrateServiceError(get_exception_message(Messages.MigrateService, "VERIFY_MIGRATION_KEY_FAILED"))
