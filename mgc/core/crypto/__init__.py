"""加密算法包标识

用途：
- 标识crypto包，使Python能够识别为可导入的包
- 统一导出加密算法功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持RSA、SM4等其他加密算法
"""

# 导出加密功能
from .aes_crypto import AESCrypto
from .hash_crypto import HashCrypto
from .rsa_crypto import RSACrypto
from .sm4_crypto import SM4Crypto

__all__ = ["AESCrypto", "HashCrypto", "RSACrypto", "SM4Crypto"]

