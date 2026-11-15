"""输出层包标识

用途：
- 标识output_layer包，使Python能够识别为可导入的包
- 统一导出输出层功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多输出格式
"""

# 导出输出层功能
from .text_output import TextOutput

__all__ = ["TextOutput"]
