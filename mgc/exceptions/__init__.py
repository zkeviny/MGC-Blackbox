"""异常处理层包标识

用途：
- 标识exceptions包，使Python能够识别为可导入的包
- 统一导出异常类

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多异常类型
"""

# 导出异常类
from .crypto_exceptions import CryptoException, KeyGenerationError, EncryptionError, DecryptionError
from .agent_exceptions import AgentException, InputError, OutputError

__all__ = [
    "CryptoException", "KeyGenerationError", "EncryptionError", "DecryptionError",
    "AgentException", "InputError", "OutputError"
]
