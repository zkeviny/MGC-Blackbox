"""
命令行对话框实现

用途：
- 命令行交互模式
- 无 GUI 环境时的备选方案
"""

from typing import Tuple, Optional
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
        """显示用户须知"""
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

    def input_change_root_key(self) -> Optional[Tuple[str, str, str, str]]:
        """
        Enter old and new root key for change

        Output: (old_personal_key, old_weight_param, new_personal_key, new_weight_param)
                or None if user cancels
        """
        print("\n" + "=" * 60)
        print("[ROOT KEY CHANGE]")
        print("=" * 60)

        print("\n[STEP 1] Verify old key")

        while True:
            old_personal_key = input("Current Personal Key: ").strip()
            if old_personal_key:
                break
            print("Cannot be empty, please try again")

        while True:
            old_weight_param = input("Current Weight Parameter (1-9): ").strip()
            if old_weight_param.isdigit() and 1 <= int(old_weight_param) <= 9:
                break
            print("Please enter a single digit 1-9")

        print("\n[STEP 2] Enter new key")

        while True:
            new_personal_key = input("New Personal Key: ").strip()
            if new_personal_key:
                break
            print("Cannot be empty, please try again")

        while True:
            new_weight_param = input("New Weight Parameter (1-9): ").strip()
            if new_weight_param.isdigit() and 1 <= int(new_weight_param) <= 9:
                break
            print("Please enter a single digit 1-9")

        if old_personal_key == new_personal_key and old_weight_param == new_weight_param:
            print("\n[ERROR] New key cannot be the same as old key")
            return None

        return old_personal_key, old_weight_param, new_personal_key, new_weight_param

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
