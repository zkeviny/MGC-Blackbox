"""黑盒与AI/Agent交互接口

用途：
- 实现MGC_V1_AI_Interaction.md中定义的接口规范
- 处理AI/Agent的请求
- 安全前置校验（接口层职责）
- 调用StorageService处理业务逻辑

依赖：
- 依赖utils/log_utils.py
- 依赖service/storage_service.py
"""

import json
import time
import re
import os
from typing import Dict, Any, Tuple, Set
from mgc.utils.log_utils import logger
from mgc.utils.path_utils import get_query_list_file
from mgc.service.storage_service import StorageService


class BlackboxInterface:
    """黑盒与AI/Agent交互接口"""
    
    SPECIAL_CHARS = set('!@#$%^&*()+=[]{}|;:"<>?/')
    REQUEST_ID_PATTERN = re.compile(r'^req-\d{8}-\d{4}$')
    
    def __init__(self):
        """初始化接口"""
        self.storage_service = StorageService()
        self.processed_requests: Set[str] = set()
    
    def handle_request(self, request_json: str) -> str:
        """
        处理AI/Agent请求
        
        入参：
            request_json: AI/Agent发送的JSON请求字符串
            
        出参：
            标准化的JSON响应字符串
        """
        try:
            request_data = json.loads(request_json)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parsing error: {str(e)}")
            return self._build_error_response(
                request_id="",
                code=400,
                message="JSON格式错误",
                fail_reason=str(e)
            )
        
        valid, error_msg = self._validate_request(request_data)
        if not valid:
            return error_msg
        
        request_id = request_data.get("request_id")
        self.processed_requests.add(request_id)
        
        response = self.storage_service.handle_request(request_data)
        return json.dumps(response, ensure_ascii=False)
    
    def _validate_request(self, request_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        安全前置校验（接口层职责）
        
        入参：
            request_data: 请求数据字典
            
        出参：
            (是否通过, 错误响应JSON字符串)
        """
        request_id = request_data.get("request_id", "")
        
        valid, error = self._validate_required_fields(request_data)
        if not valid:
            return False, self._build_error_response(
                request_id=request_id,
                code=400,
                message="请求参数缺失",
                fail_reason=error
            )
        
        request_id = request_data.get("request_id")
        
        if not self._validate_request_id_format(request_id):
            return False, self._build_error_response(
                request_id=request_id,
                code=400,
                message="请求ID格式错误",
                fail_reason="request_id格式应为req-YYYYMMDD-XXXX"
            )
        
        if request_id in self.processed_requests:
            return False, self._build_error_response(
                request_id=request_id,
                code=400,
                message="重复请求",
                fail_reason="该请求已处理"
            )
        
        version = request_data.get("version")
        if version != "1.0":
            return False, self._build_error_response(
                request_id=request_id,
                code=400,
                message="接口版本不兼容",
                fail_reason=f"仅支持v1.0，当前版本: {version}"
            )
        
        timestamp = request_data.get("timestamp")
        current_time = int(time.time())
        if abs(current_time - timestamp) > 300:
            return False, self._build_error_response(
                request_id=request_id,
                code=400,
                message="请求时间戳过期",
                fail_reason="请求时间与当前时间差超过5分钟"
            )
        
        valid, error = self._validate_params(request_data)
        if not valid:
            return False, self._build_error_response(
                request_id=request_id,
                code=400,
                message="参数校验失败",
                fail_reason=error
            )
        
        agent_uuid = request_data.get("agent_uuid")
        if not self._validate_agent_permission(agent_uuid):
            return False, self._build_error_response(
                request_id=request_id,
                code=403,
                message="权限校验失败",
                fail_reason="Agent UUID与清单绑定UUID不一致"
            )
        
        return True, ""
    
    def _validate_required_fields(self, request_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        校验必要字段存在性
        
        入参：
            request_data: 请求数据字典
            
        出参：
            (是否通过, 错误信息)
        """
        required_fields = ['request_id', 'agent_uuid', 'operation_type', 
                          'version', 'timestamp', 'params']
        for field in required_fields:
            if field not in request_data or request_data.get(field) is None:
                return False, f"缺少必需字段: {field}"
        return True, ""
    
    def _validate_request_id_format(self, request_id: str) -> bool:
        """
        校验request_id格式
        
        入参：
            request_id: 请求ID
            
        出参：
            是否合法
        """
        return bool(self.REQUEST_ID_PATTERN.match(request_id))
    
    def _validate_params(self, request_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        校验参数合法性
        
        入参：
            request_data: 请求数据字典
            
        出参：
            (是否通过, 错误信息)
        """
        params = request_data.get("params", {})
        operation_type = request_data.get("operation_type")
        
        if operation_type == "add":
            return self._validate_add_params(params)
        elif operation_type == "modify":
            return self._validate_modify_params(params)
        elif operation_type == "delete":
            return self._validate_delete_params(params)
        elif operation_type == "query":
            return self._validate_query_params(params)
        else:
            return False, f"不支持的操作类型: {operation_type}"
    
    def _validate_add_params(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """校验add操作参数"""
        info_owner = params.get("info_owner")
        info_type = params.get("info_type")
        
        if not info_owner:
            return False, "info_owner字段不可为空"
        if not info_type:
            return False, "info_type字段不可为空"
        
        if not self._validate_field_content(info_owner):
            return False, "info_owner包含非法字符"
        if not self._validate_field_content(info_type):
            return False, "info_type包含非法字符"
        
        return True, ""
    
    def _validate_modify_params(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """校验modify操作参数"""
        item_id = params.get("item_id")
        info_owner = params.get("info_owner")
        info_type = params.get("info_type")
        
        if not item_id:
            return False, "item_id字段不可为空"
        
        if not self._validate_item_id_format(item_id):
            return False, "item_id格式不符合ql-YYYYMMDD-XXXX规范"
        
        if info_owner and not self._validate_field_content(info_owner):
            return False, "info_owner包含非法字符"
        if info_type and not self._validate_field_content(info_type):
            return False, "info_type包含非法字符"
        
        return True, ""
    
    def _validate_delete_params(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """校验delete操作参数"""
        item_id = params.get("item_id")
        
        if not item_id:
            return False, "item_id字段不可为空"
        
        if not self._validate_item_id_format(item_id):
            return False, "item_id格式不符合ql-YYYYMMDD-XXXX规范"
        
        return True, ""
    
    def _validate_query_params(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """校验query操作参数"""
        info_owner = params.get("info_owner")
        info_type = params.get("info_type")
        
        if not info_owner:
            return False, "info_owner字段不可为空"
        if not info_type:
            return False, "info_type字段不可为空"
        
        if not self._validate_field_content(info_owner):
            return False, "info_owner包含非法字符"
        if not self._validate_field_content(info_type):
            return False, "info_type包含非法字符"
        
        return True, ""
    
    def _validate_field_content(self, field_value: str) -> bool:
        """
        校验字段内容（禁止特殊字符）
        
        入参：
            field_value: 字段值
            
        出参：
            是否合法
        """
        if not field_value:
            return False
        return not any(char in self.SPECIAL_CHARS for char in field_value)
    
    def _validate_item_id_format(self, item_id: str) -> bool:
        """
        校验item_id格式
        
        入参：
            item_id: 条目ID
            
        出参：
            是否合法
        """
        if not item_id:
            return False
        pattern = re.compile(r'^ql-\d{8}-\d{4}$')
        return bool(pattern.match(item_id))
    
    def _validate_agent_permission(self, agent_uuid: str) -> bool:
        """
        校验Agent权限（与query_list绑定UUID一致性）
        
        入参：
            agent_uuid: Agent UUID
            
        出参：
            是否有权限
        """
        query_list_path = get_query_list_file()
        if not os.path.exists(query_list_path):
            return True
        
        try:
            with open(query_list_path, 'r', encoding='utf-8') as f:
                query_list = json.load(f)
                bind_uuid = query_list.get('meta', {}).get('bind_agent_uuid', '')
                if not bind_uuid:
                    logger.debug("Query list exists but not bound to Agent UUID, access denied")
                    return False
                return agent_uuid == bind_uuid
        except Exception as e:
            logger.debug(f"Failed to read query list: {str(e)}")
            return False
    
    def _build_error_response(self, request_id: str, code: int, 
                             message: str, fail_reason: str = "") -> str:
        """
        构建错误响应
        
        入参：
            request_id: 请求ID
            code: 错误码
            message: 错误消息
            fail_reason: 失败原因
            
        出参：
            JSON格式错误响应字符串
        """
        response = {
            "request_id": request_id,
            "code": code,
            "message": message,
            "data": {},
            "timestamp": int(time.time()),
            "trace_id": self._generate_trace_id()
        }
        if fail_reason:
            response["fail_reason"] = fail_reason
        return json.dumps(response, ensure_ascii=False)
    
    def _generate_trace_id(self) -> str:
        """
        生成追踪ID
        
        出参：
            追踪ID（格式：trace-YYYYMMDD-XXXX）
        """
        today = time.strftime('%Y%m%d')
        timestamp = int(time.time() * 1000)
        random_suffix = timestamp % 10000
        return f"trace-{today}-{random_suffix:04d}"
    
    def initialize_storage(self, mysql_host: str, mysql_port: int,
                          mysql_root_password: str, agent_uuid: str,
                          personal_key: str, weight_param: int) -> str:
        """
        初始化存储服务
        
        入参：
            mysql_host: MySQL主机地址
            mysql_port: MySQL端口
            mysql_root_password: MySQL root密码
            agent_uuid: Agent UUID
            personal_key: 个人密钥
            weight_param: 权重参数（必须）
            
        出参：
            初始化结果的JSON响应字符串
        """
        try:
            result = self.storage_service.initialize_database(
                mysql_host=mysql_host,
                mysql_port=mysql_port,
                mysql_root_password=mysql_root_password,
                agent_uuid=agent_uuid,
                personal_key=personal_key,
                weight_param=weight_param
            )
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Storage service initialization exception: {str(e)}")
            error_response = {
                "code": 500,
                "message": f"存储服务初始化失败: {str(e)}",
                "data": {}
            }
            return json.dumps(error_response, ensure_ascii=False)
    
    def cleanup(self) -> None:
        """清理资源"""
        self.storage_service.cleanup()
        self.processed_requests.clear()
        logger.debug("Blackbox interface resources cleaned up")
