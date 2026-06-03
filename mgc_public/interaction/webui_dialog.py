"""
WebUI 对话框实现

用途：
- 启动 WebUI 服务
- 打开默认浏览器
- 等待用户完成交互
"""

import os
import sys
import webbrowser
import threading
import time
from typing import Tuple

from .base_dialog import BaseDialog


class WebuiDialog(BaseDialog):
    """WebUI 实现"""

    def show_user_notice(self) -> int:
        """
        启动 WebUI 并显示用户须知

        出参：
            1: 新安装（WebUI 启动后直接返回，让 main.py 继续检查）
            2: 迁移/重建
            0: 不安装
           -1: 取消
        """
        self._start_webui_service()
        # 不再等待用户完成，直接返回新安装
        # main.py 会检查密钥文件是否存在来判断安装是否完成
        return BaseDialog.RESULT_NEW_INSTALL

    def confirm(self, message: str) -> bool:
        """WebUI 模式下不常用，直接返回 True"""
        return True

    def show_message(self, title: str, message: str):
        """WebUI 模式下不常用"""
        pass

    def input_root_key(self) -> Tuple[str, str]:
        """
        WebUI 模式下：等待用户在浏览器中完成输入

        出参：(personal_key, weight_param)
        """
        self._wait_for_result()
        from .webui_dialog import get_webui_result
        result = get_webui_result()
        return result.get("personal_key", ""), result.get("weight_param", "")

    def input_migrate_key(self) -> str:
        """
        迁移模式：等待用户从 WebUI 输入数据库路径

        出参：数据库路径
        """
        self._wait_for_result()
        from .webui_dialog import get_webui_result
        result = get_webui_result()
        return result.get("db_path", "")

    def _start_webui_service(self):
        """启动 WebUI 服务"""
        default_port = 57218
        
        def run():
            from mgc.presentation.webui.app import app, set_server_control
            import uvicorn
            port = self._find_available_port(default_port)
            self._port = port
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

        def open_browser(port):
            time.sleep(1)
            webbrowser.open(f"http://127.0.0.1:{port}/")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        browser_thread = threading.Thread(target=open_browser, args=(default_port,), daemon=True)
        browser_thread.start()

    def _find_available_port(self, start_port: int) -> int:
        """寻找可用端口"""
        import socket
        port = start_port
        while port >= 57200:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", port))
                    return port
            except OSError:
                port -= 1
        return 57218

    def _wait_for_result(self):
        """等待 WebUI 返回结果"""
        from .webui_dialog import wait_for_completion
        wait_for_completion()


_webui_result = {}
_webui_completed = threading.Event()


def set_webui_result(result: dict):
    """设置 WebUI 返回结果"""
    global _webui_result
    _webui_result = result
    _webui_completed.set()


def get_webui_result() -> dict:
    """获取 WebUI 返回结果"""
    return _webui_result


def wait_for_completion():
    """等待用户完成交互"""
    _webui_completed.wait()
    _webui_completed.clear()