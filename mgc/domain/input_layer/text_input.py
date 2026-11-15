"""文本输入模块

用途：
- 处理文本输入
- 将文本内容转换为标准化输入数据
- 为解析层提供文本输入数据

依赖：
- 依赖models/input_model.py
- 依赖config.enum_config.OperationType

未来演进：
- 可扩展支持更多文本格式
- 可添加文本验证和错误处理
"""

import json
from mgc.models.input_model import InputData, MGCRequest
from mgc.config.enum_config import OperationType
from mgc.utils.cache_utils import save_input_cache
from mgc.utils.request_converter import convert_to_mgc_request

class TextInput:
    """文本输入处理
    
    实现文本输入功能，支持JSON格式解析
    """
    
    def __init__(self):
        """初始化文本输入处理器"""
        pass
    
    def process_text(self, text, agent_uuid: str = ""):
        """处理文本输入

        Args:
            text: 文本内容
            agent_uuid: Agent UUID标识（来源优先级：入参 > 配置 > 默认值）

        Returns:
            InputData: 标准化输入数据
        
        Raises:
            ValueError: 当agent_uuid缺失时抛出异常
        """
        if not agent_uuid:
            raise ValueError("agent_uuid is required for data isolation")
        
        try:
            # 尝试解析JSON格式
            json_data = json.loads(text)
            # 解析JSON数据，创建InputData
            return self._parse_json_input(json_data, original_text=text, agent_uuid=agent_uuid)
        except json.JSONDecodeError:
            # 非JSON格式，直接作为文本处理
            return InputData(
                input_type="text",
                content=text,
                agent_uuid=agent_uuid
            )
    
    def _parse_json_input(self, json_data, original_text="", agent_uuid: str = ""):
        """解析JSON格式输入

        Args:
            json_data: JSON数据
            original_text: 原始文本内容（用于缓存）
            agent_uuid: Agent UUID标识

        Returns:
            InputData: 标准化输入数据
        """
        # 验证JSON格式
        if not self.validate_text(json_data):
            error_msg = "Invalid JSON format"
            save_input_cache(
                input_type="text",
                content=original_text,
                error_message=error_msg
            )
            raise ValueError(error_msg)

        # 提取字段
        info_owner = json_data.get('info_owner')
        info_type = json_data.get('info_type')
        operation_str = json_data.get('operation_type')
        content = json_data.get('content', '')

        # 转换operation_type为枚举
        operation = None
        if operation_str:
            try:
                operation = OperationType(operation_str)
            except ValueError as e:
                error_msg = f"Invalid operation type: {operation_str}"
                save_input_cache(
                    input_type="text",
                    content=original_text,
                    error_message=error_msg
                )
                raise ValueError(error_msg)

        # 创建标准化输入数据
        return InputData(
            input_type="text",
            content=content,
            info_owner=info_owner,
            info_type=info_type,
            operation=operation,
            agent_uuid=agent_uuid
        )
    
    def validate_text(self, text_or_data):
        """验证文本
        
        Args:
            text_or_data: 文本内容或JSON数据
        
        Returns:
            bool: 文本是否有效
        """
        # 如果是JSON数据，验证必要字段
        if isinstance(text_or_data, dict):
            # 检查必要字段
            if 'info_owner' in text_or_data and 'info_type' in text_or_data:
                return True
            return False
        # 如果是文本，检查是否非空
        elif isinstance(text_or_data, str):
            return bool(text_or_data.strip())
        return False

    def to_mgc_request(self, input_data: InputData):
        """转换为MGCRequest对象

        Args:
            input_data: InputData对象

        Returns:
            MGCRequest: MGC请求对象
        """
        return convert_to_mgc_request(input_data)
