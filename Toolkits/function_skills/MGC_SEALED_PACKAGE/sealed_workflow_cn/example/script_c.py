"""C · script_c.py

C 脚本：通过 subprocess.run（字面量列表）调用 config_a.py，
并把问候语写到桌面 txt2 文件中。

演示 ext08 识别的模式：
  - `subprocess.run([sys.executable, "config_a.py", "--user", "...", "--output", "..."])`
    （subprocess 字面量列表）
"""

import argparse
import subprocess
import sys
from pathlib import Path


def _resolve_desktop():
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home()
    return desktop


def fetch_greeting_via_subprocess(user, greeting, output_path):
    """用 subprocess 启动 config_a.py，传入 --user / --greeting / --output。"""
    # ── 同包 subprocess：MGC ext08 自动识别 ──────────────────────────
    completed = subprocess.run(
        [
            sys.executable,           # Python 解释器路径
            "config_a.py",            # 字面量：同包相对路径
            "--user", user,           # 字面量参数
            "--greeting", greeting,   # 字面量参数
            "--output", str(output_path),  # 字面量参数
        ],
        capture_output=True,           # 捕获 stdout / stderr
        text=True,                     # UTF-8 解码
        encoding="utf-8",
    )

    if completed.returncode != 0:
        print(
            f"[script_c] config_a failed: rc={completed.returncode}\n"
            f"stderr: {completed.stderr}",
            file=sys.stderr,
            flush=True,
        )
        raise RuntimeError(f"config_a.py exited with code {completed.returncode}")

    # subprocess 的 stdout 也会通过 capture_output 拿到
    return completed.stdout.strip() or None


def write_summary_file(user, greeting):
    """写桌面 txt2.txt，包含本脚本运行摘要。"""
    desktop = _resolve_desktop()
    target = desktop / "txt2.txt"
    target.parent.mkdir(parents=True, exist_ok=True)

    target.write_text(
        f"[script_c] 调用方式：subprocess (字面量列表)\n"
        f"[script_c] 调用方：script_c.py\n"
        f"[script_c] 被调用方：config_a.py\n"
        f"[script_c] 传入 user：{user}\n"
        f"[script_c] 传入 greeting：{greeting}\n",
        encoding="utf-8",
    )
    print(f"[script_c] summary wrote to: {target}", file=sys.stderr, flush=True)
    return target


def run(user="脚本 C 演示用户", greeting="你好，本问候来自 script_c.py via subprocess", output=None):
    """对外统一入口，供 D 用 subprocess 调用。"""
    desktop = _resolve_desktop()
    config_derived = desktop / "txt2_via_a.txt"

    # 调 A（subprocess 字面量列表）—— ext08 识别
    fetch_greeting_via_subprocess(user, greeting, config_derived)

    # 写本脚本摘要
    summary = write_summary_file(user, greeting)

    if output:
        Path(output).write_text(str(summary), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(
        prog="script_c",
        description="C 脚本：通过 subprocess 调用 config_a.py",
    )
    parser.add_argument("--user", default="脚本 C 演示用户")
    parser.add_argument(
        "--greeting",
        default="你好，本问候来自 script_c.py via subprocess",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="把 txt2.txt 的实际路径写入该文件",
    )
    args = parser.parse_args()

    run(user=args.user, greeting=args.greeting, output=args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())