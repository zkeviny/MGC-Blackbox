"""
API路由模块

功能：
- 注册所有API路由
- 定义统一的入参和返回格式
- 处理参数校验和异常处理

依赖：
- FastAPI（轻量级、高性能、异步支持）
- Pydantic（参数校验）
- src/core/mgc_service/mgc_core_service.py（MGC核心服务）
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import httpx

from mgc.config.i18n_config import get_api_message
from mgc.service.storage_service import StorageService
from mgc.service.script_executor_service import ScriptExecutorService
from mgc.service.script_save_orchestrator import enrich_script_fields
from mgc.service.runtime_env_checker import RuntimeWarning, check as _runtime_env_check
from mgc.core.mgc_service.crypto_service import CryptoService, CryptoError
from mgc.core.mgc_service.sensitive_service import SensitiveService, SensitiveServiceError
from mgc.core.mgc_service.sealed_payload_parser import (
    apply_sealed_payload,
    build_capsule_payload,
    build_stored_meta,
    parse_sealed_payload,
    resolve_output_dir,
    write_capsule_json,
)
from mgc.domain.logging.operation_log_manager import get_operation_log_manager
from mgc.core.auth.token_manager import get_token_manager

# === 1.5.2 hotfix Bug A 修复（PM 决策 2026-09-26）===
# 后缀→平台白名单。仅含 detect_script_platform 已能产出 run_command 的脚本语言。
# .js / .zsh 在 1.5.2 不支持，不进表。优先级：shebang > 后缀 > pattern。
_SUFFIX_TO_PLATFORM = {
    ".py":   "python",
    ".sh":   "bash",
    ".bash": "bash",
    ".ps1":  "powershell",
    ".bat":  "bat",
    ".cmd":  "bat",
}


class APIRouterError(Exception):
    """API路由异常"""
    pass


def detect_script_platform(content: str, file_suffix: Optional[str] = None) -> Optional[str]:
    """Detect script platform

    Args:
        content: script content
        file_suffix: 可选，文件后缀（含 .，如 ".py"）。当 content 无 shebang 且
                     pattern 不足以推断时，作为兜底判断。
                     优先级：shebang > 后缀 > pattern。

    Returns:
        platform identifier: python3/python/bash/powershell/bat, or None
    """
    if not content:
        return None

    first_line = content.strip().split('\n')[0]

    if first_line.startswith('#!'):
        shebang = first_line[2:].lower()
        if 'python3' in shebang:
            return 'python3'
        elif 'python' in shebang:
            return 'python'
        elif 'bash' in shebang or '/sh' in shebang:
            return 'bash'
        elif 'powershell' in shebang or 'pwsh' in shebang:
            return 'powershell'
        elif 'cmd' in shebang:
            return 'bat'

    content_lower = content.lower()

    # === 1.5.2 hotfix Bug A 修复：re.search 真正匹配 regex；阈值 >=1 ===
    ps_patterns = [r'\$\w+', r'\b(get|set|new)-\w+', r'-eq\b', r'-ne\b']
    if sum(1 for p in ps_patterns if re.search(p, content_lower)) >= 2:
        return 'powershell'

    py_patterns = [r'\bdef\s+\w+\(', r'\bimport\s+\w+', r'\bclass\s+\w+:',
                   r'\bif\s+__name__', r'\bprint\s*\(', r'\belse\s*:']
    if sum(1 for p in py_patterns if re.search(p, content_lower)) >= 2:
        return 'python'

    sh_patterns = [r'\bif\s+\[', r'\bfor\s+\w+\s+in', r'\bwhile\s+',
                   r'\$\(', r'\$\w+', r'\becho\s+']
    if sum(1 for p in sh_patterns if re.search(p, content_lower)) >= 2:
        return 'bash'

    bat_patterns = [r'@echo\s+off', r'\bset\s+\w+=', r'%\w+%', r'\bgoto\s+']
    if sum(1 for p in bat_patterns if re.search(p, content_lower)) >= 2:
        return 'bat'

    # === 1.5.2 后缀兜底（PM 决策）：仅在 shebang + pattern 都未命中时启用 ===
    if file_suffix:
        suffix_norm = file_suffix.lower().strip()
        if suffix_norm in _SUFFIX_TO_PLATFORM:
            return _SUFFIX_TO_PLATFORM[suffix_norm]

    return None


def get_run_command(platform: str) -> str:
    """根据平台获取运行命令

    Args:
        platform: 平台标识符

    Returns:
        对应的运行命令
    """
    commands = {
        'python3': 'python3',
        'python': 'python',
        'bash': 'bash',
        'powershell': 'pwsh',
        'bat': 'cmd /c'
    }
    return commands.get(platform, platform)


class InitRequest(BaseModel):
    """初始化请求"""
    mode: str
    user_agreed: bool
    authorization_source: Optional[str] = None
    key_input_method: Optional[str] = None
    root_key: str
    migrate_key: str
    save_path: Optional[str] = None
    database_type: Optional[str] = None


class EncryptRequest(BaseModel):
    """加密请求"""
    mode: str
    content: str


class EncryptBatchRequest(BaseModel):
    """批量加密请求"""
    mode: str
    content: list


class DecryptRequest(BaseModel):
    """解密请求"""
    mode: str
    content: str


class DecryptBatchRequest(BaseModel):
    """批量解密请求"""
    mode: str
    content: list


class SensitiveSaveRequest(BaseModel):
    """敏感信息保存请求"""
    mode: Optional[str] = None
    info_type: Optional[str] = None
    info_owner: Optional[str] = None
    diff_1: Optional[str] = None
    diff_2: Optional[str] = None
    diff_3: Optional[str] = None
    api_key: Optional[str] = None
    content: Optional[str] = None
    update_if_exists: bool = False
    ext01: Optional[str] = None
    ext02: Optional[str] = None
    ext03: Optional[str] = None
    ext04: Optional[str] = None
    ext05: Optional[str] = None
    ext06: Optional[str] = None
    ext07: Optional[str] = None
    ext08: Optional[str] = None
    ext09: Optional[str] = None
    ext10: Optional[str] = None
    ext11: Optional[str] = None
    ext12: Optional[str] = None
    ext13: Optional[str] = None
    ext14: Optional[str] = None
    ext15: Optional[str] = None
    ext16: Optional[str] = None
    ext17: Optional[str] = None
    ext18: Optional[str] = None
    ext19: Optional[str] = None
    ext20: Optional[str] = None
    ext21: Optional[str] = None
    ext22: Optional[str] = None
    ext23: Optional[str] = None
    ext24: Optional[str] = None
    ext25: Optional[str] = None
    ext26: Optional[str] = None
    ext27: Optional[str] = None
    ext28: Optional[str] = None
    ext29: Optional[str] = None
    ext30: Optional[str] = None


class SensitiveGetRequest(BaseModel):
    """敏感信息获取请求"""
    info_type: Optional[str] = None
    info_owner: Optional[str] = None
    diff_1: Optional[str] = None
    diff_2: Optional[str] = None
    diff_3: Optional[str] = None
    action: Optional[str] = None
    ext02: Optional[str] = None
    ext04: Optional[str] = None  # node_pub for seal
    wait_result: Optional[bool] = False
    # PR-5 (1.5.0 phase2 / 技能授权): package / seal_package 必传输出目录
    output_dir: Optional[str] = None


class UnsealForChildRequest(BaseModel):
    """子进程 unseal RPC 请求（phase4 方案C）。

    专门用于 patched_run 在 bootstrap 子进程内调主进程 unseal sealed 脚本。
    通过 X-MGC-Internal-Token header 鉴权（与 mgc_api_token 隔离）。
    主进程 unseal 前强制 5+1 校验（同 owner + diff_1 + diff_2 + ext08.calls）。

    phase5+ 扩展：补传 target 完整 5 字段，让主进程能用 4 字段主键精确查 target，
    避免同 info_owner 多 diff_2 同名脚本的歧义（否则 DIFF2_MISMATCH 失败）。
    """
    # caller_ctx：bootstrap1 子进程的 ctx（patched_run 所在）
    caller_info_owner: str
    caller_diff_1: str = ""
    caller_diff_2: str = ""
    # ext08.calls（caller 的 callgraph，用于 5+1 校验 target 是否被授权）
    caller_ext08_calls: Optional[list] = None
    # 被 unseal 的脚本标识（target 完整身份，phase5+ 补全）
    target_diff_3: str
    target_info_type: str = "script"
    # ★ phase5+ 新增：target 完整身份（与 caller 同 diff_2 包内语义）
    target_info_owner: str = ""
    target_diff_1: str = ""
    target_diff_2: str = ""


class SensitiveUpdateRequest(BaseModel):
    """敏感信息更新请求"""
    key_alias: str
    new_content: str


class SensitiveDeleteRequest(BaseModel):
    """敏感信息删除请求"""
    info_type: str
    info_owner: str
    diff_1: Optional[str] = None
    diff_2: Optional[str] = None
    diff_3: Optional[str] = None


class MigrateRequest(BaseModel):
    """迁移请求"""
    mode: str
    migrate_key: str


class MigrateKeyModifyRequest(BaseModel):
    """迁移密钥修改请求"""
    mode: str
    old_migrate_key: str
    new_migrate_key: str


class CipherVerifyRequest(BaseModel):
    """密文校验请求"""
    mode: str
    content: str


class SkillUpdateRequest(BaseModel):
    """Skill版本更新请求"""
    mode: str
    action: str
    offline_mode: bool = False
    auto_update: bool = False
    backup_before_update: bool = True


class SkillHeartbeatRequest(BaseModel):
    """Skill心跳记录请求"""
    mode: str
    skill_name: str
    action: Optional[str] = None
    result: Optional[str] = None


class SkillUninstallRequest(BaseModel):
    """Skill卸载请求"""
    mode: str
    action: str
    backup_data: bool = True
    keep_config: bool = True


class APIRouterManager:
    """API路由管理器"""

    def __init__(self, mgc_core_service, crypto_service=None, sensitive_service=None,
                 migrate_service=None, status_service=None,
                 skills_manager=None, database_handler=None, update_service=None):
        """
        初始化API路由管理器

        入参：
            mgc_core_service: MGC核心服务实例
            crypto_service: 加密解密服务实例（可选）
            sensitive_service: 敏感信息托管服务实例（可选）
            migrate_service: 迁移授权服务实例（可选）
            status_service: 状态查询服务实例（可选）
            skills_manager: Skills管理器实例（可选）
            database_handler: 数据库处理器实例（可选，用于操作日志）
            update_service: 版本更新服务实例（可选）
        """
        self.mgc_core_service = mgc_core_service
        self.crypto_service = crypto_service
        self.sensitive_service = sensitive_service
        self.migrate_service = migrate_service
        self.status_service = status_service
        self.skills_manager = skills_manager
        self.database_handler = database_handler
        self.storage_service = StorageService()
        self.update_service = update_service
        
        self.operation_log_manager = get_operation_log_manager(crypto_service)
        self.token_manager = get_token_manager()
        self.token_validation_enabled = True
        
        self.script_executor = ScriptExecutorService()

        if self.sensitive_service and self.script_executor:
            # phase3：使用 bind_script_executor 同时更新 sensitive_service 和 script_execution_service
            if hasattr(self.sensitive_service, "bind_script_executor"):
                self.sensitive_service.bind_script_executor(self.script_executor)
            else:
                self.sensitive_service.script_executor = self.script_executor
        
        from mgc.utils.log_utils import logger
        logger.info(f"APIRouterManager received crypto_service: {type(crypto_service)}")
        
        self.router = APIRouter(prefix="/api/mgc")
        self._register_routes()
    
    def _validate_token(self, request) -> bool:
        """
        校验请求令牌
        
        入参：
            request: FastAPI 请求对象
            
        出参：
            True 表示校验通过，False 表示校验失败
        """
        import logging
        logger = logging.getLogger("MirginCipher")
        
        if not self.token_validation_enabled:
            logger.info("Token validation disabled, allowing request")
            return True
        
        token = request.headers.get("X-MGC-Token")
        if not token:
            logger.warning("Token missing in request headers")
            return False
        
        logger.debug(f"Token received: {token[:20] if token else 'None'}...")
        result = self.token_manager.validate_token(token)
        logger.debug(f"Token validation result: {result}")
        return result
    
    def _get_token_dependency(self):
        """
        获取 token 校验依赖函数（用于 FastAPI 依赖注入）
        """
        from fastapi import Request, HTTPException

        async def require_token(request: Request):
            if not self._validate_token(request):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or missing token",
                    headers={"X-Token-Hint": "Token path: ~/.mgc/database/mgc_black_box/.mgc_token"}
                )
            return True

        return require_token

    def _get_internal_token_dependency(self):
        """
        获取 internal_token 校验依赖（phase4 方案C）。

        用于 /sensitive/unseal_for_child RPC 鉴权：
        - 与 mgc_api_token 完全隔离（独立 header X-MGC-Internal-Token）
        - 仅 mgc 子进程内部使用，远程攻击者拿不到 internal_token
        - 即使 mgc_api_token 泄露，远程仍无法调 unseal RPC
        """
        from fastapi import Request, HTTPException

        async def require_internal_token(request: Request):
            provided_token = request.headers.get("X-MGC-Internal-Token", "")
            # 从 sensitive_service._internal_token 拿真实 token
            sensitive_service = getattr(self, "sensitive_service", None)
            if not sensitive_service:
                raise HTTPException(
                    status_code=500,
                    detail="sensitive_service not initialized"
                )
            expected_token = getattr(sensitive_service, "_internal_token", "")
            if not expected_token:
                raise HTTPException(
                    status_code=500,
                    detail="internal_token not generated"
                )
            if not provided_token or provided_token != expected_token:
                # 鉴权失败：返回 403（不要泄漏 expected_token 任何信息）
                raise HTTPException(
                    status_code=403,
                    detail="Invalid or missing internal token"
                )
            return True

        return require_internal_token
    
    def _register_routes(self):
        """注册所有API路由"""
        token_dep = self._get_token_dependency()
        internal_token_dep = self._get_internal_token_dependency()

        from fastapi import Depends

        # === Active endpoints ===
        self.router.add_api_route("/init", self._init, methods=["POST"], dependencies=[Depends(token_dep)])
        self.router.add_api_route("/init/silent", self._init_silent, methods=["POST"], dependencies=[Depends(token_dep)])
        self.router.add_api_route("/status", self._status, methods=["GET"])
        self.router.add_api_route("/service/start", self._service_start, methods=["POST"], dependencies=[Depends(token_dep)])
        self.router.add_api_route("/service/stop", self._service_stop, methods=["POST"])
        self.router.add_api_route("/sensitive/save", self._sensitive_save, methods=["POST"], dependencies=[Depends(token_dep)])
        self.router.add_api_route("/sensitive/get", self._sensitive_get, methods=["POST"], dependencies=[Depends(token_dep)])
        # 1.5.4 phase6：WebUI 用它做胶囊预解析，与 _sensitive_save 共用同一份规则
        self.router.add_api_route("/sensitive/parse_sealed", self._sensitive_parse_sealed, methods=["POST"], dependencies=[Depends(token_dep)])
        # phase4 方案C：子进程 unseal RPC（仅 internal_token 鉴权）
        self.router.add_api_route(
            "/sensitive/unseal_for_child",
            self._sensitive_unseal_for_child,
            methods=["POST"],
            dependencies=[Depends(internal_token_dep)],
        )
        self.router.add_api_route("/version/check", self._version_check, methods=["GET"])
        self.router.add_api_route("/heartbeat", self._heartbeat, methods=["POST"], dependencies=[Depends(token_dep)])

        # === Deprecated endpoints (reserved) ===
        # self.router.add_api_route("/encrypt", self._encrypt, methods=["POST"])
        # self.router.add_api_route("/encrypt/batch", self._encrypt_batch, methods=["POST"])
        # self.router.add_api_route("/decrypt", self._decrypt, methods=["POST"])
        # self.router.add_api_route("/decrypt/batch", self._decrypt_batch, methods=["POST"])
        # self.router.add_api_route("/sensitive/save/silent", self._sensitive_save_silent, methods=["POST"])
        # self.router.add_api_route("/sensitive/code/save", self._sensitive_code_save, methods=["POST"])
        # self.router.add_api_route("/sensitive/list", self._sensitive_list, methods=["GET"])
        self.router.add_api_route("/sensitive/delete", self._sensitive_delete, methods=["POST"], dependencies=[Depends(token_dep)])
        # self.router.add_api_route("/sensitive/update", self._sensitive_update, methods=["POST"])
        # self.router.add_api_route("/migrate", self._migrate, methods=["POST"])
        # self.router.add_api_route("/migrate/silent", self._migrate_silent, methods=["POST"])
        # self.router.add_api_route("/migrate-key/modify", self._migrate_key_modify, methods=["POST"])
        # self.router.add_api_route("/migrate-key/modify/silent", self._migrate_key_modify_silent, methods=["POST"])
        # self.router.add_api_route("/migrate-key/path", self._migrate_key_path, methods=["GET"])
        # self.router.add_api_route("/device", self._device, methods=["GET"])
        # self.router.add_api_route("/service/restart", self._service_restart, methods=["POST"])
        # self.router.add_api_route("/log", self._log, methods=["GET"])
        # self.router.add_api_route("/cipher/verify", self._cipher_verify, methods=["POST"])
        # self.router.add_api_route("/provider/add", self._provider_add, methods=["POST"])
        # self.router.add_api_route("/provider/update", self._provider_update, methods=["POST"])
        # self.router.add_api_route("/provider/delete", self._provider_delete, methods=["POST"])
        # self.router.add_api_route("/provider/list", self._provider_list, methods=["GET"])
        # self.router.add_api_route("/provider/get", self._provider_get, methods=["POST"])
        # self.router.add_api_route("/provider/verify", self._provider_verify, methods=["POST"])
        # self.router.add_api_route("/skill/update", self._skill_update, methods=["POST"])
        # self.router.add_api_route("/skill/version", self._skill_version, methods=["GET"])
        # self.router.add_api_route("/skill/heartbeat", self._skill_heartbeat, methods=["POST"])
        # self.router.add_api_route("/skill/stats", self._skill_stats, methods=["GET"])
        # self.router.add_api_route("/skill/uninstall", self._skill_uninstall, methods=["POST"])

    def _attach_to_core_service(self):
        """Attach router to MGC core service"""
        try:
            if not self.mgc_core_service:
                return
            self.mgc_core_service.include_router(self.get_router())
        except Exception:
            # Failure does not block initialization
            return

    @staticmethod
    def _parse_root_key(root_key: str) -> tuple:
        """
        解析根密钥与权重参数（统一口径）

        规则：
        - 允许格式：个人密钥_权重参数
        - 若解析失败，使用默认权重参数1000
        """
        from mgc.domain.crypto_layer.root_key_parser import parse_root_key
        return parse_root_key(root_key)

    def _ensure_crypto_services(self, root_key: str):
        """初始化CryptoService与SensitiveService（仅在缺失时）"""
        if self.crypto_service:
            return
        from mgc.domain.crypto_layer.root_key_parser import parse_root_key
        personal_key, weight_param = parse_root_key(root_key)
        if not personal_key:
            return
        self.crypto_service = CryptoService(personal_key, weight_param)
        if self.database_handler:
            self.sensitive_service = SensitiveService(self.crypto_service, self.database_handler)

    def get_router(self) -> APIRouter:
        """
        获取FastAPI路由对象

        出参：
            APIRouter: FastAPI路由对象
        """
        return self.router

    async def _init(self, request: InitRequest):
        """初始化MGC（弹框交互版）"""
        try:
            if not request.user_agreed:
                return {"code": 403, "msg": get_api_message("USER_NOT_AGREE_INSTALLATION"), "data": {}}

            from mgc.domain.crypto_layer.root_key_parser import parse_root_key
            personal_key, weight_param = parse_root_key(request.root_key)
            
            result = self.storage_service.initialize_database(
                agent_uuid="init_dialog",
                personal_key=personal_key,
                weight_param=weight_param
            )
            
            self._ensure_crypto_services(request.root_key)
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Initialization installation failed: {str(e)}")

    async def _init_silent(self, request: InitRequest):
        """初始化MGC（命令行静默版）"""
        try:
            if not request.user_agreed:
                return {"code": 403, "msg": get_api_message("USER_NOT_AGREE_INSTALLATION"), "data": {}}

            from mgc.domain.crypto_layer.root_key_parser import parse_root_key
            personal_key, weight_param = parse_root_key(request.root_key)
            
            result = self.storage_service.initialize_database(
                agent_uuid="init_silent",
                personal_key=personal_key,
                weight_param=weight_param
            )
            
            self._ensure_crypto_services(request.root_key)
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _sensitive_unseal_for_child(self, request: UnsealForChildRequest):
        """子进程 unseal RPC（phase4 方案C）。

        仅接受 X-MGC-Internal-Token 鉴权，强制 5+1 校验：
        - info_owner 一致
        - diff_1 一致
        - diff_2 一致
        - target_diff_3 在 caller_ext08_calls 中（callgraph 静态授权）

        通过后调用 sensitive_service.unseal_and_run 拿真明文（priv_key 在主进程内存）。

        Args:
            request: UnsealForChildRequest
                - caller_info_owner: caller 的 info_owner（patched_run 所在 bootstrap1）
                - caller_diff_1/2: caller 的 diff_1/2
                - caller_ext08_calls: caller 的 ext08.calls（callgraph list）
                - target_diff_3: 要 unseal 的脚本 diff_3

        Returns:
            {"code": 200, "data": "真明文"} 或 5+1 校验失败 200+错误码
        """
        try:
            # 1. 校验 caller_ctx 必要字段
            if not request.caller_info_owner:
                return {
                    "code": 400,
                    "msg": "MISSING_CALLER_CTX",
                    "hint": "caller_info_owner is required",
                    "data": {},
                }
            if not request.target_diff_3:
                return {
                    "code": 400,
                    "msg": "MISSING_TARGET",
                    "hint": "target_diff_3 is required",
                    "data": {},
                }
            if not self.sensitive_service:
                return {
                    "code": 500,
                    "msg": "SENSITIVE_SERVICE_NOT_INITIALIZED",
                    "data": {},
                }

            # 2. 拿 target record
            # ★ phase5+ 修复：用完整 4 字段主键查 target，避免同 info_owner 多 diff_2 同名脚本的歧义
            #   （之前只传 info_type + diff_3，会查到错 record 导致 5+1 diff_2 mismatch）
            target_records = self.sensitive_service.get_sensitive(
                info_type=request.target_info_type,
                info_owner=getattr(request, "target_info_owner", "") or "",
                diff_1=getattr(request, "target_diff_1", "") or "",
                diff_2=getattr(request, "target_diff_2", "") or "",
                diff_3=request.target_diff_3,
            )
            if not target_records:
                return {
                    "code": 404,
                    "msg": "TARGET_NOT_FOUND",
                    "hint": f"No script found with diff_3={request.target_diff_3}",
                    "data": {},
                }
            target_record = target_records[0]

            # 3. 5+1 校验
            # 4.1 owner 一致
            target_owner = target_record.get("info_owner", "")
            if target_owner != request.caller_info_owner:
                logger.warning(
                    f"[5+1] unseal_for_child owner mismatch: "
                    f"target_owner={target_owner} vs caller={request.caller_info_owner}"
                )
                return {
                    "code": 403,
                    "msg": "OWNER_MISMATCH",
                    "hint": "caller_info_owner does not match target owner",
                    "data": {},
                }

            # 4.2 diff_1 一致
            target_diff_1 = target_record.get("diff_1", "") or ""
            caller_diff_1 = request.caller_diff_1 or ""
            if target_diff_1 != caller_diff_1:
                logger.warning(
                    f"[5+1] unseal_for_child diff_1 mismatch: "
                    f"target={target_diff_1!r} vs caller={caller_diff_1!r}"
                )
                return {
                    "code": 403,
                    "msg": "DIFF1_MISMATCH",
                    "hint": "caller diff_1 does not match target diff_1",
                    "data": {},
                }

            # 4.3 diff_2 一致
            target_diff_2 = target_record.get("diff_2", "") or ""
            caller_diff_2 = request.caller_diff_2 or ""
            if target_diff_2 != caller_diff_2:
                logger.warning(
                    f"[5+1] unseal_for_child diff_2 mismatch: "
                    f"target={target_diff_2!r} vs caller={caller_diff_2!r}"
                )
                return {
                    "code": 403,
                    "msg": "DIFF2_MISMATCH",
                    "hint": "caller diff_2 does not match target diff_2",
                    "data": {},
                }

            # 4.4 ext08.calls 必须包含 target_diff_3（callgraph 静态授权）
            caller_calls = request.caller_ext08_calls or []
            target_in_calls = False
            for c in caller_calls:
                if isinstance(c, dict) and c.get("target_diff_3") == request.target_diff_3:
                    target_in_calls = True
                    break
            if not target_in_calls:
                logger.warning(
                    f"[5+1] unseal_for_child target not in caller ext08.calls: "
                    f"target={request.target_diff_3}, calls={caller_calls}"
                )
                return {
                    "code": 403,
                    "msg": "NOT_IN_CALLS",
                    "hint": f"target {request.target_diff_3} not in caller ext08.calls",
                    "data": {},
                }

            # 5. unseal（priv_key 仅主进程）
            try:
                # unseal_and_run 已在 sensitive_service 实现，传入 record 信息
                # 内部 unseal_and_run line 158 decrypt_with_node_priv
                from mgc.core.mgc_service.seal_service import SealService
                from mgc.core.mgc_service.node_key_service import (
                    get_or_init_node_key_service,
                )
                # 1.5.4 fix：sensitive_service 上没有 node_key_service 属性，必须 lazy-init
                # 否则 free mode unseal 找不到 default_node_priv → 必崩
                seal_svc = SealService(
                    sensitive_service=self.sensitive_service,
                    node_key_service=get_or_init_node_key_service(self.sensitive_service),
                )
                plain_text, _, _ = seal_svc.unseal_and_run({
                    "content": target_record.get("plain_text", ""),
                    "ext01": target_record.get("ext01", ""),
                    "ext03": target_record.get("ext03", ""),
                    "ext07": target_record.get("ext07", ""),
                    "ext09": target_record.get("ext09", ""),
                })
                if not plain_text:
                    return {
                        "code": 500,
                        "msg": "UNSEAL_FAILED",
                        "hint": "unseal returned empty content",
                        "data": {},
                    }
                # === 1.5.2 hotfix（PM 决策 2026-09-26）：同时返回 target 的 ext08 ===
                # 让 sealed loader 在 exec child 期间能切到 child 的边表，
                # 支持多层链式 import（A → B → C 全部识别）。
                # 向前兼容：旧 sealed_import_hook 1.5.1 期望 data 为字符串，
                # 通过 isinstance(data, str) 判断（hook 端做兼容）。
                target_ext08 = target_record.get("ext08", "") or ""
                return {
                    "code": 200,
                    "msg": "UNSEAL_OK",
                    "hint": "Decrypted for child process. Burn after use.",
                    "data": {
                        "plain_text": plain_text,
                        "ext08": target_ext08,
                    },
                }
            except Exception as e:
                logger.error(f"unseal_for_child unseal failed: {e}")
                return {
                    "code": 500,
                    "msg": "UNSEAL_FAILED",
                    "hint": str(e),
                    "data": {},
                }
        except Exception as e:
            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="UNSEAL_FOR_CHILD",
                    key_alias=request.target_diff_3 if request else "",
                    operation_result="FAILED",
                    info_owner=request.caller_info_owner if request else "",
                    fail_reason=str(e)
                )
            raise HTTPException(status_code=500, detail=str(e))

    async def _encrypt(self, request: EncryptRequest):
        """加密单条文本"""
        from mgc.utils.log_utils import logger
        import traceback
        try:
            logger.info(f"crypto_service in _encrypt: {type(self.crypto_service)}")
            
            if not self.crypto_service:
                logger.info("crypto_service is None!")
                return {"code": 500, "msg": get_api_message("ENCRYPTION_SERVICE_NOT_INITIALIZED"), "data": {}}

            cipher = self.crypto_service.encrypt_text(request.content)
            logger.debug(f"encrypt result: {cipher[:20]}...")  # Masked output

            # Skip operation logging to avoid SQLite thread safety issue
            # if self.database_handler:
            #     self.database_handler.insert_operation_log(
            #         operation_type="encrypt",
            #         operation_result="success"
            #     )

            return {"code": 200, "msg": get_api_message("ENCRYPTION_SUCCESSFUL"), "data": {"cipher": cipher}}
        except Exception as e:
            err_msg = f"Encrypt error: {type(e).__name__}: {str(e)}"
            logger.info(err_msg)
            logger.info(traceback.format_exc())
            # Skip operation logging to avoid SQLite thread safety issue
            # if self.database_handler:
            #     self.database_handler.insert_operation_log(
            #         operation_type="encrypt",
            #         operation_result="failed",
            #         error_message=str(e)
            #     )
            raise HTTPException(status_code=500, detail=str(e))

    async def _encrypt_batch(self, request: EncryptBatchRequest):
        """批量加密文本"""
        try:
            if not self.crypto_service:
                return {"code": 500, "msg": get_api_message("ENCRYPTION_SERVICE_NOT_INITIALIZED"), "data": {}}

            ciphers = self.crypto_service.encrypt_batch(request.content)

            # Skip operation logging to avoid SQLite thread safety issue
            # if self.database_handler:
            #     self.database_handler.insert_operation_log(
            #         operation_type="encrypt_batch",
            #         operation_result="success"
            #     )

            return {"code": 200, "msg": get_api_message("BATCH_ENCRYPTION_SUCCESSFUL"), "data": {"ciphers": ciphers}}
        except Exception as e:
            if self.database_handler:
                self.database_handler.insert_operation_log(
                    operation_type="encrypt_batch",
                    operation_result="failed",
                    error_message=str(e)
                )
            raise HTTPException(status_code=500, detail=str(e))

    async def _decrypt(self, request: DecryptRequest):
        """解密单条文本"""
        from mgc.utils.log_utils import logger
        try:
            logger.info(f"crypto_service in _decrypt: {type(self.crypto_service)}")
            
            if not self.crypto_service:
                return {"code": 500, "msg": get_api_message("ENCRYPTION_SERVICE_NOT_INITIALIZED"), "data": {}}

            plain = self.crypto_service.decrypt_text(request.content)
            logger.debug(f"decrypt result: {plain[:20]}...")  # Masked output

            # Skip operation logging to avoid SQLite thread safety issue
            # if self.database_handler:
            #     self.database_handler.insert_operation_log(
            #         operation_type="decrypt",
            #         operation_result="success"
            #     )

            return {"code": 200, "msg": get_api_message("DECRYPTION_SUCCESSFUL"), "data": {"plain": plain}}
        except Exception as e:
            if self.database_handler:
                self.database_handler.insert_operation_log(
                    operation_type="decrypt",
                    operation_result="failed",
                    error_message=str(e)
                )
            raise HTTPException(status_code=500, detail=str(e))

    async def _decrypt_batch(self, request: DecryptBatchRequest):
        """批量解密文本"""
        try:
            if not self.crypto_service:
                return {"code": 500, "msg": get_api_message("ENCRYPTION_SERVICE_NOT_INITIALIZED"), "data": {}}

            plains = self.crypto_service.decrypt_batch(request.content)

            # Skip operation logging to avoid SQLite thread safety issue
            # if self.database_handler:
            #     self.database_handler.insert_operation_log(
            #         operation_type="decrypt_batch",
            #         operation_result="success"
            #     )

            return {"code": 200, "msg": get_api_message("BATCH_DECRYPTION_SUCCESSFUL"), "data": {"plains": plains}}
        except Exception as e:
            if self.database_handler:
                self.database_handler.insert_operation_log(
                    operation_type="decrypt_batch",
                    operation_result="failed",
                    error_message=str(e)
                )
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def _build_run_warnings(entry: dict) -> list[dict]:
        """1.5.0: Compute runtime env-check warnings for a script entry.

        Returns a list of plain-dict warnings (suitable for JSON), or []
        if no issues / check skipped. Failure-tolerant (no exceptions).
        """
        try:
            warnings = _runtime_env_check(entry, deadline_sec=3.0)
        except Exception as e:
            import logging as _lg
            _lg.getLogger(__name__).debug("runtime env check failed: %s", e)
            return []
        return [
            {"code": w.code, "message": w.message, "details": w.details}
            for w in warnings
        ]

    @staticmethod
    def _format_warnings_hint(warnings: list[dict]) -> str:
        """Render a list of {code, message, details} entries as a single
        human-readable block suitable for the response 'hint' field.

        Format (one warning per line, no leading newline):
            Warnings:
            - [CODE] message (detail1, detail2)
        Empty input -> "".
        """
        if not warnings:
            return ""
        lines = []
        for w in warnings:
            if not isinstance(w, dict):
                continue
            code = w.get("code") or "WARNING"
            msg = w.get("message") or ""
            details = w.get("details") or []
            line = f"- [{code}] {msg}"
            if details:
                line += f" ({', '.join(str(d) for d in details)})"
            lines.append(line)
        if not lines:
            return ""
        return "Warnings:\n" + "\n".join(lines)

    @classmethod
    def _attach_warnings(cls, response: dict, warnings: list[dict]) -> dict:
        """Attach warnings to response['data']['warnings'] AND append a
        human-readable 'Warnings:' block to response['hint'] (idempotent).

        Existing hint content is preserved (newline-separated). Empty
        warnings input is a no-op.
        """
        if not warnings:
            return response
        data = response.setdefault("data", {})
        existing = data.get("warnings") or []
        data["warnings"] = existing + warnings
        # Append formatted warnings to hint so that downstream consumers
        # (e.g. Trae IDE's mcp_mgc-blackbox that bypasses mcp_server.py)
        # can still surface the advisory to the agent in human-readable form.
        warning_text = cls._format_warnings_hint(warnings)
        if warning_text:
            existing_hint = response.get("hint") or ""
            if existing_hint:
                response["hint"] = f"{existing_hint}\n{warning_text}"
            else:
                response["hint"] = warning_text
        return response

    @classmethod
    def _build_sealed_saved_entry(cls, rec: Dict[str, Any]) -> Dict[str, Any]:
        """1.6.0：构造密封包导入时 data.saved 中的一条记录。

        与 plain folder 分支的 folder_save_orchestrator._build_saved_entry
        字段风格对齐，但**内容按密封包语义**填充：

        - diff_3 / info_type / ext01 / ext02 / ext05 / ext06 / ext08 / ext10
          与普通文件夹一致；
        - 额外带 **info_owner**（记录实际生效的 owner = 包内原值）与
          **ext09**（密封模式：p2p mode / free mode / chain mode），
          让 agent 从返回值就能判断「用哪个 owner 查」+「这是哪种密封」；
        - **不含 ext03**（RSA 包裹的密钥材料）与 **ext07**（源节点公钥）：
          这两项属于密文材料，不该在导入回执里回显给 agent。

        Args:
            rec: 包内单条记录（含 meta + ext 字段）

        Returns:
            可直接放入 data.saved 的 dict
        """
        return {
            "diff_3": rec.get("diff_3", ""),
            "info_type": rec.get("info_type", ""),
            # 1.6.0：记录实际生效的 owner（密封包内记录级 owner 原样保留）
            "info_owner": rec.get("info_owner", ""),
            "ext01": rec.get("ext01", "") or "",
            "ext02": rec.get("ext02", "") or "",
            "ext05": rec.get("ext05", "") or "",
            "ext06": rec.get("ext06", "") or "",
            "ext08": rec.get("ext08", "") or "",
            # 1.6.0：密封模式标识（p2p mode / free mode / chain mode）
            "ext09": rec.get("ext09", "") or "",
            "ext10": rec.get("ext10", "") or "supported",
            "warnings": [],
        }

    @classmethod
    def _build_sealed_owner_warning(
        cls,
        passed_info_owner: str,
        sealed_records: list,
    ) -> list:
        """1.6.0：构造「包内记录级 owner 未被调用方 owner 覆盖」的 advisory warning。

        背景（.mgc_file 密封包导入）：
            密封包内每条记录保留其原始 info_owner，调用方传入的 info_owner
            只作用于「包组」层面（文件夹三元组），不写入记录级 owner。

            这是**设计如此**，不是疏漏——跨脚本密文执行（unseal_for_child）
            的 5+1 校验要求调用方与被调用脚本的 info_owner 完全一致，
            若导入时改写记录级 owner，import / from-import / subprocess
            三种跨脚本调用会全部 OWNER_MISMATCH 失败。

            但调用方（agent）传了新 owner 后接口仍返回成功，随后用新 owner
            查询得到 NOT_FOUND，容易误判「数据丢失」。本 warning 明确告知
            「你的 owner 没生效」以及「该用哪个 owner 查」。

        Args:
            passed_info_owner: 调用方传入的 info_owner
            sealed_records: 包内记录列表（每条含 info_owner）

        Returns:
            warning dict 列表（无异常情况返回空列表）
        """
        if not sealed_records:
            return []
        passed = str(passed_info_owner or "").strip()
        record_owners = sorted({
            str(rec.get("info_owner", "") or "") for rec in sealed_records
        })
        # 调用方没传 owner，或包内 owner 与传入 owner 完全一致 → 无需提示
        if not passed or record_owners == [passed]:
            return []
        return [{
            "code": "INFO_OWNER_NOT_APPLIED",
            "message": (
                f"Sealed package records keep their original info_owner "
                f"({record_owners}) — required for cross-script sealed execution "
                f"(the 5+1 check requires caller and target to share one "
                f"info_owner). The info_owner you passed ('{passed}') applies "
                f"to the package group only, NOT to the individual records. "
                f"Use mgc_find(info_owner='<original owner>') to locate the "
                f"imported records."
            ),
            "details": [
                f"passed_info_owner={passed}",
                f"record_info_owners={record_owners}",
            ],
        }]

    async def _sensitive_parse_sealed(self, request: Request):
        """1.5.4 phase6：密封胶囊预解析（供 WebUI Save 页预填表单用）。

        与 _sensitive_save 的前置解析共用 sealed_payload_parser，
        保证 WebUI 与 MCP / API 的识别结果不会出现差异。
        """
        try:
            body = await request.json()
            content = body.get("content", "") if isinstance(body, dict) else ""
            parsed = parse_sealed_payload(content)
            if not parsed:
                return {
                    "code": 200,
                    "msg": "NOT_SEALED_PAYLOAD",
                    "hint": "Content is not a sealed capsule.",
                    "data": {},
                }
            data = {
                "info_type": parsed["info_type"],
                "diff_1": parsed["diff_1"],
                "diff_2": parsed["diff_2"],
                "diff_3": parsed["diff_3"],
                "content": parsed["content"],
            }
            for i in range(1, 31):
                data[f"ext{i:02d}"] = parsed[f"ext{i:02d}"]
            # info_owner 单独返回，前端按"用户已填则不回填"规则自行决定
            data["capsule_info_owner"] = parsed["info_owner"]
            return {"code": 200, "msg": "SEALED_PAYLOAD_PARSED", "hint": "", "data": data}
        except Exception as e:
            return {"code": 400, "msg": "PARSE_FAILED", "hint": str(e), "data": {}}

    async def _sensitive_save(self, request: SensitiveSaveRequest):
        """保存敏感信息（交互版）"""
        try:
            if not self.sensitive_service:
                return {
                    "code": 500,
                    "msg": get_api_message("SENSITIVE_SERVICE_NOT_INITIALIZED"),
                    "hint": "Sensitive service not initialized. Please call /api/mgc/init with root key first.",
                    "data": {}
                }

            # PR-5 (1.5.0 phase2 / 技能授权): info_type=file 分发
            # - content 是 .mgc_file 路径 → 调 sealed_package_importer 批量入库
            # - content 是本机目录路径 → 调 folder_save_orchestrator 批量入库
            if request.info_type == "file" and request.content:
                return await self._sensitive_save_folder_or_sealed(request)

            # 1.5.4 phase6：密封胶囊自动解析。
            # mgc_seal 现在导出的 JSON 自带 identity / diff / ext 全字段，
            # 调用方（或 WebUI）把整段 JSON 塞进 content 即可，无需逐字段拆分。
            # 四条入口（mgc_save / mgc_save_file / WebUI Save / WebUI SaveFile）
            # 都在这里汇合，解析规则只有这一份。
            sealed_payload = None
            if request.content:
                sealed_payload = parse_sealed_payload(request.content)
                if sealed_payload:
                    apply_sealed_payload(request, sealed_payload)

            has_required = bool(request.info_owner and request.content)

            # 1.5.2 hotfix P0: 拒绝任何节点身份凭证（__NODE_PUB__ / node_priv / ...）的写操作
            # 统一通过 NODE_CREDENTIALS_REGISTRY 配置管理，新增凭证类型只需改 registry。
            from mgc.core.mgc_service.node_credentials_registry import is_node_credential
            if is_node_credential(request.info_type):
                return {
                    "code": 403,
                    "msg": "NODE_KEY_WRITE_PROTECTED",
                    "hint": f"'{request.info_type}' is system-managed and cannot be "
                            "modified via API. It is generated by NodeKeyService and "
                            "can be viewed via the WebUI Node Public Key page.",
                    "data": {}
                }

            if not has_required:
                return {
                    "code": 201,
                    "msg": "PARAM_REQUIRED",
                    "hint": "info_owner = ownership description (e.g. user's GitHub), content = sensitive content",
                    "data": {
                        "required_params": ["info_owner", "content"],
                        "optional_params": ["info_type", "diff_1", "diff_2", "diff_3", "ext01", "ext02", "update_if_exists"],
                        "param_hints": {
                            "info_owner": "Ownership description: e.g. user's GitHub / Amy's GitHub / my Aliyun",
                            "content": "Sensitive content",
                            "info_type": "Information type: password/token/api_key/phone/script/config (optional)",
                            "ext01": "Startup command for script (auto-detected if not provided)",
                            "ext02": "Startup arguments for script (optional; for scripts, ext02 can be omitted — MGC will auto-extract and assemble). Manual entry should be a JSON array string, e.g. '[\"--flag\", \"value\"]'.",
                            "update_if_exists": "Update if exists: true/false (default false)"
                        }
                    }
                }



            duplicate_check = self.sensitive_service.check_duplicate(
                info_type=request.info_type,
                info_owner=request.info_owner,
                diff_1=request.diff_1,
                diff_2=request.diff_2,
                diff_3=request.diff_3
            )

            if duplicate_check.get("exists") and not request.update_if_exists:
                return {
                    "code": 409,
                    "msg": "DUPLICATE_EXISTS",
                    "hint": "Entry exists. Add diff_1/diff_2/diff_3 to differentiate, or set update_if_exists=true to update.",
                    "data": {
                        "duplicate_fields": duplicate_check.get("duplicates", []),
                        "suggestion": "Add diff_1/diff_2/diff_3 to differentiate, or set update_if_exists=true to update."
                    }
                }

            # Auto-detect script platform and fill ext01
            # === 1.5.2 hotfix：传 file_suffix（基于 diff_3），shebang > 后缀 > pattern ===
            if not request.ext01:
                _suffix = Path(request.diff_3).suffix.lower() if request.diff_3 else None
                platform = detect_script_platform(request.content, file_suffix=_suffix)
                if platform:
                    request.ext01 = get_run_command(platform)

            # v1.4 新增: 静态解析 script 自动生成 ext02
            warning = None
            recognized_arg_names: list = []
            unrecognized_arg_names: list = []
            # ext03 非空 = 1.5.4+ 密封记录：content 是密文，任何静态分析都只会
            # 产出假数据（ext02 解析失败、ext05 空、ext06 fallback 成"全部平台"）。
            # 此时只信任调用方传入的 ext 字段，不做任何自动识别。
            is_sealed_capsule = bool(request.ext03)
            if request.info_type == "script" and not is_sealed_capsule:
                try:
                    from mgc.service.script_parser_service import parse_script_to_ext02
                    (
                        auto_ext02,
                        is_degraded,
                        degrade_reason,
                        has_dynamic_args,
                        recognized_arg_names,
                        unrecognized_arg_names,
                    ) = parse_script_to_ext02(request.content)
                    if auto_ext02 is not None:
                        # 解析器返回了非空 ext02（可能含部分动态默认）
                        if has_dynamic_args:
                            # 含动态 args → 保留用户值；用解析结果填充空白
                            # warning 始终发（提示用户重新存入可自动更新）
                            warning = "dynamic_args_detected"
                            # 用户未传 → 用 MGC 部分解析结果
                            if not request.ext02:
                                request.ext02 = auto_ext02
                            # else: 用户已传 → 保留用户值
                        else:
                            # 纯静态 args → MGC 自动覆盖用户值（需求 L68）
                            request.ext02 = auto_ext02
                            warning = "args_recognized"
                    else:
                        # 完全无法解析（无 add_argument / SyntaxError）
                        if has_dynamic_args:
                            # 检测到动态 → dynamic_args_detected
                            warning = "dynamic_args_detected"
                        else:
                            # 完全无 add_argument → args_not_recognized
                            warning = "args_not_recognized"
                        if not request.ext02:
                            request.ext02 = ""
                except Exception as parse_err:
                    # 解析器异常不影响主流程
                    if not request.ext02:
                        request.ext02 = ""
                    warning = "args_not_recognized"

            # 1.5.0: For info_type=script, auto-fill ext05/ext06 unless caller
            # explicitly provided them. Uses model_fields_set so that an explicit
            # empty string from the caller is preserved.
            _payload_for_orchestrator = {
                "info_type": request.info_type,
                "content": request.content,
                "ext01": request.ext01,
                "ext05": getattr(request, "ext05", None),
                "ext06": getattr(request, "ext06", None),
            }
            enrich_script_fields(_payload_for_orchestrator, request.model_fields_set)
            if request.info_type == "script" and not is_sealed_capsule:
                request.ext05 = _payload_for_orchestrator.get("ext05", "")
                request.ext06 = _payload_for_orchestrator.get("ext06", "")

            ext_fields = {}
            for i in range(1, 31):
                ext_key = f"ext{i:02d}"
                ext_value = getattr(request, ext_key, None)
                # ext05 / ext06 are managed by the orchestrator and must be
                # written even when empty (so update can clear stale values).
                if ext_key in ("ext05", "ext06"):
                    ext_fields[ext_key] = ext_value if ext_value is not None else ""
                elif ext_value:
                    ext_fields[ext_key] = ext_value

            self.sensitive_service.save_code_sensitive(
                info_type=request.info_type,
                info_owner=request.info_owner,
                diff_1=request.diff_1,
                diff_2=request.diff_2,
                diff_3=request.diff_3,
                content=request.content,
                **ext_fields
            )

            msg = "Updated successfully" if duplicate_check.get("exists") else "Save successful"
            hint = "Stored encrypted in MGC. Ready anytime."
            response_data: dict = {}
            # 1.5.0 (PR-7): 透传 args 识别结构化信息
            if request.info_type == "script" and (recognized_arg_names or unrecognized_arg_names):
                response_data["recognized_arg_names"] = recognized_arg_names
                response_data["unrecognized_arg_names"] = unrecognized_arg_names
            # 1.5.4 phase6：回显实际存入的元数据，让调用方确认 info / diff / ext
            # 都按预期落库，下次调用可直接照抄地址三元组，不必猜。
            # friction fix: 原先只在密封胶囊分支回填，普通 script 存不进来——
            # agent 存完不知道 diff_* 落在哪，只能猜。
            if request.info_type == "script" or sealed_payload:
                response_data["parsed_sealed_payload"] = bool(sealed_payload)
                response_data["stored_meta"] = build_stored_meta(request)
            response = {"code": 200, "msg": get_api_message("SAVE_SUCCESSFUL") if not duplicate_check.get("exists") else msg, "hint": hint, "data": response_data}
            if warning:
                response["warning"] = warning
            return response
        except Exception as e:
            import traceback
            import sys
            import tempfile
            
            debug_path = os.path.join(tempfile.gettempdir(), 'mgc_debug.log')
            
            # Write exception to debug file
            with open(debug_path, 'a') as f:
                f.write(f"[ERROR] _sensitive_save: {type(e).__name__}: {e}\n")
                f.write(traceback.format_exc())
            
            # Also print to stderr
            print(f"[ERROR] _sensitive_save: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc()
            
            raise HTTPException(status_code=500, detail=str(e))

    # ============================================================
    # PR-5 (1.5.0 phase2 / 技能授权) — folder / sealed package save
    # ============================================================

    async def _sensitive_save_folder_or_sealed(self, request: SensitiveSaveRequest):
        """PR-5: info_type=file 批量入库入口（plain folder / .mgc_file sealed package）。

        不走 duplicate_check / enrich_script_fields（folder_save_orchestrator
        内部已处理 enrich；sealed package 直存不 enrich）。

        评审 P5B 改造（2026-08-28）：
        - 删除 make_save_callback 复用，改为 save_folder_record 直调
        - sealed 分支：sealed=True（白名单 ext01/ext02/ext03/ext05/ext06/ext07）
        - folder 分支：folder_save_orchestrator.save_folder(payload, sensitive_service)
        """
        try:
            from mgc.service import folder_save_orchestrator, sealed_package_importer
            from mgc.service.record_save_helper import save_folder_record

            content = request.content or ""
            info_owner = request.info_owner or ""
            diff_1 = request.diff_1 or ""

            if not info_owner:
                return {
                    "code": 400,
                    "msg": "MISSING_REQUIRED_FIELDS",
                    "hint": "info_owner is required for folder / sealed package save",
                    "data": {"error": "MISSING_REQUIRED_FIELDS"},
                }

            # ---- 分支 1: .mgc_file 密封包导入 ----
            if content.endswith(".mgc_file"):
                parsed = sealed_package_importer.import_sealed_package(content)
                if parsed.get("code") != 200:
                    return parsed
                sealed_records = parsed.get("data", {}).get("records", [])
                saved = []
                failed = []
                for rec in sealed_records:
                    # sealed=True：白名单 ext01/ext02/ext03/ext05/ext06/ext07，绝不重新解析
                    res = save_folder_record(self.sensitive_service, rec, sealed=True)
                    if 200 <= res.get("code", 0) < 300:
                        # 1.6.0：saved 元素从裸字符串升级为 dict（与 plain folder
                        # 分支的 folder_save_orchestrator._build_saved_entry 对齐），
                        # 让 agent 直接从返回值读到记录实际生效的 info_owner
                        # （密封包内记录级 owner 原样保留，见下方 warning 说明），
                        # 不必再靠 mgc_find 试探。
                        saved.append(self._build_sealed_saved_entry(rec))
                    else:
                        failed.append({
                            "diff_3": rec.get("diff_3", ""),
                            "error": res.get("msg") or res.get("hint") or "save failed",
                        })

                # 1.6.0：包内记录级 owner 与调用方传入 owner 不一致时，
                # 给出 advisory warning（不改 code / 不改 saved 结构）。
                # 记录级 owner 原样保留是跨脚本密文执行（5+1 校验）的硬前提，
                # 不能改写；这里只是把「你的 owner 没生效 + 该用哪个 owner 查」
                # 明确告诉 agent，避免它误判数据丢失。
                owner_warnings = self._build_sealed_owner_warning(
                    request.info_owner, sealed_records
                )
                # 1.6.0：补 saved_diff3（List[str]），与 plain folder 分支对齐
                saved_diff3 = [r.get("diff_3", "") for r in saved]

                if failed and not saved:
                    resp = {
                        "code": 400,
                        "msg": "BATCH_PARTIAL_FAILURE",
                        "hint": f"All {len(failed)} sealed record(s) failed to import",
                        "data": {
                            "saved": saved,
                            "saved_diff3": saved_diff3,
                            "failed": failed,
                            "count": len(saved),
                        },
                    }
                    return self._attach_warnings(resp, owner_warnings)
                # P0-3: sealed package 成功时附 hint
                hint = "Sealed package imported. Please have the agent save the README.md to its skill manager for later invocation."
                if failed:
                    resp = {
                        "code": 200,
                        "msg": "BATCH_PARTIAL_SUCCESS",
                        "hint": f"Sealed package partially imported: {len(saved)} ok, {len(failed)} failed.",
                        "data": {
                            "saved": saved,
                            "saved_diff3": saved_diff3,
                            "failed": failed,
                            "count": len(saved),
                        },
                    }
                    return self._attach_warnings(resp, owner_warnings)
                resp = {
                    "code": 200,
                    "msg": "OPERATION_SUCCESSFUL",
                    "hint": hint,
                    "data": {
                        "saved": saved,
                        "saved_diff3": saved_diff3,
                        "failed": failed,
                        "count": len(saved),
                    },
                }
                return self._attach_warnings(resp, owner_warnings)

            # ---- 分支 2: 本机目录（明文批量入库） ----
            import os as _os
            if _os.path.isdir(content):
                payload = {
                    "content": content,
                    "info_owner": info_owner,
                    "diff_1": diff_1,
                    "update_if_exists": bool(request.update_if_exists) or True,  # folder default true
                }
                # folder_save_orchestrator 内部 save_folder_record(..., sealed=False)
                result = folder_save_orchestrator.save_folder(payload, self.sensitive_service)
                return result

            # ---- 分支 3: 本机单文件（1.5.4 phase6） ----
            # mgc_save_file 能处理单个 .py / .json，但WebUI save 页走的是
            # info_type=file 这条 API 路径，原来只认目录和 .mgc_file，导致
            # 录入单文件路径时报PATH_NOT_LOCAL。这里复用同一套类型推断 +
            # 密封胶囊探测，让两条入口行为一致。
            if _os.path.isfile(content):
                from mgc.core.mgc_service.sealed_payload_parser import parse_sealed_payload

                file_path = Path(content)
                try:
                    raw_text = file_path.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    return {
                        "code": 400,
                        "msg": "FILE_READ_FAILED",
                        "hint": f"cannot read {content}: {e}",
                        "data": {"error": "FILE_READ_FAILED"},
                    }

                single = request.model_dump()
                single["content"] = raw_text
                single["info_owner"] = info_owner
                single["info_type"] = request.info_type or ""

                suffix = file_path.suffix.lower()
                capsule = None
                if suffix == ".json":
                    try:
                        capsule = parse_sealed_payload(raw_text)
                    except Exception:
                        capsule = None
                if capsule:
                    single["info_type"] = "script"
                elif suffix in (".py", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd"):
                    single["info_type"] = "script"
                elif suffix in (".json", ".yaml", ".yml", ".toml", ".ini", ".conf"):
                    single["info_type"] = "config"
                else:
                    single["info_type"] = "text"

                # 与 mgc_save_file 一致：文件名只补空的 diff 位，不覆盖已有值
                if single["info_type"] == "script":
                    if not single.get("diff_1"):
                        single["diff_1"] = file_path.stem
                    if not single.get("diff_3"):
                        single["diff_3"] = file_path.stem
                else:
                    if not single.get("diff_3"):
                        single["diff_3"] = file_path.name

                single_req = SensitiveSaveRequest(**{
                    k: v for k, v in single.items()
                    if k in SensitiveSaveRequest.model_fields
                })
                return await self._sensitive_save(single_req)

            return {
                "code": 400,
                "msg": "PATH_NOT_LOCAL",
                "hint": f"info_type=file requires content to be a local folder, a single local file, or a .mgc_file path; got: {content}",
                "data": {"error": "PATH_NOT_LOCAL"},
            }
        except Exception as e:
            import sys, traceback
            print(f"[ERROR] _sensitive_save_folder_or_sealed: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc()
            return {
                "code": 500,
                "msg": "FOLDER_SAVE_FAILED",
                "hint": str(e),
                "data": {"error": type(e).__name__},
            }

    async def _sensitive_get_folder_or_sealed(self, request: "SensitiveGetRequest"):
        """PR-5: info_type=file 批量导出入口（action=package / seal_package）。

        action=package       → package_exporter.export_folder()         （明文）
        action=seal_package  → sealed_package_exporter.export_sealed_package()（密封）
        """
        try:
            from mgc.service import package_exporter, sealed_package_exporter
            from mgc.service.backend_callback_adapter import (
                make_query_callback,
                make_seal_callback,
                make_self_node_pub_getter,
            )

            action = (request.action or "").strip()
            info_owner = request.info_owner or ""
            diff_2 = request.diff_2 or ""
            diff_1 = request.diff_1 or ""
            output_dir = request.output_dir or ""

            if not info_owner:
                return {"code": 400, "msg": "MISSING_REQUIRED_FIELDS",
                        "hint": "info_owner is required for package / seal_package",
                        "data": {"error": "MISSING_REQUIRED_FIELDS"}}
            if not diff_2:
                return {"code": 400, "msg": "MISSING_REQUIRED_FIELDS",
                        "hint": "diff_2 is required for package / seal_package",
                        "data": {"error": "MISSING_REQUIRED_FIELDS"}}
            if not output_dir:
                return {"code": 400, "msg": "MISSING_REQUIRED_FIELDS",
                        "hint": "output_dir is required for package / seal_package",
                        "data": {"error": "MISSING_REQUIRED_FIELDS"}}

            query_cb = make_query_callback(self.sensitive_service, info_type=None)

            # ---- action=package (明文导出) ----
            if action == "package":
                return package_exporter.export_folder(
                    info_owner=info_owner,
                    diff_2=diff_2,
                    output_dir=output_dir,
                    diff_1=diff_1,
                    query_callback=query_cb,
                )

            # ---- action=seal_package (密封包导出) ----
            if action == "seal_package":
                ext04 = request.ext04 or ""
                # 1.6.0：mode 由 ext04 形态决定（不新增任何请求字段）
                #   空 → free mode；JSON 数组 / "@文件路径" → chain mode；PEM → p2p mode
                from mgc.service.chain_spec_parser import CHAIN_MODE, detect_mode
                seal_mode = detect_mode(ext04)
                _logger = __import__("logging").getLogger(__name__)
                if seal_mode == CHAIN_MODE:
                    _logger.info(
                        "seal_package: ext04 is a chain spec -> chain mode; the "
                        "package will be split per target node_pub."
                    )
                elif seal_mode == "free mode":
                    _logger.info(
                        "seal_package: ext04 is empty -> auto-sealing in free mode; "
                        "any mgc node receiving this package can import and run it."
                    )
                # 老路径保留：明确报错逻辑已移到 sealed_package_exporter；这里只做 mode 决策

                # 优先用注入的 SealService；未注入则按需动态 import
                # （与 _sensitive_get L1352 / L1208 的 SealService 按需模式一致）
                seal_service = getattr(self, "seal_service", None)
                if seal_service is None:
                    seal_service = getattr(self, "_seal_service", None)
                if seal_service is None and hasattr(self, "mgc_core_service"):
                    seal_service = getattr(self.mgc_core_service, "seal_service", None)
                # P0-2 修复（2026-08-30）：ApiRouter 未在 __init__ 创建 node_key_service，
                # getattr 永远拿 None → make_self_node_pub_getter 返回空 →
                # MGCFILE.json 顶层 source_node_pub + 每条 record.ext07 一直为空。
                # 1.5.4 重构：用统一的 get_or_init_node_key_service helper（同时支持
                # self 上的实例与 lazy-init 两条路径）。
                from mgc.core.mgc_service.node_key_service import (
                    get_or_init_node_key_service,
                )
                node_key_service = (
                    getattr(self, "node_key_service", None)
                    or getattr(self, "_node_key_service", None)
                    or get_or_init_node_key_service(self.sensitive_service)
                )

                if seal_service is None:
                    try:
                        from mgc.core.mgc_service.seal_service import SealService
                        # 1.5.4：把上面 lazy-init 出的 node_key_service 传给 SealService
                        # （free mode 需要它来取 default_node_pub）
                        seal_service = SealService(
                            sensitive_service=self.sensitive_service,
                            node_key_service=node_key_service,
                        )
                    except Exception as e:
                        return {"code": 500, "msg": "SEAL_SERVICE_UNAVAILABLE",
                                "hint": f"SealService initialization failed: {e}",
                                "data": {"error": "SEAL_SERVICE_UNAVAILABLE"}}

                self_pub = make_self_node_pub_getter(node_key_service)()
                sealed_result = sealed_package_exporter.export_sealed_package(
                    info_owner=info_owner,
                    diff_2=diff_2,
                    ext04=ext04,
                    output_dir=output_dir,
                    diff_1=diff_1,
                    query_callback=query_cb,
                    seal_callback=make_seal_callback(seal_service),
                    self_node_pub=self_pub,
                    # 1.5.4：根据 ext04 是否传入自动判定 mode（PM Q5 决策）
                    mode=seal_mode,
                )
                # P0-10 修复（2026-08-30）：检测 ext04 == 本机 node_pub 时警告。
                # 本机密封会导致：若存入 mgc，明文 script 会被自动覆盖为密文，
                # 此操作不可逆。需在 hint 中明确警告用户。
                # 1.6.0：chain mode 下 ext04 是 JSON 字符串，直接比较必然不等——
                # 改为逐 target 比对其 node_pub。
                if (isinstance(sealed_result, dict)
                        and sealed_result.get("code") == 200
                        and self_pub):
                    self_sealed = False
                    if seal_mode == CHAIN_MODE:
                        chain_targets = (
                            sealed_result.get("data", {}).get("targets", []) or []
                        )
                        self_sealed = any(
                            (t.get("node_pub", "") or "").strip() == self_pub.strip()
                            for t in chain_targets
                        )
                    else:
                        self_sealed = ext04.strip() == self_pub.strip()
                    if self_sealed:
                        sealed_result["hint"] = (
                            sealed_result.get("hint", "")
                            + "\n\n[WARNING] ext04 equals this node's node_pub — you are "
                              "sealing scripts for yourself. Importing this .mgc_file "
                              "back into mgc will OVERWRITE the original plaintext "
                              "scripts with ciphertext, and this operation is IRREVERSIBLE. "
                              "Proceed only if you fully understand the consequence."
                        )
                # 1.6.0：密封成功（code=200）时，chain mode 追加分发指引，
                # 提示编排方核实主 readme（含 node_pub ↔ task_package 映射与全部 warnings）。
                # 仅当返回 code=200（成功）时追加，错误响应不追加。
                if isinstance(sealed_result, dict) and sealed_result.get("code") == 200:
                    if seal_mode == CHAIN_MODE:
                        chain_data = sealed_result.get("data", {})
                        chain_hint = (
                            f"\n\nSealed chain package generated at "
                            f"'{chain_data.get('delivery_path', '')}' — "
                            f"{chain_data.get('package_count', 0)} task package(s), "
                            f"{chain_data.get('file_count', 0)} file(s) total. "
                            f"Please verify the main README.md before distributing — "
                            f"it contains the node_pub ↔ task_package mapping and all "
                            f"warnings."
                        )
                        sealed_result["hint"] = sealed_result.get("hint", "") + chain_hint
                return sealed_result

            return {"code": 400, "msg": "UNKNOWN_ACTION",
                    "hint": f"unknown action for info_type=file: {action!r}",
                    "data": {"error": "UNKNOWN_ACTION"}}
        except Exception as e:
            import sys, traceback
            print(f"[ERROR] _sensitive_get_folder_or_sealed: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc()
            return {
                "code": 500,
                "msg": "FOLDER_GET_FAILED",
                "hint": str(e),
                "data": {"error": type(e).__name__},
            }

    async def _sensitive_save_silent(self, request: SensitiveSaveRequest):
        """保存AI API Key（命令行静默版）"""
        try:
            if not self.sensitive_service:
                return {"code": 500, "msg": get_api_message("SENSITIVE_SERVICE_NOT_INITIALIZED"), "data": {}}

            # 1.5.2 hotfix P0: 拒绝任何节点身份凭证（__NODE_PUB__ / node_priv / ...）的写操作
            # 统一通过 NODE_CREDENTIALS_REGISTRY 配置管理。
            from mgc.core.mgc_service.node_credentials_registry import is_node_credential
            if is_node_credential(request.info_type):
                return {
                    "code": 403,
                    "msg": "NODE_KEY_WRITE_PROTECTED",
                    "hint": f"'{request.info_type}' is system-managed and cannot be "
                            "modified via API. It is generated by NodeKeyService and "
                            "can be viewed via the WebUI Node Public Key page.",
                    "data": {}
                }

            if request.info_type and request.info_owner and request.api_key:
                self.sensitive_service.save_api_key(
                    key_alias=request.key_alias,
                    info_type=request.info_type,
                    info_owner=request.info_owner,
                    diff_1=request.diff_1,
                    diff_2=request.diff_2,
                    diff_3=request.diff_3,
                    api_key=request.api_key
                )
            elif request.content:
                self.sensitive_service.save_code_sensitive(
                    key_alias=request.key_alias,
                    info_type=request.info_type,
                    info_owner=request.info_owner,
                    diff_1=request.diff_1,
                    diff_2=request.diff_2,
                    diff_3=request.diff_3,
                    content=request.content
                )

            # Skip operation logging to avoid SQLite thread safety issue
            # if self.database_handler:
            #     self.database_handler.insert_operation_log(
            #         operation_type="sensitive_save_silent",
            #         operation_result="success"
            #     )

            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="SAVE",
                    key_alias=request.key_alias or "",
                    operation_result="SUCCESS",
                    info_owner=request.info_owner
                )

            return {"code": 200, "msg": get_api_message("SAVE_SUCCESSFUL"), "hint": "Stored encrypted in MGC. Ready anytime.", "data": {}}
        except Exception as e:
            # if self.database_handler:
            #     self.database_handler.insert_operation_log(
            #         operation_type="sensitive_save_silent",
            #         operation_result="failed",
            #         error_message=str(e)
            #     )
            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="SAVE",
                    key_alias=request.key_alias or "",
                    operation_result="FAILED",
                    info_owner=request.info_owner
                )
            raise HTTPException(status_code=500, detail=str(e))

    async def _sensitive_code_save(self, request: SensitiveSaveRequest):
        """保存代码敏感信息"""
        try:
            if not self.sensitive_service:
                return {"code": 500, "msg": get_api_message("SENSITIVE_SERVICE_NOT_INITIALIZED"), "data": {}}

            self.sensitive_service.save_code_sensitive(
                key_alias=request.key_alias,
                content=request.content
            )

            return {"code": 200, "msg": get_api_message("SAVE_SUCCESSFUL"), "hint": "Stored encrypted in MGC. Ready anytime.", "data": {}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _sensitive_list(self):
        """Get sensitive list (masked)"""
        try:
            if not self.sensitive_service:
                return {"code": 500, "msg": get_api_message("SENSITIVE_SERVICE_NOT_INITIALIZED"), "data": {}}

            sensitive_list = self.sensitive_service.get_sensitive_list()
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": {"list": sensitive_list}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _sensitive_get(self, request: SensitiveGetRequest):
        """获取敏感信息（按类型+归属+差异查询）"""
        try:
            if not self.sensitive_service:
                return {
                    "code": 500,
                    "msg": get_api_message("SENSITIVE_SERVICE_NOT_INITIALIZED"),
                    "hint": "Sensitive service not initialized. Please call /api/mgc/init with root key first.",
                    "data": {}
                }

            if not request.info_type and not request.info_owner:
                info_list = self.sensitive_service.get_info_list()
                return {
                    "code": 201,
                    "msg": "LIST_RETRIEVED",
                    "hint": "Choose the required item from the list. Do not expose outside MGC unless necessary.",
                    "data": {
                        "info_list": info_list
                    }
                }

            # PR-5 (1.5.0 phase2 / 技能授权): info_type=file + action in (package, seal_package)
            # → 调 _sensitive_get_folder_or_sealed
            if request.info_type == "file" and (request.action or "").strip() in ("package", "seal_package"):
                return await self._sensitive_get_folder_or_sealed(request)

            has_type = bool(request.info_type)
            has_owner = bool(request.info_owner)

            if not has_type or not has_owner:
                info_list = self.sensitive_service.get_info_list(
                    info_type=request.info_type,
                    info_owner=request.info_owner,
                    diff_1=request.diff_1,
                    diff_2=request.diff_2,
                    diff_3=request.diff_3
                )
                return {
                    "code": 201,
                    "msg": "LIST_RETRIEVED",
                    "hint": "Index result. Provide exact info_type + info_owner to get content.",
                    "data": {
                        "info_list": info_list
                    }
                }

            # === 1.5.2 hotfix (P0)：mgc_run 参数健壮性 ===
            # 仅在 script + run 场景做"唯一性"校验：diff_1/2/3 全部非必填，
            # 但只要匹配到 ≥2 条候选，就强制报错让调用方补充 diff 字段再试。
            # 禁止"仅 info_owner 单字段模糊匹配后静默取第一条"——这是 PM 用例 7.5
            # 暴露的根因（MCP handler 没正确转发 script 字段时，整个 owner 范围被
            # 静默取第一条，导致跑错脚本）。
            # 兼容历史数据：1.5.1 之前存入的脚本可能 diff_1/2/3 全空，唯一匹配应放行。
            # 其他场景（mgc_get 单条读取、folder 等）保持原宽松匹配行为。
            is_script_run = (
                request.info_type == "script"
                and (request.action or "").strip() == "run"
            )
            if is_script_run:
                # 精确预查询：script+run 场景禁止"多条匹配静默取第一条"
                pre_query = self.sensitive_service.get_sensitive(
                    info_type=request.info_type,
                    info_owner=request.info_owner,
                    diff_1=request.diff_1,
                    diff_2=request.diff_2,
                    diff_3=request.diff_3
                )
                if len(pre_query) > 1:
                    # 多条匹配 → 报错，禁止静默取第一条
                    # 把 None / 'None' 归一化为空字符串（folder save 的 diff_1=NULL
                    # 时 hint 不显示 'None' 字面量，避免干扰 agent 解析）
                    matches = [
                        {
                            "diff_1": "" if r.get("diff_1") in (None, "None") else r.get("diff_1", ""),
                            "diff_2": "" if r.get("diff_2") in (None, "None") else r.get("diff_2", ""),
                            "diff_3": "" if r.get("diff_3") in (None, "None") else r.get("diff_3", "")
                        }
                        for r in pre_query
                    ]
                    # 1.5.4 phase6 修订：hint 不再直 dump 候选列表，而是把
                    # caller 重定向到 mgc_find 先收敛再回来 mgc_run。dump 候选
                    # 会让 agent 反复试错（逐条 diff_3 喂出来撞运气），实际
                    # 路径上 mgc_find + diff_3 一次即可唯一收敛——更稳的链路。
                    _hint_lines = [
                        f"{len(matches)} candidates match the given fields. "
                        "Call mgc_find(info_owner=...) first to list every record "
                        "under this owner and pick the right diff_3, then "
                        "re-invoke mgc_run with diff_3 set. Do NOT blind-loop "
                        "diff_3 — use mgc_find's indexed result."
                    ]
                    # friction fix: 补一句 diff_2 的必要性 —— folder 脚本靠
                    # diff_2 收窄，不带就多条命中，是实测最高频的踩坑点。
                    _hint_lines.append(
                        "For folder-imported scripts always pass diff_2 (the "
                        "folder name) together with diff_3 (the script's path "
                        "inside the folder): diff_2 narrows the lookup to one "
                        "folder, diff_3 picks the single script."
                    )
                    return {
                        "code": 409,
                        "msg": "AMBIGUOUS_SCRIPT",
                        "hint": "\n".join(_hint_lines),
                        "data": {
                            "matches": matches,
                            "count": len(pre_query),
                            "suggestion": (
                                "Call mgc_find(info_owner=...) to list every "
                                "record under this owner, pick the correct "
                                "diff_3 (and optionally diff_2), then re-invoke "
                                "mgc_run with diff_3 set. Without diff_3 the "
                                "lookup is ambiguous and refused."
                            )
                        }
                    }
                # 唯一匹配或 0 匹配 → 落入下方通用逻辑（0 匹配走 404 NOT_FOUND 分支）

            pub_hint_override = None

            sensitive_data = self.sensitive_service.get_sensitive(
                info_type=request.info_type,
                info_owner=request.info_owner,
                diff_1=request.diff_1,
                diff_2=request.diff_2,
                diff_3=request.diff_3
            )

            if not sensitive_data:
                if request.info_type == "__NODE_PUB__":
                    # 1.5.4：info_owner == '__DEFAULT_NODE_PUB__' 走 default node pub 查询
                    # （PM Q3 决策：所有 1.5.4+ 节点共享同一对 RSA）。
                    # 独立于本机 node_pub，db 没有则先 ensure_default_keys() 再返回。
                    # 完全独立路径：default_node_pub 查询完成后直接 return，
                    # 不再走下方 canonical-owner fallback（防止被覆盖成本机 pub）。
                    if request.info_owner == "__DEFAULT_NODE_PUB__":
                        try:
                            from mgc.core.mgc_service.node_key_service import (
                                NodeKeyService,
                                NodeKeyServiceError,
                            )
                            nks = NodeKeyService(
                                sensitive_service=self.sensitive_service
                            )
                            try:
                                nks.ensure_default_keys()
                            except NodeKeyServiceError as e:
                                return {
                                    "code": 409,
                                    "msg": "NODE_KEY_WRITE_PROTECTED",
                                    "hint": str(e),
                                    "data": {}
                                }
                            sensitive_data = self.sensitive_service.get_sensitive(
                                info_type="__NODE_PUB__",
                                info_owner="__DEFAULT_NODE_PUB__",
                            )
                        except Exception as e:
                            logger.warning(
                                f"__DEFAULT_NODE_PUB__ query failed: {e}"
                            )
                            sensitive_data = []

                        if not sensitive_data:
                            return {
                                "code": 404,
                                "msg": "NOT_FOUND",
                                "hint": "default_node_pub not found even after ensure_default_keys.",
                                "data": {},
                            }
                        # 找到 default_node_pub，直接走下方通用 return 路径（通过 goto-style）。
                        # 把 sensitive_data 设为只有一个元素的 list，且
                        # 在下方会被"action == run"/SEAL 等分支放过——
                        # 这里最简单的做法是直接构造 return。
                        default_pub_plain = sensitive_data[0].get("plain_text", "")
                        return {
                            "code": 200,
                            "msg": "OPERATION_SUCCESSFUL",
                            "hint": (
                                "Returned default_node_pub (1.5.4+ shared "
                                "RSA keypair). All 1.5.4+ nodes share this "
                                "key — it is intentionally public."
                            ),
                            "data": default_pub_plain,
                        }
                    # P0 fix 2026-09-27: canonical-owner fallback BEFORE any
                    # generation. node_pub is always stored with
                    # info_owner='__NODE_PUB__'; a caller passing another
                    # owner must get the existing record back, never a
                    # regenerated keypair (which would invalidate all sealed
                    # history).
                    sensitive_data = self.sensitive_service.get_sensitive(
                        info_type="__NODE_PUB__",
                        info_owner="__NODE_PUB__"
                    )
                    if sensitive_data:
                        pub_hint_override = (
                            "WARNING: info_owner mismatch. The request "
                            f"info_owner='{request.info_owner}' matched no "
                            "record; the canonical node_pub (stored with "
                            "info_owner='__NODE_PUB__') was returned "
                            "instead. Always query with info_type="
                            "'__NODE_PUB__' AND info_owner='__NODE_PUB__'."
                        )
                        logger.warning(
                            "node_pub queried with non-canonical owner "
                            f"'{request.info_owner}'; returned canonical "
                            "__NODE_PUB__ record instead"
                        )
                    else:
                        from mgc.core.mgc_service.node_key_service import (
                            NodeKeyService,
                            NodeKeyServiceError,
                        )
                        nks = NodeKeyService(
                            sensitive_service=self.sensitive_service
                        )
                        try:
                            nks.ensure_public_key()
                        except NodeKeyServiceError as e:
                            return {
                                "code": 409,
                                "msg": "NODE_KEY_WRITE_PROTECTED",
                                "hint": str(e),
                                "data": {}
                            }
                        sensitive_data = self.sensitive_service.get_sensitive(
                            info_type="__NODE_PUB__",
                            info_owner="__NODE_PUB__"
                        )
                
            if not sensitive_data:
                return {
                    "code": 404,
                    "msg": "NOT_FOUND",
                    "hint": "Information not found. Please confirm the info is stored, or call get with empty params to list all stored info.",
                    "data": {
                        "suggestion": "No matching info found. Please provide exact info_type + info_owner, or use mgc_list for fuzzy search."
                    }
                }
            
            if request.action == "run" and request.info_type == "script":
                script_data = self.sensitive_service.get_sensitive(
                    info_type=request.info_type,
                    info_owner=request.info_owner,
                    diff_1=request.diff_1,
                    diff_2=request.diff_2,
                    diff_3=request.diff_3
                )
                
                if not script_data:
                    return {
                        "code": 404,
                        "msg": "NOT_FOUND",
                        "hint": "Script not found",
                        "data": {}
                    }
                
                script_content = script_data[0].get("plain_text", "")
                ext01 = script_data[0].get("ext01", "")
                stored_ext03 = script_data[0].get("ext03", "")
                
                if stored_ext03:
                    # 1.5.1 BUG-C：sealed 脚本统一走 phase3 新路径（sensitive_service.run_script）。
                    # 老 sealed 分支（先 unseal_and_run 再 execute_script_async）有两个问题：
                    # 1. python3 + cmd args + stdin 源码模式 Python 解释器会 reject args
                    # 2. 与 phase3 设计文档"统一入口"目标脱节
                    # phase3 新路径通过 `python -m mgc.bootstrap` + stdin payload 规避以上问题，
                    # 且 unseal 逻辑统一在 ScriptExecutionService._decrypt_and_unseal 里。
                    try:
                        result = self.sensitive_service.run_script(
                            info_type=request.info_type,
                            info_owner=request.info_owner,
                            diff_1=request.diff_1,
                            diff_2=request.diff_2,
                            diff_3=request.diff_3,
                            runtime_ext02=request.ext02 or "",
                        )
                    except Exception as e:
                        return {
                            "code": 500,
                            "msg": "RUN_FAILED",
                            "hint": str(e),
                            "data": {}
                        }

                    if result.get("status") == "failed":
                        # ScriptExecutionService 返回 failed（如 unseal 失败/找不到）
                        err = result.get("error", "unknown")
                        if "decrypt" in err.lower() or "unseal" in err.lower():
                            return {
                                "code": 500,
                                "msg": "UNSEAL_FAILED",
                                "hint": err,
                                "data": {}
                            }
                        return {
                            "code": 500,
                            "msg": "RUN_FAILED",
                            "hint": err,
                            "data": {}
                        }

                    # Return minimal response for sealed script (security: no pid/content exposed).
                    # Sealed scripts must NOT expose pid back to the agent. The pid leaks the
                    # process command line (args may carry internal_token / caller_key) and
                    # the temporary unsealed file path on disk (e.g. /tmp/mgc_unseal_*.py),
                    # which would defeat the sealed-encryption guarantee. The agent can
                    # observe completion via external side effects (output files, DB rows,
                    # log files) instead of OS-level pid inspection.
                    # 1.5.0: attach runtime env warnings based on the ORIGINAL entry's
                    # ext05 / ext06 (unsealing does not change compatibility).
                    return self._attach_warnings(
                        {
                            "code": 200,
                            "msg": "executed",
                            "hint": "Sealed script executed. Check external output.",
                            "data": {"status": "started"},
                        },
                        self._build_run_warnings(script_data[0]),
                    )
                else:
                    result = self.sensitive_service.run_script(
                        info_type=request.info_type,
                        info_owner=request.info_owner,
                        diff_1=request.diff_1,
                        diff_2=request.diff_2,
                        diff_3=request.diff_3,
                        runtime_ext02=request.ext02
                    )
                    # v1.4 新增: 透传 split fallback hint
                    result_hint = result.get("hint")
                    if not result_hint:
                        # 没有 split fallback hint 时使用默认 PID 提示
                        result_hint = f"PID: {result.get('pid', 'N/A')}"
                    response = {
                        "code": 200 if result.get("status") in ["success", "started"] else 500,
                        "msg": result.get("status", "unknown"),
                        "hint": result_hint,
                        "data": result
                    }
                    # 1.5.0: attach runtime env warnings
                    return self._attach_warnings(
                        response,
                        self._build_run_warnings(script_data[0]),
                    )
                
                request_key = f"{request.info_type}:{request.info_owner}:{request.diff_1 or ''}:{request.diff_2 or ''}:{request.diff_3 or ''}"
                
                self.script_executor.execute_script_async(
                    request_key=request_key,
                    script_content=script_content,
                    ext01=ext01,
                    ext02=request.ext02 or ""
                )
                
                if request.wait_result:
                    for i in range(3):
                        import asyncio
                        await asyncio.sleep(3)
                        result = self.script_executor.get_task_result(request_key)
                        if result.get("status") in ["success", "failed"]:
                            if self.operation_log_manager:
                                self.operation_log_manager.log_operation(
                                    operation_type="RUN_SCRIPT",
                                    key_alias=request.diff_1 or "",
                                    operation_result=result.get("status", "failed"),
                                    info_owner=request.info_owner
                                )
                            return self._attach_warnings(
                                {
                                    "code": 200 if result.get("status") == "success" else 500,
                                    "msg": result.get("status", "failed"),
                                    "data": result
                                },
                                self._build_run_warnings(script_data[0]),
                            )
                    return self._attach_warnings(
                        {
                            "code": 408,
                            "msg": "TIMEOUT",
                            "hint": "No result obtained",
                            "data": {}
                        },
                        self._build_run_warnings(script_data[0]),
                    )
                else:
                    if self.operation_log_manager:
                        self.operation_log_manager.log_operation(
                            operation_type="RUN_SCRIPT",
                            key_alias=request.diff_1 or "",
                            operation_result="started",
                            info_owner=request.info_owner
                        )
                    return self._attach_warnings(
                        {
                            "code": 200,
                            "msg": "started",
                            "data": {
                                "status": "started",
                                "message": "Transmission successful"
                            }
                        },
                        self._build_run_warnings(script_data[0]),
                    )
            
            # 1.5.4：去掉 `and request.ext04`——free mode (ext04 空) 也要进入 SEAL 分支
            if request.action == "SEAL":
                script_data = self.sensitive_service.get_sensitive(
                    info_type=request.info_type,
                    info_owner=request.info_owner,
                    diff_1=request.diff_1,
                    diff_2=request.diff_2,
                    diff_3=request.diff_3
                )
                
                if not script_data:
                    return {
                        "code": 404,
                        "msg": "NOT_FOUND",
                        "hint": "Script not found",
                        "data": {}
                    }
                
                script_content = script_data[0].get("plain_text", "")

                try:
                    from mgc.core.mgc_service.seal_service import SealService
                    from mgc.core.mgc_service.node_key_service import (
                        get_or_init_node_key_service,
                    )
                    # 1.5.4：注入 node_key_service 以支持 free mode
                    seal_svc = SealService(
                        sensitive_service=self.sensitive_service,
                        node_key_service=get_or_init_node_key_service(self.sensitive_service),
                    )
                    # 1.5.4：拿本机 node_pub 作为 source_node_pub（必传）
                    source_node_pub = ""
                    try:
                        nks = getattr(seal_svc, "node_key_service", None)
                        if nks:
                            source_node_pub = nks.get_public_key() or ""
                    except Exception:
                        pass
                    if not source_node_pub:
                        return {
                            "code": 409,
                            "msg": "NODE_KEY_WRITE_PROTECTED",
                            "hint": "source_node_pub unavailable. The local node_pub "
                                    "is required by mgc 1.5.4+ to seal scripts. "
                                    "Trigger NodeKeyService.ensure_public_key() first.",
                            "data": {},
                        }
                    # 1.5.4 PM Q5：ext04 非空 → p2p；空 → free
                    # 1.6.0：单脚本胶囊不支持 chain mode（chain 是多节点拆包语义），
                    # 误传 chain spec 时明确报错，避免被静默当成 p2p 处理。
                    if request.ext04 and (
                        (request.ext04 or "").strip().startswith("[")
                        or (request.ext04 or "").strip().startswith("@")
                    ):
                        return {
                            "code": 400,
                            "msg": "CHAIN_MODE_NOT_SUPPORTED_FOR_SINGLE_SEAL",
                            "hint": "chain mode (a JSON array of targets, or "
                                    "'@<path>') is only supported by mgc_seal_package "
                                    "for multi-node task packages. Use "
                                    "mgc_seal_package with a target node_pub to "
                                    "seal a single script.",
                            "data": {"error": "CHAIN_MODE_NOT_SUPPORTED_FOR_SINGLE_SEAL"},
                        }
                    if request.ext04:
                        seal_mode = "p2p mode"
                    else:
                        seal_mode = "free mode"
                    sealed = seal_svc.seal_script(
                        script_content,
                        out_node_pub=request.ext04,
                        mode=seal_mode,
                        source_node_pub=source_node_pub,
                    )
                    # Carry forward every ext field the source record has, using
                    # the 1.5.4 unprefixed key (ext01, ext05, ext08, ...) so the
                    # downstream MCP forward loop can pick them up uniformly.
                    for i in range(1, 31):
                        ext_key = f"ext{i:02d}"
                        ext_val = script_data[0].get(ext_key, "")
                        if ext_val:
                            sealed[ext_key] = ext_val

                    # 1.5.4 phase6：补齐 identity 与 diff 三元组，让胶囊自描述。
                    # 只有 content 是新生成的密文，其余字段全部原样透传。
                    capsule = build_capsule_payload(
                        {
                            "info_type": request.info_type,
                            "info_owner": request.info_owner,
                            "diff_1": script_data[0].get("diff_1", ""),
                            "diff_2": script_data[0].get("diff_2", ""),
                            "diff_3": script_data[0].get("diff_3", ""),
                            **{f"ext{i:02d}": sealed.get(f"ext{i:02d}", "") for i in range(1, 31)},
                        },
                        sealed,
                    )

                    # 落盘：MCP / API 调用方必须传 output_dir（无桌面兜底）；
                    # WebUI 不传，只拿内存 JSON 去做浏览器下载。
                    if request.output_dir:
                        capsule_path = write_capsule_json(
                            resolve_output_dir(request.output_dir),
                            request.info_owner,
                            capsule,
                        )
                        capsule["delivery_path"] = str(capsule_path.parent)
                        capsule["capsule_path"] = str(capsule_path)
                        hint = (
                            f"Sealed capsule written to {capsule_path}. "
                            "To persist it on any MGC node, pass the JSON content to "
                            "mgc_save -- MGC auto-parses info_type / info_owner / "
                            "diff_* / ext* and stores them as-is. BEFORE saving, decide "
                            "whether to change `info_owner` in the JSON: keeping the "
                            "original owner on the SAME node OVERWRITES the source "
                            "record, while a DIFFERENT node keeps the source intact. "
                            "Records missing ext07 (source_node_pub) or ext09 (seal_mode) "
                            "cannot be unsealed."
                        )
                    else:
                        hint = (
                            "Script sealed. Use the Download button to save the capsule "
                            "JSON, then paste it into the Save page on the target MGC "
                            "node -- MGC auto-parses info_type / info_owner / diff_* / "
                            "ext* and stores them as-is. NOTE: saving under the original "
                            "info_owner on the SAME node OVERWRITES the source record, "
                            "while a DIFFERENT node keeps the source intact."
                        )

                    return {
                        "code": 200,
                        "msg": "SEAL_SUCCESSFUL",
                        "hint": hint,
                        "data": capsule
                    }
                except Exception as e:
                    return {
                        "code": 500,
                        "msg": "SEAL_FAILED",
                        "hint": str(e),
                        "data": {}
                    }
            
            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="GET",
                    key_alias=request.diff_1 or "",
                    operation_result="SUCCESS",
                    info_owner=request.info_owner
                )
            
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "hint": pub_hint_override or "Decrypted from MGC. Burn after use.", "data": sensitive_data[0].get("plain_text") if sensitive_data else ""}
        except Exception as e:
            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="GET",
                    key_alias=request.diff_1 or "",
                    operation_result="FAILED",
                    info_owner=request.info_owner
                )
            raise HTTPException(status_code=500, detail=str(e))

    async def _sensitive_update(self, request: SensitiveUpdateRequest):
        """更新敏感信息"""
        try:
            if not self.sensitive_service:
                return {"code": 500, "msg": get_api_message("SENSITIVE_SERVICE_NOT_INITIALIZED"), "data": {}}

            self.sensitive_service.update_sensitive(
                key_alias=request.key_alias,
                new_content=request.new_content
            )

            return {"code": 200, "msg": get_api_message("UPDATE_SUCCESSFUL"), "data": {}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _sensitive_delete(self, request: SensitiveDeleteRequest):
        """删除敏感信息"""
        try:
            if not self.sensitive_service:
                return {"code": 500, "msg": get_api_message("SENSITIVE_SERVICE_NOT_INITIALIZED"), "data": {}}

            # 1.5.2 hotfix P0: 拒绝任何节点身份凭证（__NODE_PUB__ / node_priv / ...）的删除
            # 统一通过 NODE_CREDENTIALS_REGISTRY 配置管理。
            from mgc.core.mgc_service.node_credentials_registry import is_node_credential
            if is_node_credential(request.info_type):
                return {
                    "code": 403,
                    "msg": "NODE_KEY_WRITE_PROTECTED",
                    "hint": f"'{request.info_type}' is system-managed and cannot be "
                            "deleted. It persists for the lifetime of the node.",
                    "data": {}
                }

            if not request.info_owner:
                return {"code": 400, "msg": get_api_message("KEY_ALIAS_CANNOT_BE_EMPTY"), "data": {}}

            result = self.sensitive_service.delete_sensitive(
                request.info_type,
                request.info_owner,
                request.diff_1,
                request.diff_2,
                request.diff_3
            )

            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="DELETE",
                    key_alias=request.info_owner,
                    operation_result="SUCCESS"
                )

            return {"code": 200, "msg": get_api_message("DELETE_SUCCESSFUL"), "data": {}}
        except Exception as e:
            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="DELETE",
                    key_alias=request.info_owner,
                    operation_result="FAILED"
                )
            raise HTTPException(status_code=500, detail=str(e))

    async def _migrate(self, request: MigrateRequest):
        """设备迁移授权（弹框交互版）"""
        try:
            if not self.migrate_service:
                return {"code": 500, "msg": get_api_message("MIGRATION_SERVICE_NOT_INITIALIZED"), "data": {}}

            result = self.migrate_service.authorize_migration(request.migrate_key)
            
            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="MIGRATE",
                    key_alias="migration",
                    operation_result="SUCCESS"
                )
            
            return {"code": 200, "msg": get_api_message("MIGRATION_AUTHORIZATION_SUCCESSFUL"), "data": result}
        except Exception as e:
            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="MIGRATE",
                    key_alias="migration",
                    operation_result="FAILED"
                )
            raise HTTPException(status_code=500, detail=str(e))

    async def _migrate_silent(self, request: MigrateRequest):
        """设备迁移授权（命令行静默版）"""
        try:
            if not self.migrate_service:
                return {"code": 500, "msg": get_api_message("MIGRATION_SERVICE_NOT_INITIALIZED"), "data": {}}

            result = self.migrate_service.authorize_migration(request.migrate_key)
            
            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="MIGRATE",
                    key_alias="migration",
                    operation_result="SUCCESS"
                )
            
            return {"code": 200, "msg": get_api_message("MIGRATION_AUTHORIZATION_SUCCESSFUL"), "data": result}
        except Exception as e:
            if self.operation_log_manager:
                self.operation_log_manager.log_operation(
                    operation_type="MIGRATE",
                    key_alias="migration",
                    operation_result="FAILED"
                )
            raise HTTPException(status_code=500, detail=str(e))

    async def _migrate_key_modify(self, request: MigrateKeyModifyRequest):
        """修改迁移密钥（弹框交互版）"""
        try:
            if not self.migrate_service:
                return {"code": 500, "msg": get_api_message("MIGRATION_SERVICE_NOT_INITIALIZED"), "data": {}}

            self.migrate_service.modify_migrate_key(
                old_migrate_key=request.old_migrate_key,
                new_migrate_key=request.new_migrate_key
            )

            return {"code": 200, "msg": get_api_message("MODIFICATION_SUCCESSFUL"), "data": {}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _migrate_key_modify_silent(self, request: MigrateKeyModifyRequest):
        """修改迁移密钥（命令行静默版）"""
        try:
            if not self.migrate_service:
                return {"code": 500, "msg": get_api_message("MIGRATION_SERVICE_NOT_INITIALIZED"), "data": {}}

            self.migrate_service.modify_migrate_key(
                old_migrate_key=request.old_migrate_key,
                new_migrate_key=request.new_migrate_key
            )

            return {"code": 200, "msg": get_api_message("MODIFICATION_SUCCESSFUL"), "data": {}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _migrate_key_path(self):
        """获取迁移密钥保存路径"""
        try:
            if not self.migrate_service:
                return {"code": 500, "msg": get_api_message("MIGRATION_SERVICE_NOT_INITIALIZED"), "data": {}}

            path = self.migrate_service.get_migrate_key_path()
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": {"path": path}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _status(self):
        """获取服务状态"""
        try:
            if not self.status_service:
                return {"code": 500, "msg": get_api_message("STATUS_SERVICE_NOT_INITIALIZED"), "data": {}}

            status = self.status_service.get_status()
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": status}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _device(self):
        """获取设备信息"""
        try:
            if not self.status_service:
                return {"code": 500, "msg": get_api_message("STATUS_SERVICE_NOT_INITIALIZED"), "data": {}}

            device_info = self.status_service.get_device()
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": device_info}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _service_start(self):
        """启动服务"""
        try:
            if not self.mgc_core_service:
                return {"code": 500, "msg": get_api_message("MGC_CORE_SERVICE_NOT_INITIALIZED"), "data": {}}

            await self.mgc_core_service.start()
            return {"code": 200, "msg": get_api_message("SERVICE_STARTED_SUCCESSFULLY"), "data": {}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _service_stop(self):
        """停止服务"""
        try:
            if not self.mgc_core_service:
                return {"code": 500, "msg": get_api_message("MGC_CORE_SERVICE_NOT_INITIALIZED"), "data": {}}

            await self.mgc_core_service.stop()
            return {"code": 200, "msg": get_api_message("SERVICE_STOPPED_SUCCESSFULLY"), "data": {}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _service_restart(self):
        """重启服务"""
        try:
            if not self.mgc_core_service:
                return {"code": 500, "msg": get_api_message("MGC_CORE_SERVICE_NOT_INITIALIZED"), "data": {}}

            await self.mgc_core_service.restart()
            return {"code": 200, "msg": get_api_message("SERVICE_RESTARTED_SUCCESSFULLY"), "data": {}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _log(self):
        """获取日志"""
        try:
            if not self.status_service:
                return {"code": 500, "msg": get_api_message("STATUS_SERVICE_NOT_INITIALIZED"), "data": {}}

            logs = self.status_service.get_log()
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": {"logs": logs}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _cipher_verify(self, request: CipherVerifyRequest):
        """校验密文"""
        try:
            if not self.crypto_service:
                return {"code": 500, "msg": get_api_message("ENCRYPTION_SERVICE_NOT_INITIALIZED"), "data": {}}

            result = self.crypto_service.verify_cipher(request.content)
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _version_check(self):
        """检查版本更新"""
        try:
            if not self.update_service:
                return {"code": 500, "msg": get_api_message("UPDATE_SERVICE_NOT_INITIALIZED"), "data": {}}

            result = self.update_service.check_version()
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _heartbeat(self):
        """发送心跳"""
        try:
            if not self.update_service:
                return {"code": 500, "msg": get_api_message("UPDATE_SERVICE_NOT_INITIALIZED"), "data": {}}

            result = self.update_service.send_heartbeat()
            return {"code": 200, "msg": get_api_message("OPERATION_SUCCESSFUL"), "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _skill_update(self, request: SkillUpdateRequest):
        """检查或执行Skill版本更新"""
        try:
            if not self.skills_manager:
                return {"code": 500, "msg": "Skills manager not initialized", "data": {}}

            if request.action == "check":
                result = self.skills_manager.check_updates(request.offline_mode)
                return {"code": 200, "msg": "Check update successful", "data": result}
            elif request.action == "execute":
                return {"code": 500, "msg": "Execute update not implemented", "data": {}}
            else:
                return {"code": 400, "msg": "Invalid action", "data": {}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _skill_version(self):
        """获取Skills版本信息"""
        try:
            if not self.skills_manager:
                return {"code": 500, "msg": "Skills manager not initialized", "data": {}}

            result = self.skills_manager.get_version_info()
            return {"code": 200, "msg": "Get version info successful", "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _skill_heartbeat(self, request: SkillHeartbeatRequest):
        """记录Skill心跳"""
        try:
            if not self.skills_manager:
                return {"code": 500, "msg": "Skills manager not initialized", "data": {}}

            result = self.skills_manager.record_heartbeat(request.skill_name)
            return {"code": 200, "msg": "Heartbeat record successful", "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _skill_stats(self):
        """获取Skill心跳统计"""
        try:
            if not self.skills_manager:
                return {"code": 500, "msg": "Skills manager not initialized", "data": {}}

            result = self.skills_manager.get_heartbeat_stats()
            return {"code": 200, "msg": "Statistics retrieval successful", "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _skill_uninstall(self, request: SkillUninstallRequest):
        """准备卸载或查询卸载状态"""
        try:
            if not self.skills_manager:
                return {"code": 500, "msg": "Skills manager not initialized", "data": {}}

            if request.action == "prepare":
                result = self.skills_manager.prepare_uninstall()
                return {"code": 200, "msg": "Uninstall preparation completed", "data": result}
            elif request.action == "status":
                return {"code": 200, "msg": "Uninstall status query successful", "data": {"status": "completed", "progress": 100}}
            else:
                return {"code": 400, "msg": "Invalid action", "data": {}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

