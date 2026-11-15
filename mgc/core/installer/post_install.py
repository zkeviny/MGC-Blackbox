"""安装后处理脚本

功能：
- 创建用户目录结构
- 复制配置文件
- 复制Skill文档
- 初始化数据库

依赖：
- os（文件操作）
- shutil（文件复制）
- pathlib（路径操作）
"""

import os
import shutil
from pathlib import Path
from mgc.utils.path_utils import get_user_dir
from mgc.config.i18n_config import Messages


def create_directory_structure():
    """
    创建用户目录结构

    @return: 是否创建成功
    """
    try:
        user_dir = get_user_dir()

        # 创建目录
        directories = [
            user_dir / "config",
            user_dir / "data",
            user_dir / "cache",
            user_dir / "logs",
            user_dir / "skills",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        return True
    except Exception as e:
        print(f"Failed to create directory structure: {e}")
        return False


def copy_config_files():
    """
    复制配置文件

    @return: 是否复制成功
    """
    try:
        user_dir = get_user_dir()
        config_dir = user_dir / "config"

        # 检查配置文件是否已存在
        if (config_dir / "remote_config.yaml").exists():
            print("Config file already exists, skipping copy")
            return True

        # 复制示例配置文件
        src_config = Path(__file__).parent.parent.parent / "config" / "remote_config.yaml.example"
        if src_config.exists():
            shutil.copy(src_config, config_dir / "remote_config.yaml.example")
            print("Config file copied successfully")
            return True
        else:
            print("Config file not found in source")
            return False
    except Exception as e:
        print(f"Failed to copy config files: {e}")
        return False


def copy_skill_documents():
    """
    复制Skill文档

    @return: 是否复制成功
    """
    try:
        user_dir = get_user_dir()
        skills_dir = user_dir / "skills"

        # 检查Skill文档是否已存在
        if list(skills_dir.glob("*.skill")):
            print("Skill documents already exist, skipping copy")
            return True

        # 复制Skill文档
        src_skills = Path(__file__).parent.parent.parent.parent.parent / "skills"
        if src_skills.exists():
            for skill_file in src_skills.glob("*.skill"):
                shutil.copy(skill_file, skills_dir / skill_file.name)
            print(f"Skill documents copied successfully: {len(list(skills_dir.glob('*.skill')))} files")
            return True
        else:
            print("Skill documents not found in source")
            return False
    except Exception as e:
        print(f"Failed to copy skill documents: {e}")
        return False


def initialize_database():
    """
    初始化数据库

    @return: 是否初始化成功
    """
    try:
        from mgc.core.mgc_service.database.database_handler import DatabaseHandler
        from mgc.config.enum_config import DatabaseType

        # 初始化数据库
        db_handler = DatabaseHandler()
        db_handler.connect()

        print("Database initialized successfully")
        return True
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        return False


def post_install():
    """
    执行安装后处理

    @return: 是否全部成功
    """
    print("MirginCipher Post-Installation Process")
    print("=" * 50)

    # 创建目录结构
    if not create_directory_structure():
        print("Failed to create directory structure")
        return False

    # 复制配置文件
    if not copy_config_files():
        print("Failed to copy config files")
        return False

    # 复制Skill文档
    if not copy_skill_documents():
        print("Failed to copy skill documents")
        return False

    # 初始化数据库
    if not initialize_database():
        print("Failed to initialize database")
        return False

    print("\n✓ Post-installation completed successfully")
    return True


if __name__ == "__main__":
    success = post_install()
    exit(0 if success else 1)
