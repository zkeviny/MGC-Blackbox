"""
交互对话框抽象基类

用途：
- 定义所有对话框的抽象接口
- 统一返回码

返回码定义：
- RESULT_NO_INSTALL = 0   不安装
- RESULT_NEW_INSTALL = 1   初次安装
- RESULT_MIGRATE = 2      取消/迁移（预留）
- RESULT_CANCEL = -1   取消
"""

from abc import ABC, abstractmethod
from typing import Tuple


class BaseDialog(ABC):
    """交互对话框抽象基类"""

    RESULT_NO_INSTALL = 0
    RESULT_NEW_INSTALL = 1
    RESULT_MIGRATE = 2
    RESULT_CANCEL = -1

    @abstractmethod
    def show_user_notice(self) -> int:
        """
        显示用户须知

        出参：
            -1: 取消
             0: 不安装
             1: 初次安装
             2: 迁移（预留）
        """
        pass

    @abstractmethod
    def input_root_key(self) -> Tuple[str, str]:
        """
        输入根密钥（两个独立输入）

        出参：(personal_key, weight_param)
        """
        pass

    @abstractmethod
    def input_migrate_key(self) -> str:
        """输入迁移密钥"""
        pass

    @abstractmethod
    def confirm(self, message: str) -> bool:
        """确认按钮"""
        pass

    @abstractmethod
    def show_message(self, title: str, message: str):
        """显示消息"""
        pass