"""
数据库配置模块

功能：
- 管理数据库连接配置
- 支持从配置文件或环境变量读取配置
- 提供默认配置和配置验证
- 支持 SQLCipher 和 MySQL

依赖：
- os（环境变量读取）
- pathlib（路径处理）
- platform（平台检测）
"""

import os
import sys
import platform
import yaml
from typing import Dict, Optional
from pathlib import Path

from mgc.config.enum_config import DatabaseType
from mgc.config.path_config import DB_DIR


class DatabaseConfigError(Exception):
    """数据库配置异常"""
    pass


class DatabaseConfig:
    """数据库配置"""

    _config_file = Path(__file__).parent / "database_config.yaml"

    @staticmethod
    def get_config() -> Dict[str, any]:
        """
        获取数据库配置

        功能：
        - 优先从配置文件读取database_type
        - 环境变量作为覆盖层
        - 未配置时使用默认值（sqlcipher）

        出参：
            dict: 数据库配置
            {
                "database_type": "sqlcipher",
                "sqlcipher": {"db_file": "...", "charset": "UTF8"},
                "mysql": {"host": "...", "port": 3306, ...}
            }

        异常：
            DatabaseConfigError: 配置无效时抛出
        """
        database_type = os.getenv(
            "MGC_DATABASE_TYPE", DatabaseType.SQLCIPHER.value
        )

        config = {
            "database_type": database_type,
            "mysql": {
                "host": os.getenv("MGC_MYSQL_HOST", "localhost"),
                "port": int(os.getenv("MGC_MYSQL_PORT", "3306")),
                "user": os.getenv("MGC_MYSQL_USER", "root"),
                "password": os.getenv("MGC_MYSQL_PASSWORD", ""),
                "database": os.getenv(
                    "MGC_MYSQL_DATABASE", "mgc_black_box"
                )
            },
            "sqlcipher": {
                "db_file": os.getenv(
                    "MGC_SQLCIPHER_DB_FILE",
                    str(DB_DIR / "mgc_black_box.db")
                ),
                "charset": "UTF8"
            }
        }

        DatabaseConfig._validate_config(config)
        return config

    @staticmethod
    def _validate_config(config: Dict[str, any]):
        """
        验证数据库配置

        入参：
            config: 数据库配置字典

        异常：
            DatabaseConfigError: 配置无效时抛出
        """
        database_type = config.get("database_type")
        supported_types = [t.value for t in DatabaseType]

        if database_type not in supported_types:
            raise DatabaseConfigError(
                f"Unsupported database type: {database_type}. "
                f"Supported types: {supported_types}"
            )

        if database_type == "mysql":
            mysql_config = config.get("mysql", {})
            if not mysql_config.get("host"):
                raise DatabaseConfigError(
                    "MySQL host is required"
                )

    @staticmethod
    def save_config(config: Dict[str, any]) -> None:
        """
        保存配置到文件

        入参：
            config: 数据库配置字典

        异常：
            DatabaseConfigError: 保存失败时抛出
        """
        try:
            DatabaseConfig._validate_config(config)
            with open(DatabaseConfig._config_file, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True)
        except Exception as e:
            raise DatabaseConfigError(
                f"Failed to write database config: {e}"
            )

    @staticmethod
    def get_database_type() -> str:
        """
        获取当前数据库类型

        出参：
            str: 数据库类型（sqlcipher/mysql）
        """
        config = DatabaseConfig.get_config()
        return config.get("database_type", DatabaseType.SQLCIPHER.value)