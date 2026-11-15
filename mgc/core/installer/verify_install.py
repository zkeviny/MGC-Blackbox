"""安装验证脚本

功能：
- 验证MirginCipher安装是否成功
- 检查核心模块是否可导入
- 检查用户目录是否创建
- 检查配置文件是否存在
- 检查Skill文档是否存在

依赖：
- os（文件操作）
- pathlib（路径操作）
"""

from pathlib import Path
from mgc.utils.path_utils import get_user_dir
from mgc.config.i18n_config import Messages


def verify_install():
    """
    验证安装

    @return: 是否验证成功
    """
    errors = []

    # 检查核心模块导入
    try:
        from mgc.core.mgc_service.crypto_service import CryptoService
        from mgc.core.mgc_service.mgc_core_service import MGCCoreService
        from mgc.core.weight.weight_service import WeightService
        from mgc.config.enum_config import UpdateLevel
    except ImportError as e:
        errors.append(Messages.Package.CORE_MODULE_IMPORT_FAILED.format(error=e))

    # 检查用户目录
    user_dir = get_user_dir()

    if not user_dir.exists():
        errors.append(f"用户目录不存在: {user_dir}")

    # 检查配置文件
    config_dir = user_dir / "config"
    if not config_dir.exists():
        errors.append(f"配置目录不存在: {config_dir}")

    # 检查Skill文档
    skills_dir = user_dir / "skills"
    if not skills_dir.exists():
        errors.append(f"Skill目录不存在: {skills_dir}")

    if errors:
        print(Messages.Package.INSTALL_VERIFICATION_FAILED)
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print(Messages.Package.INSTALL_VERIFICATION_SUCCESSFUL)
        return True


if __name__ == "__main__":
    success = verify_install()
    exit(0 if success else 1)
