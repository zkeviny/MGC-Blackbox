"""
MySQL处理器

功能：
- 管理MySQL数据库连接
- 初始化数据库和表结构（一次性操作，使用root权限）
- 创建mgc_user_1账户
- 执行数据库操作（使用mgc_user_1低权限账户）

安全规范：
- 初始化完成后必须断开root连接并清空凭证
- 仅授予mgc_user_1最小权限（SELECT, INSERT）
- 所有配置从enum_config统一读取

依赖：
- pymysql（MySQL驱动）
- src/config/enum_config.py（枚举配置）
- src/domain/crypto_layer/password_generator.py（密码生成）
"""

import pymysql
import logging
import json
import os
import re
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from mgc.config.enum_config import ConfigDefaults
from mgc.config.path_config import LOG_DIR
from mgc.domain.crypto_layer.password_generator import generate_mgc_user1_password

logger = logging.getLogger(__name__)

MGC_USER_1 = "mgc_user_1"


class MySQLHandler:
    """MySQL处理器"""

    def __init__(self, host: str = "localhost", port: int = 3306,
                 user: str = "root", password: str = ""):
        """
        初始化MySQL处理器

        入参：
            host: MySQL主机地址
            port: MySQL端口
            user: MySQL用户名
            password: MySQL密码
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connection = None

    def connect(self) -> None:
        """
        连接MySQL数据库
        """
        try:
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                charset='utf8mb4'
            )
            logger.debug(f"MySQL connection successful: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"MySQL connection failed: {e}")
            raise

    def disconnect(self) -> None:
        """
        断开MySQL数据库连接并清空凭证
        """
        if self.connection:
            self.connection.close()
            self.connection = None
        self.user = ""
        self.password = ""
        logger.debug("MySQL connection closed, credentials cleared")

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
        
        # 密码长度限制（8-64字符）
        if len(password) < 8 or len(password) > 64:
            return False
        
        # 仅允许字母、数字、特殊字符（排除SQL注入风险字符）
        pattern = r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?]+$'
        if not re.match(pattern, password):
            return False
        
        # 排除单引号和双引号（防止SQL注入）
        if "'" in password or '"' in password or "\\" in password:
            return False
        
        return True

    def initialize_database(self, hardware_info: Dict[str, str], 
                         salts: Dict[str, int]) -> str:
        """
        初始化数据库（一次性操作，使用root权限）

        入参：
            hardware_info: 硬件信息字典（cpu_serial, disk_id, motherboard_serial）
            salts: 动态盐字典

        出参：
            mgc_user_1账户密码（用于后续连接）

        安全规范：
            - 执行完成后必须断开root连接并清空凭证
            - 仅授予mgc_user_1最小权限（SELECT, INSERT）
        """
        self.connect()

        cursor = self.connection.cursor()
        mgc_user1_password = None

        try:
            database_name = ConfigDefaults.DATABASE_NAME

            # 创建数据库
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute(f"USE {database_name}")
            logger.debug(f"Database {database_name} created")

            # 生成mgc_user_1账户密码
            mgc_user1_password = generate_mgc_user1_password(
                cpu_serial=hardware_info["cpu_serial"],
                disk_id=hardware_info["disk_id"],
                salts=salts
            )

            # 验证密码格式
            if not self._validate_password(mgc_user1_password):
                raise ValueError("生成的密码格式不合法")

            # 创建mgc_user_1账户（如果已存在则先删除）
            try:
                cursor.execute(f"DROP USER IF EXISTS '{MGC_USER_1}'@'%'")
            except Exception:
                pass

            # 使用参数化查询创建用户（MySQL 8.0+支持）
            try:
                cursor.execute(f"CREATE USER '{MGC_USER_1}'@'%' IDENTIFIED BY %s", (mgc_user1_password,))
            except Exception:
                # 如果不支持参数化查询，使用转义处理
                escaped_password = pymysql.escape_string(mgc_user1_password)
                cursor.execute(f"CREATE USER '{MGC_USER_1}'@'%' IDENTIFIED BY '{escaped_password}'")

            # 授予最小权限（仅SELECT和INSERT）
            cursor.execute(f"GRANT SELECT, INSERT ON {database_name}.* TO '{MGC_USER_1}'@'%'")
            cursor.execute("FLUSH PRIVILEGES")
            logger.debug(f"{MGC_USER_1} account created and authorized (SELECT, INSERT only)")

            # 创建mgc_user_info表
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
                    
                    -- 新增字段：支持5字段查询清单结构
                    diff1 VARCHAR(100) DEFAULT '',
                    diff2 VARCHAR(100) DEFAULT '',
                    diff3 VARCHAR(100) DEFAULT '',
                    
                    -- 新增字段：支持ext01~ext30扩展
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
                    
                    -- 索引
                    INDEX idx_info_type (info_type),
                    INDEX idx_info_owner (info_owner),
                    INDEX idx_extract_account_password (extract_account, extract_password),
                    INDEX idx_diff_fields (info_type, info_owner, diff1, diff2, diff3)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            logger.debug("mgc_user_info table created")

            # 创建agent_used_log表
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
            logger.debug("agent_used_log table created")

            # 创建mgc_system_env表（环境因子·终身只读）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mgc_system_env (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    env_factor_cipher TEXT NOT NULL COMMENT '初始环境因子密文（终身不变）',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='MGC 初始环境因子表（只读、唯一一行、终身不可修改）'
            """)
            logger.debug("mgc_system_env table created")

            # 创建mgc_root_secure表（根密钥·迁移授权·最高密级）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mgc_root_secure (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    root_key_cipher TEXT NOT NULL COMMENT '根密钥密文（硬件加密）',
                    migrate_key_hash VARCHAR(255) NOT NULL COMMENT '迁移密钥哈希（验证用）',
                    hardware_fp VARCHAR(255) COMMENT '绑定硬件标识',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='MGC 根密钥与迁移授权安全表'
            """)
            logger.debug("mgc_root_secure table created")

            self.connection.commit()
            return mgc_user1_password

        except Exception as e:
            self.connection.rollback()
            logger.error(f"Database initialization failed: {e}")
            raise e

        finally:
            cursor.close()
            # 安全规范：断开root连接并清空凭证
            self.disconnect()
            logger.debug("Root privileges disconnected, credentials cleared")

    def insert_user_info(self, connection, info_type: str, info_owner: str,
                       extract_account: str, extract_password: str,
                       info_plaintext: str) -> int:
        """
        插入用户信息

        入参：
            connection: 数据库连接（从连接池获取）
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
                (info_type, info_owner, extract_account, extract_password, info_plaintext)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (info_type, info_owner, extract_account, extract_password, info_plaintext))
            connection.commit()

            logger.debug(f"User info inserted: {info_owner}/{info_type}")
            return cursor.lastrowid

        except Exception as e:
            connection.rollback()
            logger.error(f"User info insert failed: {e}")
            raise e

        finally:
            cursor.close()

    def query_user_info(self, connection, extract_account: str, extract_password: str) -> Optional[dict]:
        """
        查询用户信息

        入参：
            connection: 数据库连接（从连接池获取）
            extract_account: 提取账户
            extract_password: 提取密码

        出参：
            用户信息，未找到返回None
        """
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        try:
            sql = """
                SELECT * FROM mgc_user_info
                WHERE extract_account = %s AND extract_password = %s
            """
            cursor.execute(sql, (extract_account, extract_password))
            result = cursor.fetchone()

            if result:
                logger.debug(f"User info query successful: {result['info_owner']}/{result['info_type']}")
            else:
                logger.debug("User info query failed: record not found")

            return result

        except Exception as e:
            logger.error(f"User info query failed: {e}")
            raise e

        finally:
            cursor.close()

    def get_log_table_name(self) -> str:
        """
        获取当日日志表名

        出参：
            表名，格式：agent_used_log_YYYYMMDD
        """
        today = datetime.now().strftime("%Y%m%d")
        return f"agent_used_log_{today}"

    def create_log_table(self, connection) -> None:
        """
        创建当日日志表

        入参：
            connection: 数据库连接
        """
        table_name = self.get_log_table_name()
        cursor = connection.cursor()

        try:
            # 检查表是否存在
            cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
            if cursor.fetchone():
                return

            # 创建表
            sql = f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                `log_id` VARCHAR(32) NOT NULL,
                `agent_name` VARCHAR(64) NOT NULL,
                `agent_uuid` VARCHAR(64) NOT NULL,
                `operation_type` VARCHAR(16) NOT NULL,
                `operation_time` DATETIME NOT NULL,
                `item_id` VARCHAR(32) NOT NULL,
                `entry_mark` VARCHAR(64) NOT NULL,
                `operation_result` VARCHAR(8) NOT NULL,
                `fail_reason` VARCHAR(128),
                PRIMARY KEY (`log_id`),
                INDEX `idx_agent_uuid` (`agent_uuid`),
                INDEX `idx_operation_type` (`operation_type`),
                INDEX `idx_operation_time` (`operation_time`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(sql)
            connection.commit()
            logger.debug(f"Log table {table_name} created")
        finally:
            cursor.close()

    def _desensitize_entry_mark(self, entry_mark: str) -> str:
        """
        脱敏 entry_mark

        入参：
            entry_mark: 原始 entry_mark

        出参：
            脱敏后的 entry_mark
        """
        if not entry_mark:
            return ""

        # 提取类型和序号
        parts = entry_mark.split("-")
        if len(parts) < 2:
            return entry_mark

        info_type = "-".join(parts[:-1])
        serial = parts[-1]

        # 脱敏处理：保留前2字符+*+序号
        if len(info_type) >= 2:
            desensitized_type = info_type[:2] + "*"
        else:
            desensitized_type = info_type + "*"

        return f"{desensitized_type}-{serial}"

    def _cache_log(self, log_id: str, agent_name: str, agent_uuid: str, 
                   operation_type: str, item_id: str, entry_mark: str, 
                   operation_result: str, fail_reason: str = None) -> None:
        """
        缓存日志到本地文件

        入参：
            与 insert_log 相同
        """
        # 确保缓存目录存在
        cache_dir = LOG_DIR / "cache"
        cache_dir.mkdir(exist_ok=True, parents=True)

        # 生成缓存文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        cache_file = cache_dir / f"log_cache_{timestamp}.json"

        # 构建日志数据
        log_data = {
            "log_id": log_id,
            "agent_name": agent_name,
            "agent_uuid": agent_uuid,
            "operation_type": operation_type,
            "operation_time": datetime.now().isoformat(),
            "item_id": item_id,
            "entry_mark": entry_mark,
            "operation_result": operation_result,
            "fail_reason": fail_reason
        }

        # 写入缓存文件
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Log cached locally: {cache_file}")

    def sync_cached_logs(self, connection) -> int:
        """
        同步缓存的日志到数据库

        入参：
            connection: 数据库连接

        出参：
            同步成功的日志数量
        """
        cache_dir = LOG_DIR / "cache"
        if not cache_dir.exists():
            return 0

        synced_count = 0

        # 遍历缓存文件
        for cache_file in cache_dir.glob("log_cache_*.json"):
            try:
                # 读取缓存文件
                with open(cache_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)

                # 插入日志
                self.insert_log(
                    connection=connection,
                    log_id=log_data["log_id"],
                    agent_name=log_data["agent_name"],
                    agent_uuid=log_data["agent_uuid"],
                    operation_type=log_data["operation_type"],
                    item_id=log_data["item_id"],
                    entry_mark=log_data["entry_mark"],
                    operation_result=log_data["operation_result"],
                    fail_reason=log_data["fail_reason"]
                )

                # 删除缓存文件
                os.remove(cache_file)
                synced_count += 1
                logger.debug(f"Cache log synced: {log_data['log_id']}")
            except Exception as e:
                # 同步失败，保留缓存文件
                logger.error(f"Cache log sync failed: {e}")
                pass

        return synced_count

    def insert_log(self, connection, log_id: str, agent_name: str, agent_uuid: str,
                  operation_type: str, item_id: str = None, entry_mark: str = None,
                  operation_result: str = "SUCCESS", fail_reason: str = None) -> None:
        """
        插入日志

        入参：
            connection: 数据库连接（从连接池获取）
            log_id: 日志ID
            agent_name: Agent名称
            agent_uuid: Agent UUID
            operation_type: 操作类型
            item_id: 条目ID
            entry_mark: 条目标识
            operation_result: 操作结果
            fail_reason: 失败原因
        """
        # 脱敏 entry_mark
        desensitized_entry_mark = self._desensitize_entry_mark(entry_mark or "")

        # 确保当日表存在
        self.create_log_table(connection)

        table_name = self.get_log_table_name()
        cursor = connection.cursor()

        try:
            sql = f"""
                INSERT INTO `{table_name}` 
                (log_id, agent_name, agent_uuid, operation_type, operation_time, 
                 item_id, entry_mark, operation_result, fail_reason)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                log_id, agent_name, agent_uuid, operation_type, 
                item_id or "", desensitized_entry_mark, operation_result, fail_reason
            ))
            connection.commit()

            logger.debug(f"Log inserted: {log_id}/{operation_type}")

        except Exception as e:
            connection.rollback()
            logger.error(f"Log insert failed: {e}")
            # 日志写入失败，使用本地缓存
            self._cache_log(log_id, agent_name, agent_uuid, operation_type, 
                           item_id, entry_mark, operation_result, fail_reason)
            raise e

        finally:
            cursor.close()

    def cleanup_old_logs(self, connection, days: int = 30) -> int:
        """
        清理旧日志

        入参：
            connection: 数据库连接（从连接池获取）
            days: 保留天数

        出参：
            删除的记录数
        """
        cursor = connection.cursor()

        try:
            # 清理主表日志
            sql = """
                DELETE FROM agent_used_log
                WHERE operation_time < DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            cursor.execute(sql, (days,))
            deleted_count = cursor.rowcount

            # 清理历史分表
            cursor.execute("SHOW TABLES LIKE 'agent_used_log_%'")
            tables = cursor.fetchall()

            for table in tables:
                table_name = table[0]
                # 提取日期部分
                date_str = table_name.replace("agent_used_log_", "")
                try:
                    table_date = datetime.strptime(date_str, "%Y%m%d")
                    # 计算天数差
                    days_diff = (datetime.now() - table_date).days
                    if days_diff > days:
                        cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                        logger.debug(f"Expired log table deleted: {table_name}")
                except ValueError:
                    pass

            connection.commit()

            logger.debug(f"Old logs cleaned: {deleted_count} records")
            return deleted_count

        except Exception as e:
            connection.rollback()
            logger.error(f"Old log cleanup failed: {e}")
            raise e

        finally:
            cursor.close()
    
    def insert_info(self, connection, info_type: str, info_owner: str,
                   extract_account: str, extract_password: str,
                   info_plaintext: str, diff1: str = "", diff2: str = "",
                   diff3: str = "", ext_fields: Dict[str, str] = None) -> None:
        """
        插入信息

        入参：
            connection: 数据库连接
            info_type: 信息类型
            info_owner: 信息归属
            extract_account: 提取账户名
            extract_password: 提取密码
            info_plaintext: 敏感信息内容（明文）
            diff1: 差异1字段
            diff2: 差异2字段
            diff3: 差异3字段
            ext_fields: ext01~ext30字段字典
        """
        cursor = connection.cursor()

        try:
            if ext_fields is None:
                ext_fields = {}
            
            sql = """
                INSERT INTO mgc_user_info
                (info_type, info_owner, extract_account, extract_password, info_plaintext,
                 diff1, diff2, diff3,
                 ext01, ext02, ext03, ext04, ext05, ext06, ext07, ext08, ext09, ext10,
                 ext11, ext12, ext13, ext14, ext15, ext16, ext17, ext18, ext19, ext20,
                 ext21, ext22, ext23, ext24, ext25, ext26, ext27, ext28, ext29, ext30)
                VALUES (%s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(sql, (
                info_type, info_owner, extract_account, extract_password, info_plaintext,
                diff1, diff2, diff3,
                ext_fields.get("ext01", ""), ext_fields.get("ext02", ""), ext_fields.get("ext03", ""),
                ext_fields.get("ext04", ""), ext_fields.get("ext05", ""), ext_fields.get("ext06", ""),
                ext_fields.get("ext07", ""), ext_fields.get("ext08", ""), ext_fields.get("ext09", ""),
                ext_fields.get("ext10", ""), ext_fields.get("ext11", ""), ext_fields.get("ext12", ""),
                ext_fields.get("ext13", ""), ext_fields.get("ext14", ""), ext_fields.get("ext15", ""),
                ext_fields.get("ext16", ""), ext_fields.get("ext17", ""), ext_fields.get("ext18", ""),
                ext_fields.get("ext19", ""), ext_fields.get("ext20", ""), ext_fields.get("ext21", ""),
                ext_fields.get("ext22", ""), ext_fields.get("ext23", ""), ext_fields.get("ext24", ""),
                ext_fields.get("ext25", ""), ext_fields.get("ext26", ""), ext_fields.get("ext27", ""),
                ext_fields.get("ext28", ""), ext_fields.get("ext29", ""), ext_fields.get("ext30", "")
            ))
            connection.commit()

            logger.debug(f"Info inserted: {info_type}/{info_owner}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Info insert failed: {e}")
            raise e
        finally:
            cursor.close()
    
    def query_info(self, connection, extract_account: str, extract_password: str = "") -> Optional[dict]:
        """
        查询信息

        入参：
            connection: 数据库连接
            extract_account: 提取账户名
            extract_password: 提取密码（可选，如果不提供则仅使用账户名查询）

        出参：
            信息字典，未找到返回None
        """
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        try:
            if extract_password:
                # 使用账户名+密码查询（算法6规则）
                sql = """
                    SELECT * FROM mgc_user_info
                    WHERE extract_account = %s AND extract_password = %s
                """
                cursor.execute(sql, (extract_account, extract_password))
            else:
                # 仅使用账户名查询（向后兼容）
                sql = """
                    SELECT * FROM mgc_user_info
                    WHERE extract_account = %s
                """
                cursor.execute(sql, (extract_account,))
            
            result = cursor.fetchone()

            if result:
                logger.debug(f"Info query successful: {extract_account}")
            else:
                logger.debug("Info query failed: record not found")

            return result

        except Exception as e:
            logger.error(f"Info query failed: {e}")
            raise e

        finally:
            cursor.close()
    
    def update_info(self, connection, item_id: str, item_name: str, 
                   item_value: str) -> None:
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

            logger.debug(f"Info updated: {item_id}/{item_name}")
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

            logger.debug(f"Info deleted: {item_id}")
        except Exception as e:
            connection.rollback()
            logger.error(f"Info delete failed: {e}")
            raise e
        finally:
            cursor.close()