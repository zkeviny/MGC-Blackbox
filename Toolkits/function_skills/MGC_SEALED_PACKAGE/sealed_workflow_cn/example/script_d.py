"""D · script_d.py

D 脚本：同时调用 B 和 C 两种脚本（import + subprocess 并存），
演示 driver 模式：把 B / C 的产出都汇总到桌面 txt1.txt + txt2.txt。

演示 ext08 同时识别两种模式：
  - `import script_b` + `script_b.run(...)`                （import）
  - `subprocess.run([sys.executable, "script_c.py", ...])` （subprocess 字面量）
"""

import argparse
import subprocess
import sys
from pathlib import Path

# ── 同包 import：MGC 1.5.1 ext08 自动识别 ─────────────────────────────
import script_b                              # 模式：import


def _resolve_desktop():
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home()
    return desktop


def call_b_via_import(user):
    """通过 import 直接调用 script_b.run() —— ext08 识别的 import 模式。"""
    return script_b.run(user=user)


def call_c_via_subprocess(user, greeting):
    """通过 subprocess 启动 script_c.py —— ext08 识别的 subprocess 模式。"""
    completed = subprocess.run(
        [
            sys.executable,
            "script_c.py",
            "--user", user,
            "--greeting", greeting,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if completed.returncode != 0:
        print(
            f"[script_d] script_c failed: rc={completed.returncode}\n"
            f"stderr: {completed.stderr}",
            file=sys.stderr,
            flush=True,
        )
        raise RuntimeError(f"script_c.py exited with code {completed.returncode}")
    return completed


def write_combined_summary(b_path, c_stdout):
    """把 B / C 的产出汇总到桌面 combined.txt。"""
    desktop = _resolve_desktop()
    target = desktop / "combined.txt"
    target.parent.mkdir(parents=True, exist_ok=True)

    target.write_text(
        f"[script_d] ===== 汇总 =====\n"
        f"[script_d] 调用方：script_d.py\n"
        f"[script_d] B (import)         写到：{b_path}\n"
        f"[script_d] C (subprocess)     stdout：{(c_stdout or '').strip() or '(无 stdout 输出)'}\n"
        f"[script_d] C 的 txt2.txt 与 txt2_via_a.txt 已写到桌面\n",
        encoding="utf-8",
    )
    print(f"[script_d] combined wrote to: {target}", file=sys.stderr, flush=True)
    return target


def run(user="脚本 D 演示用户", greeting="你好，本问候来自 script_d.py 编排 BC"):
    """D 的对外入口（供 mgc_run 调用）。"""
    b_path = call_b_via_import(user)
    c_result = call_c_via_subprocess(user, greeting)
    combined = write_combined_summary(b_path, c_result.stdout)

    # 在桌面同时确保 txt1.txt / txt2.txt 都存在（来自 B 和 C 的脚本）
    print(
        f"[script_d] 完成。B 输出：{b_path}\n"
        f"[script_d] C stdout：{c_result.stdout.strip()}\n"
        f"[script_d] 汇总：{combined}",
        file=sys.stderr,
        flush=True,
    )
    return combined


def main():
    parser = argparse.ArgumentParser(
        prog="script_d",
        description="D 脚本：编排 B (import) + C (subprocess)，汇总产出",
    )
    parser.add_argument("--user", default="脚本 D 演示用户")
    parser.add_argument(
        "--greeting",
        default="你好，本问候来自 script_d.py 编排 BC",
    )
    args = parser.parse_args()

    run(user=args.user, greeting=args.greeting)
    return 0


if __name__ == "__main__":
    sys.exit(main())