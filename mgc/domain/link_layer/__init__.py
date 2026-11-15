"""链路层包标识

用途：
- 标识link_layer包，使Python能够识别为可导入的包
- 统一导出链路层功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持多Agent/多设备链路互通、密文记忆、工作量证明互认
"""

# 统一导出链路层接口
from .link_reserve import LinkReserve
from .cipher_memory import CipherMemory

__all__ = ["LinkReserve", "CipherMemory"]

