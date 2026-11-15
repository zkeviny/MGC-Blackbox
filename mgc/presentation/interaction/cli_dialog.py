"""
命令行对话框实现

用途：
- 命令行交互模式
- 无 GUI 环境时的备选方案
"""

from typing import Tuple
import os

from .base_dialog import BaseDialog


def _get_load_user_notice():
    from .dialog_factory import load_user_notice
    return load_user_notice()


def _check_db_key_exists() -> bool:
    """检查 DB_KEY.json 是否存在"""
    from mgc.key_storage.db_key_manager import exists
    return exists()


def _check_database_exists() -> bool:
    """检查数据库是否存在"""
    from mgc.config.path_config import DB_FILE
    return DB_FILE.exists()


class CliDialog(BaseDialog):
    """命令行实现"""

    def show_user_notice(self) -> int:
        """显示用户须知（保留旧路径，仅供恢复场景使用）"""
        notice = _get_load_user_notice()
        print("\n" + "=" * 60)
        print(notice)
        print("=" * 60)

        db_key_exists = _check_db_key_exists()
        db_exists = _check_database_exists()

        print("\nOptions:")
        if db_exists:
            print("  1 - Confirm")
        else:
            print("  1 - New Install")
        print("  2 - Migrate (database exist)")
        print("  0 - Exit")

        valid_choices = ["0", "1", "2"]

        while True:
            choice = input("Select option: ").strip()
            if choice in valid_choices:
                return int(choice)
            print("Invalid selection, please try again")

    def choose_init_path(self) -> int:
        """
        1.5.3 新增：CLI 询问初始化路径（仅 fresh install 场景使用）。

        打印 InitFlow.CLI_BANNER + 1/2/3 三选项。
        返回 BaseDialog.RESULT_RANDOM_GENERATE / RESULT_NEW_INSTALL / RESULT_CANCEL_INSTALL。
        """
        from mgc.config.i18n_config import Messages

        print(Messages.InitFlow.CLI_BANNER)

        while True:
            raw = input(Messages.InitFlow.CLI_PROMPT).strip()
            if raw == "1":
                return BaseDialog.RESULT_RANDOM_GENERATE
            if raw == "2":
                return BaseDialog.RESULT_NEW_INSTALL
            if raw == "3":
                return BaseDialog.RESULT_CANCEL_INSTALL
            print(Messages.InitFlow.CLI_INVALID)

    def choose_recovery_path(self) -> int:
        """
        1.5.3.1 新增：CLI 询问恢复路径（db 存在但 key 丢失 / 解密失败场景）。

        返回 BaseDialog.RESULT_WEBUI_RECOVERY / RESULT_CLI_INPUT / RESULT_CANCEL_INSTALL。
        """
        from mgc.config.i18n_config import Messages

        print(Messages.InitFlow.CLI_RECOVERY_BANNER)

        while True:
            raw = input(Messages.InitFlow.CLI_PROMPT).strip()
            if raw == "1":
                return BaseDialog.RESULT_WEBUI_RECOVERY
            if raw == "2":
                return BaseDialog.RESULT_CLI_INPUT
            if raw == "3":
                return BaseDialog.RESULT_CANCEL_INSTALL
            print(Messages.InitFlow.CLI_INVALID)

    def input_root_key(self) -> Tuple[str, str]:
        """
        Enter Root Key (two separate inputs)

        Output: (personal_key, weight_param)
        """
        print("\n[WARNING] Please remember your personal key and weight parameter.")
        print("[WARNING] Loss will result in unrecoverable data and failed migration.")
        print("\nEnter Root Key")

        while True:
            personal_key = input("Personal Key: ").strip()
            if personal_key:
                break
            print("Cannot be empty, please try again")

        while True:
            weight_param = input("Weight Parameter (1-9): ").strip()
            if weight_param.isdigit() and 1 <= int(weight_param) <= 9:
                break
            print("Please enter a single digit 1-9")

        return personal_key, weight_param

    def input_migrate_key(self) -> Tuple[str, str, str]:
        """
        Enter Migration Key and Database Path

        Output: (personal_key, weight_param, db_path)
        """
        print("\n[WARNING] For device migration, you need to provide the database path from the old environment.")
        print("[WARNING] The database will be copied to the current MGC installation directory.")

        print("\nEnter Database Path (from old environment):")
        while True:
            db_path = input("Database Path: ").strip()
            if db_path and os.path.exists(db_path):
                break
            print("File does not exist, please try again")

        print("\nEnter Root Key from old environment")

        while True:
            personal_key = input("Personal Key: ").strip()
            if personal_key:
                break
            print("Cannot be empty, please try again")

        while True:
            weight_param = input("Weight Parameter (1-9): ").strip()
            if weight_param.isdigit() and 1 <= int(weight_param) <= 9:
                break
            print("Please enter a single digit 1-9")

        return personal_key, weight_param, db_path

    def confirm(self, message: str) -> bool:
        """Confirm button"""
        print(f"\n{message}")
        print("Options: y (yes) / n (no)")
        while True:
            choice = input("Confirm (y/n): ").strip().lower()
            if choice in ("y", "yes"):
                return True
            if choice in ("n", "no"):
                return False
            print("Invalid selection")

    def show_message(self, title: str, message: str):
        """显示消息"""
        print(f"\n{title}")
        print(message)
