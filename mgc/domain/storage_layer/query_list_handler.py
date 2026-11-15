"""
查询清单处理器

功能：
- 管理查询清单的增删改查
- 生成条目ID和条目标识
- 实现备份机制
- 校验Agent UUID权限

依赖：
- src/config/path_config.py（路径配置）
- src/config/enum_config.py（枚举配置）
- src/utils/path_utils.py（路径工具）
"""

import json
import os
import time
import shutil
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from mgc.utils.path_utils import (
    get_query_list_file,
    get_query_list_backup_dir,
    ensure_directories
)
from mgc.config.enum_config import OperationType, OperationResult


class QueryListHandler:
    """查询清单处理器"""

    def __init__(self):
        """初始化查询清单处理器"""
        self.query_list_file = get_query_list_file()
        self.backup_dir = get_query_list_backup_dir()
        self.bind_agent_uuid = None

    def initialize_query_list(self, agent_uuid: str) -> dict:
        """
        初始化查询清单

        入参：
            agent_uuid: Agent UUID

        出参：
            查询清单数据
        """
        ensure_directories()
        Path(self.backup_dir).mkdir(exist_ok=True, parents=True)

        query_list_data = {
            "meta": {
                "version": "1.0",
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bind_agent_uuid": agent_uuid
            },
            "items": []
        }

        self._write_file(self.query_list_file, json.dumps(query_list_data, indent=2, ensure_ascii=False))
        self.bind_agent_uuid = agent_uuid

        return query_list_data

    def load_query_list(self) -> dict:
        """
        加载查询清单

        出参：
            查询清单数据
        """
        if not os.path.exists(self.query_list_file):
            raise FileNotFoundError("查询清单文件不存在")

        with open(self.query_list_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            if "meta" not in data or "items" not in data:
                raise ValueError("查询清单格式错误：缺少meta或items字段")
            
            if data["meta"].get("version") != "1.0":
                raise ValueError("查询清单版本不兼容，仅支持v1.0")
            
            self.bind_agent_uuid = data["meta"].get("bind_agent_uuid")
            return data

    def save_query_list(self, query_list_data: dict) -> None:
        """
        保存查询清单

        入参：
            query_list_data: 查询清单数据
        """
        query_list_data["meta"]["last_update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._write_file(self.query_list_file, json.dumps(query_list_data, indent=2, ensure_ascii=False))

    def add_item(self, info_owner: str, info_type: str, agent_uuid: str) -> dict:
        """
        新增条目

        入参：
            info_owner: 信息归属
            info_type: 信息类型
            agent_uuid: Agent UUID

        出参：
            新增的条目
        """
        if not self.validate_agent_uuid(agent_uuid):
            raise PermissionError("Agent UUID与清单绑定UUID不一致，无操作权限")

        if not info_owner or not info_type:
            raise ValueError("信息归属和信息类型不可为空")

        if not self._validate_field_content(info_owner):
            raise ValueError("信息归属包含非法字符或长度超过限制")

        if not self._validate_field_content(info_type):
            raise ValueError("信息类型包含非法字符或长度超过限制")

        query_list_data = self.load_query_list()

        item_id = self.generate_item_id()
        entry_mark = self.generate_entry_mark(info_type)

        new_item = {
            "item_id": item_id,
            "info_owner": info_owner,
            "info_type": info_type,
            "submit_agent_uuid": agent_uuid,
            "entry_mark": entry_mark,
            "extend_fields": {}
        }

        query_list_data["items"].append(new_item)
        self.save_query_list(query_list_data)

        return new_item

    def modify_item(self, item_id: str, info_owner: str, info_type: str, agent_uuid: str) -> dict:
        """
        修改条目

        入参：
            item_id: 条目ID
            info_owner: 信息归属
            info_type: 信息类型
            agent_uuid: Agent UUID

        出参：
            修改后的条目
        """
        if not self.validate_agent_uuid(agent_uuid):
            raise PermissionError("Agent UUID与清单绑定UUID不一致，无操作权限")

        if info_owner and not self._validate_field_content(info_owner):
            raise ValueError("信息归属包含非法字符或长度超过限制")

        if info_type and not self._validate_field_content(info_type):
            raise ValueError("信息类型包含非法字符或长度超过限制")

        query_list_data = self.load_query_list()

        for item in query_list_data["items"]:
            if item["item_id"] == item_id:
                if info_owner:
                    item["info_owner"] = info_owner
                if info_type:
                    item["info_type"] = info_type
                    item["entry_mark"] = self.generate_entry_mark(info_type)
                self.save_query_list(query_list_data)
                return item

        raise ValueError(f"未找到条目ID: {item_id}")

    def delete_item(self, item_id: str, agent_uuid: str) -> None:
        """
        删除条目

        入参：
            item_id: 条目ID
            agent_uuid: Agent UUID
        """
        if not self.validate_agent_uuid(agent_uuid):
            raise PermissionError("Agent UUID与清单绑定UUID不一致，无操作权限")

        query_list_data = self.load_query_list()

        query_list_data["items"] = [item for item in query_list_data["items"] if item["item_id"] != item_id]
        self.save_query_list(query_list_data)

    def query_item(self, item_id: str, agent_uuid: str) -> dict:
        """
        查询条目

        入参：
            item_id: 条目ID
            agent_uuid: Agent UUID

        出参：
            条目数据
        """
        if not self.validate_agent_uuid(agent_uuid):
            raise PermissionError("Agent UUID与清单绑定UUID不一致，无操作权限")

        query_list_data = self.load_query_list()

        for item in query_list_data["items"]:
            if item["item_id"] == item_id:
                return item

        raise ValueError(f"未找到条目ID: {item_id}")

    def query_items(self, info_type: str = "", info_owner: str = "", agent_uuid: str = "") -> List[dict]:
        """
        查询多个条目

        入参：
            info_type: 信息类型（可选）
            info_owner: 信息归属（可选）
            agent_uuid: Agent UUID（可选，用于权限验证）

        出参：
            匹配的条目列表
        """
        if agent_uuid and not self.validate_agent_uuid(agent_uuid):
            raise PermissionError("Agent UUID与清单绑定UUID不一致，无操作权限")

        query_list_data = self.load_query_list()
        matching_items = []

        for item in query_list_data["items"]:
            match = True
            if info_type and item.get("info_type") != info_type:
                match = False
            if info_owner and item.get("info_owner") != info_owner:
                match = False
            
            if match:
                matching_items.append(item)

        return matching_items

    def match_item(self, info_owner: str, info_type: str, agent_uuid: str) -> Optional[str]:
        """
        匹配查询（仅返回item_id）

        入参：
            info_owner: 信息归属
            info_type: 信息类型
            agent_uuid: Agent UUID

        出参：
            匹配的item_id，未找到返回None
        """
        if not self.validate_agent_uuid(agent_uuid):
            raise PermissionError("Agent UUID与清单绑定UUID不一致，无操作权限")

        query_list_data = self.load_query_list()

        for item in query_list_data["items"]:
            if item["info_owner"] == info_owner and item["info_type"] == info_type:
                return item["item_id"]

        return None

    def generate_item_id(self) -> str:
        """
        生成条目ID

        出参：
            条目ID（格式：ql-YYYYMMDD-XXXX）
        """
        today = datetime.now().strftime("%Y%m%d")
        
        query_list_data = self.load_query_list()
        
        max_seq = 0
        for item in query_list_data["items"]:
            if item["item_id"].startswith(f"ql-{today}"):
                try:
                    seq = int(item["item_id"].split("-")[-1])
                    max_seq = max(max_seq, seq)
                except (ValueError, IndexError):
                    pass
        
        new_seq = max_seq + 1
        return f"ql-{today}-{new_seq:04d}"

    def generate_entry_mark(self, info_type: str) -> str:
        """
        生成条目标识

        入参：
            info_type: 信息类型

        出参：
            条目标识（格式：{info_type}-{sequence}）
        """
        query_list_data = self.load_query_list()

        sequence = 1
        for item in query_list_data["items"]:
            if item["info_type"] == info_type:
                sequence += 1

        return f"{info_type}-{sequence}"

    def validate_agent_uuid(self, agent_uuid: str) -> bool:
        """
        验证Agent UUID

        入参：
            agent_uuid: Agent UUID

        出参：
            是否验证通过
        """
        # 系统级agent_uuid（如定时任务）允许访问
        if agent_uuid.startswith("system-"):
            return True
        
        if not self.bind_agent_uuid:
            try:
                query_list_data = self.load_query_list()
                self.bind_agent_uuid = query_list_data["meta"]["bind_agent_uuid"]
            except (FileNotFoundError, ValueError):
                return False

        return agent_uuid == self.bind_agent_uuid

    def backup_query_list(self) -> str:
        """
        备份查询清单

        出参：
            备份文件路径
        """
        ensure_directories()
        Path(self.backup_dir).mkdir(exist_ok=True, parents=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.backup_dir, f"query_list_backup_{timestamp}.json")

        shutil.copy2(self.query_list_file, backup_file)

        self._cleanup_old_backups()

        return backup_file

    def _cleanup_old_backups(self) -> None:
        """清理超过7天的备份文件"""
        if not os.path.exists(self.backup_dir):
            return

        now = time.time()
        seven_days = 7 * 24 * 60 * 60

        for filename in os.listdir(self.backup_dir):
            file_path = os.path.join(self.backup_dir, filename)
            if os.path.isfile(file_path):
                if now - os.path.getmtime(file_path) > seven_days:
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

    def _validate_field_content(self, field_value: str) -> bool:
        """
        验证字段内容（禁止特殊字符，限制长度）

        入参：
            field_value: 字段值

        出参：
            是否合法
        """
        if not field_value:
            return False
        
        # 检查特殊字符
        special_chars = set('!@#$%^&*()+=[]{}|;:"<>?/')
        if any(char in special_chars for char in field_value):
            return False
        
        # 限制字段长度（最多50个字符）
        if len(field_value) > 50:
            return False
        
        return True

    def _write_file(self, file_path: str, content: str) -> None:
        """
        写入文件

        入参：
            file_path: 文件路径
            content: 文件内容
        """
        # newline="" 禁止 Windows 下自动转成 CRLF，保持内容与源一致
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)