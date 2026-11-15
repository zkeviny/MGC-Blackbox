"""演进层包标识

用途：
- 标识evolve_layer包，使Python能够识别为可导入的包
- 统一导出演进层功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持认知规则迭代和加密单元版本升级
"""

# 导出演进层功能
from .track_analyzer import TrackAnalyzer
from .cipher_updater import CipherUpdater

__all__ = ["TrackAnalyzer", "CipherUpdater"]
