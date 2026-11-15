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

        1.5.3 行为：仅在 main.py 走"恢复场景"（db 存在 / db_key 解密失败）时调用。
        fresh install 不走此路径，由 choose_init_path 在终端先询问。

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

    def choose_init_path(self) -> int:
        """
        1.5.3 新增：WebUI 模式下 choose_init_path 不会调用（仅 CLI 使用）。
        保留抽象方法实现，避免破坏 BaseDialog 抽象校验。
        """
        # 直接走 WebUI 流程；等价于 show_user_notice + RESULT_NEW_INSTALL
        self._start_webui_service()
        return BaseDialog.RESULT_NEW_INSTALL

    def choose_recovery_path(self) -> int:
        """
        1.5.3.1 新增：WebUI 模式下恢复场景走 choose_recovery_path 不会调用（仅 CLI 使用）。
        保留抽象方法实现，等价于 show_user_notice + RESULT_WEBUI_RECOVERY。
        """
        self._start_webui_service()
        return BaseDialog.RESULT_WEBUI_RECOVERY

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
            # 1.5.3.2 bug 修复：port 找到后立即置位，让 open_browser 用真实 port
            self._port_ready.set()
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

        def open_browser():
            # 1.5.3.2 bug 修复：等 run() 找到 port 后再开浏览器（解决 race）
            # 之前是 time.sleep(1) + 用写死 default_port → 降级时打开 57218 但 server 在 57217
            self._port_ready.wait(timeout=5)
            time.sleep(0.5)  # 给 uvicorn 监听 socket 一点时间
            webbrowser.open(f"http://127.0.0.1:{self._port}/")

        self._port_ready = threading.Event()
        self._port = default_port  # 占位，run() 找到后立即覆盖

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        # 1.5.3.2 bug 修复：传 self._port（不传 default_port），
        # open_browser 等 port 准备好再开浏览器
        browser_thread = threading.Thread(target=open_browser, daemon=True)
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