"""数据模型包标识

用途：
- 标识models包，使Python能够识别为可导入的包
- 统一导出核心数据模型

依赖：
- 无外部依赖

未来演进：
- 可扩展为包含模型验证和管理的核心逻辑
"""

# 导出核心数据模型
from .input_model import InputData
from .cognition_model import CognitionRule
from .storage_model import InfoStorageUnit
from .cipher_model import CipherUnit

__all__ = ["InputData", "CognitionRule", "InfoStorageUnit", "CipherUnit"]
