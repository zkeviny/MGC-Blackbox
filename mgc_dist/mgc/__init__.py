"""MirginCipher包标识

用途：
- 标识src包，使Python能够识别为可导入的包
- 定义项目的版本号和核心常量
- 为项目提供统一的版本管理

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多核心常量和版本信息
"""

# 项目版本号
__version__ = "1.0.0"

# 项目名称
__project__ = "MirginCipher"

# 项目描述
__description__ = "AI Agent隐私信息加密工具"

# 作者信息
__author__ = "MirginCipher Team"

# 版权信息
__copyright__ = "Copyright 2026 MirginCipher"

# 许可证信息
__license__ = "Proprietary"

# 核心常量
CORE_CONSTANTS = {
    "ENCRYPTION_ALGORITHM": "AES-256",
    "HASH_ALGORITHM": "SHA-256",
    "VERSION": __version__
}
