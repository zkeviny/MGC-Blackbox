r"""
用户须知确认模块

用途：
- 显示用户须知内容，等待用户确认是否同意
- 支持弹框交互模式和指令自动模式
- 用户须知包含详细的安全规则说明

参考文档：
- document/1.0细节需求文档/MGC启动与密钥输入交互模式.md

限制条件：
- 必须使用src/config/enum_config.py中定义的枚举值
- 必须使用src/config/path_config.py中定义的相对路径
- 所有IO操作必须捕获异常
"""

import sys
import os
from typing import Optional, Tuple

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from mgc.config.enum_config import InstallSource
from mgc.config.i18n_config import get_ui_message, get_exception_message, Messages


class UserNoticeError(Exception):
    """用户须知确认异常"""
    pass


class UserNotice:
    """用户须知确认类"""
    
    def __init__(self):
        """初始化用户须知确认类"""
        self.notice_content = self._get_notice_content()
    
    def _get_notice_content(self) -> str:
        """
        获取用户须知内容
        
        出参：
            用户须知内容字符串
        """
        return f"""{get_ui_message(Messages.UserNotice, "TITLE")}
{get_ui_message(Messages.UserNotice, "TOOL_DESCRIPTION")}
{get_ui_message(Messages.UserNotice, "INFO_MANAGEMENT")}
{get_ui_message(Messages.UserNotice, "PRIVILEGE_DESCRIPTION")}
{get_ui_message(Messages.UserNotice, "UNINSTALLATION_DESCRIPTION")}
{get_ui_message(Messages.UserNotice, "COMPLETE_CLEANUP")}
{get_ui_message(Messages.UserNotice, "AGREEMENT_NOTICE")}

{get_ui_message(Messages.UserNotice, "PRIVACY_STATEMENT")}"""
    
    def show_notice_dialog(self) -> bool:
        """
        弹框交互模式：显示用户须知弹窗
        
        出参：
            True表示同意，False表示不同意
        """
        try:
            print(self.notice_content)
            print("\n" + "="*60)
            print(get_ui_message(Messages.UserNotice, "ENTER_YOUR_CHOICE"))
            print("  " + get_ui_message(Messages.UserNotice, "AGREE_OPTION"))
            print("  " + get_ui_message(Messages.UserNotice, "EXIT_OPTION"))
            print("="*60)
            
            while True:
                choice = input("\n" + get_ui_message(Messages.UserNotice, "SELECT_OPTION")).strip()
                if choice == "1":
                    print("\n✓ " + get_ui_message(Messages.UserNotice, "AGREED_SUCCESS"))
                    return True
                elif choice == "2":
                    print("\n✗ " + get_ui_message(Messages.UserNotice, "EXITED_SUCCESS"))
                    return False
                else:
                    print("\n" + get_ui_message(Messages.UserNotice, "INVALID_INPUT"))
        except KeyboardInterrupt:
            print("\n\n✗ " + get_ui_message(Messages.UserNotice, "USER_INTERRUPTED"))
            return False
        except Exception as e:
            raise UserNoticeError(get_exception_message(Messages.UserNotice, "POPUP_INTERACTION_MODE_EXCEPTION", error=str(e)))
    
    def show_notice_command(self, auto_agree: bool = False) -> bool:
        """
        指令自动模式：显示用户须知内容
        
        入参：
            auto_agree: 是否自动同意（--agree参数）
        
        出参：
            True表示同意，False表示不同意
        """
        try:
            print(self.notice_content)
            print("\n" + "="*60)
            
            if auto_agree:
                print("✓ " + get_ui_message(Messages.UserNotice, "DETECTED_AGREE_PARAMETER"))
                return True
            
            print(get_ui_message(Messages.UserNotice, "ENTER_YES_TO_AGREE"))
            print("="*60)
            
            choice = input("\n" + get_ui_message(Messages.UserNotice, "ENTER_YOUR_CHOICE_AGAIN")).strip().lower()
            if choice == "yes":
                print("\n✓ " + get_ui_message(Messages.UserNotice, "AGREED_SUCCESS_AGAIN"))
                return True
            else:
                print("\n✗ " + get_ui_message(Messages.UserNotice, "DID_NOT_AGREE"))
                return False
        except KeyboardInterrupt:
            print("\n\n✗ " + get_ui_message(Messages.UserNotice, "USER_INTERRUPTED_AGAIN"))
            return False
        except Exception as e:
            raise UserNoticeError(get_exception_message(Messages.UserNotice, "COMMAND_AUTOMATIC_MODE_EXCEPTION", error=str(e)))
    
    def show_notice(self, install_source: InstallSource, auto_agree: bool = False) -> bool:
        """
        显示用户须知并获取用户确认
        
        入参：
            install_source: 安装来源（弹框交互模式或指令自动模式）
            auto_agree: 是否自动同意（仅指令模式有效）
        
        出参：
            True表示同意，False表示不同意
        
        异常：
            UserNoticeError: 用户须知确认失败时抛出
        """
        if install_source == InstallSource.DIALOG:
            return self.show_notice_dialog()
        elif install_source == InstallSource.COMMAND:
            return self.show_notice_command(auto_agree)
        else:
            raise UserNoticeError(f"未知的安装来源: {install_source}")
