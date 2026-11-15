r"""
根密钥硬件加密存储模块

用途：
- 将根密钥经硬件指纹加密后存入mgc_root_secure表
- 不对外暴露、不传输、不明文落地
- 存储迁移密钥的哈希值，不存储明文迁移密钥
- 复用优先级12的SHA-256核心模块

参考文档：
- document/1.0细节需求文档/迁移密钥+根密钥处理方案.md

限制条件：
- 必须使用src/config/path_config.py中定义的相对路径
- 所有IO操作必须捕获异常
- 根密钥经硬件指纹加密存储，不对外暴露、不传输、不明文落地
- 迁移密钥仅在创建mgc_env_access账号时进入内存，使用后立即清空
- 迁移密钥不参与加密过程
"""

import logging
import os
import sys
from typing import Optional, Dict

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from mgc.domain.crypto_layer.hardware_fingerprint import get_hardware_fingerprint
from mgc.domain.crypto_layer.sha256_core import sha256_hash
from mgc.domain.crypto_layer.credential_generator import aes_encrypt, aes_decrypt
from mgc.domain.crypto_layer.root_key_crypto import _get_aes_key_3, get_aes_key_2
from mgc.config.i18n_config import get_exception_message, Messages

logger = logging.getLogger(__name__)


class RootKeyEncryptorError(Exception):
    """根密钥加密异常"""
    pass


class RootKeyEncryptor:
    """根密钥硬件加密存储类"""
    
    def __init__(self):
        """初始化根密钥加密类"""
        pass
    
    def encrypt_root_key(self, root_key: str, hardware_fingerprint: str) -> str:
        """
        使用硬件指纹加密根密钥
        
        功能：
        - 使用硬件指纹对根密钥进行加密
        - 生成加密后的根密钥
        
        入参：
            root_key: 根密钥
            hardware_fingerprint: 硬件指纹
        
        出参：
            加密后的根密钥（SHA-256哈希值）
        
        异常：
            RootKeyEncryptorError: 加密失败时抛出
        """
        try:
            if not root_key or not hardware_fingerprint:
                raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ROOT_KEY_AND_HARDWARE_FINGERPRINT_CANNOT_BE_EMPTY"))
            
            # 使用硬件指纹加密根密钥
            root_key_cipher = sha256_hash(f"{root_key}_{hardware_fingerprint}")
            
            logger.debug("Root key encrypted successfully")
            return root_key_cipher
        except Exception as e:
            error_msg = f"Root key encryption failed: {str(e)}"
            logger.error(error_msg)
            raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ROOT_KEY_ENCRYPTION_FAILED", error=str(e)))
    
    def hash_migrate_key(self, migrate_key: str) -> str:
        """
        计算迁移密钥的哈希值
        
        功能：
        - 计算迁移密钥的SHA-256哈希值
        - 用于验证迁移密钥，不存储明文迁移密钥
        
        入参：
            migrate_key: 迁移密钥
        
        出参：
            迁移密钥的哈希值
        
        异常：
            RootKeyEncryptorError: 哈希计算失败时抛出
        """
        try:
            if not migrate_key:
                raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "MIGRATE_KEY_CANNOT_BE_EMPTY"))
            
            # 计算迁移密钥的哈希值
            migrate_key_hash = sha256_hash(migrate_key)
            
            logger.debug("Migrate key hash calculated successfully")
            return migrate_key_hash
        except Exception as e:
            error_msg = f"Migrate key hash calculation failed: {str(e)}"
            logger.error(error_msg)
            raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "MIGRATE_KEY_HASH_CALCULATION_FAILED", error=str(e)))
    
    def store_root_key_to_db(self, root_key_cipher: str, migrate_key_hash: str, 
                             hardware_fingerprint: str, db_handler,
                             root_key: str = None) -> bool:
        """
        存储根密钥到数据库
        
        功能：
        - 单表模式 (SINGLE_INFO_UNIT=True): 存入 mgc_info_1 表
        - 多表模式: 存入 mgc_root_secure 表
        
        入参：
            root_key_cipher: 加密后的根密钥
            migrate_key_hash: 迁移密钥的哈希值
            hardware_fingerprint: 硬件指纹
            db_handler: 数据库处理器
        
        出参：
            True表示成功，False表示失败
        
        异常：
            RootKeyEncryptorError: 存储失败时抛出
        """
        try:
            db_type = getattr(db_handler, 'database_type', 'mysql')
            from mgc.config.database_config import DatabaseConfig as DC
            from mgc.config.enum_config import ConfigItem, ConfigDefaults
            config_dict = DC.get_config()
            single_info_unit = config_dict.get(ConfigItem.SINGLE_INFO_UNIT, ConfigDefaults.SINGLE_INFO_UNIT)
            
            if single_info_unit:
                check_sql = "SELECT COUNT(*) as count FROM mgc_info_1 WHERE diff_1 = 'ROOT_KEY'"
                result = db_handler.execute_query(check_sql)
                
                if result and result[0]['count'] > 0:
                    raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "MGC_ROOT_SECURE_TABLE_ALREADY_HAS_DATA"))
                
                insert_sql = """
                INSERT INTO mgc_info_1 (
                    extract_account,
                    extract_password,
                    info_plaintext,
                    info_type,
                    info_owner,
                    diff_1
                ) VALUES (?, ?, ?, ?, ?, 'ROOT_KEY')
                """
                if db_type == "sqlcipher":
                    combined_data = f"{root_key}|{migrate_key_hash}|{hardware_fingerprint}"
                    if root_key and "_" in root_key:
                        parts = root_key.strip().split("_")
                        personal_key = parts[0]
                        weight_param = parts[1] if len(parts) > 1 else "1"
                        aes_key_2 = get_aes_key_2(personal_key, weight_param)
                        aes_key_3 = _get_aes_key_3(aes_key_2)
                        combined_data = aes_encrypt(combined_data, aes_key_3)
                else:
                    combined_data = f"{root_key_cipher}|{migrate_key_hash}|{hardware_fingerprint}"
                params = (
                    "root_key_account",
                    hardware_fingerprint[:32],
                    combined_data,
                    "SYSTEM",
                    "SYSTEM",
                )
            else:
                db_type = getattr(db_handler, 'database_type', 'mysql')
                
                check_sql = "SELECT COUNT(*) as count FROM mgc_root_secure"
                result = db_handler.execute_query(check_sql)
                
                if result and result[0]['count'] > 0:
                    raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "MGC_ROOT_SECURE_TABLE_ALREADY_HAS_DATA"))
                
                if db_type == "sqlcipher":
                    insert_sql = """
                    INSERT INTO mgc_root_secure (
                        root_key_cipher,
                        migrate_key_hash,
                        hardware_fp,
                        created_at
                    ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """
                else:
                    insert_sql = """
                    INSERT INTO mgc_root_secure (
                        id,
                        root_key_cipher,
                        migrate_key_hash,
                        hardware_fp,
                        created_at
                    ) VALUES (GEN_ID(GEN_MGC_ID, 1), %s, %s, %s, CURRENT_TIMESTAMP)
                    """
                
                params = (
                    root_key_cipher,
                    migrate_key_hash,
                    hardware_fingerprint
                )
            
            db_handler.execute_update(insert_sql, params)
            
            logger.debug("Root key stored successfully")
            return True
        except Exception as e:
            error_msg = f"Root key storage failed: {str(e)}"
            logger.error(error_msg)
            raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ROOT_KEY_STORAGE_FAILED", error=str(e)))
    
    def encrypt_and_store_root_key(self, root_key: str, migrate_key: str, 
                                   hardware_fingerprint: str, db_handler) -> Dict[str, str]:
        """
        加密并存储根密钥（完整流程）
        
        功能：
        - 使用硬件指纹加密根密钥
        - 计算迁移密钥的哈希值
        - 存储到mgc_root_secure表
        
        入参：
            root_key: 根密钥
            migrate_key: 迁移密钥
            hardware_fingerprint: 硬件指纹
            db_handler: 数据库处理器
        
        出参：
            加密后的数据字典
            {
                "root_key_cipher": str,
                "migrate_key_hash": str,
                "hardware_fingerprint": str
            }
        
        异常：
            RootKeyEncryptorError: 加密或存储失败时抛出
        """
        try:
            # 加密根密钥
            root_key_cipher = self.encrypt_root_key(root_key, hardware_fingerprint)
            
            # 计算迁移密钥的哈希值
            migrate_key_hash = self.hash_migrate_key(migrate_key)
            
            # 存储到数据库（SQLCipher模式传递明文，其他模式传递密文）
            db_type = getattr(db_handler, 'database_type', 'mysql')
            self.store_root_key_to_db(root_key_cipher, migrate_key_hash, 
                                     hardware_fingerprint, db_handler, root_key)
            
            return {
                "root_key_cipher": root_key_cipher,
                "migrate_key_hash": migrate_key_hash,
                "hardware_fingerprint": hardware_fingerprint
            }
        except Exception as e:
            error_msg = f"Encrypt and store root key failed: {str(e)}"
            logger.error(error_msg)
            raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ENCRYPT_AND_STORE_ROOT_KEY_FAILED", error=str(e)))
    
    def verify_root_key(self, root_key: str, db_handler) -> bool:
        """
        验证根密钥
        
        功能：
        - 使用当前硬件指纹加密输入的根密钥
        - 与数据库中存储的根密钥进行比对
        - 用于启动时的根密钥验证
        
        入参：
            root_key: 根密钥
            db_handler: 数据库处理器
        
        出参：
            True表示验证成功，False表示验证失败
        
        异常：
            RootKeyEncryptorError: 验证失败时抛出
        """
        try:
            # 获取当前硬件指纹
            current_hardware_fp = get_hardware_fingerprint()
            
            # 从数据库获取存储的根密钥
            query_sql = "SELECT root_key_cipher, hardware_fp FROM mgc_root_secure LIMIT 1"
            result = db_handler.execute_query(query_sql)
            
            if not result or len(result) == 0:
                raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ROOT_KEY_NOT_FOUND_IN_DATABASE"))
            
            stored_data = result[0]
            stored_root_key_cipher = stored_data['root_key_cipher']
            stored_hardware_fp = stored_data['hardware_fp']
            
            # 验证硬件指纹是否一致
            if current_hardware_fp != stored_hardware_fp:
                logger.warning("Hardware fingerprint mismatch, hardware may have changed")
                return False
            
            # 使用存储的硬件指纹加密输入的根密钥
            input_root_key_cipher = sha256_hash(f"{root_key}_{stored_hardware_fp}")
            
            # 比对加密后的根密钥
            is_valid = input_root_key_cipher == stored_root_key_cipher
            
            if is_valid:
                logger.debug("Root key verified successfully")
            else:
                logger.debug("Root key verification failed")
            
            return is_valid
        except Exception as e:
            error_msg = f"Root key verification failed: {str(e)}"
            logger.error(error_msg)
            raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ROOT_KEY_VERIFICATION_FAILED", error=str(e)))
    
    def verify_migrate_key(self, migrate_key: str, db_handler) -> bool:
        """
        验证迁移密钥
        
        功能：
        - 计算输入的迁移密钥的哈希值
        - 与数据库中存储的迁移密钥哈希值进行比对
        - 用于迁移时的迁移密钥验证
        
        入参：
            migrate_key: 迁移密钥
            db_handler: 数据库处理器
        
        出参：
            True表示验证成功，False表示验证失败
        
        异常：
            RootKeyEncryptorError: 验证失败时抛出
        """
        try:
            input_migrate_key_hash = sha256_hash(migrate_key)
            
            # 从数据库获取存储的迁移密钥哈希值
            query_sql = "SELECT migrate_key_hash FROM mgc_root_secure LIMIT 1"
            result = db_handler.execute_query(query_sql)
            
            if not result or len(result) == 0:
                raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "MIGRATE_KEY_HASH_NOT_FOUND_IN_DATABASE"))
            
            stored_migrate_key_hash = result[0]['migrate_key_hash']
            
            # 比对迁移密钥哈希值
            is_valid = input_migrate_key_hash == stored_migrate_key_hash
            
            if is_valid:
                logger.debug("Migrate key verified successfully")
            else:
                logger.debug("Migration key verification failed")
            
            return is_valid
        except Exception as e:
            error_msg = f"Migrate key verification failed: {str(e)}"
            logger.error(error_msg)
            raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "MIGRATE_KEY_VERIFICATION_FAILED", error=str(e)))
    
    def retrieve_root_key(self, root_key: str, db_handler) -> Dict[str, str]:
        """
        检索根密钥
        
        功能：
        - 验证输入的根密钥是否正确
        - 如果正确，返回解析后的个人密钥和权重参数
        - 用于日常账号生成时提取动态盐
        
        入参：
            root_key: 根密钥（格式：个人密钥_权重参数）
            db_handler: 数据库处理器
        
        出参：
            {
                "personal_key": str,
                "weight_param": str
            }
        
        异常：
            RootKeyEncryptorError: 检索失败时抛出
        """
        try:
            # 先验证根密钥
            is_valid = self.verify_root_key(root_key, db_handler)
            if not is_valid:
                raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ROOT_KEY_VERIFICATION_FAILED_RETRIEVE"))
            
            # 解析根密钥（格式：个人密钥_权重参数）
            parts = root_key.strip().split('_')
            if len(parts) != 2:
                raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ROOT_KEY_FORMAT_ERROR_PERSONAL_KEY_WEIGHT_PARAM"))
            
            personal_key = parts[0]
            weight_param = parts[1]
            
            logger.debug("Root key retrieved successfully")
            return {
                "personal_key": personal_key,
                "weight_param": weight_param
            }
        except Exception as e:
            error_msg = f"Root key retrieval failed: {str(e)}"
            logger.error(error_msg)
            raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ROOT_KEY_RETRIEVAL_FAILED", error=str(e)))

    def decrypt_root_key_from_db(self, encrypted_data: str, aes_key_2: str) -> Dict[str, str]:
        """
        从数据库解密根密钥

        功能：
        - 使用 AES_KEY_3 解密存储的组合数据
        - 返回解密后的明文根密钥

        入参：
            encrypted_data: 加密后的字符串
            aes_key_2: AES_KEY_2 (SHA-256(个人密钥+权重参数))

        出参：
            {
                "root_key": str,
                "migrate_key_hash": str,
                "hardware_fingerprint": str
            }

        异常：
            RootKeyEncryptorError: 解密失败时抛出
        """
        try:
            from mgc.domain.crypto_layer.root_key_crypto import decrypt_root_key_data
            return decrypt_root_key_data(encrypted_data, aes_key_2)
        except Exception as e:
            error_msg = f"Root key decryption failed: {str(e)}"
            logger.error(error_msg)
            raise RootKeyEncryptorError(get_exception_message(Messages.RootKeyEncryptor, "ROOT_KEY_DECRYPTION_FAILED", error=str(e)))
