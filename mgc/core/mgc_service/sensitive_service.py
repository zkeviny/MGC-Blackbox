"""
敏感信息托管模块

功能：
- 提供敏感信息托管功能
- 包括AI API Key托管、代码敏感信息托管、托管清单查询等
- 所有敏感信息加密存储，支持脱敏展示

依赖：
- src/core/mgc_service/crypto_service.py（加密解密服务）
- src/core/mgc_service/database/database_handler.py（数据库操作）
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import secrets
import traceback

from mgc.core.mgc_service.crypto_service import CryptoService, CryptoError
from mgc.core.mgc_service.database.database_handler import DatabaseHandler, DatabaseError
from mgc.core.mgc_service.script_execution_service import ScriptExecutionService
from mgc.service.script_executor_service import ScriptExecutorService
from mgc.config.i18n_config import get_exception_message, Messages
from mgc.utils.log_utils import logger


class SensitiveServiceError(Exception):
    """敏感信息托管异常"""
    pass


class SensitiveService:
    """敏感信息托管服务"""

    @staticmethod
    def _mask_alias(alias: str) -> str:
        """
        脱敏别名

        功能：
        - 保留前2位和后2位
        - 中间用星号代替
        - 如果别名长度小于等于4，则全部显示

        入参：
            alias: 原始别名

        出参：
            str: 脱敏后的别名
        """
        if len(alias) <= 4:
            return alias
        return alias[:2] + '*' * (len(alias) - 4) + alias[-2:]

    def __init__(self, crypto_service: CryptoService, database_handler: DatabaseHandler, script_executor: ScriptExecutorService = None):
        """
        初始化敏感信息托管服务

        入参：
            crypto_service: 加密解密服务
            database_handler: 数据库处理器
            script_executor: 脚本执行服务（可选）
        """
        self.crypto_service = crypto_service
        self.database_handler = database_handler
        self.script_executor = script_executor
        self._sqlcipher_single = self._check_sqlcipher_single_mode()
        self.weight_param = crypto_service.weight_param
        self.dynamic_salts = crypto_service.dynamic_salts
        self.environment_cipher = self._get_environment_cipher()
        # phase4 方案C：internal_token 仅在主进程内存（不写 environ 到子进程启动环境）
        # 子进程通过 stdin payload 内部传递，专门用于 /sensitive/unseal_for_child RPC 鉴权
        # 与 mgc_api_token 隔离（mgc_api_token 泄露 ≠ 可远程 unseal）
        self._internal_token: str = secrets.token_hex(32)  # 64 字符 hex
        # phase3：ScriptExecutionService（统一执行入口）
        self.script_execution_service = ScriptExecutionService(
            sensitive_service=self,
            script_executor=script_executor,
        )
        # 把 internal_token 注入到 ScriptExecutionService（payload 构造时用）
        self.script_execution_service._internal_token = self._internal_token
        # phase3：把 sensitive_service 引用传给 script_executor（payload 构造时用）
        if script_executor is not None:
            script_executor._sensitive_service_ref = self

    def bind_script_executor(self, script_executor: ScriptExecutorService) -> None:
        """延迟绑定 script_executor（phase3 修复）。

        当 SensitiveService 创建时 script_executor 还未初始化，可调用本方法
        后续注入（通常在 build_services() 内部晚一步初始化时）。

        同时把 sensitive_service 引用传给 script_executor。
        """
        self.script_executor = script_executor
        self.script_execution_service.script_executor = script_executor
        script_executor._sensitive_service_ref = self
        logger.info("phase3: script_executor bound to sensitive_service")

    def set_api_info(self, port: int, token: str) -> None:
        """注入 mgc 主进程 HTTP API 信息（bootstrap 子进程 HTTP 调用主进程时用）。

        应在 mgc 主进程 HTTP 服务启动后调用一次。
        """
        self.script_execution_service.set_api_info(port, token)

    def _get_environment_cipher(self) -> str:
        """从数据库获取初始环境密文"""
        try:
            result = self.database_handler.execute_query(
                "SELECT info_plaintext FROM mgc_info_1 WHERE diff_1 = 'environment_cipher' LIMIT 1"
            )
            if result and result[0].get('info_plaintext'):
                return result[0]['info_plaintext']
            return None
        except Exception as e:
            logger.warning(f"_get_environment_cipher error: {e}")
            return None

    def _ensure_environment_cipher(self) -> str:
        """确保获取到环境密文，如果初始化时未获取到则尝试重新获取"""
        if self.environment_cipher:
            return self.environment_cipher
        return self._get_environment_cipher()

    def _check_sqlcipher_single_mode(self) -> bool:
        """检测是否为 SQLCipher 单表模式"""
        try:
            result = self.database_handler.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='mgc_info_1'"
            )
            exists = bool(result)
            logger.info(f"_check_sqlcipher_single_mode: mgc_info_1 exists = {exists}")
            return exists
        except Exception as e:
            logger.error(f"_check_sqlcipher_single_mode error: {e}")
            return False

    def _generate_account_password(self, info_type: str, info_owner: str,
                                     diff_1: str = None, diff_2: str = None, diff_3: str = None,
                                     ext_fields: dict = None) -> tuple:
        """
        生成虚拟账户和密码

        入参：
            info_type: 信息类型
            info_owner: 归属字段
            diff_1/2/3: 差异字段
            ext_fields: 扩展字段

        出参：
            tuple: (extract_account, extract_password)
        """
        from mgc.domain.crypto_layer import generate_info_cipher, extract_account_password

        info_cipher = generate_info_cipher(
            info_type=info_type,
            info_owner=info_owner,
            diff_1=diff_1,
            diff_2=diff_2,
            diff_3=diff_3,
            ext_fields=ext_fields,
            environment_cipher=self.environment_cipher,
            weight_param=self.weight_param,
            salts=self.dynamic_salts
        )

        account, password = extract_account_password(info_cipher, self.dynamic_salts)
        return (account, password)

    def _save_to_mgc_info_1(self, info_type: str = None, info_owner: str = None,
                              diff_1: str = None, diff_2: str = None, diff_3: str = None,
                              sensitive_type: str = None, content: str = None, **ext_fields) -> bool:
        """SQLCipher 单表模式：存入 mgc_info_1（支持更新）"""
        # 1.5.2 hotfix P0: 拒绝写入任何节点身份凭证（__NODE_PUB__ / node_priv / ...）
        # 统一通过 NODE_CREDENTIALS_REGISTRY 配置管理，新增凭证类型只需改 registry。
        from mgc.core.mgc_service.node_credentials_registry import (
            assert_writable_by_node_key_service,
        )
        assert_writable_by_node_key_service(info_type or sensitive_type)
        try:
            info_fields = {
                'info_type': info_type or sensitive_type or 'DEFAULT',
                'info_owner': info_owner,
                'diff_1': diff_1,
                'diff_2': diff_2,
                'diff_3': diff_3,
                'environment_cipher': self.environment_cipher,
                'weight_param': self.weight_param,
                'salts': self.dynamic_salts,
                **{k: v for k, v in ext_fields.items() if v}
            }

            account, password = self._generate_account_password(
                info_type=info_fields['info_type'],
                info_owner=info_fields['info_owner'],
                diff_1=diff_1,
                diff_2=diff_2,
                diff_3=diff_3
            )

            cipher = self.crypto_service.encrypt_text(content, info_fields)

            ext_keys = [k for k in info_fields.keys() if k.startswith('ext') and info_fields.get(k)]
            
            check_sql = """
                SELECT id FROM mgc_info_1 
                WHERE info_type = ? AND info_owner = ? 
                AND (diff_1 = ? OR (diff_1 IS NULL AND ? IS NULL))
                AND (diff_2 = ? OR (diff_2 IS NULL AND ? IS NULL))
                AND (diff_3 = ? OR (diff_3 IS NULL AND ? IS NULL))
                LIMIT 1
            """
            existing = self.database_handler.execute_query(
                check_sql, (info_type, info_owner, diff_1, diff_1, diff_2, diff_2, diff_3, diff_3)
            )

            base_update = "info_plaintext = ?, extract_account = ?, extract_password = ?"
            base_params = [cipher, account, password]
            for ek in ext_keys:
                base_update += f", {ek} = ?"
                base_params.append(info_fields.get(ek, ''))
            
            if existing:
                where_clause = "info_type = ? AND info_owner = ? AND (diff_1 = ? OR (diff_1 IS NULL AND ? IS NULL)) AND (diff_2 = ? OR (diff_2 IS NULL AND ? IS NULL)) AND (diff_3 = ? OR (diff_3 IS NULL AND ? IS NULL))"
                update_sql = f"UPDATE mgc_info_1 SET {base_update} WHERE {where_clause}"
                params = base_params + [info_type, info_owner, diff_1, diff_1, diff_2, diff_2, diff_3, diff_3]
                self.database_handler.execute_update(update_sql, tuple(params))
            else:
                columns = "extract_account, extract_password, info_plaintext, info_type, info_owner, diff_1, diff_2, diff_3" + ("," + ",".join(ext_keys) if ext_keys else "")
                placeholders = "?, ?, ?, ?, ?, ?, ?, ?" + (", ?" * len(ext_keys) if ext_keys else "")
                insert_sql = f"INSERT INTO mgc_info_1 ({columns}) VALUES ({placeholders})"
                params = [account, password, cipher, info_type, info_owner, diff_1, diff_2, diff_3]
                for ek in ext_keys:
                    params.append(info_fields.get(ek, ''))
                self.database_handler.execute_update(insert_sql, tuple(params))
            return True
        except Exception as e:
            raise SensitiveServiceError(f"存入失败: {e}")

    def _get_from_mgc_info_1(self, key_alias: str, sensitive_type: str = None) -> list:
        """SQLCipher 单表模式：从 mgc_info_1 取出（返回原密文）"""
        try:
            info_type = sensitive_type or 'DEFAULT'
            
            account, password = self._generate_account_password(
                info_type=info_type,
                info_owner=key_alias,
                diff_1=sensitive_type,
                diff_2=key_alias,
                diff_3=None
            )

            query = "SELECT info_plaintext FROM mgc_info_1 WHERE extract_account = ? AND extract_password = ?"
            params = (account, password)
            if sensitive_type:
                query += " AND diff_1 = ?"
                params = (account, password, sensitive_type)
            result = self.database_handler.execute_query(query, params)
            return [row['info_plaintext'] for row in result] if result else []
        except Exception as e:
            raise SensitiveServiceError(f"取出失败: {e}")

    def save_api_key(self, info_type: str, info_owner: str,
                       diff_1: str = None, diff_2: str = None, diff_3: str = None,
                       api_key: str = None) -> bool:
        """
        保存AI API Key

        功能：
        - SQLCipher单表模式：存入mgc_info_1
        - 多表模式：存入mgc_sensitive_info和mgc_ai_providers表

        入参：
            key_alias: 密钥别名
            info_type: 信息类型
            info_owner: 信息归属人
            diff_1/2/3: 差异字段
            api_key: API Key

        出参：
            bool: True表示保存成功，False表示保存失败
        """
        try:
            if not info_type or not info_owner or not api_key:
                raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "PARAMETERS_CANNOT_BE_EMPTY"))

            if hasattr(self, '_sqlcipher_single') and self._sqlcipher_single:
                return self._save_to_mgc_info_1(
                    info_type=info_type,
                    info_owner=info_owner,
                    diff_1=diff_1,
                    diff_2=diff_2,
                    diff_3=diff_3,
                    sensitive_type="API_KEY",
                    content=api_key
                )
            
            return False

        except DatabaseError as e:
            raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "DATABASE_OPERATION_FAILED") + f" Details: {str(e)}")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "SAVE_AI_API_KEY_FAILED") + f" | Exception: {str(e)} | Traceback: {tb}")

    def check_duplicate(self, info_type: str = None, info_owner: str = None,
                          diff_1: str = None, diff_2: str = None, diff_3: str = None) -> dict:
        """检查是否存在重复记录"""
        try:
            if not self._sqlcipher_single:
                return {"exists": False, "duplicates": []}

            query = "SELECT info_type, info_owner, diff_1, diff_2, diff_3 FROM mgc_info_1 WHERE info_type = ? AND info_owner = ?"
            params = (info_type, info_owner)

            if diff_1:
                query += " AND diff_1 = ?"
                params = params + (diff_1,)
            else:
                query += " AND (diff_1 IS NULL OR diff_1 = '')"

            if diff_2:
                query += " AND diff_2 = ?"
                params = params + (diff_2,)
            else:
                query += " AND (diff_2 IS NULL OR diff_2 = '')"

            if diff_3:
                query += " AND diff_3 = ?"
                params = params + (diff_3,)

            result = self.database_handler.execute_query(query, params)

            if result:
                duplicates = []
                for r in result:
                    duplicates.append({
                        "info_type": r["info_type"],
                        "info_owner": r["info_owner"],
                        "diff_1": r.get("diff_1"),
                        "diff_2": r.get("diff_2"),
                        "diff_3": r.get("diff_3")
                    })
                return {"exists": True, "duplicates": duplicates}

            return {"exists": False, "duplicates": []}
        except Exception as e:
            logger.error(f"check_duplicate error: {e}")
            return {"exists": False, "duplicates": []}

    def save_code_sensitive(self, info_type: str = None, info_owner: str = None,
                              diff_1: str = None, diff_2: str = None, diff_3: str = None,
                              content: str = None, **ext_fields) -> bool:
        """保存代码敏感信息"""
        try:
            if not content:
                raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "PARAMETERS_CANNOT_BE_EMPTY"))

            if self._sqlcipher_single:
                result = self._save_to_mgc_info_1(
                    info_type=info_type,
                    info_owner=info_owner,
                    diff_1=diff_1,
                    diff_2=diff_2,
                    diff_3=diff_3,
                    sensitive_type="CODE",
                    content=content,
                    **ext_fields
                )
                return result

            with open(r'd:\MirginCipher\debug.log', 'a') as f:
                f.write(f"[DEBUG] save_code_sensitive: _sqlcipher_single={self._sqlcipher_single}, returning False\n")
            return False

        except DatabaseError as e:
            logger.error(f"DatabaseError in save_code_sensitive: {e}")
            raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "DATABASE_OPERATION_FAILED"))
        except SensitiveServiceError:
            raise
        except Exception as e:
            logger.error(f"Exception in save_code_sensitive: {e}")
            logger.error(traceback.format_exc())
            raise SensitiveServiceError(f"Save failed: {type(e).__name__}: {str(e)}")

    def get_info_list(
        self,
        info_type: str = None,
        info_owner: str = None,
        diff_1: str = None,
        diff_2: str = None,
        diff_3: str = None
    ) -> List[Dict[str, any]]:
        """
        Get sensitive info list with optional fuzzy search.

        Args:
            info_type: info type (optional, LIKE)
            info_owner: info owner (optional, LIKE)
            diff_1: diff field 1 (optional, LIKE)
            diff_2: diff field 2 (optional, LIKE)
            diff_3: diff field 3 (optional, LIKE)

        Returns:
            List of info metadata without content.
        """
        try:
            if not self._sqlcipher_single:
                return []

            conditions = ["info_owner != 'SYSTEM'"]
            params = []

            if info_type:
                conditions.append("info_type LIKE ?")
                params.append(f"%{info_type}%")
            if info_owner:
                conditions.append("info_owner LIKE ?")
                params.append(f"%{info_owner}%")
            if diff_1:
                conditions.append("diff_1 LIKE ?")
                params.append(f"%{diff_1}%")
            if diff_2:
                conditions.append("diff_2 LIKE ?")
                params.append(f"%{diff_2}%")
            if diff_3:
                conditions.append("diff_3 LIKE ?")
                params.append(f"%{diff_3}%")

            query = f"SELECT info_type, info_owner, diff_1, diff_2, diff_3, ext01, ext02, ext03, ext04, ext05, ext06, ext07, ext08, ext09, ext10, ext11, ext12, ext13, ext14, ext15, ext16, ext17, ext18, ext19, ext20, ext21, ext22, ext23, ext24, ext25, ext26, ext27, ext28, ext29, ext30 FROM mgc_info_1 WHERE {' AND '.join(conditions)}"
            result = self.database_handler.execute_query(query, tuple(params))

            items = []
            for r in result:
                item = {
                    "info_type": r["info_type"],
                    "info_owner": r["info_owner"],
                    "diff_1": r["diff_1"],
                    "diff_2": r["diff_2"],
                    "diff_3": r["diff_3"]
                }
                for i in range(1, 31):
                    ext_key = f"ext{i:02d}"
                    if r.get(ext_key):
                        item[ext_key] = r[ext_key]
                items.append(item)
            return items
        except Exception as e:
            logger.error(f"get_info_list error: {e}")
            return []

    def get_sensitive_list(self) -> List[Dict[str, any]]:
        """
        获取托管清单

        功能：
        - SQLCipher单表模式：从mgc_info_1查询（返回解密后的明文）
        - 多表模式：从mgc_sensitive_info查询（脱敏）

        出参：
            list: 托管清单
        """
        try:
            if self._sqlcipher_single:
                result = self.database_handler.execute_query(
                    "SELECT diff_2 as key_alias, info_type, info_owner, diff_1, diff_2, diff_3 FROM mgc_info_1 WHERE diff_1 IN ('API_KEY', 'CODE')"
                )
                return [{"key_alias": r["key_alias"], "info_type": r["info_type"], "info_owner": r["info_owner"], "diff_1": r["diff_1"], "diff_2": r["diff_2"], "diff_3": r["diff_3"]} for r in result]
            
            result = self.database_handler.get_sensitive_list()

            sensitive_list = []
            for item in result:
                sensitive_list.append({
                    "key_alias": self._mask_alias(item['key_alias']),
                    "type": item['sensitive_type'],
                    "created_at": item['created_at'].strftime("%Y-%m-%d %H:%M:%S")
                })

            return sensitive_list

        except DatabaseError as e:
            raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "DATABASE_OPERATION_FAILED"))
        except Exception as e:
            raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "GET_HOSTING_LIST_FAILED"))

    def _delete_from_mgc_info_1(self, info_type: str = None, info_owner: str = None, diff_1: str = None, diff_2: str = None, diff_3: str = None) -> bool:
        """SQLCipher 单表模式：从 mgc_info_1 删除

        1.5.1 phase7:
        - info_type 可选（folder 删除场景：跨多种 info_type）
        - diff_1 / diff_3 不参与 folder 删除过滤（实测 diff_3 实际存的是真实路径字符串，非 None；folder 删除应只按 owner+diff_2 删）
        - diff_2 必填或可选（不传则按 owner 删所有）
        """
        # 1.5.2 hotfix P0: 拒绝删除任何节点身份凭证（__NODE_PUB__ / node_priv / ...）
        # 统一通过 NODE_CREDENTIALS_REGISTRY 配置管理。
        from mgc.core.mgc_service.node_credentials_registry import (
            assert_writable_by_node_key_service,
        )
        assert_writable_by_node_key_service(info_type)
        try:
            # 构建动态删除条件
            conditions = []
            params = []

            # 1.5.1 phase7: info_type 可选；空字符串/None 表示通配（folder 删除场景）
            if info_type:
                conditions.append("info_type = ?")
                params.append(info_type)

            if info_owner:
                conditions.append("info_owner = ?")
                params.append(info_owner)

            # 1.5.1 phase7: diff_1 不参与 folder 删除过滤（保留入参仅为接口兼容）
            # 1.5.1 phase7: diff_3 不参与 folder 删除过滤（实测 diff_3 实际存的是真实路径字符串）

            if diff_2:
                conditions.append("diff_2 = ?")
                params.append(diff_2)
            # else: 不传 diff_2 → 仅按 owner 删除（高危，理论上不该走到）

            sql = "DELETE FROM mgc_info_1 WHERE " + " AND ".join(conditions)
            affected = self.database_handler.execute_update(sql, tuple(params))
            return True
        except Exception as e:
            raise SensitiveServiceError(f"删除失败: {e}")

    def _update_mgc_info_1(self, key_alias: str, new_content: str) -> bool:
        """SQLCipher 单表模式：更新 mgc_info_1"""
        try:
            cipher = self.crypto_service.encrypt_text(new_content)
            self.database_handler.execute_update(
                "UPDATE mgc_info_1 SET info_plaintext = ? WHERE diff_2 = ?",
                (cipher, key_alias)
            )
            return True
        except Exception as e:
            raise SensitiveServiceError(f"更新失败: {e}")

    def get_sensitive(self, info_type: str = None, info_owner: str = None,
                       diff_1: str = None, diff_2: str = None, diff_3: str = None) -> List[Dict[str, any]]:
        """
        获取敏感信息（按类型+归属+差异查询）

        入参：
            info_type: 信息类型
            info_owner: 信息归属人
            diff_1/2/3: 差异字段

        出参：
            list: 敏感信息列表（含解密后的明文 plain_text）
        """
        try:
            import inspect
            caller_frame = inspect.currentframe().f_back
            caller_class = caller_frame.f_locals.get('self', None)
            caller_name = type(caller_class).__name__ if caller_class else ""
            whitelist = ["NodeKeyService", "SealService", "SensitiveService"]
            is_whitelisted = caller_name in whitelist
            
            conditions = []
            params = []

            if not is_whitelisted and info_owner == "SYSTEM":
                return []
            
            if info_type:
                conditions.append("info_type = ?")
                params.append(info_type)
            if info_owner:
                conditions.append("info_owner = ?")
                params.append(info_owner)
            if diff_1:
                conditions.append("diff_1 = ?")
                params.append(diff_1)
            if diff_2:
                conditions.append("diff_2 = ?")
                params.append(diff_2)
            if diff_3:
                conditions.append("diff_3 = ?")
                params.append(diff_3)

            if not conditions:
                raise SensitiveServiceError("查询条件不能为空")

            query = f"SELECT diff_2 as key_alias, info_type, info_owner, diff_1, diff_2, diff_3, info_plaintext, ext01, ext02, ext03, ext04, ext05, ext06, ext07, ext08, ext09, ext10, ext11, ext12, ext13, ext14, ext15, ext16, ext17, ext18, ext19, ext20, ext21, ext22, ext23, ext24, ext25, ext26, ext27, ext28, ext29, ext30 FROM mgc_info_1 WHERE {' AND '.join(conditions)}"
            result = self.database_handler.execute_query(query, tuple(params))

            sensitive_list = []
            for r in result:
                try:
                    info_fields = {
                        'info_type': r['info_type'],
                        'info_owner': r['info_owner'],
                        'diff_1': r['diff_1'],
                        'diff_2': r['diff_2'],
                        'diff_3': r['diff_3'],
                        'environment_cipher': self.environment_cipher,
                        'weight_param': self.weight_param,
                        'salts': self.dynamic_salts
                    }
                    plain_text = self.crypto_service.decrypt_text(r["info_plaintext"], info_fields)
                except CryptoError as e:
                    raise SensitiveServiceError(f"decrypt failed: {str(e)}")
                except Exception as e:
                    raise SensitiveServiceError(f"查询失败: {e}")
                
                item = {
                    "key_alias": r["key_alias"],
                    "info_type": r["info_type"],
                    "info_owner": r["info_owner"],
                    "diff_1": r["diff_1"],
                    "diff_2": r["diff_2"],
                    "diff_3": r["diff_3"],
                    "plain_text": plain_text
                }
                for i in range(1, 31):
                    ext_key = f"ext{i:02d}"
                    val = r.get(ext_key)
                    if val:
                        item[ext_key] = val
                sensitive_list.append(item)

            return sensitive_list
        except Exception as e:
            raise SensitiveServiceError(f"查询失败: {e}")

    def _query_node_pub(self) -> List[Dict[str, Any]]:
        try:
            query = "SELECT info_type, info_owner, info_plaintext FROM mgc_info_1 WHERE info_type = '__NODE_PUB__' AND info_owner = '__NODE_PUB__'"
            result = self.database_handler.execute_query(query)
            if result:
                return [{"plain_text": result[0]["info_plaintext"]}]
            return []
        except Exception:
            return []

    def _auto_generate_node_key(self) -> List[Dict[str, Any]]:
        try:
            from mgc.core.mgc_service.node_key_service import NodeKeyService
            nks = NodeKeyService(sensitive_service=self)
            pub = nks.ensure_public_key()
            # 1.5.4：顺延确保 default_node_pub/priv 也在 SQLCipher 中。
            # 老节点升级到 1.5.4 时首次调用本方法时会自动写入共享默认密钥；
            # 新节点初始化时也会一并写入。与 ensure_public_key 一样，
            # 异常自然上抛——上层（如 api_router）已 try/except NodeKeyServiceError。
            try:
                nks.ensure_default_keys()
            except Exception as _e:
                logger.warning(f"ensure_default_keys skipped: {_e}")
            return self._query_node_pub()
        except Exception:
            return []

    def delete_sensitive(self, info_type: str, info_owner: str, diff_1: str = None, diff_2: str = None, diff_3: str = None) -> bool:
        """
        删除敏感信息

        功能：
        - SQLCipher单表模式：从mgc_info_1删除
        - 多表模式：从mgc_sensitive_info删除

        入参：
            info_type: 信息类型
            info_owner: 密钥别名
            diff_1, diff_2, diff_3: 额外区分字段

        出参：
            bool: True表示删除成功，False表示删除失败

        异常：
            SensitiveServiceError: 删除失败时抛出
        """
        try:
            if not info_owner:
                raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "KEY_ALIAS_CANNOT_BE_EMPTY"))

            if self._sqlcipher_single:
                return self._delete_from_mgc_info_1(info_type, info_owner, diff_1, diff_2, diff_3)

            # 1.5.1 phase7: 多表模式下透传 diff_1/2/3 到 delete_sensitive_info
            # 之前 key_alias=info_owner 会误删整个 owner 下所有记录；folder 删除场景下不安全
            affected_rows = self.database_handler.delete_sensitive_info(key_alias, diff_1, diff_2, diff_3)

            if affected_rows == 0:
                raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "KEY_ALIAS_DOES_NOT_EXIST", key_alias=key_alias))

            return True

        except DatabaseError as e:
            raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "DATABASE_OPERATION_FAILED"))
        except SensitiveServiceError:
            raise
        except Exception as e:
            raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "DELETE_SENSITIVE_INFO_FAILED"))

    def update_sensitive(self, key_alias: str, new_content: str) -> bool:
        """
        更新敏感信息

        功能：
        - SQLCipher单表模式：更新mgc_info_1（加密存储）
        - 多表模式：更新mgc_sensitive_info

        入参：
            key_alias: 密钥别名
            new_content: 新的敏感信息内容

        出参：
            bool: True表示更新成功，False表示更新失败

        异常：
            SensitiveServiceError: 更新失败时抛出
        """
        try:
            if not key_alias or not new_content:
                raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "PARAMETERS_CANNOT_BE_EMPTY"))

            if self._sqlcipher_single:
                return self._update_mgc_info_1(key_alias, new_content)

            existing_info = self.database_handler.get_sensitive_info(key_alias)
            if not existing_info:
                raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "KEY_ALIAS_DOES_NOT_EXIST", key_alias=key_alias))

            affected_rows = self.database_handler.update_sensitive_info(key_alias, new_content)

            if affected_rows == 0:
                raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "UPDATE_KEY_ALIAS_FAILED", key_alias=key_alias))

            return True

        except DatabaseError as e:
            raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "DATABASE_OPERATION_FAILED"))
        except SensitiveServiceError:
            raise
        except Exception as e:
            raise SensitiveServiceError(get_exception_message(Messages.SensitiveService, "UPDATE_SENSITIVE_INFO_FAILED"))

    def run_script(self, info_type: str = None, info_owner: str = None,
                   diff_1: str = None, diff_2: str = None, diff_3: str = None,
                   runtime_ext02: str = None) -> dict:
        """
        运行脚本

        入参：
            info_type: 信息类型
            info_owner: 脚本名称
            diff_1/2/3: 差异字段
            runtime_ext02: 运行时参数（可选，覆盖存储的ext02）

        出参：
            dict: {pid, status, output, error}
        """
        try:
            if not self.script_executor:
                return {"status": "failed", "error": "Script executor not initialized"}

            sensitive_data = self.get_sensitive(
                info_type=info_type,
                info_owner=info_owner,
                diff_1=diff_1,
                diff_2=diff_2,
                diff_3=diff_3
            )

            if not sensitive_data:
                return {"status": "failed", "error": "Script not found"}

            record = sensitive_data[0]
            ext01 = record.get("ext01", "")
            ext08_str = record.get("ext08", "")
            ext03_str = record.get("ext03", "")
            has_ext08 = bool(ext08_str)
            # 1.5.1 BUG-C：sealed 脚本（ext03 非空）也走 phase3 新路径，
            # 因为老 Popen + stdin 源码模式无法同时传 args 给 python3
            # （python3 会把 --xxx 当成自己的选项 reject）。
            # phase3 用 `python -m mgc.bootstrap` 通过 stdin payload 传脚本源码 + args，
            # 完全规避 Python 解释器的参数限制。
            # 1.5.1 phase4 路由收敛：所有脚本执行统一走 phase3 新路径。
            # 原因：老 Popen 路径在 ext02 非空时 python3 会把 --xxx 当成自己的选项
            # 拒绝并 exit 1，导致 v5/v6/v7 等明文脚本"返回 started 但 defunct"的回归 BUG。
            # phase3 用 in-memory exec + sys.argv 注入完全规避该问题。
            # 老路径（ScriptExecutorService.execute_script）代码保留作 fallback，
            # 待 PMC 评审通过后废弃。
            has_sealed = bool(ext03_str)
            use_phase3 = True  # phase4：路由收敛，全走新路径

            if use_phase3:
                logger.info(
                    f"run_script: {diff_3} has ext08={has_ext08} sealed={has_sealed}, "
                    f"routing through ScriptExecutionService"
                )
                return self.script_execution_service.execute(
                    info_type=info_type,
                    info_owner=info_owner,
                    diff_1=diff_1,
                    diff_2=diff_2,
                    diff_3=diff_3,
                    runtime_ext02=runtime_ext02,
                )

            # 老路径：ext08 为空且非 sealed
            script_content = record.get("plain_text", "")
            ext02 = runtime_ext02 or record.get("ext02", "")

            if not ext01:
                return {"status": "failed", "error": "ext01 (startup command) is required"}

            result = self.script_executor.execute_script(
                script_content=script_content,
                ext01=ext01,
                ext02=ext02
            )

            return result

        except Exception as e:
            logger.error(f"Error in run_script: {e}")
            return {"status": "failed", "error": str(e)}

            raise SensitiveServiceError(f"List providers failed: {e}")
