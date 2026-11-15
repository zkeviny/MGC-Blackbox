"""加密相关异常

用途：
- 定义加密相关的异常类
- 为加密操作提供标准化的异常处理
- 确保加密过程中的错误能够被正确捕获和处理

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多加密相关的异常类型
"""

class CryptoException(Exception):
    """加密异常基类"""
    pass

class KeyGenerationError(CryptoException):
    """密钥生成错误"""
    pass

class EncryptionError(CryptoException):
    """加密错误"""
    pass

class DecryptionError(CryptoException):
    """解密错误"""
    pass

class HashError(CryptoException):
    """哈希错误"""
    pass
