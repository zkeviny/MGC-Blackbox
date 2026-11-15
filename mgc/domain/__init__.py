"""领域分层包标识

用途：
- 标识domain包，使Python能够识别为可导入的包
- 统一导出领域分层功能

依赖：
- 无外部依赖

未来演进：
- 可扩展支持更多领域分层功能
"""

# 导出领域分层功能
from .input_layer import file_input, text_input
from .parse_layer import plaintext_parser
from .crypto_layer import cipher_unit
from .judge_layer import cipher_matcher
from .call_layer import cipher_caller
from .output_layer import text_output
from .evolve_layer import track_analyzer, cipher_updater
from .link_layer import link_reserve

__all__ = [
    "file_input", "text_input",
    "plaintext_parser",
    "cipher_unit",
    "cipher_matcher",
    "cipher_caller",
    "text_output",
    "track_analyzer", "cipher_updater",
    "link_reserve"
]
