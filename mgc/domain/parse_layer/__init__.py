"""解析层包标识

用途：
- 标识parse_layer包，使Python能够识别为可导入的包
- 统一导出解析层功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持认知规则解析
"""

# 导出解析层功能
from .plaintext_parser import PlaintextParser
from .cognition_parser import CognitionParser

__all__ = ["PlaintextParser", "CognitionParser"]
