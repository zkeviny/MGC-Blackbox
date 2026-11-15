"""
调度服务

功能：
- 实现备份与清理的定时调度
- 管理查询清单和日志的备份
- 清理过期的备份文件和日志
"""

import schedule
import time
import logging
import threading
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from mgc.domain.storage_layer.query_list_handler import QueryListHandler
from mgc.domain.data_layer.database_initializer import DatabaseInitializer
from mgc.domain.data_layer.db_pool import DatabasePool
from mgc.config.path_config import QUERY_LIST_BACKUP_DIR, LOG_DIR
from mgc.config.enum_config import ConfigDefaults

logger = logging.getLogger(__name__)

class SchedulerService:
    """调度服务"""
    
    def __init__(self):
        """初始化调度服务"""
        self.query_list_handler = QueryListHandler()
        self.db_initializer = DatabaseInitializer()
        self.system_agent_uuid = ConfigDefaults.SYSTEM_AGENT_UUID
        self.system_agent_whitelist = ConfigDefaults.SYSTEM_AGENT_WHITELIST
    
    def _validate_system_agent(self, agent_uuid: str) -> bool:
        """验证系统级agent_uuid
        
        入参：
            agent_uuid: Agent UUID
            
        出参：
            是否验证通过
        """
        return agent_uuid in self.system_agent_whitelist
    
    def start(self):
        """启动调度服务"""
        schedule.every().day.at("00:00").do(self.perform_daily_backup)
        schedule.every().day.at("00:00").do(self.perform_daily_cleanup)

        scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        scheduler_thread.start()

    def _run_scheduler(self):
        """运行调度循环"""
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    def perform_daily_backup(self):
        """执行每日备份"""
        try:
            if not self._validate_system_agent(self.system_agent_uuid):
                logger.error(f"System-level agent_uuid verification failed: {self.system_agent_uuid}")
                return

            if not ConfigDefaults.QUERY_LIST_ENABLED:
                logger.debug("Query list feature disabled, skipping backup")
                return

            logger.debug(f"Scheduled task started: backup query list, agent_uuid: {self.system_agent_uuid}")
            backup_file = self.query_list_handler.backup_query_list()
            logger.debug(f"Query list backup successful: {backup_file}")

            if not ConfigDefaults.LOG_SYSTEM_ENABLED:
                logger.debug("Log system disabled, skipping log backup")
                return

            logger.debug("Log backup completed")
        except Exception as e:
            logger.error(f"Daily backup failed: {e}")
    
    def perform_daily_cleanup(self):
        """执行每日清理"""
        try:
            if not self._validate_system_agent(self.system_agent_uuid):
                logger.error(f"System-level agent_uuid verification failed: {self.system_agent_uuid}")
                return

            logger.debug(f"Scheduled task started: daily cleanup, agent_uuid: {self.system_agent_uuid}")
            
            if not ConfigDefaults.QUERY_LIST_ENABLED:
                logger.debug("Query list feature disabled, skipping query list backup cleanup")
            else:
                self._cleanup_old_backups(QUERY_LIST_BACKUP_DIR, 7)

            if not ConfigDefaults.LOG_SYSTEM_ENABLED:
                logger.debug("Log system disabled, skipping log cleanup")
            else:
                retention_days = ConfigDefaults.LOG_RETENTION_DAYS

                log_backup_dir = LOG_DIR / "backup"
                self._cleanup_old_backups(log_backup_dir, retention_days)

                error_log_dir = LOG_DIR / "error"
                self._cleanup_old_backups(error_log_dir, 7)

                cache_dir = LOG_DIR / "cache"
                self._cleanup_old_backups(cache_dir, 7)

                try:
                    db_pool = DatabasePool.get_instance()
                    connection = db_pool.get_connection()

                    try:
                        self.db_initializer.cleanup_old_logs(connection, retention_days)
                        logger.debug("MySQL log table cleanup completed")
                    finally:
                        connection.close()
                except RuntimeError as e:
                    logger.debug(f"Database connection pool not initialized, skipping MySQL log table cleanup: {e}")
                except Exception as e:
                    logger.error(f"MySQL table cleanup failed: {e}")

            logger.debug("Daily cleanup completed")
        except Exception as e:
            logger.error(f"Daily cleanup failed: {e}")

    def recover_cache_logs(self):
        """恢复缓存日志到数据库"""
        if not ConfigDefaults.LOG_SYSTEM_ENABLED:
            logger.debug("Log system disabled, skipping cache log recovery")
            return

        cache_dir = LOG_DIR / "cache"
        if not cache_dir.exists():
            return

        for cache_file in cache_dir.glob("log_cache_*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)

                try:
                    db_pool = DatabasePool.get_instance()
                    connection = db_pool.get_connection()

                    try:
                        self.db_initializer.insert_log(
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

                        cache_file.unlink()
                        logger.debug(f"Cache log recovered: {cache_file}")
                    finally:
                        connection.close()
                except RuntimeError as e:
                    logger.debug(f"Database connection pool not initialized, skipping cache log recovery: {e}")
            except Exception as e:
                logger.error(f"Cache log recovery failed: {e}")
    
    def _cleanup_old_backups(self, directory: Path, days: int):
        """清理过期的备份文件
        
        入参：
            directory: 目录路径
            days: 保留天数
        """
        if not directory.exists():
            return
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for file in directory.glob("*"):
            if file.is_file():
                file_time = datetime.fromtimestamp(file.stat().st_mtime)
                if file_time < cutoff_date:
                    os.remove(file)
                    logger.debug(f"Expired file cleaned: {file}")