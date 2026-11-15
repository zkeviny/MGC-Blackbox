"""录入层输出数据模型

用途：
- 定义录入层的标准化输出模型
- 统一文件和文本输入的数据结构
- 为解析层提供标准化的输入数据

依赖：
- src.config.enum_config.OperationType

未来演进：
- 可扩展支持对话和工作流输入
- 可添加输入验证和错误处理
"""

from dataclasses import dataclass
from typing import Optional, Union, Dict, Any
from mgc.config.enum_config import OperationType

@dataclass
class InputData:
    """录入层输出数据模型

    Attributes:
        input_type: str - 输入类型（text/file）
        content: Union[str, bytes] - 输入内容
        source_path: Optional[str] - 源文件路径（如果是文件输入）
        user_id: Optional[str] - 用户标识
        timestamp: float - 输入时间戳
        metadata: dict - 元数据
        info_owner: Optional[str] - 信息归属
        info_type: Optional[str] - 信息类型
        operation: Optional[OperationType] - 操作类型
        agent_uuid: Optional[str] - Agent UUID标识
    """
    input_type: str
    content: Union[str, bytes]
    source_path: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: float = 0.0
    metadata: dict = None
    info_owner: Optional[str] = None
    info_type: Optional[str] = None
    operation: Optional[OperationType] = None
    agent_uuid: Optional[str] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.metadata is None:
            self.metadata = {}

@dataclass
class MGCRequest:
    """MGC请求模型

    符合MGC_V1_AI_Interaction.md规范

    Attributes:
        request_id: str - AI/Agent生成唯一标识，格式：req-YYYYMMDD-XXXX
        agent_uuid: str - 绑定查询清单的Agent UUID
        operation_type: OperationType - 操作类型枚举（add/modify/delete/query）
        version: str - 接口版本，V1.0固定为"1.0"
        timestamp: int - 秒级时间戳（AI/Agent本地系统时间）
        params: Dict[str, Any] - 场景化参数
        info_owner: Optional[str] - 信息归属（用户/部门名称）
        info_type: Optional[str] - 信息类型（如手机号/银行卡号/API密钥）
        content: Optional[str] - 操作内容（如新增/修改的具体信息）
        metadata: Optional[Dict[str, Any]] - 扩展元数据
    """
    request_id: str
    agent_uuid: str
    operation_type: OperationType
    version: str = "1.0"
    timestamp: int = 0
    params: Dict[str, Any] = None
    info_owner: Optional[str] = None
    info_type: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.params is None:
            self.params = {}
        if self.timestamp == 0:
            import time
            self.timestamp = int(time.time())


@dataclass
class MGCResponse:
    """MGC响应模型

    符合MGC_V1_AI_Interaction.md规范

    Attributes:
        request_id: str - 与请求中的request_id原样返回
        code: int - 状态码：200/400/403/500
        message: str - 人类可读提示信息
        timestamp: int - 黑盒响应时的秒级时间戳
        trace_id: str - 黑盒生成的链路追踪ID
        data: Optional[Dict[str, Any]] - 业务返回数据
        metadata: Optional[Dict[str, Any]] - 扩展元数据
    """
    request_id: str
    code: int
    message: str
    timestamp: int = 0
    trace_id: str = ""
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.data is None:
            self.data = {}
        if self.timestamp == 0:
            import time
            self.timestamp = int(time.time())
        if not self.trace_id:
            import uuid
            self.trace_id = f"trace-{self.timestamp}-{uuid.uuid4().hex[:8]}"
