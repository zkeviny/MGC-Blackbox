"""卸载脚本

功能：
- 卸载MirginCipher
- 保留或删除用户数据

依赖：
- os（文件操作）
- shutil（文件删除）
- pathlib（路径操作）
"""

import os
import shutil
from pathlib import Path
from mgc.utils.path_utils import get_user_dir
from mgc.config.i18n_config import Messages


def uninstall(clean_data=False):
    """
    卸载MirginCipher

    @param clean_data: 是否清理用户数据（默认False）
    """
    from mgc.utils.path_utils import get_user_dir
    user_dir = get_user_dir()

    print("MirginCipher卸载流程")
    print("=" * 50)

    # 提示用户数据保留
    if not clean_data:
        print(f"\n{Messages.Package.USER_DATA_WILL_BE_PRESERVED}")
        print(f"User data directory: {user_dir}")
        print("For complete uninstall, run: mgc uninstall --clean-data")
    else:
        print(f"\n{Messages.Package.WARNING_USER_DATA_WILL_BE_DELETED}")
        print(f"User data directory: {user_dir}")
        confirm = input(Messages.Package.CONFIRM_DELETE_USER_DATA)
        if confirm.lower() != "yes":
            print(Messages.Package.CANCEL_UNINSTALLATION)
            return

    # 清理用户数据（可选）
    if clean_data and user_dir.exists():
        shutil.rmtree(user_dir)
        print(f"✓ 已删除用户数据: {user_dir}")

    print(f"\n✓ {Messages.Package.UNINSTALL_COMPLETE}")
    print(Messages.Package.PLEASE_RUN.format(command="pip uninstall mirgincipher"))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MirginCipher Uninstaller")
    parser.add_argument(
        "--clean-data",
        action="store_true",
        help="删除用户数据（默认保留）"
    )
    args = parser.parse_args()

    uninstall(clean_data=args.clean_data)
