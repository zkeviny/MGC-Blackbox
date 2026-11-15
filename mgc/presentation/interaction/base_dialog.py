"""
交互对话框抽象基类

用途：
- 定义所有对话框的抽象接口
- 统一返回码

返回码定义：
- RESULT_NO_INSTALL = 0          不安装
- RESULT_NEW_INSTALL = 1         初次安装（人工通过 WebUI 设置）
- RESULT_MIGRATE = 2             迁移
- RESULT_RANDOM_GENERATE = 3     1.5.3 新增：随机生成 personal_key + weight
- RESULT_CANCEL_INSTALL = 4      1.5.3 新增：取消安装并关闭 MGC
- RESULT_WEBUI_RECOVERY = 5      1.5.3.1 新增：恢复场景走 WebUI
- RESULT_CLI_INPUT = 6           1.5.3.1 新增：恢复场景 CLI 直接输入秘钥
- RESULT_CANCEL = -1             取消（兼容旧语义）
"""

from abc import ABC, abstractmethod
from typing import Tuple


class BaseDialog(ABC):
    """交互对话框抽象基类"""

    RESULT_NO_INSTALL = 0
    RESULT_NEW_INSTALL = 1
    RESULT_MIGRATE = 2
    RESULT_RANDOM_GENERATE = 3   # 1.5.3 新增
    RESULT_CANCEL_INSTALL = 4    # 1.5.3 新增
    RESULT_WEBUI_RECOVERY = 5    # 1.5.3.1 新增
    RESULT_CLI_INPUT = 6         # 1.5.3.1 新增
    RESULT_CANCEL = -1

    @abstractmethod
    def show_user_notice(self) -> int:
        """
        显示用户须知

        出参（1.5.3 fresh install 三选项语义）：
            BaseDialog.RESULT_RANDOM_GENERATE (3): 随机生成 personal_key + weight
            BaseDialog.RESULT_NEW_INSTALL (1): 人工通过 WebUI 设置
            BaseDialog.RESULT_CANCEL_INSTALL (4): 取消并关闭 MGC

        兼容保留：
            RESULT_NO_INSTALL (0) / RESULT_MIGRATE (2) / RESULT_CANCEL (-1)
        """
        pass

    @abstractmethod
    def choose_init_path(self) -> int:
        """
        1.5.3 新增：CLI 询问初始化路径（fresh install 场景）。

        出参：
            BaseDialog.RESULT_RANDOM_GENERATE (3): 选 1
            BaseDialog.RESULT_NEW_INSTALL (1):    选 2
            BaseDialog.RESULT_CANCEL_INSTALL (4): 选 3
        """
        pass

    @abstractmethod
    def choose_recovery_path(self) -> int:
        """
        1.5.3.1 新增：CLI 询问恢复路径（db 存在但 key 丢失 / 解密失败场景）。

        出参：
            BaseDialog.RESULT_WEBUI_RECOVERY (5): 选 1（启 WebUI 设置）
            BaseDialog.RESULT_CLI_INPUT (6):      选 2（CLI 直接输入）
            BaseDialog.RESULT_CANCEL_INSTALL (4): 选 3（取消）
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