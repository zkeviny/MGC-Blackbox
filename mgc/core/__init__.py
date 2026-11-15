"""核心层包标识

用途：
- 标识core包，使Python能够识别为可导入的包
- 统一导出核心加密功能

依赖：
- 无外部依赖

未来演进：
- 可扩展为包含更多核心加密功能
"""

# 导出核心加密功能
from .crypto import aes_crypto, hash_crypto
from .weight import user_weight

__all__ = ["aes_crypto", "hash_crypto", "user_weight"]
