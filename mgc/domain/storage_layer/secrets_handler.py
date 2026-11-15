"""
密钥模板处理器

功能：
- 读取密钥模板文件（customer_secrets.md）
- 解析动态盐
- 提供动态盐查询接口

依赖：
- src/config/path_config.py（路径配置）
- src/utils/path_utils.py（路径工具）
"""

import os
import re
from typing import Dict, Optional

from mgc.utils.path_utils import get_customer_secrets_file


class SecretsHandler:
    """密钥模板处理器"""

    def __init__(self):
        """初始化密钥模板处理器"""
        self.secrets_file = get_customer_secrets_file()
        self.secrets_data = {}

    def load_secrets(self) -> dict:
        """
        加载密钥模板

        出参：
            密钥模板数据
        """
        if not os.path.exists(self.secrets_file):
            raise FileNotFoundError("密钥模板文件不存在")

        with open(self.secrets_file, 'r', encoding='utf-8') as f:
            content = f.read()

        self.secrets_data = self._parse_secrets(content)
        return self.secrets_data

    def get_dynamic_salt(self, salt_index: int) -> str:
        """
        获取动态盐

        入参：
            salt_index: 动态盐索引（1-10）

        出参：
            动态盐值
        """
        if not self.secrets_data:
            self.load_secrets()

        salt_key = f"salt{salt_index}"
        if salt_key not in self.secrets_data:
            raise ValueError(f"动态盐{salt_index}不存在")

        return self.secrets_data[salt_key]

    def get_all_salts(self) -> Dict[str, str]:
        """
        获取所有动态盐

        出参：
            包含所有动态盐的字典
        """
        if not self.secrets_data:
            self.load_secrets()

        return self.secrets_data

    def _parse_secrets(self, content: str) -> dict:
        """
        解析密钥模板内容

        入参：
            content: 密钥模板内容

        出参：
            解析后的密钥数据
        """
        secrets = {}

        for i in range(1, 11):
            pattern = rf"动态盐{i}[:：]\s*(\d+)"
            match = re.search(pattern, content)
            if match:
                secrets[f"salt{i}"] = int(match.group(1))

        if not secrets:
            raise ValueError("密钥模板中未找到动态盐数据")

        return secrets
