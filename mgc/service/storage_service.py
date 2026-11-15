"""
存储服务（SQLCipher 版本）

功能：
- SQLCipher 数据库操作（双层加密架构）
- 整合查询清单管理、密钥模板管理
- 实现AI/Agent交互接口

2026年4月1日调整：
- 移除 MySQL，迁移到 SQLCipher
- 双层加密：第一层 AES_KYE_N + 第二层 SQLCipher
- 不再使用 root 权限

依赖：
- src/domain/storage_layer/（查询清单、密钥模板）
- src/domain/crypto_layer/（加密模块）
- src/core/database/（SQLCipher 操作层）
- src/config/enum_config.py（枚举配置）
"""

import json
import os
import time
import logging
import hashlib
import uuid
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path

from mgc.domain.storage_layer import QueryListHandler, SecretsHandler
from mgc.domain.crypto_layer import (
    hardware_fingerprint,
    dynamic_salt,
    weight_generator,
    CognitionEncryptor,
    generate_environment_cipher,
    generate_mgc_user1_password,
    sha256_core
)
from mgc.domain.judge_layer import CipherMatcher
from mgc.models.cognition_model import CognitionRule
from mgc.config.enum_config import ConfigDefaults, OperationType
from mgc.config.path_config import PROJECT_ROOT
from mgc.core.installer.root_key_encryptor import RootKeyEncryptor


class QueryListItem:
    """查询清单条目对象
    
    用于封装查询清单中的字典数据，提供属性访问
    """
    def __init__(self, data: dict):
        self.item_id = data.get("item_id", "")
        self.info_type = data.get("info_type", "")
        self.info_owner = data.get("info_owner", "")
        self.info_plaintext = data.get("info_plaintext", "")
        self.diff1 = data.get("diff1", "")
        self.diff2 = data.get("diff2", "")
        self.diff3 = data.get("diff3", "")
        self.ext_fields = data.get("ext_fields", {})

logger = logging.getLogger(__name__)


class StorageService:
    """存储服务（SQLCipher 版本）

    2026年4月1日调整：迁移到 SQLCipher 双层加密架构
    - 第一层：AES_KYE_N 加密（密钥 = 信息密文）
    - 第二层：SQLCipher 数据库加密（密钥 = AES_KYE_2）
    """

    def __init__(self):
        """初始化存储服务（SQLCipher 版本）"""
        self.query_list_handler = QueryListHandler()
        self.secrets_handler = SecretsHandler()
        self.hardware_info = None
        self.weight_parameter = None
        self.salts = None
        self.environment_cipher = None
        self.cipher_matcher = CipherMatcher()
        self.cognition_encryptor = None

    def initialize_database(self, agent_uuid: str, personal_key: str, weight_param: int) -> Dict[str, any]:
        """
        初始化数据库（SQLCipher 版本）

        2026年4月1日调整：SQLCipher 双层加密

        入参：
            agent_uuid: Agent UUID
            personal_key: 个人密钥
            weight_param: 权重参数（必须）

        出参：
            初始化结果

        双层加密流程：
        1. 采集硬件信息，生成 AES_KEY_2
        2. 初始化 SQLCipher 数据库（AES_KEY_2 作为密钥）
        3. 生成初始环境密文
        4. 存储初始化数据（个性化权重、初始环境密文等）
        """
        if not weight_param or weight_param <= 0:
            raise ValueError("weight_param 不能为空，必须传入有效的权重参数")

        try:
            self.hardware_info = hardware_fingerprint.get_hardware_info()
            logger.debug("Hardware info collection completed")

            hardware_hash = hardware_fingerprint.get_hardware_fingerprint()
            logger.debug("Hardware fingerprint hash generated")

            from mgc.domain.crypto_layer.dynamic_salt import extract_dynamic_salts
            self.salts = extract_dynamic_salts(personal_key, weight_param)
            logger.debug("Dynamic salt calculation completed")

            self.weight_parameter = weight_param
            logger.debug("Weight parameter configured")

            env_cipher_obj = generate_environment_cipher(
                cpu_serial=self.hardware_info[0],
                disk_id=self.hardware_info[1],
                salts=self.salts
            )
            self.environment_cipher = env_cipher_obj[0] if env_cipher_obj else ""
            logger.debug(f"Initial environment cipher: {self.environment_cipher[:16]}...")

            from mgc.domain.crypto_layer.root_key_crypto import get_aes_key_2
            aes_key_2 = get_aes_key_2(personal_key, str(weight_param))
            logger.debug("AES_KEY_2 generated (using personal_key + weight_param)")

            from mgc.core.database.sqlcipher_handler import SQLCipherHandler
            SQLCipherHandler.set_aes_key_2(aes_key_2)
            SQLCipherHandler.initialize()
            logger.debug("SQLCipher database initialized")
            
            from mgc.core.mgc_service.database.database_handler import DatabaseHandler
            db_handler = DatabaseHandler()
            db_handler.init_database_tables()
            logger.debug("Database tables initialized")

            from mgc.domain.crypto_layer.root_key_crypto import encrypt_weight_param
            encrypted_weight_param = encrypt_weight_param(str(weight_param), aes_key_2)
            
            check_weight_param_sql = "SELECT COUNT(*) as count FROM mgc_info_1 WHERE diff_1 = 'weight_param'"
            weight_param_result = db_handler.execute_query(check_weight_param_sql)
            
            if weight_param_result and weight_param_result[0]['count'] > 0:
                logger.info("weight_param already exists, skip")
            else:
                db_handler.execute_update(
                    "INSERT INTO mgc_info_1 (extract_account, extract_password, info_plaintext, info_type, info_owner, diff_1) VALUES (?, ?, ?, ?, ?, ?)",
                    ("weight_param", encrypted_weight_param[:32], encrypted_weight_param, "SYSTEM", "SYSTEM", "weight_param")
                )
                logger.debug("Weight parameter stored (encrypted)")

            check_env_cipher_sql = "SELECT COUNT(*) as count FROM mgc_info_1 WHERE diff_1 = 'environment_cipher'"
            env_cipher_result = db_handler.execute_query(check_env_cipher_sql)
            
            if env_cipher_result and env_cipher_result[0]['count'] > 0:
                logger.info("environment_cipher already exists, skip")
            else:
                db_handler.execute_update(
                    "INSERT INTO mgc_info_1 (extract_account, extract_password, info_plaintext, info_type, info_owner, diff_1) VALUES (?, ?, ?, ?, ?, ?)",
                    ("environment_cipher", self.environment_cipher[:32], self.environment_cipher, "SYSTEM", "SYSTEM", "environment_cipher")
                )
                logger.info("environment_cipher success")

            self.cognition_encryptor = CognitionEncryptor(salts=self.salts)
            logger.debug("CognitionEncryptor initialized")

            query_list_data = self.query_list_handler.initialize_query_list(agent_uuid)
            logger.debug("Query list initialized")

            # Migration key no longer saved to file
            # migration_key = self._generate_migration_key(personal_key, self.hardware_info)
            # self._save_migration_key(migration_key)
            # logger.debug("Migration key generated and saved")
            
            try:
                root_key = f"{personal_key}_{weight_param}"
                migrate_key = personal_key + str(weight_param)
                hardware_fp = hardware_fingerprint.get_hardware_fingerprint()

                encryptor = RootKeyEncryptor()
                encryptor.encrypt_and_store_root_key(
                    root_key=root_key,
                    migrate_key=migrate_key,
                    hardware_fingerprint=hardware_fp,
                    db_handler=db_handler
                )
                logger.debug("ROOT_KEY encrypted and stored")
            except Exception as e:
                logger.debug(f"ROOT_KEY storage failed: {e}")
            
            try:
                from mgc.key_storage.db_key_manager import save as save_db_key
                save_db_key(personal_key, str(weight_param))
                logger.debug("DB_KEY.json saved")
            except Exception as e:
                logger.debug(f"DB_KEY.json save failed: {e}")
            
            try:
                from mgc.core.auth.token_manager import get_token_manager
                token_mgr = get_token_manager()
                token_mgr.generate_token()
                token_mgr.save_token()
                logger.debug("MGC token generated")
            except Exception as e:
                logger.debug(f"MGC token generation failed: {e}")

            return {
                "code": 200,
                "message": "SQLCipher 数据库初始化成功",
                "data": {
                    "agent_uuid": agent_uuid,
                    "hardware_hash": hardware_hash,
                    "weight_parameter": self.weight_parameter
                }
            }

        except Exception as e:
            logger.debug(f"Storage service initialization failed: {e}")
            return {
                "code": 500,
                "message": f"存储服务初始化失败: {str(e)}",
                "data": {}
            }

    def _generate_migration_key(self, personal_key: str, hardware_info) -> str:
        """
        生成迁移密钥

        入参：
            personal_key: 个人密钥
            hardware_info: 硬件信息（可能是元组或字典）

        出参：
            迁移密钥
        """
        if isinstance(hardware_info, tuple):
            hardware_dict = {
                "cpu_serial": hardware_info[0] if len(hardware_info) > 0 else "",
                "disk_id": hardware_info[1] if len(hardware_info) > 1 else "",
                "motherboard_serial": hardware_info[2] if len(hardware_info) > 2 else ""
            }
        else:
            hardware_dict = hardware_info
        combined_data = personal_key + json.dumps(hardware_dict, sort_keys=True)
        migration_key = hashlib.sha256(combined_data.encode('utf-8')).hexdigest()
        return migration_key

    def _save_migration_key(self, migration_key: str) -> None:
        """
        保存迁移密钥到文件

        入参：
            migration_key: 迁移密钥
        """
        # Disabled - migration key no longer saved to file
        pass
        # key_file = get_migrate_key_file()
        # os.makedirs(os.path.dirname(key_file), exist_ok=True)
        #
        # with open(key_file, 'w', encoding='utf-8') as f:
        #     f.write(f"迁移密钥: {migration_key}\n")
        #     f.write("\n")
        #     f.write("重要提示：\n")
        #     f.write("1. 请妥善保管此文件，切勿泄露\n")
        #     f.write("2. 环境变更时需要此密钥进行认证\n")
        #     f.write("3. 丢失此密钥可能导致无法迁移数据\n")

    def _calculate_info_cipher(self, info_type: str, info_owner: str,
                               diff1: str, diff2: str, diff3: str,
                               ext_fields: Dict) -> str:
        """
        计算信息密文（完整信息哈希密文）

        2026年4月1日调整：根据算法5规则

        规则：
        - 类型(重复个性化权重第9个数的次数)
        - 初始环境密文(重复个性化权重第"动态盐2"次)
        - 归属字段
        - 差异1(重复"动态盐3"次)
        - 差异2(重复"动态盐4"次)
        - 差异3(重复"动态盐5"次)
        - ext01~ext30(按顺序循环重复动态盐3、4、5、6、7、8、9、10、2、1)

        执行 SHA-256 哈希

        入参：
            info_type: 信息类型
            info_owner: 归属字段
            diff1/diff2/diff3: 差异字段
            ext_fields: 扩展字段

        出参：
            str: 信息密文（64位十六进制）
        """
        from mgc.domain.crypto_layer import sha256_hash

        if not self.environment_cipher:
            raise ValueError("初始环境密文未初始化")

        if not self.weight_parameter or not self.salts:
            raise ValueError("权重参数或动态盐未初始化")

        components = []

        weight_str = str(self.weight_parameter)
        repeat_9 = int(weight_str[8]) if len(weight_str) >= 9 else 1
        if repeat_9 == 0:
            repeat_9 = 1
        components.append(info_type * repeat_9)

        repeat_salt2 = self.salts.get('salt2', 1)
        components.append(self.environment_cipher * repeat_salt2)

        components.append(info_owner)

        repeat_salt3 = self.salts.get('salt3', 1)
        repeat_salt4 = self.salts.get('salt4', 1)
        repeat_salt5 = self.salts.get('salt5', 1)
        components.append(diff1 * repeat_salt3 if diff1 else "")
        components.append(diff2 * repeat_salt4 if diff2 else "")
        components.append(diff3 * repeat_salt5 if diff3 else "")

        ext_salt_cycle = [3, 4, 5, 6, 7, 8, 9, 10, 2, 1]
        sorted_ext = sorted(ext_fields.items())
        for i, (key, value) in enumerate(sorted_ext):
            repeat = self.salts.get(f"salt{ext_salt_cycle[i % 10]}", 1)
            if value:
                components.append(value * repeat)

        return sha256_hash("".join(components))

    def handle_request(self, request: Dict[str, any]) -> Dict[str, any]:
        """
        处理AI/Agent请求（业务逻辑层）

        入参：
            request: 请求对象（已通过接口层安全前置校验）

        出参：
            响应对象
        """
        try:
            request_id = request.get("request_id")
            agent_uuid = request.get("agent_uuid")
            operation_type = request.get("operation_type")
            params = request.get("params", {})

            trace_id = self._generate_trace_id()

            if operation_type == "add":
                return self._handle_add_operation(request_id, agent_uuid, params, trace_id)
            elif operation_type == "modify":
                return self._handle_modify_operation(request_id, agent_uuid, params, trace_id)
            elif operation_type == "delete":
                return self._handle_delete_operation(request_id, agent_uuid, params, trace_id)
            elif operation_type == "query":
                return self._handle_query_operation(request_id, agent_uuid, params, trace_id)
            else:
                return self._build_error_response(
                    request_id=request_id,
                    code=400,
                    message="不支持的操作类型",
                    fail_reason=f"操作类型: {operation_type}"
                )
        except Exception as e:
            logger.debug(f"Request processing failed: {e}")
            return self._build_error_response(
                request_id=request.get("request_id", ""),
                code=500,
                message="处理请求失败",
                fail_reason=str(e)
            )

    def _handle_add_operation(self, request_id: str, agent_uuid: str,
                            params: Dict[str, any], trace_id: str) -> Dict[str, any]:
        """
        处理添加操作（SQLCipher 版本）

        2026年4月1日调整：双层加密
        - 第一层：AES_KYE_N 加密（密钥 = 信息密文）
        - 第二层：SQLCipher 数据库加密

        入参：
            request_id: 请求ID
            agent_uuid: Agent UUID
            params: 参数
            trace_id: 追踪ID

        出参：
            响应对象
        """
        try:
            info_type = params.get("info_type", "default")
            info_owner = params.get("info_owner", "")
            info_plaintext = params.get("info_plaintext", "")
            diff1 = params.get("diff1", "")
            diff2 = params.get("diff2", "")
            diff3 = params.get("diff3", "")
            ext_fields = params.get("ext_fields", {})

            if not info_owner or not info_plaintext:
                return self._build_error_response(
                    request_id=request_id,
                    code=400,
                    message="参数缺失",
                    fail_reason="info_owner和info_plaintext不能为空"
                )

            cognition_rule = CognitionRule(
                rule_id=str(uuid.uuid4()),
                rule_type=info_type,
                content=info_plaintext,
                info_owner=info_owner,
                info_type=info_type,
                operation=OperationType.STORE,
                diff1=diff1,
                diff2=diff2,
                diff3=diff3,
                ext_fields=ext_fields
            )

            existing_items = self.query_list_handler.query_items(
                info_type=info_type,
                info_owner=info_owner
            )

            existing_rules = {}
            for item in existing_items:
                query_list_item = QueryListItem(item)
                existing_key = f"{query_list_item.info_type}:{query_list_item.info_owner}"
                existing_rules[existing_key] = CognitionRule(
                    rule_id=query_list_item.item_id,
                    rule_type=query_list_item.info_type,
                    content=query_list_item.info_plaintext,
                    info_owner=query_list_item.info_owner,
                    info_type=query_list_item.info_type,
                    operation=OperationType.STORE,
                    diff1=query_list_item.diff1,
                    diff2=query_list_item.diff2,
                    diff3=query_list_item.diff3,
                    ext_fields=query_list_item.ext_fields
                )

            duplicate_result = self.cipher_matcher.check_duplicate(
                cognition_rule=cognition_rule,
                existing_rules=existing_rules
            )

            if duplicate_result.is_duplicate:
                if duplicate_result.scenario == 4:
                    return self._build_error_response(
                        request_id=request_id,
                        code=400,
                        message="差异字段必填",
                        fail_reason=f"info_type+info_owner已存在，diff1必填"
                    )
                elif duplicate_result.scenario == 5:
                    return self._build_error_response(
                        request_id=request_id,
                        code=400,
                        message="差异字段必填",
                        fail_reason=f"diff1已重复，diff2必填"
                    )
                elif duplicate_result.scenario == 6:
                    return self._build_error_response(
                        request_id=request_id,
                        code=400,
                        message="差异字段必填",
                        fail_reason=f"diff2已重复，diff3必填"
                    )
                elif duplicate_result.scenario == 3:
                    return self._build_error_response(
                        request_id=request_id,
                        code=409,
                        message="信息已存在",
                        fail_reason="完全匹配，拒绝存入"
                    )

            info_cipher = self._calculate_info_cipher(
                info_type, info_owner, diff1, diff2, diff3, ext_fields
            )

            from mgc.domain.crypto_layer.aes_key_n import encrypt_with_aes_key_n
            ciphertext = encrypt_with_aes_key_n(info_plaintext, info_cipher)

            storage_unit = self.cognition_encryptor.encrypt(cognition_rule, agent_uuid="")
            extract_account = storage_unit.extract_account
            extract_password = storage_unit.extract_password

            from mgc.core.database.sqlcipher_handler import SQLCipherHandler
            record_id = SQLCipherHandler.insert_info(
                info_plaintext=ciphertext,
                diff_1=diff1,
                diff_2=diff2,
                diff_3=diff3,
                ext_fields=ext_fields
            )

            return self._build_success_response(
                request_id=request_id,
                data={
                    "item_id": str(record_id),
                    "extract_account": extract_account,
                    "extract_password": extract_password
                }
            )
        except Exception as e:
            logger.debug(f"Add operation failed: {e}")
            return self._build_error_response(
                request_id=request_id,
                code=500,
                message="添加操作失败",
                fail_reason=str(e)
            )

    def _handle_modify_operation(self, request_id: str, agent_uuid: str,
                               params: Dict[str, any], trace_id: str) -> Dict[str, any]:
        """
        处理修改操作

        入参：
            request_id: 请求ID
            agent_uuid: Agent UUID
            params: 参数
            trace_id: 追踪ID

        出参：
            响应对象
        """
        try:
            connection = self.db_pool.get_connection()
            try:
                item_id = params.get("item_id")
                item_name = params.get("item_name")
                item_value = params.get("item_value")

                # 调用 query_list_handler 修改条目（使用正确的参数）
                # 注意：query_list_handler 的 modify_item 方法需要 item_id, info_owner, info_type, agent_uuid
                self.query_list_handler.modify_item(
                    item_id=item_id,
                    info_owner=item_name,  # 使用 item_name 作为 info_owner
                    info_type="default",  # 使用默认类型
                    agent_uuid=agent_uuid
                )

                self.db_initializer.update_info(
                    connection=connection,
                    item_id=item_id,
                    item_name=item_name,
                    item_value=item_value
                )

                return self._build_success_response(
                    request_id=request_id,
                    data={"item_id": item_id}
                )
            finally:
                connection.close()
        except Exception as e:
            logger.debug(f"Update operation failed: {e}")
            return self._build_error_response(
                request_id=request_id,
                code=500,
                message="修改操作失败",
                fail_reason=str(e)
            )

    def _handle_delete_operation(self, request_id: str, agent_uuid: str,
                               params: Dict[str, any], trace_id: str) -> Dict[str, any]:
        """
        处理删除操作

        入参：
            request_id: 请求ID
            agent_uuid: Agent UUID
            params: 参数
            trace_id: 追踪ID

        出参：
            响应对象
        """
        try:
            connection = self.db_pool.get_connection()
            try:
                item_id = params.get("item_id")

                # 调用 query_list_handler 删除条目（使用正确的参数）
                self.query_list_handler.delete_item(
                    item_id=item_id,
                    agent_uuid=agent_uuid
                )

                self.db_initializer.delete_info(
                    connection=connection,
                    item_id=item_id
                )

                return self._build_success_response(
                    request_id=request_id,
                    data={"item_id": item_id}
                )
            finally:
                connection.close()
        except Exception as e:
            logger.debug(f"Delete operation failed: {e}")
            return self._build_error_response(
                request_id=request_id,
                code=500,
                message="删除操作失败",
                fail_reason=str(e)
            )

    def _handle_query_operation(self, request_id: str, agent_uuid: str,
                               params: Dict[str, any], trace_id: str) -> Dict[str, any]:
        """
        处理查询操作（SQLCipher 版本）

        2026年4月1日调整：双层解密
        - 第一层：SQLCipher 数据库解密
        - 第二层：AES_KYE_N 解密（密钥 = 信息密文）

        入参：
            request_id: 请求ID
            agent_uuid: Agent UUID
            params: 参数
            trace_id: 追踪ID

        出参：
            响应对象
        """
        try:
            extract_account = params.get("item_id")
            extract_password = params.get("extract_password", "")

            info_type = params.get("info_type", "")
            info_owner = params.get("info_owner", "")
            diff1 = params.get("diff1", "")
            diff2 = params.get("diff2", "")
            diff3 = params.get("diff3", "")
            ext_fields = params.get("ext_fields", {})

            info_cipher = self._calculate_info_cipher(
                info_type, info_owner, diff1, diff2, diff3, ext_fields
            )

            from mgc.core.database.sqlcipher_handler import SQLCipherHandler
            records = SQLCipherHandler.query_all()

            matched_record = None
            for record in records:
                stored_diff1 = record.get("diff_1", "")
                stored_diff2 = record.get("diff_2", "")
                stored_diff3 = record.get("diff_3", "")

                if (stored_diff1 == diff1 and stored_diff2 == diff2 and
                    stored_diff3 == diff3):
                    matched_record = record
                    break

            if not matched_record:
                return self._build_error_response(
                    request_id=request_id,
                    code=404,
                    message="信息不存在",
                    fail_reason="未找到匹配记录"
                )

            from mgc.domain.crypto_layer.aes_key_n import decrypt_with_aes_key_n
            ciphertext = matched_record.get("info_plaintext", "")
            plaintext = decrypt_with_aes_key_n(ciphertext, info_cipher)

            return self._build_success_response(
                request_id=request_id,
                data={"info_plaintext": plaintext}
            )
        except Exception as e:
            logger.debug(f"Query operation failed: {e}")
            return self._build_error_response(
                request_id=request_id,
                code=500,
                message="查询操作失败",
                fail_reason=str(e)
            )

    def _generate_trace_id(self) -> str:
        """
        生成追踪ID

        出参：
            追踪ID
        """
        return f"trace-{int(time.time())}"

    def _build_success_response(self, request_id: str, data: Dict[str, any]) -> Dict[str, any]:
        """
        构建成功响应

        入参：
            request_id: 请求ID
            data: 响应数据

        出参：
            响应对象
        """
        return {
            "request_id": request_id,
            "code": 200,
            "message": "操作成功",
            "data": data
        }

    def _build_error_response(self, request_id: str, code: int,
                            message: str, fail_reason: str = "") -> Dict[str, any]:
        """
        构建错误响应

        入参：
            request_id: 请求ID
            code: 错误码
            message: 错误消息
            fail_reason: 失败原因

        出参：
            响应对象
        """
        return {
            "request_id": request_id,
            "code": code,
            "message": message,
            "data": {},
            "fail_reason": fail_reason
        }