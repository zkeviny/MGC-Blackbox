"""A · config_a.py

示例工作流的配置脚本（同时支持 `import` 和 `subprocess` 调用）。

- 作为模块被 import 时：导出 `DEFAULT_USER`、`get_greeting(name)` 等常量与函数
- 作为子进程被 subprocess 运行时：解析命令行参数，把问候语输出到指定文件

跨平台兼容：仅使用 Python 标准库。
"""

import argparse
import os
import sys
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────
# 模块导出（供 B / D 用 import / from-import 引用）
# ──────────────────────────────────────────────────────────────────────

DEFAULT_USER = "MirginCipher 演示用户"
DEFAULT_GREETING = "你好，本问候来自 config_a.py"


def get_greeting(name=None):
    """返回对指定用户的问候语。供 import 端调用。"""
    target = name or DEFAULT_USER
    return f"{DEFAULT_GREETING}（问候对象：{target}）"


# ──────────────────────────────────────────────────────────────────────
# 作为子进程入口（供 C / D 用 subprocess 调用）
# ──────────────────────────────────────────────────────────────────────

def _resolve_output_path(output_arg):
    """根据 --output 参数解析目标写入路径。

    兼容以下三种写法（字符串字面量）：
      1. 绝对路径
      2. ./relative.txt 相对路径（相对工作目录）
      3. ~ 开头用户目录
    """
    if not output_arg:
        return None
    expanded = os.path.expanduser(output_arg)
    return Path(expanded)


def main():
    parser = argparse.ArgumentParser(
        prog="config_a",
        description="A 配置脚本：演示 argparse 自动识别 + 作为子进程被调用",
    )
    parser.add_argument(
        "--user",
        default=DEFAULT_USER,
        help="问候对象，默认为 DEFAULT_USER",
    )
    parser.add_argument(
        "--greeting",
        default=DEFAULT_GREETING,
        help="问候内容，默认为 DEFAULT_GREETING",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="把问候语写到指定路径（演示：显式落盘结果物）",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="同时把问候语打到 stdout",
    )
    args = parser.parse_args()

    message = f"{args.greeting}（问候对象：{args.user}）"

    if args.print:
        # subprocess.run(capture_output=True) 可读到这一行
        print(message, flush=True)

    output_path = _resolve_output_path(args.output)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(message + "\n", encoding="utf-8")
        # 这一行不会被上层捕获，仅写 stderr 方便调试
        print(f"[config_a] wrote to: {output_path}", file=sys.stderr, flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())