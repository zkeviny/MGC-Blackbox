"""明文信息解析模块

用途：
- 解析InputData中的明文信息
- 将InputData转换为CognitionRule
- 提取关键字段并标记待派生凭证

依赖：
- src.models.input_model.InputData
- src.models.cognition_model.CognitionRule

未来演进：
- 可扩展支持更复杂的解析逻辑
- 可添加解析规则配置
"""

import uuid
from mgc.models.input_model import InputData
from mgc.models.cognition_model import CognitionRule
from mgc.config.enum_config import OperationType


class PlaintextParser:
    """明文信息解析器
    
    实现明文信息解析功能，将InputData转换为CognitionRule
    """
    
    def __init__(self):
        """初始化解析器"""
        pass
    
    def parse_input_data(self, input_data: InputData) -> CognitionRule:
        """解析InputData，转换为CognitionRule
        
        Args:
            input_data: 输入数据模型
        
        Returns:
            CognitionRule: 解析后的认知规则
        
        Raises:
            ValueError: 当输入数据无效时抛出异常
        """
        # 验证输入数据
        if not input_data:
            raise ValueError("InputData cannot be None")
        
        # 提取关键字段
        fields = self._extract_fields(input_data)
        
        # 生成规则ID
        rule_id = self._generate_rule_id()
        
        # 标记待派生凭证
        extract_account, extract_password = self._mark_derived_credentials(input_data)
        
        # 创建CognitionRule
        return CognitionRule(
            rule_id=rule_id,
            rule_type=input_data.input_type,
            content=input_data.content if isinstance(input_data.content, str) else str(input_data.content),
            info_owner=fields.get("info_owner", ""),
            info_type=fields.get("info_type", ""),
            operation=input_data.operation or OperationType.ADD,
            extract_account=extract_account,
            extract_password=extract_password,
            metadata=input_data.metadata or {},
            agent_uuid=input_data.agent_uuid or ""
        )
    
    def _extract_fields(self, input_data: InputData) -> dict:
        """提取关键字段
        
        Args:
            input_data: 输入数据模型
        
        Returns:
            dict: 提取的字段
        """
        fields = {}
        
        # 从InputData中提取字段
        if input_data.info_owner:
            fields['info_owner'] = input_data.info_owner
        
        if input_data.info_type:
            fields['info_type'] = input_data.info_type
        
        return fields
    
    def _mark_derived_credentials(self, input_data: InputData) -> tuple:
        """标记待派生凭证标识
        
        Args:
            input_data: 输入数据模型
        
        Returns:
            tuple: (extract_account, extract_password)
        """
        # 初始值为空字符串
        extract_account = ""
        extract_password = ""
        
        # 根据info_type判断是否需要派生凭证
        # 这里可以根据实际业务逻辑扩展
        if input_data.info_type:
            # 例如：如果是银行账户，可能需要派生密码
            if '银行' in input_data.info_type or '银行卡' in input_data.info_type:
                extract_password = "需要派生"
            # 例如：如果是邮箱，可能需要派生账户
            elif '邮箱' in input_data.info_type:
                extract_account = "需要派生"
        
        return extract_account, extract_password
    
    def _generate_rule_id(self) -> str:
        """生成规则ID
        
        Returns:
            str: 规则ID
        """
        # 使用UUID生成唯一ID
        return f"rule-{uuid.uuid4().hex[:8]}"
