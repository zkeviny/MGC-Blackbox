"""B · script_b.py

B 脚本：通过 `import config_a` 和 `from config_a import get_greeting` 两种方式
从 A 取值，并把问候语写到桌面 txt1 文件中。

演示 ext08 识别的两种模式：
  - `import config_a`                                （普通 import）
  - `from config_a import get_greeting, DEFAULT_USER`（from-import）
"""

import argparse
import sys
from pathlib import Path

# ── 同包 import：MGC ext08 自动识别 ──────────────────────────────────
import config_a                              # 模式：import
from config_a import get_greeting, DEFAULT_USER  # 模式：from-import


def _resolve_desktop():
    """跨平台获取桌面路径。Linux 不一定有 ~/Desktop，回退到 home。"""
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home()
    return desktop


def write_greeting_file(user_name=None, tag="[script_b]"):
    """把对指定用户的问候语写入桌面 txt1 文件。"""
    # 调用从 config_a 导入的函数
    message = get_greeting(user_name)

    desktop = _resolve_desktop()
    target = desktop / "txt1.txt"

    # 显式落盘结果物（MGC 黑盒执行不依赖 print，被调用方通过文件读取）
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"{tag} {message}\n"
        f"{tag} DEFAULT_USER from import = {DEFAULT_USER}\n",
        encoding="utf-8",
    )
    print(f"[script_b] wrote to: {target}", file=sys.stderr, flush=True)
    return target


def run(user=None, output=None):
    """对外统一入口，供 D 用 import 调用。"""
    target_user = user or DEFAULT_USER
    written = write_greeting_file(target_user)
    if output:
        # 如果调用方传入 --output，则把本脚本的产出路径告知调用方
        Path(output).write_text(str(written), encoding="utf-8")
    return written


def main():
    parser = argparse.ArgumentParser(
        prog="script_b",
        description="B 脚本：通过 import / from-import 从 config_a 取问候语",
    )
    parser.add_argument("--user", default=None, help="覆盖默认问候对象")
    parser.add_argument(
        "--output",
        default=None,
        help="把 txt1.txt 的实际路径写入该文件",
    )
    args = parser.parse_args()

    run(user=args.user, output=args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())