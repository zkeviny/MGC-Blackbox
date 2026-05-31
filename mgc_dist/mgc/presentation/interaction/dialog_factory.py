"""
对话框工厂

用途：
- 自动检测可用对话框类型
- 统一创建对话框实例

支持类型：
- webui: Web 界面交互
- gui: tkinter 弹框（已废弃）
- cli: 命令行交互
- auto: 自动检测
"""

import sys
import os
from typing import Optional

from .base_dialog import BaseDialog


class DialogFactory:
    """对话框工厂"""

    DIALOG_WEBUI = "webui"
    DIALOG_GUI = "gui"
    DIALOG_CLI = "cli"
    DIALOG_AUTO = "auto"

    _instance: Optional[BaseDialog] = None

    @staticmethod
    def create(dialog_type: str = None) -> BaseDialog:
        """
        创建对话框实例

        入参：
            dialog_type: "webui"/"gui"/"cli"/"auto"，默认 auto

        出参：
            BaseDialog 实例
        """
        if not dialog_type:
            dialog_type = DialogFactory.DIALOG_AUTO

        if dialog_type == DialogFactory.DIALOG_WEBUI:
            from .webui_dialog import WebuiDialog
            return WebuiDialog()

        if dialog_type == DialogFactory.DIALOG_GUI:
            # GUI 已废弃，提示使用 WebUI 或 CLI
            print("[DEPRECATED] GUI is deprecated. Use WebUI or CLI.")
            raise RuntimeError("GUI is deprecated. Use WebUI or CLI.")

        if dialog_type == DialogFactory.DIALOG_CLI:
            from .cli_dialog import CliDialog
            return CliDialog()

        if dialog_type == DialogFactory.DIALOG_AUTO:
            return DialogFactory._auto_detect()

        raise ValueError(f"未知对话框类型: {dialog_type}")

    @staticmethod
    def _auto_detect() -> BaseDialog:
        """
        自动检测可用对话框类型

        检测逻辑（优先级）：
        1. WebUI 优先尝试
        2. WebUI 失败则降级到 CLI
        3. CLI 不可用 → 报错
        """
        print("[DialogFactory] Auto-detecting dialog type...")

        print("[DialogFactory] Trying WebUI...")
        try:
            from .webui_dialog import WebuiDialog
            return WebuiDialog()
        except Exception as e:
            print(f"[DialogFactory] WebUI failed: {e}")
            print("[DialogFactory] Falling back to CLI...")
            try:
                from .cli_dialog import CliDialog
                return CliDialog()
            except Exception as e2:
                raise RuntimeError(f"WebUI and CLI both unavailable: {e}, {e2}")

    @staticmethod
    def _create_cli() -> BaseDialog:
        """创建 CLI 对话框"""
        from .cli_dialog import CliDialog
        return CliDialog()


def load_user_notice() -> str:
    """
    加载用户须知内容

    出参：
        str: 用户须知文本
    """
    notice_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "config", "user_notice.txt"
    )
    try:
        with open(notice_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ("MGC will be installed on this device for storing AI Agent privacy information.\n\n"
                "Options:\nYes - New install\nNo - Do not install")