"""
Agent日志管理器

功能：
- 按日分表创建日志表
- 日志插入与缓存同步
- 旧日志清理
- entry_mark脱敏处理

安全规范：
- 日志写入失败时缓存到本地文件
- 缓存日志在下次连接成功时自动同步

依赖：
- src/config/path_config.py（路径配置）
"""

import logging
import json
import os
from datetime import datetime

from mgc.config.path_config import LOG_DIR

logger = logging.getLogger(__name__)


class AgentLogManager:
    """Agent日志管理器（按日分表）"""

    def __init__(self, database_type: str):
        """
        初始化日志管理器

        入参：
            database_type: 数据库类型（sqlcipher/mysql）
        """
        self.database_type = database_type

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
            cursor.execute(
                f"SHOW TABLES LIKE '{table_name}'"
            )
            if cursor.fetchone():
                return

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
            logger.info(f"Log table {table_name} created")
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
        parts = entry_mark.split("-")
        if len(parts) < 2:
            return entry_mark
        info_type = "-".join(parts[:-1])
        serial = parts[-1]
        if len(info_type) >= 2:
            desensitized = info_type[:2] + "*"
        else:
            desensitized = info_type + "*"
        return f"{desensitized}-{serial}"

    def _cache_log(
        self, log_id: str, agent_name: str,
        agent_uuid: str, operation_type: str,
        item_id: str, entry_mark: str,
        operation_result: str, fail_reason: str = None
    ) -> None:
        """缓存日志到本地文件"""
        cache_dir = LOG_DIR / "cache"
        cache_dir.mkdir(exist_ok=True, parents=True)

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )
        cache_file = cache_dir / f"log_cache_{timestamp}.json"

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

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(
                    log_data, f, indent=2, ensure_ascii=False
                )
            logger.info(f"Log cached: {cache_file}")
        except Exception as e:
            logger.error(f"Log cache failed: {e}")

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
        for cache_file in cache_dir.glob("log_cache_*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)

                self.insert_log(
                    connection=connection,
                    log_id=log_data["log_id"],
                    agent_name=log_data["agent_name"],
                    agent_uuid=log_data["agent_uuid"],
                    operation_type=log_data[
                        "operation_type"
                    ],
                    item_id=log_data["item_id"],
                    entry_mark=log_data["entry_mark"],
                    operation_result=log_data[
                        "operation_result"
                    ],
                    fail_reason=log_data.get("fail_reason")
                )

                os.remove(cache_file)
                synced_count += 1
            except Exception as e:
                logger.error(f"Log sync failed: {e}")

        return synced_count

    def insert_log(
        self, connection, log_id: str, agent_name: str,
        agent_uuid: str, operation_type: str,
        item_id: str = None, entry_mark: str = None,
        operation_result: str = "SUCCESS",
        fail_reason: str = None
    ) -> None:
        """
        插入日志

        入参：
            connection: 数据库连接
            log_id: 日志ID
            agent_name: Agent名称
            agent_uuid: Agent UUID
            operation_type: 操作类型
            item_id: 条目ID
            entry_mark: 条目标识
            operation_result: 操作结果
            fail_reason: 失败原因
        """
        desensitized = self._desensitize_entry_mark(
            entry_mark or ""
        )
        self.create_log_table(connection)
        table_name = self.get_log_table_name()
        cursor = connection.cursor()

        try:
            sql = f"""
                INSERT INTO `{table_name}`
                (log_id, agent_name, agent_uuid,
                 operation_type, operation_time,
                 item_id, entry_mark,
                 operation_result, fail_reason)
                VALUES (%s, %s, %s, %s, NOW(),
                        %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                log_id, agent_name, agent_uuid,
                operation_type,
                item_id or "", desensitized,
                operation_result, fail_reason
            ))

            connection.commit()
            logger.info(
                f"Log inserted: {log_id}/{operation_type}"
            )
        except Exception as e:
            connection.rollback()
            logger.error(f"Log insert failed: {e}")
            self._cache_log(
                log_id, agent_name, agent_uuid,
                operation_type, item_id, entry_mark,
                operation_result, fail_reason
            )
            raise e
        finally:
            cursor.close()

    def cleanup_old_logs(self, connection, days: int = 30) -> int:
        """
        清理旧日志

        入参：
            connection: 数据库连接
            days: 保留天数

        出参：
            删除的记录数
        """
        cursor = connection.cursor()

        try:
            sql = """
                DELETE FROM agent_used_log
                WHERE operation_time <
                DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            cursor.execute(sql, (days,))
            deleted = cursor.rowcount

            cursor.execute(
                "SHOW TABLES LIKE 'agent_used_log_%'"
            )
            tables = cursor.fetchall()

            for table in tables:
                tname = table[0]
                date_str = tname.replace(
                    "agent_used_log_", ""
                )
                try:
                    table_date = datetime.strptime(
                        date_str, "%Y%m%d"
                    )
                    days_diff = (
                        datetime.now() - table_date
                    ).days
                    if days_diff > days:
                        cursor.execute(
                            f"DROP TABLE IF EXISTS "
                            f"`{tname}`"
                        )
                        logger.info(
                            f"Dropped old log table: "
                            f"{tname}"
                        )
                except ValueError:
                    pass

            connection.commit()
            logger.info(f"Cleaned {deleted} old logs")
            return deleted

        except Exception as e:
            connection.rollback()
            logger.error(f"Log cleanup failed: {e}")
            raise e
        finally:
            cursor.close()
