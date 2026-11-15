"""个性化权重包标识

用途：
- 标识weight包，使Python能够识别为可导入的包
- 统一导出个性化权重功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多权重生成和管理功能
"""

# 导出个性化权重功能
from .user_weight import UserWeight

__all__ = ["UserWeight"]
