r"""
迁移密钥文件保存模块

用途：
- 将迁移密钥自动导出为MGC迁移密钥.txt文件
- 支持弹框模式自定义路径和指令模式默认路径
- 提示用户妥善保管，明确风险提示

参考文档：
- document/1.0细节需求文档/MGC启动与密钥输入交互模式.md

限制条件：
- 必须使用src/config/path_config.py中定义的相对路径
- 所有IO操作必须捕获异常
"""

import os
from pathlib import Path
from typing import Tuple

from mgc.config.i18n_config import get_exception_message, get_ui_message, Messages


class MigrateKeySaveError(Exception):
    """迁移密钥保存异常"""
    pass


class MigrateKeySaver:
    """迁移密钥文件保存类"""
    
    def __init__(self):
        """初始化迁移密钥文件保存类"""
        pass
    
    def save_migrate_key(self, migrate_key: str, save_path: str, install_source: str, personal_key: str = None, weight_param: str = None) -> Tuple[bool, str]:
        """
        保存迁移密钥到指定路径
        
        入参：
            migrate_key: 迁移密钥
            save_path: 保存路径
            install_source: 安装来源（弹框交互模式或指令自动模式）
            personal_key: 个人密钥（可选）
            weight_param: 权重参数（可选）
        
        出参：
            (is_success, message)
            is_success: 是否成功
            message: 成功/失败消息
        
        异常：
            MigrateKeySaveError: 保存失败时抛出
        """
        try:
            save_path = self._normalize_save_path(save_path)
            self._ensure_directory_exists(save_path)
            self._write_migrate_key_file(migrate_key, save_path, personal_key, weight_param)
            
            message = get_ui_message(Messages.MigrateKeySaverUI, "MIGRATE_KEY_SAVED_TO", save_path=save_path) + "\n" + get_ui_message(Messages.MigrateKeySaverUI, "KEY_LOSS_CANNOT_MIGRATE")
            
            if install_source == "DIALOG":
                self._show_save_success_dialog(save_path)
            else:
                self._show_save_success_command(save_path)
            
            return True, message
        except Exception as e:
            error_msg = f"迁移密钥保存失败: {str(e)}"
            if install_source == "DIALOG":
                self._show_save_error_dialog(error_msg)
            else:
                self._show_save_error_command(error_msg)
            raise MigrateKeySaveError(get_exception_message(Messages.MigrateKeySaver, "SAVE_MIGRATE_KEY_FAILED", error=str(e)))
    
    def _normalize_save_path(self, save_path: str) -> str:
        """
        规范化保存路径
        
        入参：
            save_path: 原始保存路径
        
        出参：
            规范化后的保存路径
        """
        path = Path(save_path)
        
        # 检查路径是否以分隔符结尾（目录路径）
        if save_path.endswith(os.sep) or save_path.endswith('/'):
            path = path / "MGC迁移密钥.txt"
        elif path.is_dir():
            path = path / "MGC迁移密钥.txt"
        
        if path.suffix != ".txt":
            path = path.with_suffix(".txt")
        
        return str(path.absolute())
    
    def _ensure_directory_exists(self, save_path: str) -> None:
        """
        确保保存目录存在
        
        入参：
            save_path: 保存路径
        
        异常：
            MigrateKeySaveError: 目录创建失败时抛出
        """
        try:
            path = Path(save_path)
            directory = path.parent
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise MigrateKeySaveError(get_exception_message(Messages.MigrateKeySaver, "CREATE_SAVE_DIRECTORY_FAILED", error=str(e)))
    
    def _write_migrate_key_file(self, migrate_key: str, save_path: str, personal_key: str = None, weight_param: str = None) -> None:
        """
        写入迁移密钥文件
        
        入参：
            migrate_key: 迁移密钥
            save_path: 保存路径
            personal_key: 个人密钥（可选）
            weight_param: 权重参数（可选）
        
        异常：
            MigrateKeySaveError: 文件写入失败时抛出
        """
        try:
            content = f"""MirginCipher Migration Key

This key is used for environment migration authentication and dynamic salt encryption, please keep it safe.

Personal Key: {personal_key if personal_key else 'N/A'}
Weight Param: {weight_param if weight_param else 'N/A'}

Migration Key:
{migrate_key}

Important Notice:
- If this key is lost, environment migration will be impossible and cannot be recovered
- Do not share this key with anyone
- It is recommended to save this file in a safe location
"""
            
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            raise MigrateKeySaveError(get_exception_message(Messages.MigrateKeySaver, "WRITE_MIGRATE_KEY_FILE_FAILED", error=str(e)))
    
    def _show_save_success_dialog(self, save_path: str) -> None:
        """
        弹框模式：显示保存成功提示
        
        入参：
            save_path: 保存路径
        """
        print("\n" + "="*60)
        print(get_ui_message(Messages.MigrateKeySaverUI, "SAVE_SUCCESS_TITLE"))
        print("="*60)
        print(get_ui_message(Messages.MigrateKeySaverUI, "MIGRATE_KEY_SAVED_TO", save_path=save_path))
        print("\n" + get_ui_message(Messages.MigrateKeySaverUI, "IMPORTANT_NOTICE"))
        print(get_ui_message(Messages.MigrateKeySaverUI, "KEY_LOSS_CANNOT_MIGRATE"))
        print(get_ui_message(Messages.MigrateKeySaverUI, "DO_NOT_SHARE_KEY"))
        print(get_ui_message(Messages.MigrateKeySaverUI, "SAVE_IN_SAFE_LOCATION"))
        print("="*60)
    
    def _show_save_success_command(self, save_path: str) -> None:
        """
        指令模式：显示保存成功提示
        
        入参：
            save_path: 保存路径
        """
        print(f"\n✓ " + get_ui_message(Messages.MigrateKeySaverUI, "MIGRATE_KEY_SAVED_TO_COMMAND", save_path=save_path))
        print("  " + get_ui_message(Messages.MigrateKeySaverUI, "KEEP_SAFE_CANNOT_RECOVER"))
    
    def _show_save_error_dialog(self, error_msg: str) -> None:
        """
        弹框模式：显示保存失败提示
        
        入参：
            error_msg: 错误消息
        """
        print("\n" + "="*60)
        print(get_ui_message(Messages.MigrateKeySaverUI, "SAVE_FAILED_TITLE"))
        print("="*60)
        print(get_ui_message(Messages.MigrateKeySaverUI, "ERROR_INFORMATION", error_msg=error_msg))
        print("="*60)
    
    def _show_save_error_command(self, error_msg: str) -> None:
        """
        指令模式：显示保存失败提示
        
        入参：
            error_msg: 错误消息
        """
        print(f"\n✗ {error_msg}")
