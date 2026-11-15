"""
Root Key Change Service

Two-step commit ensures data consistency.
"""

import logging
from typing import Optional

from mgc.domain.crypto_layer.credential_generator import aes_encrypt
from mgc.domain.crypto_layer.root_key_crypto import (
    _get_aes_key_3,
    decrypt_root_key_data,
    encrypt_weight_param,
    decrypt_weight_param,
    get_aes_key_2
)
from mgc.domain.crypto_layer.sha256_core import sha256_hash
from mgc.key_storage.db_key_manager import save as save_db_key
from mgc.core.database.sqlcipher_handler import SQLCipherHandler
from mgc.domain.logging.operation_log_manager import OperationLogManager
from mgc.config.i18n_config import get_exception_message, Messages
from mgc.config.enum_config import OperationType

logger = logging.getLogger(__name__)


class RootKeyChangeServiceError(Exception):
    """根密钥修改异常"""
    pass


class RootKeyChangeService:
    """根密钥修改服务"""

    def __init__(self, database_handler, crypto_service: Optional[object] = None):
        """
        初始化根密钥修改服务

        入参：
            database_handler: 数据库处理器
            crypto_service: 加密服务（可选，用于更新内存中的密钥信息）
        """
        self.db_handler = database_handler
        self.crypto_service = crypto_service
        self.operation_log_manager = OperationLogManager()

    def verify_old_key(self, personal_key: str, weight_param: str) -> bool:
        """
        验证旧密钥

        验证方式：
        - 当内存中aes_key_2为空时：保留现有逻辑，使用候选密钥连接SQLCipher验证
        - 当内存中aes_key_2不为空时：只需要比对新输入的根密钥用aes_key_2计算后，
          是否与内存中的aes_key_2的哈希值一致即可

        入参：
            personal_key: 原个人密钥
            weight_param: 原权重参数

        出参：
            bool: 验证成功返回 True

        异常：
            RootKeyChangeServiceError: 验证失败时抛出
        """
        try:
            if not personal_key or not weight_param:
                raise RootKeyChangeServiceError(
                    get_exception_message(
                        Messages.RootKeyChangeService,
                        "PERSONAL_KEY_AND_WEIGHT_PARAM_CANNOT_BE_EMPTY"
                    )
                )

            candidate_aes_key_2 = get_aes_key_2(personal_key, weight_param)
            current_aes_key_2 = SQLCipherHandler._aes_key_2

            if current_aes_key_2 is None:
                SQLCipherHandler.set_aes_key_2(candidate_aes_key_2)
                self.db_handler.connect()

                query_sql = "SELECT info_plaintext FROM mgc_info_1 WHERE diff_1 = 'ROOT_KEY'"
                result = self.db_handler.execute_query(query_sql)

                if not result or len(result) == 0:
                    raise RootKeyChangeServiceError(
                        get_exception_message(Messages.RootKeyChangeService, "ROOT_KEY_NOT_FOUND_IN_DATABASE")
                    )

                encrypted_root_key = result[0]["info_plaintext"]
                decrypt_root_key_data(encrypted_root_key, candidate_aes_key_2)

                logger.info("Old key verification successful (full verification mode)")
                return True

            if candidate_aes_key_2 != current_aes_key_2:
                raise RootKeyChangeServiceError(
                    get_exception_message(Messages.RootKeyChangeService, "OLD_KEY_VERIFICATION_FAILED")
                )

            logger.info("Old key verification successful (hash comparison mode)")
            return True

        except RootKeyChangeServiceError:
            self._clear_stale_connection()
            raise
        except Exception as e:
            logger.error(f"Old key verification failed: {e}")
            self._clear_stale_connection()
            raise RootKeyChangeServiceError(
                get_exception_message(Messages.RootKeyChangeService, "ROOT_KEY_AUTHENTICATION_FAILED")
            )

    def _clear_stale_connection(self) -> None:
        """清除线程缓存的数据库连接（验证失败时调用）"""
        if hasattr(self.db_handler, '_thread_local'):
            self.db_handler._thread_local.connection = None

    def change_root_key(
        self,
        old_personal_key: str,
        old_weight_param: str,
        new_personal_key: str,
        new_weight_param: str
    ) -> bool:
        """
        修改根密钥

        流程：
        1. 计算新旧 AES_KEY_2/3
        2. 解密旧的 ROOT_KEY 和 weight_param
        3. 用新 AES_KEY_3 重新加密
        4. 写入数据库（两步提交）
        5. 重建 DB_KEY.json
        6. 更新 SQLCipher 密钥
        7. 记录日志

        入参：
            old_personal_key: 原个人密钥
            old_weight_param: 原权重参数
            new_personal_key: 新个人密钥
            new_weight_param: 新权重参数

        出参：
            bool: 修改成功返回 True

        异常：
            RootKeyChangeServiceError: 修改失败时抛出
        """
        try:
            if not old_personal_key or not old_weight_param:
                raise RootKeyChangeServiceError(
                    get_exception_message(
                        Messages.RootKeyChangeService,
                        "PERSONAL_KEY_AND_WEIGHT_PARAM_CANNOT_BE_EMPTY"
                    )
                )

            if not new_personal_key or not new_weight_param:
                raise RootKeyChangeServiceError(
                    get_exception_message(
                        Messages.RootKeyChangeService,
                        "NEW_PERSONAL_KEY_AND_WEIGHT_PARAM_CANNOT_BE_EMPTY"
                    )
                )

            if old_personal_key == new_personal_key and old_weight_param == new_weight_param:
                raise RootKeyChangeServiceError(
                    get_exception_message(Messages.RootKeyChangeService, "NEW_KEY_CANNOT_BE_SAME_AS_OLD_KEY")
                )

            old_aes_key_2 = get_aes_key_2(old_personal_key, old_weight_param)

            new_aes_key_2 = get_aes_key_2(new_personal_key, new_weight_param)

            encrypted_root_key = self._get_encrypted_root_key_from_db()
            decrypted_root_key = decrypt_root_key_data(encrypted_root_key, old_aes_key_2)

            encrypted_weight_param = self._get_encrypted_weight_param_from_db()
            decrypted_weight_param = decrypt_weight_param(encrypted_weight_param, old_aes_key_2)
            original_weight_param = decrypted_weight_param[0]

            save_db_key(new_personal_key, new_weight_param)

            new_aes_key_3 = _get_aes_key_3(new_aes_key_2)

            migrate_key_hash = sha256_hash("")
            combined_data = (f"{decrypted_root_key['root_key']}|"
                           f"{migrate_key_hash}|"
                           f"{decrypted_root_key['hardware_fingerprint']}")
            new_encrypted_root_key = aes_encrypt(combined_data, new_aes_key_3)

            new_encrypted_weight_param = encrypt_weight_param(
                original_weight_param, new_aes_key_2
            )

            self._update_encrypted_root_key(new_encrypted_root_key)
            self._update_encrypted_weight_param(new_encrypted_weight_param)

            save_db_key(new_personal_key, new_weight_param)

            old_db_key = SQLCipherHandler._get_db_key()

            SQLCipherHandler.set_aes_key_2(new_aes_key_2)

            new_db_key = SQLCipherHandler._get_db_key()

            self.db_handler.temp_key_storage(old_db_key, new_db_key)

            if self.crypto_service:
                self.crypto_service.root_key = new_personal_key + "_" + new_weight_param
                self.crypto_service.weight_param = int(new_weight_param)

            self.operation_log_manager.log_operation(
                operation_type=OperationType.CHANGE_ROOT_KEY,
                key_alias="ROOT_KEY",
                operation_result="SUCCESS"
            )

            logger.info("Root key changed successfully")
            return True

        except RootKeyChangeServiceError:
            self.operation_log_manager.log_operation(
                operation_type=OperationType.CHANGE_ROOT_KEY,
                key_alias="ROOT_KEY",
                operation_result="FAILED"
            )
            raise
        except Exception as e:
            logger.error(f"Root key change failed: {e}")
            self.operation_log_manager.log_operation(
                operation_type=OperationType.CHANGE_ROOT_KEY,
                key_alias="ROOT_KEY",
                operation_result="FAILED"
            )
            raise RootKeyChangeServiceError(
                get_exception_message(Messages.RootKeyChangeService, "ROOT_KEY_CHANGE_FAILED", error=str(e))
            )

    def _get_encrypted_root_key_from_db(self) -> str:
        """
        从数据库读取加密的 ROOT_KEY

        出参：
            str: 加密的 ROOT_KEY 数据

        异常：
            RootKeyChangeServiceError: 读取失败时抛出
        """
        try:
            query_sql = "SELECT info_plaintext FROM mgc_info_1 WHERE diff_1 = 'ROOT_KEY'"
            result = self.db_handler.execute_query(query_sql)

            if not result or len(result) == 0:
                raise RootKeyChangeServiceError(
                    get_exception_message(
                        Messages.RootKeyChangeService,
                        "ROOT_KEY_NOT_FOUND_IN_DATABASE"
                    )
                )

            return result[0]["info_plaintext"]

        except RootKeyChangeServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to get encrypted root key from DB: {e}")
            raise RootKeyChangeServiceError(
                get_exception_message(
                    Messages.RootKeyChangeService,
                    "FAILED_TO_GET_ROOT_KEY_FROM_DB",
                    error=str(e)
                )
            )

    def _get_encrypted_weight_param_from_db(self) -> str:
        """
        从数据库读取加密的 weight_param

        出参：
            str: 加密的 weight_param 数据

        异常：
            RootKeyChangeServiceError: 读取失败时抛出
        """
        try:
            query_sql = "SELECT info_plaintext FROM mgc_info_1 WHERE diff_1 = 'weight_param'"
            result = self.db_handler.execute_query(query_sql)

            if not result or len(result) == 0:
                raise RootKeyChangeServiceError(
                    get_exception_message(Messages.RootKeyChangeService, "WEIGHT_PARAM_NOT_FOUND_IN_DATABASE")
                )

            return result[0]["info_plaintext"]

        except RootKeyChangeServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to get encrypted weight param from DB: {e}")
            raise RootKeyChangeServiceError(
                get_exception_message(Messages.RootKeyChangeService, "FAILED_TO_GET_WEIGHT_PARAM_FROM_DB", error=str(e))
            )

    def _update_encrypted_root_key(self, encrypted_root_key: str) -> bool:
        """
        更新数据库中的加密 ROOT_KEY

        入参：
            encrypted_root_key: 新的加密 ROOT_KEY

        出参：
            bool: 更新成功返回 True

        异常：
            RootKeyChangeServiceError: 更新失败时抛出
        """
        try:
            update_sql = "UPDATE mgc_info_1 SET info_plaintext = ? WHERE diff_1 = 'ROOT_KEY'"
            self.db_handler.execute_update(update_sql, (encrypted_root_key,))
            logger.debug("Encrypted root key updated in database")
            return True

        except Exception as e:
            logger.error(f"Failed to update encrypted root key: {e}")
            raise RootKeyChangeServiceError(
                get_exception_message(
                    Messages.RootKeyChangeService,
                    "FAILED_TO_UPDATE_ROOT_KEY_IN_DB",
                    error=str(e)
                )
            )

    def _update_encrypted_weight_param(self, encrypted_weight_param: str) -> bool:
        """
        更新数据库中的加密 weight_param

        入参：
            encrypted_weight_param: 新的加密 weight_param

        出参：
            bool: 更新成功返回 True

        异常：
            RootKeyChangeServiceError: 更新失败时抛出
        """
        try:
            update_sql = "UPDATE mgc_info_1 SET info_plaintext = ?, extract_password = ? WHERE diff_1 = 'weight_param'"
            self.db_handler.execute_update(
                update_sql,
                (encrypted_weight_param, encrypted_weight_param[:32])
            )
            logger.debug("Encrypted weight param updated in database")
            return True

        except Exception as e:
            logger.error(f"Failed to update encrypted weight param: {e}")
            raise RootKeyChangeServiceError(
                get_exception_message(
                    Messages.RootKeyChangeService,
                    "FAILED_TO_UPDATE_WEIGHT_PARAM_IN_DB",
                    error=str(e)
                )
            )
