"""判断层包标识

用途：
- 标识judge_layer包，使Python能够识别为可导入的包
- 统一导出判断层功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更复杂的判断逻辑
"""

# 导出判断层功能
from .cipher_matcher import CipherMatcher

__all__ = ["CipherMatcher"]
