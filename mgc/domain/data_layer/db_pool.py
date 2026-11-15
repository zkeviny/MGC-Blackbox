"""
数据库连接池

功能：
- 管理数据库连接池
- 提供连接获取和释放接口
- 支持并发访问

依赖：
- pymysql（MySQL驱动）
- DBUtils（MySQL连接池库）
- src/config/enum_config.py（枚举配置）
- src/config/database_config.py（数据库配置）
"""

import logging
import threading
from typing import Optional
from pathlib import Path

from mgc.config.enum_config import ConfigDefaults
from mgc.config.database_config import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabasePool:
    """数据库连接池"""

    _instance = None
    _pool = None
    _database_type = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, host: str = "localhost", port: int = 3306,
                 user: str = "mgc_user_1", password: str = "",
                 database: str = None):
        """
        初始化数据库连接池

        入参：
            host: MySQL主机地址
            port: MySQL端口
            user: MySQL用户名
            password: MySQL密码
            database: 数据库名称
        """
        if self._database_type is not None:
            return

        self._database_type = DatabaseConfig.get_database_type()

        self._init_mysql(host, port, user, password, database)

    def _init_mysql(self, host: str, port: int,
                    user: str, password: str,
                    database: str) -> None:
        """初始化MySQL连接池"""
        try:
            from dbutils.pooled_db import PooledDB
            import pymysql

            if database is None:
                database = ConfigDefaults.DATABASE_NAME

            self._pool = PooledDB(
                creator=pymysql,
                maxconnections=10,
                mincached=2,
                maxcached=5,
                maxshared=3,
                blocking=True,
                maxusage=None,
                setsession=[],
                ping=1,
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset='utf8mb4'
            )
            logger.info("MySQL pool initialized")
        except Exception as e:
            logger.error(f"MySQL pool init failed: {e}")
            raise

    def get_connection(self):
        """
        获取数据库连接

        出参：
            数据库连接对象
        """
        if self._pool is None:
            raise RuntimeError("MySQL pool not initialized")
        return self._pool.connection()

    def release_connection(self, connection) -> None:
        """
        释放连接回池

        入参：
            connection: 数据库连接
        """
        pass

    def close_all(self) -> None:
        """关闭所有连接"""
        if self._pool is not None:
            self._pool.close()
            self._pool = None
            logger.info("MySQL pool closed")

    @staticmethod
    def get_instance():
        """
        获取连接池单例

        出参：
            DatabasePool实例
        """
        if DatabasePool._instance is None:
            raise RuntimeError(
                "DatabasePool not initialized"
            )
        return DatabasePool._instance
