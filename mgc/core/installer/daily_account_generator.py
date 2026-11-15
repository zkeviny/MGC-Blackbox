r"""
设备日常账号生成模块

用途：
- 实时采集当前设备环境因子
- 哈希生成动态账号
- 授权只读mgc_system_env表
- 复用优先级12的MySQL操作模块

参考文档：
- document/1.0细节需求文档/迁移密钥+根密钥处理方案.md

限制条件：
- 必须使用src/config/path_config.py中定义的相对路径
- 所有IO操作必须捕获异常
- 设备日常账号权限仅为只读mgc_system_env表唯一一行数据
- 用于日常运行，不接触业务数据
"""

import logging
import os
import sys
import secrets
from typing import Optional, Dict

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from mgc.domain.crypto_layer.hardware_fingerprint import get_hardware_fingerprint
from mgc.domain.crypto_layer.sha256_core import sha256_hash
from domain.crypto_layer import extract_dynamic_salts, get_salt
from mgc.config.i18n_config import get_exception_message, Messages

logger = logging.getLogger(__name__)


class DailyAccountGeneratorError(Exception):
    """设备日常账号生成异常"""
    pass


class DailyAccountGenerator:
    """设备日常账号生成类"""
    
    DAILY_ACCOUNT_PREFIX = "mgc_daily_"
    
    def __init__(self):
        """初始化设备日常账号生成类"""
        pass
    
    def generate_daily_account(self, db_handler, root_key: str = None) -> Dict[str, str]:
        """
        生成设备日常账号
        
        功能：
        - SQLCipher模式：跳过日常账号创建（MGC直连数据库）
        - 非SQLCipher模式：创建账号并授权只读mgc_system_env表
        
        入参：
            db_handler: 数据库处理器
            root_key: 根密钥（格式：个人密钥 权重参数），用于生成动态盐
        
        出参：
            账号信息字典
            {
                "account_name": str,
                "account_password": str
            }
        
        异常：
            DailyAccountGeneratorError: 生成失败时抛出
        """
        try:
            # 检查是否为 SQLCipher 模式
            db_type = getattr(db_handler, 'database_type', None)
            if db_type == "sqlcipher":
                logger.info("SQLCipher mode: skip daily account creation, MGC directly connects to database")
                return {
                    "account_name": "sqlcipher_mode",
                    "account_password": "sqlcipher_mode"
                }
            
            # 采集当前设备环境因子
            hardware_fingerprint = get_hardware_fingerprint()
            
            # 生成动态账号名和密码
            account_name, account_password = self._generate_account_credentials(hardware_fingerprint, root_key)
            
            # 创建账号
            self._create_account(account_name, account_password, db_handler)
            
            # 授予权限
            self._grant_permissions(account_name, db_handler)
            
            logger.debug(f"设备日常账号{account_name}创建成功")
            return {
                "account_name": account_name,
                "account_password": account_password
            }
        except Exception as e:
            error_msg = f"生成设备日常账号失败: {str(e)}"
            logger.error(error_msg)
            raise DailyAccountGeneratorError(get_exception_message(Messages.DailyAccountGenerator, "GENERATE_DAILY_ACCOUNT_FAILED", error=str(e)))
    
    def _generate_account_credentials(self, hardware_fingerprint: str, root_key: str = None) -> tuple:
        """
        生成账号名和密码
        
        功能：
        - 使用硬件指纹生成动态账号名
        - 使用环境因子+动态盐生成确定性密码
        
        入参：
            hardware_fingerprint: 硬件指纹
            root_key: 根密钥（格式：个人密钥 权重参数），用于生成动态盐
        
        出参：
            (account_name, account_password) 元组
        """
        try:
            # 使用硬件指纹生成账号名（取前16位）
            account_suffix = hardware_fingerprint[:16]
            account_name = f"{self.DAILY_ACCOUNT_PREFIX}{account_suffix}"
            
            # 使用环境因子+动态盐生成确定性密码
            if not root_key:
                raise DailyAccountGeneratorError(get_exception_message(Messages.DailyAccountGenerator, "ROOT_KEY_CANNOT_BE_EMPTY_FOR_DYNAMIC_SALT"))
            
            # 从根密钥中提取个人密钥和权重参数（格式：个人密钥_权重参数）
            parts = root_key.strip().split('_')
            if len(parts) != 2:
                raise DailyAccountGeneratorError(get_exception_message(Messages.DailyAccountGenerator, "ROOT_KEY_FORMAT_ERROR_PERSONAL_KEY_WEIGHT_PARAM"))
            
            personal_key = parts[0]
            weight_param = int(parts[1])
            
            # 提取动态盐
            salts = extract_dynamic_salts(personal_key, weight_param)
            dynamic_salt = str(get_salt(salts, 1))  # 使用动态盐1
            
            logger.debug(f"使用动态盐生成密码: salt1={dynamic_salt}")
            account_password = sha256_hash(f"{hardware_fingerprint}_{dynamic_salt}")
            
            logger.debug(f"生成账号名: {account_name}")
            return account_name, account_password
        except Exception as e:
            error_msg = f"生成账号凭证失败: {str(e)}"
            logger.error(error_msg)
            raise DailyAccountGeneratorError(get_exception_message(Messages.DailyAccountGenerator, "GENERATE_ACCOUNT_CREDENTIALS_FAILED", error=str(e)))
    
    def _create_account(self, account_name: str, account_password: str, db_handler) -> None:
        """
        创建账号
        
        入参：
            account_name: 账号名
            account_password: 账号密码
            db_handler: 数据库处理器
        
        异常：
            DailyAccountGeneratorError: 创建失败时抛出
        """
        try:
            # 检查账号是否已存在
            if self._account_exists(account_name, db_handler):
                logger.debug(f"Account {account_name} already exists, no need to create")
                return
            
            # 创建账号
            create_sql = f"CREATE USER '{account_name}'@'%' IDENTIFIED BY %s"
            db_handler.execute_update(create_sql, (account_password,))
            
            logger.debug(f"账号{account_name}创建成功")
        except Exception as e:
            error_msg = f"创建账号失败: {str(e)}"
            logger.error(error_msg)
            raise DailyAccountGeneratorError(get_exception_message(Messages.DailyAccountGenerator, "CREATE_ACCOUNT_FAILED", error=str(e)))
    
    def _grant_permissions(self, account_name: str, db_handler) -> None:
        """
        授予权限
        
        功能：
        - 授予只读mgc_system_env表权限
        - 不授予其他任何权限
        
        入参：
            account_name: 账号名
            db_handler: 数据库处理器
        
        异常：
            DailyAccountGeneratorError: 授权失败时抛出
        """
        try:
            # 获取数据库名
            database_name = self._get_database_name(db_handler)
            
            # 授予只读mgc_system_env表权限
            grant_sql = f"GRANT SELECT ON `{database_name}`.mgc_system_env TO '{account_name}'@'%'"
            db_handler.execute_update(grant_sql)
            
            # 刷新权限
            flush_sql = "FLUSH PRIVILEGES"
            db_handler.execute_update(flush_sql)
            
            logger.debug(f"账号{account_name}权限授予成功")
        except Exception as e:
            error_msg = f"授予权限失败: {str(e)}"
            logger.error(error_msg)
            raise DailyAccountGeneratorError(get_exception_message(Messages.DailyAccountGenerator, "GRANT_PERMISSIONS_FAILED", error=str(e)))
    
    def _get_database_name(self, db_handler) -> str:
        """
        获取数据库名
        
        入参：
            db_handler: 数据库处理器
        
        出参：
            数据库名
        """
        try:
            query_sql = "SELECT DATABASE() as db_name"
            result = db_handler.execute_query(query_sql)
            
            if result and result[0]['db_name']:
                return result[0]['db_name']
            
            return "mgc_black_box"
        except Exception as e:
            logger.debug(f"Failed to get database name: {str(e)}")
            return "mgc_black_box"
    
    def _account_exists(self, account_name: str, db_handler) -> bool:
        """
        检查账号是否已存在
        
        入参：
            account_name: 账号名
            db_handler: 数据库处理器
        
        出参：
            True表示已存在，False表示不存在
        """
        try:
            query_sql = f"SELECT COUNT(*) as count FROM mysql.user WHERE user = '{account_name}'"
            result = db_handler.execute_query(query_sql)
            
            if result and result[0]['count'] > 0:
                return True
            
            return False
        except Exception as e:
            logger.debug(f"Failed to check account existence: {str(e)}")
            return False
    
    def verify_daily_account(self, db_handler) -> bool:
        """
        验证设备日常账号是否存在
        
        功能：
        - 检查是否存在设备日常账号
        - 用于启动时的账号验证
        
        入参：
            db_handler: 数据库处理器
        
        出参：
            True表示存在，False表示不存在
        """
        try:
            # 采集当前设备环境因子
            hardware_fingerprint = get_hardware_fingerprint()
            
            # 生成账号名
            account_suffix = hardware_fingerprint[:16]
            account_name = f"{self.DAILY_ACCOUNT_PREFIX}{account_suffix}"
            
            # 检查账号是否存在
            return self._account_exists(account_name, db_handler)
        except Exception as e:
            logger.debug(f"Device daily account verification failed: {str(e)}")
            return False
    
    def regenerate_daily_account(self, db_handler, root_key: str) -> Dict[str, str]:
        """
        重新生成设备日常账号
        
        功能：
        - 删除旧的设备日常账号
        - 生成新的设备日常账号
        - 用于硬件变更或账号重置
        
        入参：
            db_handler: 数据库处理器
            root_key: 根密钥（格式：个人密钥_权重参数），用于生成动态盐
        
        出参：
            账号信息字典
            {
                "account_name": str,
                "account_password": str
            }
        
        异常：
            DailyAccountGeneratorError: 重新生成失败时抛出
        """
        try:
            # 删除旧的设备日常账号
            self._delete_all_daily_accounts(db_handler)
            
            # 生成新的设备日常账号
            return self.generate_daily_account(db_handler, root_key)
        except Exception as e:
            error_msg = f"重新生成设备日常账号失败: {str(e)}"
            logger.error(error_msg)
            raise DailyAccountGeneratorError(get_exception_message(Messages.DailyAccountGenerator, "REGENERATE_DAILY_ACCOUNT_FAILED", error=str(e)))
    
    def _delete_all_daily_accounts(self, db_handler) -> None:
        """
        删除所有设备日常账号
        
        入参：
            db_handler: 数据库处理器
        """
        try:
            # 查询所有设备日常账号
            query_sql = f"SELECT user FROM mysql.user WHERE user LIKE '{self.DAILY_ACCOUNT_PREFIX}%'"
            result = db_handler.execute_query(query_sql)
            
            if result:
                for row in result:
                    account_name = row['user']
                    drop_sql = f"DROP USER '{account_name}'@'%'"
                    db_handler.execute_update(drop_sql)
                    logger.debug(f"账号{account_name}删除成功")
            
            # 刷新权限
            flush_sql = "FLUSH PRIVILEGES"
            db_handler.execute_update(flush_sql)
        except Exception as e:
            logger.debug(f"Failed to delete device daily account: {str(e)}")
            raise DailyAccountGeneratorError(get_exception_message(Messages.DailyAccountGenerator, "DELETE_DAILY_ACCOUNTS_FAILED"))
