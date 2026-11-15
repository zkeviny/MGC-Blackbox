"""
SQLCipher 数据库操作层

功能：
- SQLCipher 数据库连接管理
- AES_KYE_2 密钥管理
- 数据库初始化和表创建
- 基本的 CRUD 操作

依赖：
- sqlcipher3（通过 sqlcipher3-wheels 安装）
"""

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mgc.config.path_config import DB_DIR, DB_FILE
from mgc.config.enum_config import DatabaseType
from mgc.domain.crypto_layer.root_key_crypto import get_aes_key_1

logger = logging.getLogger(__name__)

class SQLCipherError(Exception):
    """SQLCipher 操作异常"""
    pass


class SQLCipherHandler:
    """SQLCipher 数据库操作类"""

    _instance: Optional['SQLCipherHandler'] = None
    _connection: Optional[Any] = None
    _aes_key_2: Optional[str] = None
    _thread_local = threading.local()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_aes_key_2(cls, key: str) -> None:
        """
        设置 AES_KYE_2 密钥

        入参：
            key: AES_KYE_2 密钥（数据库密码）

        说明：
            - AES_KYE_2 每次动态计算，不存储
            - 密钥来源于原 mgc_user_1 密码生成规则
        """
        cls._aes_key_2 = key
        logger.debug("AES_KEY_2 key configured")

    @classmethod
    def _get_db_key(cls) -> str:
        """
        计算完整数据库密钥

        根据 protection_mode 决定是否拼接 aes_key_1

        出参：
            数据库密钥字符串
        """
        from mgc.config.user_settings import get_protection_mode

        if cls._aes_key_2 is None:
            raise SQLCipherError("AES_KEY_2 未设置，请先调用 set_aes_key_2()")

        db_key = cls._aes_key_2
        protection_mode = get_protection_mode()

        if protection_mode:
            aes_key_1 = get_aes_key_1()
            db_key = db_key + aes_key_1

        return db_key

    @classmethod
    def initialize(cls, db_path: Optional[str] = None) -> bool:
        """
        初始化 SQLCipher 数据库

        入参：
            db_path: 数据库文件路径，默认使用 DB_FILE

        出参：
            bool: 初始化是否成功

        异常：
            SQLCipherError: 初始化失败时抛出
        """
        # 如果已经初始化过，直接返回
        current_thread = threading.current_thread().ident
        if not hasattr(cls._thread_local, 'connection') or cls._thread_local.connection is None:
            
            try:
                import sqlcipher3

                if db_path is None:
                    db_path = str(DB_FILE)

                db_file = Path(db_path)
                db_file.parent.mkdir(parents=True, exist_ok=True)

                if cls._aes_key_2 is None:
                    raise SQLCipherError("AES_KEY_2 密钥未设置，请先调用 set_aes_key_2()")

                conn = sqlcipher3.connect(db_path)
                conn.execute(f"PRAGMA key = '{cls._get_db_key()}'")
                cls._thread_local.connection = conn
                cls._connection = conn
                
                cls._create_tables_thread_local(conn)

                logger.debug(f"SQLCipher database initialized: {db_path}")
                return True

            except Exception as e:
                logger.error(f"SQLCipher 初始化失败: {e}")
                raise SQLCipherError(f"数据库初始化失败: {e}")
        else:
            logger.debug(f"SQLCipher initialized (thread {current_thread})")
            return True

    @classmethod
    def _create_tables(cls) -> None:
        """
        创建数据库表（已废弃）
        
        说明：
        - 业务表创建由 init_database_tables() 统一管理
        - 此方法仅保留连接功能，不创建业务表
        - 符合多数据库兼容设计原则
        
        注：仍需调用 commit 以确保连接处于稳定状态
        """
        logger.debug("SQLCipher table management unified by init_database_tables()")
        if cls._thread_local.connection:
            cls._thread_local.connection.commit()

    @classmethod
    def _create_tables_thread_local(cls, conn) -> None:
        """
        创建数据库表（线程本地版本）

        说明：
        - 业务表创建由 init_database_tables() 统一管理
        - 此方法用于新连接的场景
        """
        logger.debug("SQLCipher table management unified by init_database_tables()")
        conn.commit()

    @classmethod
    def insert_info(
        cls,
        info_plaintext: str,
        diff_1: Optional[str] = None,
        diff_2: Optional[str] = None,
        diff_3: Optional[str] = None,
        ext_fields: Optional[Dict[str, str]] = None
    ) -> int:
        """
        插入隐私信息

        入参：
            info_plaintext: 信息明文（已 AES_KYE_N 加密）
            diff_1: 差异1
            diff_2: 差异2
            diff_3: 差异3
            ext_fields: 扩展字段字典 {"ext01": "value", ...}

        出参：
            int: 插入记录的 ID

        异常：
            SQLCipherError: 插入失败时抛出
        """
        if cls._connection is None:
            raise SQLCipherError("数据库未初始化，请先调用 initialize()")

        import time
        current_time = int(time.time())

        fields = ["info_plaintext", "diff_1", "diff_2", "diff_3", "created_at", "updated_at"]
        values = [info_plaintext, diff_1, diff_2, diff_3, current_time, current_time]

        if ext_fields:
            for i in range(1, 31):
                key = f"ext{i:02d}"
                if key in ext_fields:
                    fields.append(key)
                    values.append(ext_fields[key])

        placeholders = ", ".join(["?" for _ in values])
        insert_sql = f"INSERT INTO mgc_info_1 ({', '.join(fields)}) VALUES ({placeholders})"

        try:
            cursor = cls._connection.execute(insert_sql, values)
            cls._connection.commit()
            return cursor.lastrowid

        except Exception as e:
            logger.error(f"插入数据失败: {e}")
            raise SQLCipherError(f"插入数据失败: {e}")

    @classmethod
    def query_by_id(cls, record_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 ID 查询记录

        入参：
            record_id: 记录 ID

        出参：
            dict: 记录内容，未找到返回 None

        异常：
            SQLCipherError: 查询失败时抛出
        """
        if cls._connection is None:
            raise SQLCipherError("数据库未初始化，请先调用 initialize()")

        select_sql = "SELECT * FROM mgc_info_1 WHERE id = ?"

        try:
            cursor = cls._connection.execute(select_sql, (record_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

        except Exception as e:
            logger.error(f"查询数据失败: {e}")
            raise SQLCipherError(f"查询数据失败: {e}")

    @classmethod
    def query_all(cls, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        查询所有记录

        入参：
            limit: 限制返回数量
            offset: 偏移量

        出参：
            list: 记录列表

        异常：
            SQLCipherError: 查询失败时抛出
        """
        if cls._connection is None:
            raise SQLCipherError("数据库未初始化，请先调用 initialize()")

        select_sql = "SELECT * FROM mgc_info_1 LIMIT ? OFFSET ?"

        try:
            cursor = cls._connection.execute(select_sql, (limit, offset))
            rows = cursor.fetchall()

            if not rows:
                return []

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"查询数据失败: {e}")
            raise SQLCipherError(f"查询数据失败: {e}")

    @classmethod
    def update_info(
        cls,
        record_id: int,
        info_plaintext: Optional[str] = None,
        diff_1: Optional[str] = None,
        diff_2: Optional[str] = None,
        diff_3: Optional[str] = None,
        ext_fields: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        更新记录

        入参：
            record_id: 记录 ID
            info_plaintext: 信息明文
            diff_1: 差异1
            diff_2: 差异2
            diff_3: 差异3
            ext_fields: 扩展字段字典

        出参：
            bool: 是否更新成功

        异常：
            SQLCipherError: 更新失败时抛出
        """
        if cls._connection is None:
            raise SQLCipherError("数据库未初始化，请先调用 initialize()")

        import time
        current_time = int(time.time())

        update_fields = ["updated_at = ?"]
        values = [current_time]

        if info_plaintext is not None:
            update_fields.append("info_plaintext = ?")
            values.append(info_plaintext)

        if diff_1 is not None:
            update_fields.append("diff_1 = ?")
            values.append(diff_1)

        if diff_2 is not None:
            update_fields.append("diff_2 = ?")
            values.append(diff_2)

        if diff_3 is not None:
            update_fields.append("diff_3 = ?")
            values.append(diff_3)

        if ext_fields:
            for key, value in ext_fields.items():
                if key in [f"ext{i:02d}" for i in range(1, 31)]:
                    update_fields.append(f"{key} = ?")
                    values.append(value)

        values.append(record_id)

        update_sql = f"UPDATE mgc_info_1 SET {', '.join(update_fields)} WHERE id = ?"

        try:
            cursor = cls._connection.execute(update_sql, values)
            cls._connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"更新数据失败: {e}")
            raise SQLCipherError(f"更新数据失败: {e}")

    @classmethod
    def delete_by_id(cls, record_id: int) -> bool:
        """
        删除记录

        入参：
            record_id: 记录 ID

        出参：
            bool: 是否删除成功

        异常：
            SQLCipherError: 删除失败时抛出
        """
        if cls._connection is None:
            raise SQLCipherError("数据库未初始化，请先调用 initialize()")

        delete_sql = "DELETE FROM mgc_info_1 WHERE id = ?"

        try:
            cursor = cls._connection.execute(delete_sql, (record_id,))
            cls._connection.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"删除数据失败: {e}")
            raise SQLCipherError(f"删除数据失败: {e}")

    @classmethod
    def close(cls) -> None:
        """关闭数据库连接"""
        if hasattr(cls._thread_local, 'connection') and cls._thread_local.connection:
            cls._thread_local.connection.close()
            cls._thread_local.connection = None
            logger.debug("SQLCipher database connection closed")

    @classmethod
    def get_connection(cls) -> Optional[Any]:
        """
        获取数据库连接

        出参：
            connection: 数据库连接对象（线程本地）
        """
        return cls._thread_local.connection

    @classmethod
    def insert_with_credentials(
        cls,
        extract_account: str,
        extract_password: str,
        info_plaintext: Optional[str] = None,
        diff_1: Optional[str] = None,
        diff_2: Optional[str] = None,
        diff_3: Optional[str] = None,
        ext_fields: Optional[Dict[str, str]] = None
    ) -> int:
        """
        插入带凭证的记录（用于单表模式）

        入参：
            extract_account: 虚拟账户（派生凭证）
            extract_password: 虚拟密码（派生凭证）
            info_plaintext: 信息明文（已 AES_KYE_N 加密）
            diff_1: 差异1
            diff_2: 差异2
            diff_3: 差异3
            ext_fields: 扩展字段字典

        出参：
            int: 插入记录的 ID
        """
        if cls._connection is None:
            raise SQLCipherError("数据库未初始化，请先调用 initialize()")

        import time
        current_time = int(time.time())

        fields = ["extract_account", "extract_password", "info_plaintext", 
                  "diff_1", "diff_2", "diff_3", "created_at", "updated_at"]
        values = [extract_account, extract_password, info_plaintext, 
                  diff_1, diff_2, diff_3, current_time, current_time]

        if ext_fields:
            for i in range(1, 31):
                key = f"ext{i:02d}"
                if key in ext_fields:
                    fields.append(key)
                    values.append(ext_fields[key])

        placeholders = ", ".join(["?" for _ in values])
        insert_sql = f"INSERT INTO mgc_info_1 ({', '.join(fields)}) VALUES ({placeholders})"

        try:
            cursor = cls._connection.execute(insert_sql, values)
            cls._connection.commit()
            logger.debug(f"Record inserted, ID: {cursor.lastrowid}")
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"插入数据失败: {e}")
            raise SQLCipherError(f"插入数据失败: {e}")

    @classmethod
    def query_by_credentials(
        cls,
        extract_account: str,
        extract_password: str
    ) -> Optional[Dict[str, Any]]:
        """
        通过虚拟凭证查询记录（用于单表模式）

        入参：
            extract_account: 虚拟账户
            extract_password: 虚拟密码

        出参：
            dict: 记录内容，未找到返回 None
        """
        if cls._connection is None:
            raise SQLCipherError("数据库未初始化，请先调用 initialize()")

        select_sql = "SELECT * FROM mgc_info_1 WHERE extract_account = ? AND extract_password = ?"

        try:
            cursor = cls._connection.execute(select_sql, (extract_account, extract_password))
            row = cursor.fetchone()

            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

        except Exception as e:
            logger.error(f"查询数据失败: {e}")
            raise SQLCipherError(f"查询数据失败: {e}")