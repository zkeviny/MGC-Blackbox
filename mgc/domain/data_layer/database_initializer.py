"""
数据库初始化器

功能：
- 管理数据库初始化
- 创建数据库表结构
- 创建应用用户及权限管理
- 用户信息CRUD
- 日志管理（按日分表、缓存同步）
- 日志清理

安全规范：
- 初始化完成后必须断开高权限连接并清空凭证
- 所有配置从enum_config统一读取

依赖：
- src/config/enum_config.py（枚举配置）
- src/config/database_config.py（数据库配置）
- src/domain/crypto_layer/password_generator.py（密码生成）
"""

import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from mgc.config.enum_config import ConfigDefaults, DatabaseType
from mgc.config.database_config import DatabaseConfig
from mgc.config.path_config import LOG_DIR, DB_DIR

logger = logging.getLogger(__name__)

MGC_USER_1 = "mgc_user_1"


class DatabaseInitializer:
    """数据库初始化器"""

    def __init__(self, database_type: str = None):
        """
        初始化数据库初始化器

        入参：
            database_type: 数据库类型（可选，未提供时从配置读取）
        """
        if database_type is None:
            self.database_type = DatabaseConfig.get_database_type()
        else:
            self.database_type = database_type
        self.connection = None
        from mgc.domain.data_layer.agent_log_manager import (
            AgentLogManager
        )
        self.log_manager = AgentLogManager(self.database_type)

    def _connect_mysql(self, host: str, port: int,
                       user: str, password: str) -> None:
        """连接MySQL数据库"""
        try:
            import pymysql
            self.connection = pymysql.connect(
                host=host, port=port,
                user=user, password=password,
                charset='utf8mb4'
            )
            logger.info(f"MySQL connected: {host}:{port}")
        except Exception as e:
            logger.error(f"MySQL connect failed: {e}")
            raise

    def _disconnect(self) -> None:
        """断开连接并清空凭证"""
        if self.connection:
            self.connection.close()
            self.connection = None
        logger.info("Connection closed, credentials cleared")

    def disconnect(self) -> None:
        """断开数据库连接"""
        self._disconnect()

    def _validate_password(self, password: str) -> bool:
        """
        验证密码格式（防止SQL注入）

        入参：
            password: 密码

        出参：
            是否合法
        """
        if not password:
            return False
        if len(password) < 8 or len(password) > 64:
            return False
        pattern = r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?]+$'
        if not re.match(pattern, password):
            return False
        if "'" in password or '"' in password or "\\" in password:
            return False
        return True

    def initialize_database(
        self, hardware_info: Dict[str, str],
        salts: Dict[str, int],
        mysql_host: str = None, mysql_port: int = None,
        mysql_root_password: str = None
    ) -> str:
        """
        初始化数据库（一次性操作）

        入参：
            hardware_info: 硬件信息字典
            salts: 动态盐字典
            mysql_host: MySQL主机（仅MySQL模式）
            mysql_port: MySQL端口（仅MySQL模式）
            mysql_root_password: MySQL root密码（仅MySQL模式）

        出参：
            mgc_user_1账户密码

        异常：
            Exception: 初始化失败时抛出
        """
        from mgc.domain.crypto_layer.password_generator import (
            generate_mgc_user1_password
        )

        self._connect_mysql(
            mysql_host or "localhost",
            mysql_port or 3306,
            "root",
            mysql_root_password or ""
        )

        cursor = self.connection.cursor()
        mgc_user1_password = None

        try:
            mgc_user1_password = generate_mgc_user1_password(
                cpu_serial=hardware_info["cpu_serial"],
                disk_id=hardware_info["disk_id"],
                salts=salts
            )

            if not self._validate_password(mgc_user1_password):
                raise ValueError("Generated password invalid")

            self._init_mysql_tables(cursor, mgc_user1_password)

            self.connection.commit()
            return mgc_user1_password

        except Exception as e:
            self.connection.rollback()
            logger.error(f"Database init failed: {e}")
            raise e

        finally:
            cursor.close()
            self._disconnect()

    def _init_mysql_tables(self, cursor, mgc_user1_password: str) -> None:
        """初始化MySQL表结构（保留原逻辑）"""
        import pymysql

        database_name = ConfigDefaults.DATABASE_NAME

        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS {database_name} "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute(f"USE {database_name}")
        logger.info(f"Database {database_name} created")

        try:
            cursor.execute(
                f"DROP USER IF EXISTS '{MGC_USER_1}'@'%'"
            )
        except Exception:
            pass

        try:
            cursor.execute(
                f"CREATE USER '{MGC_USER_1}'@'%' "
                f"IDENTIFIED BY %s",
                (mgc_user1_password,)
            )
        except Exception:
            escaped = pymysql.escape_string(mgc_user1_password)
            cursor.execute(
                f"CREATE USER '{MGC_USER_1}'@'%' "
                f"IDENTIFIED BY '{escaped}'"
            )

        cursor.execute(
            f"GRANT SELECT, INSERT ON {database_name}.* "
            f"TO '{MGC_USER_1}'@'%'"
        )
        cursor.execute("FLUSH PRIVILEGES")
        logger.info(f"{MGC_USER_1} account created")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mgc_user_info (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                info_type VARCHAR(50) NOT NULL,
                info_owner VARCHAR(100) NOT NULL,
                extract_account VARCHAR(50) NOT NULL,
                extract_password VARCHAR(100) NOT NULL,
                info_plaintext TEXT NOT NULL,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                diff1 VARCHAR(100) DEFAULT '',
                diff2 VARCHAR(100) DEFAULT '',
                diff3 VARCHAR(100) DEFAULT '',
                ext01 VARCHAR(100) DEFAULT '',
                ext02 VARCHAR(100) DEFAULT '',
                ext03 VARCHAR(100) DEFAULT '',
                ext04 VARCHAR(100) DEFAULT '',
                ext05 VARCHAR(100) DEFAULT '',
                ext06 VARCHAR(100) DEFAULT '',
                ext07 VARCHAR(100) DEFAULT '',
                ext08 VARCHAR(100) DEFAULT '',
                ext09 VARCHAR(100) DEFAULT '',
                ext10 VARCHAR(100) DEFAULT '',
                ext11 VARCHAR(100) DEFAULT '',
                ext12 VARCHAR(100) DEFAULT '',
                ext13 VARCHAR(100) DEFAULT '',
                ext14 VARCHAR(100) DEFAULT '',
                ext15 VARCHAR(100) DEFAULT '',
                ext16 VARCHAR(100) DEFAULT '',
                ext17 VARCHAR(100) DEFAULT '',
                ext18 VARCHAR(100) DEFAULT '',
                ext19 VARCHAR(100) DEFAULT '',
                ext20 VARCHAR(100) DEFAULT '',
                ext21 VARCHAR(100) DEFAULT '',
                ext22 VARCHAR(100) DEFAULT '',
                ext23 VARCHAR(100) DEFAULT '',
                ext24 VARCHAR(100) DEFAULT '',
                ext25 VARCHAR(100) DEFAULT '',
                ext26 VARCHAR(100) DEFAULT '',
                ext27 VARCHAR(100) DEFAULT '',
                ext28 VARCHAR(100) DEFAULT '',
                ext29 VARCHAR(100) DEFAULT '',
                ext30 VARCHAR(100) DEFAULT '',
                INDEX idx_info_type (info_type),
                INDEX idx_info_owner (info_owner),
                INDEX idx_extract_account_password (extract_account, extract_password),
                INDEX idx_diff_fields (info_type, info_owner, diff1, diff2, diff3)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("mgc_user_info table created")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_used_log (
                log_id VARCHAR(32) PRIMARY KEY,
                agent_name VARCHAR(64) NOT NULL,
                agent_uuid VARCHAR(64) NOT NULL,
                operation_type VARCHAR(16) NOT NULL,
                operation_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                item_id VARCHAR(32),
                entry_mark VARCHAR(64),
                operation_result VARCHAR(8) NOT NULL,
                fail_reason VARCHAR(128),
                INDEX idx_agent_uuid (agent_uuid),
                INDEX idx_operation_type (operation_type),
                INDEX idx_operation_time (operation_time),
                INDEX idx_item_id (item_id),
                INDEX idx_operation_result (operation_result)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("agent_used_log table created")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mgc_system_env (
                id INT PRIMARY KEY AUTO_INCREMENT,
                env_factor_cipher TEXT NOT NULL COMMENT 'initial env factor cipher',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='MGC env factor table'
        """)
        logger.info("mgc_system_env table created")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mgc_root_secure (
                id INT PRIMARY KEY AUTO_INCREMENT,
                root_key_cipher TEXT NOT NULL COMMENT 'root key cipher',
                migrate_key_hash VARCHAR(255) NOT NULL COMMENT 'migration key hash',
                hardware_fp VARCHAR(255) COMMENT 'hardware fingerprint',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='MGC root key secure table'
        """)
        logger.info("mgc_root_secure table created")

    def get_log_table_name(self) -> str:
        """获取当日日志表名（委托AgentLogManager）"""
        return self.log_manager.get_log_table_name()

    def create_log_table(self, connection) -> None:
        """创建当日日志表（委托AgentLogManager）"""
        self.log_manager.create_log_table(connection)

    def insert_log(
        self, connection, log_id: str, agent_name: str,
        agent_uuid: str, operation_type: str,
        item_id: str = None, entry_mark: str = None,
        operation_result: str = "SUCCESS",
        fail_reason: str = None
    ) -> None:
        """插入日志（委托AgentLogManager）"""
        self.log_manager.insert_log(
            connection, log_id, agent_name, agent_uuid,
            operation_type, item_id, entry_mark,
            operation_result, fail_reason
        )

    def sync_cached_logs(self, connection) -> int:
        """同步缓存日志（委托AgentLogManager）"""
        return self.log_manager.sync_cached_logs(connection)

    def cleanup_old_logs(self, connection, days: int = 30) -> int:
        """清理旧日志（委托AgentLogManager）"""
        return self.log_manager.cleanup_old_logs(
            connection, days
        )

    def insert_user_info(
        self, connection, info_type: str, info_owner: str,
        extract_account: str, extract_password: str,
        info_plaintext: str
    ) -> int:
        """
        插入用户信息

        入参：
            connection: 数据库连接
            info_type: 信息类型
            info_owner: 信息归属
            extract_account: 提取账户
            extract_password: 提取密码
            info_plaintext: 明文信息

        出参：
            插入的记录ID
        """
        cursor = connection.cursor()

        try:
            sql = """
                INSERT INTO mgc_user_info
                (info_type, info_owner, extract_account,
                 extract_password, info_plaintext)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                info_type, info_owner, extract_account,
                extract_password, info_plaintext
            ))
            connection.commit()
            return cursor.lastrowid

        except Exception as e:
            connection.rollback()
            logger.error(f"User info insert failed: {e}")
            raise e
        finally:
            cursor.close()

    def query_user_info(
        self, connection, extract_account: str,
        extract_password: str
    ) -> Optional[dict]:
        """
        查询用户信息

        入参：
            connection: 数据库连接
            extract_account: 提取账户
            extract_password: 提取密码

        出参：
            用户信息，未找到返回None
        """
        cursor = connection.cursor()

        try:
            import pymysql
            cursor = connection.cursor(
                pymysql.cursors.DictCursor
            )
            sql = """
                SELECT * FROM mgc_user_info
                WHERE extract_account = %s
                AND extract_password = %s
            """
            cursor.execute(sql, (extract_account, extract_password))
            result = cursor.fetchone()

            if result:
                logger.info(
                    f"User info found: {result.get('info_owner')}"
                )
            else:
                logger.warning("User info not found")
            return result

        except Exception as e:
            logger.error(f"User info query failed: {e}")
            raise e
        finally:
            cursor.close()

    def insert_info(
        self, connection, info_type: str, info_owner: str,
        extract_account: str, extract_password: str,
        info_plaintext: str, diff1: str = "", diff2: str = "",
        diff3: str = "", ext_fields: Dict[str, str] = None
    ) -> None:
        """
        插入信息（含扩展字段）

        入参：
            connection: 数据库连接
            info_type: 信息类型
            info_owner: 信息归属
            extract_account: 提取账户名
            extract_password: 提取密码
            info_plaintext: 敏感信息内容
            diff1: 差异1字段
            diff2: 差异2字段
            diff3: 差异3字段
            ext_fields: ext01~ext30字段字典
        """
        cursor = connection.cursor()

        try:
            if ext_fields is None:
                ext_fields = {}

            ext_vals = [
                ext_fields.get(f"ext{i:02d}", "")
                for i in range(1, 31)
            ]

            sql = """
                INSERT INTO mgc_user_info
                (info_type, info_owner, extract_account,
                 extract_password, info_plaintext,
                 diff1, diff2, diff3,
                 ext01, ext02, ext03, ext04, ext05,
                 ext06, ext07, ext08, ext09, ext10,
                 ext11, ext12, ext13, ext14, ext15,
                 ext16, ext17, ext18, ext19, ext20,
                 ext21, ext22, ext23, ext24, ext25,
                 ext26, ext27, ext28, ext29, ext30)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                info_type, info_owner, extract_account,
                extract_password, info_plaintext,
                diff1, diff2, diff3, *ext_vals
            ))

            connection.commit()
            logger.debug(f"Info inserted: {info_type}")  # 脱敏：只记录类型
        except Exception as e:
            connection.rollback()
            logger.error(f"Info insert failed: {e}")
            raise e
        finally:
            cursor.close()

    def query_info(
        self, connection, extract_account: str,
        extract_password: str = ""
    ) -> Optional[dict]:
        """
        查询信息

        入参：
            connection: 数据库连接
            extract_account: 提取账户名
            extract_password: 提取密码（可选）

        出参：
            信息字典，未找到返回None
        """
        cursor = connection.cursor()

        try:
            import pymysql
            cursor = connection.cursor(
                pymysql.cursors.DictCursor
            )
            if extract_password:
                sql = """
                    SELECT * FROM mgc_user_info
                    WHERE extract_account = %s
                    AND extract_password = %s
                """
                cursor.execute(sql, (extract_account, extract_password))
            else:
                sql = """
                    SELECT * FROM mgc_user_info
                    WHERE extract_account = %s
                """
                cursor.execute(sql, (extract_account,))
            result = cursor.fetchone()

            if result:
                logger.debug("Info found")  # 移除账号信息
            else:
                logger.warning("Info not found")
            return result

        except Exception as e:
            logger.error(f"Info query failed: {e}")
            raise e
        finally:
            cursor.close()

    def update_info(
        self, connection, item_id: str,
        item_name: str, item_value: str
    ) -> None:
        """
        更新信息

        入参：
            connection: 数据库连接
            item_id: 条目ID
            item_name: 条目名称
            item_value: 条目值
        """
        cursor = connection.cursor()

        try:
            sql = """
                UPDATE mgc_user_info
                SET info_type = %s, info_plaintext = %s
                WHERE extract_account = %s
            """
            cursor.execute(sql, (item_name, item_value, item_id))

            connection.commit()
            logger.debug(f"Info updated: item_id={item_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Info update failed: {e}")
            raise e
        finally:
            cursor.close()

    def delete_info(self, connection, item_id: str) -> None:
        """
        删除信息

        入参：
            connection: 数据库连接
            item_id: 条目ID
        """
        cursor = connection.cursor()

        try:
            sql = """
                DELETE FROM mgc_user_info
                WHERE extract_account = %s
            """
            cursor.execute(sql, (item_id,))

            connection.commit()
            logger.info(f"Info deleted: item_id={item_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Info delete failed: {e}")
            raise e
        finally:
            cursor.close()
