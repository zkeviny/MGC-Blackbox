"""包配置管理

功能：
- 从配置文件读取包配置
- 支持环境变量替换
- 避免硬编码

依赖：
- yaml（PyYAML）
- os（环境变量）
"""

import os
import yaml
from pathlib import Path
from mgc.config.i18n_config import Messages


class PackageConfig:
    """包配置类"""

    def __init__(self):
        """初始化包配置"""
        config_file = Path(__file__).parent / "package_config.yaml"

        if not config_file.exists():
            raise FileNotFoundError(Messages.Package.PACKAGE_CONFIG_FILE_NOT_FOUND.format(file_path=config_file))

        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self._replace_env_vars()

    def _replace_env_vars(self):
        """替换环境变量"""
        def replace_value(value):
            if isinstance(value, str):
                if value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    
                    # 支持 ${VAR_NAME:default_value} 语法
                    if ":" in env_var:
                        var_name, default_val = env_var.split(":", 1)
                        return os.getenv(var_name, default_val)
                    else:
                        # 支持 ${VAR_NAME} 语法，环境变量不存在时保留原值
                        return os.getenv(env_var, value)
                return value
            elif isinstance(value, dict):
                return {k: replace_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_value(item) for item in value]
            return value

        self.config = replace_value(self.config)

    def get(self, key_path, default=None):
        """
        获取配置值

        @param key_path: 配置键路径（如 "package.name"）
        @param default: 默认值
        @return: 配置值
        """
        keys = key_path.split(".")
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    @property
    def package_name(self):
        """包名"""
        return self.get("package.name")

    @property
    def package_version(self):
        """包版本"""
        return self.get("package.version")

    @property
    def package_description(self):
        """包描述"""
        return self.get("package.description")

    @property
    def author_name(self):
        """作者名称"""
        return self.get("author.name")

    @property
    def author_email(self):
        """作者邮箱"""
        return self.get("author.email")

    @property
    def homepage_url(self):
        """主页URL"""
        return self.get("repository.homepage")

    @property
    def docs_url(self):
        """文档URL"""
        return self.get("repository.documentation")

    @property
    def repo_url(self):
        """仓库URL"""
        return self.get("repository.repository")


# 全局配置实例
_package_config = None


def get_package_config():
    """
    获取包配置实例

    @return: PackageConfig实例
    """
    global _package_config
    if _package_config is None:
        _package_config = PackageConfig()
    return _package_config
