"""
加密解密模块

功能：
- 提供文本加密和解密功能
- 支持单文本和批量文本处理
- 使用SHA-256派生哈希方案，根密钥作为加密密钥
- 生成动态盐，增强安全性

依赖：
- src/domain/crypto_layer/sha256_core.py（SHA-256核心算法）
- src/domain/crypto_layer/dynamic_salt.py（动态盐提取）
- src/domain/crypto_layer/environment_cipher.py（环境密码生成）
- src/domain/crypto_layer/cognition_encrypt.py（认知加密）
- src/config/enum_config.py（枚举配置）
"""

import base64
import json
from typing import Dict, List, Optional

from mgc.domain.crypto_layer.sha256_core import sha256_hash, HashingError
from mgc.domain.crypto_layer.dynamic_salt import extract_dynamic_salts, DynamicSaltError
from mgc.domain.crypto_layer.aes_key_n import encrypt_with_aes_key_n, decrypt_with_aes_key_n, generate_info_hash_cipher
from mgc.config.i18n_config import get_exception_message, Messages


class CryptoError(Exception):
    """加密解密异常"""
    pass


class CryptoService:
    """加密解密服务"""

    def __init__(self, root_key: str, weight_param: int = 1000):
        """
        初始化加密解密服务

        入参：
            root_key: 根密钥
            weight_param: 权重参数，默认1000
        """
        self.root_key = root_key
        self.weight_param = weight_param
        self.dynamic_salts = {}

        try:
            self.dynamic_salts = extract_dynamic_salts(root_key, weight_param)
        except DynamicSaltError as e:
            raise CryptoError(get_exception_message(Messages.CryptoService, "EXTRACT_DYNAMIC_SALT_FAILED"))

    def encrypt_text(self, content: str, info_fields: dict = None) -> str:
        """
        加密单条文本

        功能：
        - 使用 AES_KEY_N 加密（双层加密第一层）
        - 密钥来源：info_fields（信息完整哈希密文）
        - SQLCipher 第二层加密由数据库自动处理

        入参：
            content: 待加密的明文
            info_fields: 信息字段字典（必须包含 info_type/info_owner 等）

        出参：
            str: 加密后的密文

        异常：
            CryptoError: 加密失败时抛出
        """
        try:
            if not content:
                raise CryptoError(get_exception_message(Messages.CryptoService, "ENCRYPTION_CONTENT_CANNOT_BE_EMPTY"))

            if info_fields:
                from mgc.domain.crypto_layer import generate_info_cipher
                key_n = generate_info_cipher(
                    info_type=info_fields.get('info_type', 'DEFAULT'),
                    info_owner=info_fields.get('info_owner', ''),
                    diff_1=info_fields.get('diff_1'),
                    diff_2=info_fields.get('diff_2'),
                    diff_3=info_fields.get('diff_3'),
                    ext_fields=info_fields.get('ext_fields'),
                    environment_cipher=info_fields.get('environment_cipher'),
                    weight_param=info_fields.get('weight_param', self.weight_param),
                    salts=info_fields.get('salts', self.dynamic_salts)
                )
            else:
                key_n = generate_info_hash_cipher(self.root_key)

            cipher = encrypt_with_aes_key_n(content, key_n)
            return cipher

        except Exception as e:
            raise CryptoError(get_exception_message(Messages.CryptoService, "ENCRYPTION_FAILED"))

    def encrypt_batch(self, content_list: List[str]) -> List[str]:
        """
        批量加密文本

        功能：
        - 遍历列表，逐个加密
        - 使用 AES_KEY_N 加密

        入参：
            content_list: 待加密的明文列表

        出参：
            list: 加密后的密文列表

        异常：
            CryptoError: 加密失败时抛出
        """
        try:
            if not content_list:
                raise CryptoError(get_exception_message(Messages.CryptoService, "ENCRYPTION_CONTENT_LIST_CANNOT_BE_EMPTY"))

            key_n = generate_info_hash_cipher(self.root_key)
            ciphers = [encrypt_with_aes_key_n(content, key_n) for content in content_list]
            return ciphers

        except Exception as e:
            raise CryptoError(get_exception_message(Messages.CryptoService, "ENCRYPTION_FAILED"))

    def _validate_factors(self, info_fields: dict) -> list:
        """校验因子完整性，返回缺失的因子列表"""
        if not info_fields:
            return ["info_fields"]
        required = ['environment_cipher', 'weight_param', 'salts']
        missing = [k for k in required if not info_fields.get(k)]
        return missing

    def decrypt_text(self, content: str, info_fields: dict = None) -> str:
        """
        解密单条文本

        功能：
        - 使用 AES_KEY_N 解密（双层解密第一层）
        - 密钥来源：info_fields（信息完整哈希密文）
        - SQLCipher 第二层解密由数据库自动处理

        入参：
            content: 待解密的密文
            info_fields: 信息字段字典

        出参：
            str: 解密后的明文

        异常：
            CryptoError: 解密失败时抛出
        """
        try:
            if not content:
                raise CryptoError(get_exception_message(Messages.CryptoService, "DECRYPTION_CONTENT_CANNOT_BE_EMPTY"))

            if info_fields:
                missing = self._validate_factors(info_fields)
                if missing:
                    raise CryptoError(f"解密因子缺失: {', '.join(missing)}")
                from mgc.domain.crypto_layer import generate_info_cipher
                key_n = generate_info_cipher(
                    info_type=info_fields.get('info_type', 'DEFAULT'),
                    info_owner=info_fields.get('info_owner', ''),
                    diff_1=info_fields.get('diff_1'),
                    diff_2=info_fields.get('diff_2'),
                    diff_3=info_fields.get('diff_3'),
                    ext_fields=info_fields.get('ext_fields'),
                    environment_cipher=info_fields.get('environment_cipher'),
                    weight_param=info_fields.get('weight_param', self.weight_param),
                    salts=info_fields.get('salts', self.dynamic_salts)
                )
            else:
                key_n = generate_info_hash_cipher(self.root_key)

            plaintext = decrypt_with_aes_key_n(content, key_n)
            return plaintext

        except Exception as e:
            raise CryptoError(get_exception_message(Messages.CryptoService, "DECRYPTION_FAILED"))

    def decrypt_batch(self, content_list: List[str]) -> List[str]:
        """
        批量解密文本

        功能：
        - 遍历列表，逐个解密
        - 使用 AES_KEY_N 解密

        入参：
            content_list: 待解密的密文列表

        出参：
            list: 解密后的明文列表

        异常：
            CryptoError: 解密失败时抛出
        """
        try:
            if not content_list:
                raise CryptoError(get_exception_message(Messages.CryptoService, "DECRYPTION_CONTENT_LIST_CANNOT_BE_EMPTY"))

            key_n = generate_info_hash_cipher(self.root_key)
            plains = [decrypt_with_aes_key_n(content, key_n) for content in content_list]
            return plains

        except Exception as e:
            raise CryptoError(get_exception_message(Messages.CryptoService, "DECRYPTION_FAILED"))

    def verify_cipher(self, content: str) -> Dict[str, any]:
        """
        校验密文是否有效

        功能：
        - 检查密文格式
        - 检查是否包含动态盐
        - 验证哈希完整性
        - 返回校验结果

        入参：
            content: 待校验的密文

        出参：
            dict: 校验结果
            {
                "valid": true/false,
                "message": "校验成功/失败原因"
            }

        异常：
            CryptoError: 校验失败时抛出
        """
        try:
            if not content:
                return {"valid": False, "message": "密文为空"}

            cipher_bytes = base64.b64decode(content.encode('utf-8'))
            combined = cipher_bytes.decode('utf-8')

            parts = combined.split(':')
            if len(parts) != 3:
                return {"valid": False, "message": "密文格式错误"}

            content_hash, key_hash, salt_str = parts

            try:
                salt = int(salt_str)
            except ValueError:
                return {"valid": False, "message": "动态盐格式错误"}

            if salt < 1 or salt > 9:
                return {"valid": False, "message": "动态盐值无效"}

            current_key_hash = sha256_hash(self.root_key)
            if key_hash != current_key_hash:
                return {"valid": False, "message": "根密钥不匹配"}

            return {"valid": True, "message": "密文校验成功"}

        except base64.binascii.Error:
            return {"valid": False, "message": "密文Base64解码失败"}
        except HashingError:
            return {"valid": False, "message": "哈希计算失败"}
        except Exception as e:
            return {"valid": False, "message": f"校验失败: {str(e)}"}
