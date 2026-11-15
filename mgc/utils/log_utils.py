"""本地日志工具

用途：
- 提供本地日志记录功能
- 支持不同级别的日志输出
- 为项目提供统一的日志管理

依赖：
- 无外部依赖

未来演进：
- 可扩展支持日志文件轮转
- 可添加日志级别配置
"""

import logging
import os
from mgc.utils.path_utils import get_storage_dir

# 日志目录
LOG_DIR = os.path.join(get_storage_dir(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件路径
LOG_FILE = os.path.join(LOG_DIR, "mirgincipher.log")

# 配置日志
# encoding 固定为 utf-8：FileHandler 不传 encoding 时会退化成
# locale.getpreferredencoding(False)（Windows 中文系统 = cp936，Linux/macOS = UTF-8），
# 导致同一份日志在三个平台落盘编码不同，跨平台按 UTF-8 读取必然乱码。
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# 创建日志记录器
logger = logging.getLogger("MirginCipher")


def get_logger(name: str = None):
    """
    获取日志记录器
    
    @param name: 记录器名称
    @return: 日志记录器
    """
    if name:
        return logging.getLogger(f"MirginCipher.{name}")
    return logger


# 日志装饰器
def log_function(func):
    """日志装饰器，记录函数调用"""
    def wrapper(*args, **kwargs):
        logger.info(f"Calling function: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"Function {func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error in function {func.__name__}: {str(e)}")
            raise
    return wrapper


# ---- 1.5.1 task2：终端脱敏工具 ----
# 背景：调用 mgc 脚本时，ext 字段（特别是 ext02 启动参数、ext03 wrapped key）
# 可能在日志 / MCP 返回值中泄露秘钥。需求是"终端展示层脱敏"，不改
# 业务字段值（脚本执行器 / 数据库存储 / API 内部传递保持原文）。
#
# 设计要点：
# - **不改原值**：safe_ext_repr 仅返回字符串用于显示/日志，业务侧照旧
#   使用 ext02 原文构造子进程 argv。
# - 粒度（经用户确认 2026-09-10）：ext02 长度 ≤ 32 一律 "***"，
#   长度 > 32 才显示前 4 ... 后 4（覆盖 base64 长串场景）。
# - ext03（RSA-wrapped AES key）：任何长度一律 "***"。

# 1.5.1 task2 阈值常量
_EXT02_SHORT_MAX_LEN = 32
_EXT02_LONG_HEAD = 4
_EXT02_LONG_TAIL = 4


def safe_ext_repr(value, *, key: str = "") -> str:
    """对 ext 字段做终端安全的字符串表示。

    仅用于日志 / 终端 / MCP 返回值渲染，**不会修改原值**。
    业务侧（脚本执行、数据库落库、API 内部传递）仍使用原文。

    Args:
        value: 原始字符串值（None / "" 直接返回原样）。
        key:  ext 字段名（"ext02" / "ext03" / "ext01" / ...）。
              空字符串走"通用元数据"分支（沿用现有 inline [:N]... 风格）。

    Returns:
        脱敏后的字符串，空值返回 ""。
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        # 非字符串（如 bytes）：转字符串后按字符串处理。
        try:
            value = str(value)
        except Exception:
            return "***"
    if value == "":
        return ""

    if key == "ext03":
        # ext03 是 RSA-wrapped AES key base64，任何情况都不应原样打印。
        return "***"

    if key == "ext02":
        # ext02 是启动参数 JSON 数组字符串，可能含数据库密码等秘钥。
        # 长度 ≤ 32 一律 ***（覆盖绝大多数 launcher 场景）；
        # 仅当长度 > 32 时（理论上极少）露头尾。
        if len(value) <= _EXT02_SHORT_MAX_LEN:
            return "***"
        return (
            value[:_EXT02_LONG_HEAD]
            + "..."
            + value[-_EXT02_LONG_TAIL:]
        )

    # 通用元数据：沿用现有 inline [:N]... 风格（N=20）。
    if len(value) <= 20:
        return value
    return value[:20] + "..."
