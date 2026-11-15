"""加密辅助工具

用途：
- 提供加密相关的辅助函数
- 支持密钥生成和数据哈希
- 为加密层提供工具支持

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多加密辅助功能
- 可添加加密验证和错误处理
"""

import os
import hashlib
from mgc.config.crypto_config import AES_CONFIG, SHA256_CONFIG

# 生成密钥
def generate_key(key_length=None):
    """生成加密密钥
    
    Args:
        key_length: 密钥长度，默认使用AES_CONFIG中的配置
    
    Returns:
        bytes: 生成的密钥
    """
    if key_length is None:
        key_length = AES_CONFIG["key_length"]
    return os.urandom(key_length)

# 哈希数据
def hash_data(data, algorithm="sha256"):
    """对数据进行哈希处理
    
    Args:
        data: 要哈希的数据
        algorithm: 哈希算法，默认sha256
    
    Returns:
        str: 哈希结果
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    
    if algorithm == "sha256":
        hash_obj = hashlib.sha256()
        hash_obj.update(data)
        return hash_obj.hexdigest()
    else:
        # 未来可扩展支持其他哈希算法
        raise NotImplementedError(f"Algorithm {algorithm} not implemented")

# 生成随机初始化向量
def generate_iv(iv_length=None):
    """生成初始化向量
    
    Args:
        iv_length: 初始化向量长度，默认使用AES_CONFIG中的配置
    
    Returns:
        bytes: 生成的初始化向量
    """
    if iv_length is None:
        iv_length = AES_CONFIG["iv_length"]
    return os.urandom(iv_length)
