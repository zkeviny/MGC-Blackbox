"""加密层核心数据模型

用途：
- 定义加密层的核心数据模型（v2.0+全量加密使用）
- 统一加密认知单元的数据结构
- 为判断层和调用层提供标准化的加密单元数据

依赖：
- 无外部依赖

v1.0使用说明：
- v1.0版本不使用CipherUnit模型，仅使用InfoStorageUnit轻量结构
- CipherUnit模型为v2.0+全量加密预留，v1.0仅保留空类定义
- 所有v1.0层间交互均通过InfoStorageUnit模型

未来演进：
- v2.0+可扩展为全量加密模型，支持核心信息加密
- 可对接区块链底层实现上链存证
- 可添加更多加密相关的字段和方法
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class CipherUnit:
    """加密层核心数据模型（v2.0+全量加密使用）
    
    v1.0使用说明：
    - v1.0版本不使用CipherUnit模型，仅使用InfoStorageUnit轻量结构
    - CipherUnit模型为v2.0+全量加密预留，v1.0仅保留空类定义
    - 所有v1.0层间交互均通过InfoStorageUnit模型
    
    v2.0+演进方向：
    - 支持核心信息（info_type/info_owner/content）全量加密
    - 支持AES-256/RSA/SM4等多种加密算法
    - 支持加密单元上链存证
    
    Attributes:
        unit_id: str - 加密单元ID
        version: str - 加密单元版本
        ciphertext: str - 密文
        algorithm: str - 加密算法
        key_hash: str - 密钥哈希
        created_at: float - 创建时间戳
        updated_at: float - 更新时间戳
        metadata: dict - 元数据
    """
    unit_id: str
    version: str
    ciphertext: str
    algorithm: str
    key_hash: str
    created_at: float = 0.0
    updated_at: float = 0.0
    metadata: dict = None
    
    def __post_init__(self):
        """初始化后处理"""
        if self.metadata is None:
            self.metadata = {}
