"""调用层包标识

用途：
- 标识call_layer包，使Python能够识别为可导入的包
- 统一导出调用层功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多调用逻辑
"""

# 导出调用层功能
from .cipher_caller import CipherCaller

__all__ = ["CipherCaller"]
