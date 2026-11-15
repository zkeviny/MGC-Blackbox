"""存储层轻量数据模型

用途：
- 定义v1.0轻量存储结构InfoStorageUnit
- 包含密文片段（派生凭证+硬件指纹哈希）+明文片段（核心信息）+版本号
- 用于层间交互的标准化数据传递

依赖：
- 无外部依赖

未来演进：
- v2.0+可扩展为CipherUnit全量加密模型
- 可添加更多加密相关的字段和方法
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class InfoStorageUnit:
    """v1.0轻量存储结构
    
    核心设计原则：
    - 仅对「派生凭证（extract_account/extract_password）+硬件指纹（hardware_hash）」做SHA-256哈希加密
    - 核心业务信息（info_type/info_owner/content等）全程明文处理，不做任何加密
    - 输出轻量结构，禁止全量加密
    
    Attributes:
        unit_id: str - 存储单元唯一标识
        version: str - 存储单元版本，v1.0固定为"1.0"
        
        # 密文片段（SHA-256哈希加密）
        extract_account: str - 提取账户名（派生凭证SHA-256哈希）
        extract_password: str - 提取密码（派生凭证SHA-256哈希）
        hardware_hash: str - 硬件指纹哈希（SHA-256哈希）
        
        # 明文片段（核心业务信息，全程明文透传）
        info_type: str - 信息类型（如：手机号、邮箱、密码等）
        info_owner: str - 信息归属（如：张三、李四等）
        content: str - 敏感信息内容（明文）
        
        # 元数据
        created_at: float - 创建时间戳
        updated_at: float - 更新时间戳
        agent_uuid: str - 提交Agent的UUID标识
        metadata: dict - 扩展元数据
        
        # 新增字段：支持5字段查询清单结构
        diff1: str - 差异1字段
        diff2: str - 差异2字段
        diff3: str - 差异3字段
        
        # 新增字段：支持ext01~ext30扩展
        ext_fields: dict - ext01~ext30字段字典
    """
    
    # 基础标识
    unit_id: str
    version: str = "1.0"
    
    # 密文片段（SHA-256哈希加密）
    extract_account: str = ""  # 派生凭证哈希：用于MySQL账户名
    extract_password: str = ""  # 派生凭证哈希：用于MySQL密码
    hardware_hash: str = ""  # 硬件指纹哈希
    
    # 明文片段（核心业务信息）
    info_type: str = ""  # 信息类型
    info_owner: str = ""  # 信息归属
    content: str = ""  # 敏感信息内容（明文）
    
    # 元数据
    created_at: float = 0.0
    updated_at: float = 0.0
    agent_uuid: str = ""  # Agent提交标识
    metadata: Optional[Dict[str, Any]] = None
    
    # 新增字段：支持5字段查询清单结构
    diff1: str = ""
    diff2: str = ""
    diff3: str = ""
    
    # 新增字段：支持ext01~ext30扩展
    ext_fields: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        """初始化后处理"""
        if self.metadata is None:
            self.metadata = {}
        if self.ext_fields is None:
            self.ext_fields = {}
    
    def get_ext_field(self, index: int) -> str:
        """获取扩展字段
        
        入参：
            index: 扩展字段索引（1-30）
        
        出参：
            str: 扩展字段值
        """
        field_name = f"ext{index:02d}"
        return self.ext_fields.get(field_name, "")
    
    def get_cipher_key(self) -> str:
        """获取密文组合键（用于匹配校验）
        
        Returns:
            str: 组合键 extract_account:extract_password:hardware_hash
        """
        return f"{self.extract_account}:{self.extract_password}:{self.hardware_hash}"
    
    def is_valid(self) -> bool:
        """验证存储单元是否有效
        
        Returns:
            bool: 是否有效（密文片段必须非空）
        """
        return bool(self.extract_account and self.extract_password and self.hardware_hash)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于序列化）
        
        Returns:
            dict: 字典格式的存储单元数据
        """
        return {
            "unit_id": self.unit_id,
            "version": self.version,
            "extract_account": self.extract_account,
            "extract_password": self.extract_password,
            "hardware_hash": self.hardware_hash,
            "info_type": self.info_type,
            "info_owner": self.info_owner,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "agent_uuid": self.agent_uuid,
            "metadata": self.metadata,
            "diff1": self.diff1,
            "diff2": self.diff2,
            "diff3": self.diff3,
            "ext_fields": self.ext_fields
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InfoStorageUnit":
        """从字典创建存储单元
        
        Args:
            data: 字典格式的存储单元数据
        
        Returns:
            InfoStorageUnit: 存储单元实例
        """
        return cls(
            unit_id=data.get("unit_id", ""),
            version=data.get("version", "1.0"),
            extract_account=data.get("extract_account", ""),
            extract_password=data.get("extract_password", ""),
            hardware_hash=data.get("hardware_hash", ""),
            info_type=data.get("info_type", ""),
            info_owner=data.get("info_owner", ""),
            content=data.get("content", ""),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            agent_uuid=data.get("agent_uuid", ""),
            metadata=data.get("metadata", {}),
            diff1=data.get("diff1", ""),
            diff2=data.get("diff2", ""),
            diff3=data.get("diff3", ""),
            ext_fields=data.get("ext_fields", {})
        )
