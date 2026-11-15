r"""
初始环境因子采集与加密存储模块

[已废弃]
本模块未实际使用，实际使用模块为：src/domain/crypto_layer/environment_cipher.py
本模块保留用于参考，不参与任何业务逻辑。

用途：
- 采集用户当前设备的硬件信息（CPU序列号、硬盘ID、主板序列号）
- 生成初始环境因子，加密后存入mgc_system_env表（终身只读、不修改、不删除、唯一一行）
- 复用优先级12的硬件指纹采集模块和SHA-256核心模块

参考文档：
- document/1.0细节需求文档/迁移密钥+根密钥处理方案.md

限制条件：
- 必须使用src/config/path_config.py中定义的相对路径
- 所有IO操作必须捕获异常
- mgc_system_env表终身只读、不修改、不删除、唯一一行
"""

import logging
import os
import sys
from typing import Optional, Dict

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from mgc.domain.crypto_layer.hardware_fingerprint import get_hardware_info, get_hardware_fingerprint
from mgc.domain.crypto_layer.sha256_core import sha256_hash
from mgc.config.i18n_config import get_exception_message, Messages

logger = logging.getLogger(__name__)


class EnvFactorGeneratorError(Exception):
    """环境因子生成异常"""
    pass


class EnvFactorGenerator:
    """初始环境因子采集与加密存储类"""
    
    def __init__(self):
        """初始化环境因子生成类"""
        pass
    
    def generate_initial_env_factor(self) -> Dict[str, str]:
        """
        生成初始环境因子
        
        功能：
        - 采集硬件信息（CPU序列号、硬盘ID、主板序列号）
        - 生成硬件指纹哈希值
        - 返回初始环境因子数据
        
        出参：
            初始环境因子数据字典
            {
                "cpu_serial": str,
                "disk_id": str,
                "motherboard_serial": str,
                "hardware_fingerprint": str
            }
        
        异常：
            EnvFactorGeneratorError: 环境因子生成失败时抛出
        """
        try:
            cpu_serial, disk_id, motherboard_serial = get_hardware_info()
            hardware_fingerprint = get_hardware_fingerprint()
            
            env_factor_data = {
                "cpu_serial": cpu_serial,
                "disk_id": disk_id,
                "motherboard_serial": motherboard_serial,
                "hardware_fingerprint": hardware_fingerprint
            }
            
            logger.debug("初始环境因子生成成功")
            logger.debug("硬件信息已采集")
            
            return env_factor_data
        except Exception as e:
            error_msg = f"初始环境因子生成失败: {str(e)}"
            logger.error(error_msg)
            raise EnvFactorGeneratorError(get_exception_message(Messages.EnvFactorGenerator, "GENERATE_INITIAL_ENV_FACTOR_FAILED", error=str(e)))
    
    def encrypt_env_factor(self, env_factor_data: Dict[str, str], root_key: str) -> Dict[str, str]:
        """
        加密环境因子
        
        功能：
        - 使用根密钥加密环境因子数据
        - 返回加密后的数据
        
        入参：
            env_factor_data: 环境因子数据字典
            root_key: 根密钥
        
        出参：
            加密后的环境因子数据字典
            {
                "env_factor_cipher": str
            }
        
        异常：
            EnvFactorGeneratorError: 加密失败时抛出
        """
        try:
            if not root_key:
                raise EnvFactorGeneratorError(get_exception_message(Messages.EnvFactorGenerator, "ROOT_KEY_CANNOT_BE_EMPTY"))
            
            # 使用根密钥生成加密密钥
            encryption_key = sha256_hash(root_key)
            
            # 拼接所有环境因子字段并加密
            env_factor_str = f"{env_factor_data['cpu_serial']}|{env_factor_data['disk_id']}|{env_factor_data['motherboard_serial']}|{env_factor_data['hardware_fingerprint']}"
            env_factor_cipher = sha256_hash(f"{env_factor_str}_{encryption_key}")
            
            encrypted_data = {
                "env_factor_cipher": env_factor_cipher
            }
            
            logger.debug("环境因子加密成功")
            return encrypted_data
        except Exception as e:
            error_msg = f"环境因子加密失败: {str(e)}"
            logger.error(error_msg)
            raise EnvFactorGeneratorError(get_exception_message(Messages.EnvFactorGenerator, "ENCRYPT_ENV_FACTOR_FAILED", error=str(e)))
    
    def store_env_factor_to_db(self, encrypted_data: Dict[str, str], db_handler) -> bool:
        """
        存储环境因子到数据库
        
        功能：
        - 单表模式 (SINGLE_INFO_UNIT=True): 存入 mgc_info_1 表
        - 多表模式: 存入 mgc_system_env 表
        
        入参：
            encrypted_data: 加密后的环境因子数据字典
            db_handler: 数据库处理器
        
        出参：
            True表示成功，False表示失败
        
        异常：
            EnvFactorGeneratorError: 存储失败时抛出
        """
        try:
            from mgc.config.database_config import DatabaseConfig as DC
            from mgc.config.enum_config import ConfigItem, ConfigDefaults
            config_dict = DC.get_config()
            single_info_unit = config_dict.get(ConfigItem.SINGLE_INFO_UNIT, ConfigDefaults.SINGLE_INFO_UNIT)
            
            if single_info_unit:
                return
            else:
                db_type = getattr(db_handler, 'database_type', 'mysql')
                
                check_sql = "SELECT COUNT(*) as count FROM mgc_system_env"
                result = db_handler.execute_query(check_sql)
                
                if result and result[0]['count'] > 0:
                    raise EnvFactorGeneratorError(get_exception_message(Messages.EnvFactorGenerator, "MGC_SYSTEM_ENV_TABLE_ALREADY_HAS_DATA"))
                
                if db_type == "sqlcipher":
                    insert_sql = """
                    INSERT INTO mgc_system_env (
                        env_factor_cipher,
                        created_at
                    ) VALUES (?, CURRENT_TIMESTAMP)
                    """
                    params = (encrypted_data['env_factor_cipher'],)
                else:
                    insert_sql = """
                    INSERT INTO mgc_system_env (
                        id,
                        env_factor_cipher,
                        created_at
                    ) VALUES (GEN_ID(GEN_MGC_ENV_ID, 1), %s, CURRENT_TIMESTAMP)
                    """
                    params = (encrypted_data['env_factor_cipher'],)
            
            db_handler.execute_update(insert_sql, params)
            
            logger.debug("环境因子已成功存储到数据库")
            return True
        except Exception as e:
            error_msg = f"环境因子存储失败: {str(e)}"
            logger.error(error_msg)
            raise EnvFactorGeneratorError(get_exception_message(Messages.EnvFactorGenerator, "STORE_ENV_FACTOR_FAILED", error=str(e)))
    
    def generate_and_store_env_factor(self, root_key: str, db_handler) -> Dict[str, str]:
        """
        生成并存储初始环境因子（完整流程）
        
        功能：
        - 采集硬件信息
        - 生成初始环境因子
        - 加密环境因子
        - 存储到mgc_system_env表
        
        入参：
            root_key: 根密钥
            db_handler: 数据库处理器
        
        出参：
            初始环境因子数据字典
            {
                "cpu_serial": str,
                "disk_id": str,
                "motherboard_serial": str,
                "hardware_fingerprint": str
            }
        
        异常：
            EnvFactorGeneratorError: 生成或存储失败时抛出
        """
        try:
            # 生成初始环境因子
            env_factor_data = self.generate_initial_env_factor()
            
            # 加密环境因子
            encrypted_data = self.encrypt_env_factor(env_factor_data, root_key)
            
            # 存储到数据库
            self.store_env_factor_to_db(encrypted_data, db_handler)
            
            return env_factor_data
        except Exception as e:
            error_msg = f"生成并存储初始环境因子失败: {str(e)}"
            logger.error(error_msg)
            raise EnvFactorGeneratorError(get_exception_message(Messages.EnvFactorGenerator, "GENERATE_AND_STORE_ENV_FACTOR_FAILED", error=str(e)))
