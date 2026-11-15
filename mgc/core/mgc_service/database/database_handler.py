"""
数据库操作模块

功能：
- 管理数据库连接（支持Firebird/MySQL双驱动）
- 提供统一的数据库操作接口
- 支持敏感信息托管、AI服务商管理、操作日志记录
- 执行数据库表初始化脚本
- 内部自动处理SQL方言差异

依赖：
- pymysql（MySQL连接器）
- fdb（Firebird连接器）
- src/config/path_config.py（路径配置）
- src/config/database_config.py（数据库配置）
"""

import re
import threading
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from mgc.config.database_config import (
    DatabaseConfig, DatabaseConfigError
)
from mgc.config.database_config import DatabaseConfig as DC
from mgc.config.enum_config import DatabaseType
from mgc.config.i18n_config import get_exception_message, Messages

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """数据库异常"""
    pass


class DatabaseHandler:
    """数据库处理器（支持Firebird/MySQL双驱动）"""

    _thread_local = threading.local()

    def __init__(self, host: Optional[str] = None,
                 port: Optional[int] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 database: Optional[str] = None):
        """
        初始化数据库处理器

        入参：
            host: 数据库主机（可选，未提供时从配置读取）
            port: 数据库端口（可选，未提供时从配置读取）
            user: 数据库用户名（可选，未提供时从配置读取）
            password: 数据库密码（可选，未提供时从配置读取）
            database: 数据库名称（可选，未提供时从配置读取）
        """
        try:
            config = DatabaseConfig.get_config()
            self.database_type = config.get("database_type", "firebird")
            self.connection = None
            self._lock = threading.Lock()

            self.host = host
            self.port = port
            self.user = user
            self.password = password
            self.database = database

            if self.database_type == "firebird":
                fb_cfg = config.get("firebird", {})
                self.db_file = fb_cfg.get("db_file", "")
                self.charset = fb_cfg.get("charset", "UTF8")
            elif self.database_type == "mysql":
                self.host = (
                    host if host is not None
                    else config["mysql"]["host"]
                )
                self.port = (
                    port if port is not None
                    else config["mysql"]["port"]
                )
                self.user = (
                    user if user is not None
                    else config["mysql"]["user"]
                )
                self.password = (
                    password if password is not None
                    else config["mysql"]["password"]
                )
                self.database = (
                    database if database is not None
                    else config["mysql"]["database"]
                )
            else:
                self._sqlcipher_config = config.get("sqlcipher", {})

        except DatabaseConfigError:
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "READ_DATABASE_CONFIG_FAILED"
                )
            )

    def connect(self) -> bool:
        """
        连接数据库

        出参：
            bool: True表示连接成功

        异常：
            DatabaseError: 连接失败时抛出
        """
        try:
            if self.database_type == "firebird":
                self._connect_firebird()
            elif self.database_type == "mysql":
                self._connect_mysql()
            elif self.database_type == "sqlcipher":
                self._connect_sqlcipher()
            return True
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "CONNECT_DATABASE_FAILED"
                )
            )

    def _connect_firebird(self) -> None:
        """连接Firebird Embedded数据库"""
        try:
            from mgc.config.database_config import FirebirdLoader
            FirebirdLoader.initialize()

            import fdb as _fdb
            db_path = Path(self.db_file)
            db_path.parent.mkdir(exist_ok=True, parents=True)

            if not db_path.exists():
                self._create_firebird_db(db_path)

            self.connection = _fdb.connect(
                database=str(db_path),
                user=DatabaseConfig.FIREBIRD_SYSDBA_USER,
                password=DatabaseConfig.FIREBIRD_SYSDBA_PASSWORD,
                charset=self.charset
            )
            logger.info(
                f"Firebird connected: {self.db_file}"
            )
        except Exception as e:
            logger.error(f"Firebird connect failed: {e}")
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "FIREBIRD_CONNECT_FAILED"
                ).format(error=str(e))
            )

    def _create_firebird_db(self, db_path: Path) -> None:
        """
        创建Firebird数据库文件

        入参：
            db_path: 数据库文件路径
        """
        try:
            import fdb as _fdb
            self.connection = _fdb.create_database(
                database=str(db_path),
                user=DatabaseConfig.FIREBIRD_SYSDBA_USER,
                password=DatabaseConfig.FIREBIRD_SYSDBA_PASSWORD,
                charset=self.charset
            )
            self.connection.close()
            self.connection = None
            logger.info(f"Firebird database created: {db_path}")
        except Exception as e:
            logger.error(f"Firebird create failed: {e}")
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "FIREBIRD_INIT_FAILED"
                ).format(error=str(e))
            )

    def _connect_mysql(self) -> None:
        """连接MySQL数据库"""
        try:
            import pymysql
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            logger.info(
                f"MySQL connected: {self.host}:{self.port}"
            )
        except Exception as e:
            logger.error(f"MySQL connect failed: {e}")
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "CONNECT_DATABASE_FAILED"
                )
            )

    def _connect_sqlcipher(self) -> None:
        """连接SQLCipher数据库"""
        try:
            from mgc.core.database.sqlcipher_handler import SQLCipherHandler
            SQLCipherHandler.initialize()
            conn = SQLCipherHandler.get_connection()
            self._thread_local.connection = conn
            logger.info("SQLCipher connected")
        except Exception as e:
            logger.error(f"SQLCipher connect failed: {e}")
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "CONNECT_DATABASE_FAILED"
                )
            )

    def disconnect(self) -> bool:
        """
        断开数据库连接

        出参：
            bool: True表示断开成功
        """
        try:
            if self.connection:
                self.connection.close()
                self.connection = None
                return True
            return False
        except Exception:
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "DISCONNECT_DATABASE_FAILED"
                )
            )

    def _convert_sql(self, sql: str) -> str:
        """
        SQL方言转换（MySQL → Firebird）

        入参：
            sql: MySQL语法SQL

        出参：
            str: 转换后的SQL
        """
        if self.database_type != "firebird":
            return sql

        converted = sql
        converted = re.sub(
            r'\bAUTO_INCREMENT\b', '', converted
        )
        converted = re.sub(
            r'\bMEDIUMTEXT\b', 'BLOB SUB_TYPE TEXT', converted
        )
        converted = re.sub(
            r'\bDATETIME\b', 'TIMESTAMP', converted
        )
        converted = re.sub(
            r'\bNOW\(\)', 'CURRENT_TIMESTAMP', converted
        )
        converted = re.sub(
            r'\bIFNULL\(', 'COALESCE(', converted
        )
        converted = re.sub(
            r'\bINT\b(?!\s*\()', 'INTEGER', converted
        )
        converted = re.sub(
            r'\bLAST_INSERT_ID\(\)',
            'GEN_ID(GEN_MGC_ID, 1)', converted
        )
        converted = re.sub(
            r"COMMENT\s+'[^']*'", '', converted
        )
        converted = re.sub(
            r'\bENGINE\s*=\s*\w+', '', converted
        )
        converted = re.sub(
            r'\bDEFAULT\s+CHARSET\s*=\s*\w+', '', converted
        )
        converted = re.sub(
            r'\bCOLLATE\s+\w+', '', converted
        )
        converted = re.sub(
            r'\bON\s+UPDATE\s+CURRENT_TIMESTAMP\b', '', converted
        )
        converted = re.sub(
            r'\bUNSIGNED\b', '', converted
        )
        converted = re.sub(
            r'\bBOOL(EAN)?\b', 'SMALLINT', converted
        )
        converted = re.sub(
            r'`([^`]+)`', r'\1', converted
        )
        converted = re.sub(
            r'\bCOUNT\(\*\)\s+[Aa][Ss]\s+\w+',
            'COUNT(*)',
            converted
        )
        converted = re.sub(
            r'(\w+)\$(\w+)',
            r'"\1$\2"',
            converted
        )
        converted = converted.replace('%s', '?')
        return converted

    def execute_query(
        self, query: str, params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        执行查询语句

        入参：
            query: SQL查询语句
            params: 查询参数

        出参：
            list: 查询结果列表

        异常：
            DatabaseError: 查询失败时抛出
        """
        try:
            with self._lock:
                conn = self._get_thread_connection()
                if not conn:
                    raise DatabaseError(
                        get_exception_message(
                            Messages.DatabaseHandler,
                            "DATABASE_NOT_CONNECTED"
                        )
                    )

                converted = self._convert_sql(query)
                cursor = conn.cursor()

                if self.database_type == "firebird":
                    cursor.execute(converted, params or ())
                    columns = [
                        desc[0].lower()
                        for desc in cursor.description
                    ]
                    rows = cursor.fetchall()
                    result = []
                    for row in rows:
                        row_dict = {}
                        for col, val in zip(columns, row):
                            if hasattr(val, 'read'):
                                val = val.read()
                            row_dict[col] = val
                        result.append(row_dict)
                elif self.database_type == "sqlcipher":
                    cursor.execute(converted, params or ())
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    result = []
                    for row in rows:
                        row_dict = {}
                        for col, val in zip(columns, row):
                            row_dict[col] = val
                        result.append(row_dict)
                else:
                    cursor = conn.cursor(
                        dictionary=True
                    )
                    cursor.execute(converted, params or ())
                    result = cursor.fetchall()

                cursor.close()
                return result

        except DatabaseError:
            raise
        except Exception:
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "EXECUTE_QUERY_FAILED"
                )
            )

    def _get_thread_connection(self):
        """获取当前线程的数据库连接（SQLCipher线程安全支持）"""
        if self.database_type != DatabaseType.SQLCIPHER.value:
            return self.connection

        current_thread = threading.current_thread().ident
        existing_conn = getattr(self._thread_local, 'connection', None)

        import sqlcipher3
        from mgc.core.database.sqlcipher_handler import SQLCipherHandler
        from mgc.config.path_config import DB_FILE
        db_path = str(DB_FILE)
        aes_key = SQLCipherHandler._get_db_key()

        if existing_conn is not None:
            try:
                existing_conn.close()
            except Exception:
                pass

        self._thread_local.connection = sqlcipher3.connect(db_path)
        self._thread_local.connection.execute(f"PRAGMA key = '{aes_key}'")

        return self._thread_local.connection

    def temp_key_storage(self, old_key: str, new_key: str) -> bool:
        """
        临时密钥存储

        职责：
        - 临时存储数据库密钥
        - 调用rekey更新数据库密钥
        - 返回修改的结果

        入参：
            old_key: 旧数据库密钥
            new_key: 新数据库密钥

        出参：
            bool: 重新加密是否成功

        异常：
            DatabaseError: 重新加密失败时抛出
        """
        return self.rekey(old_key, new_key)

    def rekey(self, old_key: str, new_key: str) -> bool:
        """
        重新加密数据库密钥（SQLCipher）

        职责：
        - 拿到新旧数据库密钥
        - 验证和更新数据库密钥
        - 返回修改的结果

        入参：
            old_key: 旧数据库密钥
            new_key: 新数据库密钥

        出参：
            bool: 重新加密是否成功

        异常：
            DatabaseError: 重新加密失败时抛出
        """
        if self.database_type != DatabaseType.SQLCIPHER.value:
            raise DatabaseError("rekey 仅支持 SQLCipher 数据库")

        try:
            with self._lock:
                conn = self._get_thread_connection()
                if not conn:
                    raise DatabaseError(
                        get_exception_message(
                            Messages.DatabaseHandler,
                            "DATABASE_NOT_CONNECTED"
                        )
                    )
                conn.execute(f"PRAGMA key = '{old_key}'")
                conn.execute(f"PRAGMA rekey = '{new_key}'")
                conn.commit()
                logger.info("Database rekey completed successfully")
                return True

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Database rekey failed: {e}")
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "DATABASE_REKEY_FAILED"
                )
            )

    def execute_update(
        self, query: str, params: Optional[tuple] = None
    ) -> int:
        """
        执行更新语句（INSERT、UPDATE、DELETE）

        入参：
            query: SQL更新语句
            params: 更新参数

        出参：
            int: 影响的行数

        异常：
            DatabaseError: 更新失败时抛出
        """
        try:
            with self._lock:
                conn = self._get_thread_connection()
                if not conn:
                    raise DatabaseError(
                        get_exception_message(
                            Messages.DatabaseHandler,
                            "DATABASE_NOT_CONNECTED"
                        )
                    )

                converted = self._convert_sql(query)
                cursor = conn.cursor()
                cursor.execute(converted, params or ())
                affected = cursor.rowcount
                conn.commit()
                cursor.close()
                return affected

        except DatabaseError:
            raise
        except Exception:
            if conn:
                conn.rollback()
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "EXECUTE_UPDATE_FAILED"
                )
            )

    def insert_sensitive_info(
        self, key_alias: str, sensitive_type: str,
        provider_alias: Optional[str],
        provider_name: Optional[str],
        provider_base_url: Optional[str],
        sensitive_cipher: str
    ) -> int:
        """
        插入敏感信息

        入参：
            key_alias: 密钥别名
            sensitive_type: 敏感信息类型
            provider_alias: 服务商别名
            provider_name: 服务商名称
            provider_base_url: 服务商接口地址
            sensitive_cipher: 敏感信息密文

        出参：
            int: 插入的记录ID

        异常：
            DatabaseError: 插入失败时抛出
        """
        query = """
            INSERT INTO mgc_sensitive_info
            (key_alias, sensitive_type, provider_alias,
             provider_name, provider_base_url,
             sensitive_cipher)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        self.execute_update(
            query, (key_alias, sensitive_type, provider_alias,
                    provider_name, provider_base_url,
                    sensitive_cipher)
        )

        if self.database_type == "firebird":
            result = self.execute_query(
                "SELECT GEN_ID(GEN_MGC_ID, 0) as id FROM RDB$DATABASE"
            )
            return result[0]['id'] if result else 0
        else:
            result = self.execute_query(
                "SELECT LAST_INSERT_ID() as id"
            )
            return result[0]['id']

    def get_sensitive_info(
        self, key_alias: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取敏感信息

        入参：
            key_alias: 密钥别名

        出参：
            dict: 敏感信息数据，不存在时返回None
        """
        query = (
            "SELECT * FROM mgc_sensitive_info "
            "WHERE key_alias = %s"
        )
        result = self.execute_query(query, (key_alias,))
        return result[0] if result else None

    def get_sensitive_list(self) -> List[Dict[str, Any]]:
        """
        获取敏感信息列表（脱敏）

        出参：
            list: 敏感信息列表（脱敏）
        """
        query = """
            SELECT key_alias, sensitive_type, created_at
            FROM mgc_sensitive_info
            WHERE status = 'enabled'
            ORDER BY created_at DESC
        """
        return self.execute_query(query)

    def delete_sensitive_info(self, key_alias: str, diff_1: str = None, diff_2: str = None, diff_3: str = None) -> int:
        """
        删除敏感信息

        入参：
            key_alias: 密钥别名（即 info_owner）
            diff_1, diff_2, diff_3: 可选过滤字段；为空表示该字段通配（按 NULL/空字符串匹配）
                1.5.1 phase7: folder 删除场景下传 diff_2 即可，按 (owner, diff_2) 删除整个 folder

        出参：
            int: 删除的行数
        """
        # 1.5.1 phase7: 对齐 SQLCipher 单表模式的过滤语义（仿 _delete_from_mgc_info_1）
        conditions = ["key_alias = %s"]
        params = [key_alias]

        if diff_1:
            conditions.append("diff_1 = %s")
            params.append(diff_1)
        else:
            conditions.append("(diff_1 IS NULL OR diff_1 = '')")

        if diff_2:
            conditions.append("diff_2 = %s")
            params.append(diff_2)
        else:
            conditions.append("(diff_2 IS NULL OR diff_2 = '')")

        if diff_3:
            conditions.append("diff_3 = %s")
            params.append(diff_3)
        else:
            conditions.append("(diff_3 IS NULL OR diff_3 = '')")

        query = "DELETE FROM mgc_sensitive_info WHERE " + " AND ".join(conditions)
        return self.execute_update(query, tuple(params))

    def update_sensitive_info(
        self, key_alias: str, sensitive_cipher: str
    ) -> int:
        """
        更新敏感信息

        入参：
            key_alias: 密钥别名
            sensitive_cipher: 新的敏感信息密文

        出参：
            int: 更新的行数
        """
        query = """
            UPDATE mgc_sensitive_info
            SET sensitive_cipher = %s, updated_at = %s
            WHERE key_alias = %s
        """
        return self.execute_update(
            query, (sensitive_cipher, datetime.now(), key_alias)
        )

    def insert_operation_log(
        self, operation_type: str, operation_result: str,
        request_id: Optional[str] = None,
        provider_alias: Optional[str] = None,
        key_alias: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> int:
        """
        插入操作日志

        入参：
            operation_type: 操作类型
            operation_result: 操作结果
            request_id: 请求ID（可选）
            provider_alias: 服务商别名（脱敏，可选）
            key_alias: 密钥别名（脱敏，可选）
            error_message: 错误信息（可选）
            duration_ms: 耗时（毫秒，可选）

        出参：
            int: 插入的记录ID

        异常：
            DatabaseError: 插入失败时抛出
        """
        query = """
            INSERT INTO mgc_operation_logs
            (operation_type, operation_result,
             request_id, provider_alias, key_alias,
             error_message, duration_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        self.execute_update(
            query, (operation_type, operation_result,
                    request_id, provider_alias, key_alias,
                    error_message, duration_ms)
        )

        if self.database_type == "firebird":
            result = self.execute_query(
                "SELECT GEN_ID(GEN_MGC_ID, 0) as id FROM RDB$DATABASE"
            )
            return result[0]['id'] if result else 0
        else:
            result = self.execute_query(
                "SELECT LAST_INSERT_ID() as id"
            )
            return result[0]['id']

    def get_operation_logs(
        self, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取操作日志

        入参：
            limit: 返回条数限制

        出参：
            list: 操作日志列表
        """
        if self.database_type == "firebird":
            query = f"""
                SELECT FIRST {limit} * FROM mgc_operation_logs
                ORDER BY created_at DESC
            """
            return self.execute_query(query)
        else:
            query = """
                SELECT * FROM mgc_operation_logs
                ORDER BY created_at DESC
                LIMIT %s
            """
            return self.execute_query(query, (limit,))

    def init_database_tables(self) -> bool:
        """
        初始化数据库表

        功能：读取并执行对应数据库类型的初始化SQL脚本

        出参：
            bool: True表示初始化成功

        异常：
            DatabaseError: 初始化失败时抛出
        """
        try:
            conn = self._get_thread_connection()
            if not conn:
                raise DatabaseError(
                    get_exception_message(
                        Messages.DatabaseHandler,
                        "DATABASE_NOT_CONNECTED"
                    )
                )

            if self.database_type == "firebird":
                sql_file = (
                    Path(__file__).parent
                    / "init_tables_firebird.sql"
                )
            elif self.database_type == "sqlcipher":
                from mgc.config.enum_config import ConfigDefaults, ConfigItem
                config_dict = DC.get_config()
                if config_dict.get(ConfigItem.SINGLE_INFO_UNIT, ConfigDefaults.SINGLE_INFO_UNIT):
                    sql_file = (
                        Path(__file__).parent
                        / "init_tables_sqlcipher_single.sql"
                    )
                else:
                    sql_file = (
                        Path(__file__).parent
                        / "init_tables_sqlcipher.sql"
                    )
            else:
                sql_file = (
                    Path(__file__).parent / "init_tables.sql"
                )

            if not sql_file.exists():
                raise DatabaseError(
                    f"Init script not found: {sql_file}"
                )

            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            conn = self._get_thread_connection()
            
            if self.database_type == "firebird":
                self._execute_firebird_sql(sql_content, conn)
            else:
                cursor = conn.cursor()
                for statement in sql_content.split(';'):
                    statement = statement.strip()
                    if statement:
                        cursor.execute(statement)
                cursor.close()

            conn.commit()
            return True

        except DatabaseError:
            raise
        except Exception as e:
            conn = self._get_thread_connection()
            if conn:
                conn.rollback()
            raise DatabaseError(
                get_exception_message(
                    Messages.DatabaseHandler,
                    "INIT_TABLES_FAILED"
                ).format(error=str(e))
            )

    def _execute_firebird_sql(self, sql_content: str, conn) -> None:
        """
        执行Firebird SQL脚本（支持触发器等含内部分号的语句）

        入参：
            sql_content: SQL脚本内容
            conn: 数据库连接对象
        """
        import re
        statements = []
        current = []
        in_trigger = False

        for line in sql_content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('--'):
                continue
            is_trigger_start = bool(re.match(
                r'CREATE\s+(OR\s+ALTER\s+)?TRIGGER',
                stripped, re.IGNORECASE
            ))
            is_set_term = bool(re.match(
                r'SET\s+TERM',
                stripped, re.IGNORECASE
            ))
            if is_set_term:
                continue
            if is_trigger_start and current:
                stmt = '\n'.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            if is_trigger_start:
                in_trigger = True
            current.append(line)
            if in_trigger and (stripped.upper() == 'END' or stripped.upper() == 'END^'):
                stmt = '\n'.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                in_trigger = False
            elif not in_trigger and stripped.endswith(';'):
                stmt = '\n'.join(current).strip().rstrip(';')
                if stmt:
                    statements.append(stmt)
                current = []

        remaining = '\n'.join(current).strip().rstrip(';')
        if remaining:
            statements.append(remaining)

        for stmt in statements:
            try:
                conn.execute_immediate(stmt)
                conn.commit()
            except Exception as e:
                import logging
                logger.error(f"SQL Error: {stmt[:100]}... Error: {e}")
                is_already_exists = (
                    isinstance(e.args, tuple)
                    and len(e.args) > 0
                    and -607 in e.args
                )
                if is_already_exists:
                    continue
                if "already exists" in str(e).lower():
                    continue
                raise
