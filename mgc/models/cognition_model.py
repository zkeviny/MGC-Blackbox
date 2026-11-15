"""解析层输出数据模型

用途：
- 定义解析层的标准化输出模型
- 统一认知规则的数据结构
- 为加密层提供标准化的认知规则数据

依赖：
- src.config.enum_config.OperationType

未来演进：
- 可扩展支持多维认知规则
- 可添加规则验证和错误处理
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
from mgc.config.enum_config import OperationType

@dataclass
class CognitionRule:
    """解析层输出数据模型
    
    Attributes:
        rule_id: str - 规则ID（建议使用UUID生成，确保唯一性）
        rule_type: str - 规则类型（从InputData.input_type映射）
        content: str - 规则内容（直接映射InputData的原始content字段，不做预处理）
        info_owner: str - 信息归属
        info_type: str - 信息类型
        operation: OperationType - 操作类型
        extract_account: str - 待派生账户标识
        extract_password: str - 待派生密码标识
        metadata: dict - 元数据
        created_at: float - 创建时间戳（单位：秒，使用time.time()生成）
        weight: float - 规则权重
        dependencies: List[str] - 依赖的其他规则
        agent_uuid: str - Agent UUID标识
        diff1: str - 差异1字段
        diff2: str - 差异2字段
        diff3: str - 差异3字段
        ext_fields: Dict[str, str] - ext01~ext30字段字典
    """
    rule_id: str
    rule_type: str
    content: str
    info_owner: str
    info_type: str
    operation: OperationType
    extract_account: str = ""
    extract_password: str = ""
    metadata: dict = None
    created_at: float = 0.0
    weight: float = 1.0
    dependencies: List[str] = None
    agent_uuid: str = ""
    diff1: str = ""
    diff2: str = ""
    diff3: str = ""
    ext_fields: Dict[str, str] = None
    
    def __post_init__(self):
        """初始化后处理"""
        if self.metadata is None:
            self.metadata = {}
        if self.dependencies is None:
            self.dependencies = []
        if self.created_at == 0.0:
            import time
            self.created_at = time.time()
        if self.ext_fields is None:
            self.ext_fields = {}
    
    def get_diff_field(self, index: int) -> str:
        """获取差异字段
        
        入参：
            index: 差异字段索引（1-3）
        
        出参：
            str: 差异字段值
        """
        if index == 1:
            return self.diff1
        elif index == 2:
            return self.diff2
        elif index == 3:
            return self.diff3
        else:
            return ""
    
    def get_ext_field(self, index: int) -> str:
        """获取扩展字段
        
        入参：
            index: 扩展字段索引（1-30）
        
        出参：
            str: 扩展字段值
        """
        field_name = f"ext{index:02d}"
        return self.ext_fields.get(field_name, "")
