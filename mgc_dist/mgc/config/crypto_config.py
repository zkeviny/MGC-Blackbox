"""加密算法参数配置

用途：
- 统一管理加密算法的参数配�?- 提供AES-256和SHA-256的参数设�?- 为未来扩展其他加密算法预留接�?
依赖�?- 无外部依�?
未来演进�?- 可扩展支持RSA、SM4等其他加密算�?- 可添加算法参数的动态调整能�?"""

# AES-256加密配置
AES_CONFIG = {
    "key_length": 32,  # AES-256需�?2字节密钥
    "mode": "CBC",    # 加密模式
    "iv_length": 16,  # 初始化向量长�?
    "padding": "PKCS7" # 填充方式
}

# SHA-256哈希配置
SHA256_CONFIG = {
    "digest_size": 32,  # SHA-256输出32字节
    "block_size": 64    # 块大�?
}

# 加密单元配置
CIPHER_UNIT_CONFIG = {
    "version": "1.0",  # 加密单元版本
    "encoding": "utf-8",  # 编码方式
    "compression": False  # 是否压缩
}

# 个性化权重配置
WEIGHT_CONFIG = {
    "version": "1.0",  # 权重版本
    "dimensions": 8,    # 权重维度
    "storage_path": "storage/keys/weight.json"  # 权重存储路径
}


