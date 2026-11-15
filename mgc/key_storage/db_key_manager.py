"""
DB_KEY.json 密钥管理器

功能：
- 保存加密后的根密钥哈希到 DB_KEY.json
- 读取并解密 DB_KEY.json 获取 AES_KEY_2

存储位置：运行目录/secrets/DB_KEY.json
"""

import os
import json
from typing import Optional

from mgc.domain.crypto_layer.sha256_core import sha256_hash
from mgc.domain.crypto_layer.credential_generator import aes_encrypt, aes_decrypt
from mgc.domain.crypto_layer.hardware_fingerprint import get_hardware_info
from mgc.domain.crypto_layer.root_key_crypto import get_aes_key_1, get_aes_key_2


DB_KEY_FILE = "secrets/DB_KEY.json"


def _get_db_key_file_path() -> str:
    """获取 DB_KEY.json 的绝对路径"""
    from mgc.config.path_config import SECRETS_DIR
    return str(SECRETS_DIR / "DB_KEY.json")


class DBKeyError(Exception):
    """DB_KEY 操作异常"""
    pass


def _ensure_secrets_dir() -> None:
    """确保 secrets 目录存在"""
    db_key_file = _get_db_key_file_path()
    secrets_dir = os.path.dirname(db_key_file)
    if secrets_dir and not os.path.exists(secrets_dir):
        os.makedirs(secrets_dir, exist_ok=True)


def save(personal_key: str, weight_param: str) -> bool:
    """
    保存加密后的根密钥哈希到 DB_KEY.json

    入参：
        personal_key: 个人密钥（如 "TESTKEY123"）
        weight_param: 权重参数（如 "9"）

    出参：
        bool: 保存成功返回 True
    """
    try:
        aes_key_2 = get_aes_key_2(personal_key, weight_param)

        cpu_serial, disk_id, mobo_serial = get_hardware_info()
        aes_key_1 = get_aes_key_1()

        encrypted = aes_encrypt(aes_key_2, aes_key_1)

        _ensure_secrets_dir()

        db_key_file = _get_db_key_file_path()
        data = {
            "encrypted_key": encrypted,
            "version": "1.0"
        }
        with open(db_key_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        raise DBKeyError(f"保存 DB_KEY 失败: {e}")


def load() -> str:
    """
    读取并解密 DB_KEY.json 获取 AES_KEY_2

    出参：
        str: AES_KEY_2（SHA-256(个人密钥+权重参数)）

    异常：
        DBKeyError: 文件不存在或解密失败
    """
    if not exists():
        raise DBKeyError("DB_KEY.json 不存在")

    try:
        db_key_file = _get_db_key_file_path()
        with open(db_key_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        cpu_serial, disk_id, mobo_serial = get_hardware_info()
        aes_key_1 = get_aes_key_1()

        aes_key_2 = aes_decrypt(data["encrypted_key"], aes_key_1)
        return aes_key_2
    except Exception as e:
        raise DBKeyError(f"Failed to decrypt DB_KEY: {e}")


def exists() -> bool:
    """
    检查 DB_KEY.json 是否存在

    出参：
        bool: 存在返回 True
    """
    return os.path.exists(_get_db_key_file_path())