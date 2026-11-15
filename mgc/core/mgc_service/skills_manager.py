"""
Skills插件化部署模块

功能：
- 提供Skills插件化部署功能
- 包括Skills文件加载、版本管理、更新与升级等
- 所有Skills以纯文本文件存储，由AI阅读理解并执行

依赖：
- src/config/path_config.py（路径配置）
"""

import os
import json
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import sys

from mgc.config.i18n_config import get_exception_message, Messages
from mgc.config.path_config import HEARTBEAT_STATS_FILE, VERSION_CACHE_FILE, SKILLS_DIR

if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl


class SkillsManagerError(Exception):
    """Skills管理异常"""
    pass


class SkillsManager:
    """Skills管理器"""

    def __init__(self, skills_dir: str = None):
        """
        初始化Skills管理器

        入参：
            skills_dir: Skills文件目录（可选，默认从配置读取）
        """
        if skills_dir is None:
            skills_dir = str(SKILLS_DIR)
        self.skills_dir = skills_dir
        self._ensure_skills_dir()

    def _ensure_skills_dir(self):
        """确保Skills目录存在"""
        Path(self.skills_dir).mkdir(exist_ok=True, parents=True)

    def load_skills(self) -> Dict[str, Dict[str, any]]:
        """
        加载所有Skills

        功能：
        - 扫描Skills目录
        - 读取所有Skills文件
        - 解析文件内容
        - 返回Skills字典

        出参：
            dict: Skills字典
            {
                "skill_name": {
                    "prompt": "xxx",
                    "format": "xxx",
                    "examples": []
                }
            }

        异常：
            SkillsManagerError: 加载失败时抛出
        """
        try:
            skills = {}

            if not os.path.exists(self.skills_dir):
                return skills

            for filename in os.listdir(self.skills_dir):
                filepath = os.path.join(self.skills_dir, filename)

                if not os.path.isfile(filepath):
                    continue

                try:
                    skill_name = os.path.splitext(filename)[0]
                    skill_content = self._load_skill_file(filepath)

                    if skill_content:
                        skills[skill_name] = skill_content

                except Exception as e:
                    print(f"加载Skill文件'{filename}'失败: {str(e)}")
                    continue

            return skills

        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "LOAD_SKILLS_FAILED"))

    def get_skill(self, skill_name: str) -> Optional[Dict[str, any]]:
        """
        获取指定Skill

        功能：
        - 根据Skill名称查找文件
        - 读取文件内容
        - 解析并返回

        入参：
            skill_name: Skill名称

        出参：
            dict: Skill内容
            {
                "prompt": "xxx",
                "format": "xxx",
                "examples": []
            }

        异常：
            SkillsManagerError: 获取失败时抛出
        """
        try:
            if not skill_name:
                raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "SKILL_NAME_CANNOT_BE_EMPTY"))

            possible_files = [
                f"{skill_name}.json",
                f"{skill_name}.md",
                f"{skill_name}.txt"
            ]

            for filename in possible_files:
                filepath = os.path.join(self.skills_dir, filename)

                if os.path.exists(filepath):
                    return self._load_skill_file(filepath)

            return None

        except SkillsManagerError:
            raise
        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "GET_SKILL_FAILED"))

    def add_skill(self, skill_name: str, skill_content: Dict[str, any]) -> bool:
        """
        添加Skill

        功能：
        - 创建新文件
        - 写入Skill内容
        - 返回成功/失败

        入参：
            skill_name: Skill名称
            skill_content: Skill内容

        出参：
            bool: True表示添加成功，False表示添加失败

        异常：
            SkillsManagerError: 添加失败时抛出
        """
        try:
            if not skill_name or not skill_content:
                raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "SKILL_NAME_AND_CONTENT_CANNOT_BE_EMPTY"))

            filepath = os.path.join(self.skills_dir, f"{skill_name}.json")

            if os.path.exists(filepath):
                raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "SKILL_ALREADY_EXISTS", skill_name=skill_name))

            self._save_skill_file(filepath, skill_content)

            return True

        except SkillsManagerError:
            raise
        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "ADD_SKILL_FAILED"))

    def update_skill(self, skill_name: str, skill_content: Dict[str, any]) -> bool:
        """
        更新Skill

        功能：
        - 覆盖现有文件
        - 写入新内容
        - 返回成功/失败

        入参：
            skill_name: Skill名称
            skill_content: 新的Skill内容

        出参：
            bool: True表示更新成功，False表示更新失败

        异常：
            SkillsManagerError: 更新失败时抛出
        """
        try:
            if not skill_name or not skill_content:
                raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "SKILL_NAME_AND_CONTENT_CANNOT_BE_EMPTY"))

            filepath = os.path.join(self.skills_dir, f"{skill_name}.json")

            if not os.path.exists(filepath):
                raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "SKILL_DOES_NOT_EXIST", skill_name=skill_name))

            self._save_skill_file(filepath, skill_content)

            return True

        except SkillsManagerError:
            raise
        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "UPDATE_SKILL_FAILED"))

    def delete_skill(self, skill_name: str) -> bool:
        """
        删除Skill

        功能：
        - 删除文件
        - 返回成功/失败

        入参：
            skill_name: Skill名称

        出参：
            bool: True表示删除成功，False表示删除失败

        异常：
            SkillsManagerError: 删除失败时抛出
        """
        try:
            if not skill_name:
                raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "SKILL_NAME_CANNOT_BE_EMPTY"))

            filepath = os.path.join(self.skills_dir, f"{skill_name}.json")

            if not os.path.exists(filepath):
                raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "SKILL_DOES_NOT_EXIST", skill_name=skill_name))

            os.remove(filepath)

            return True

        except SkillsManagerError:
            raise
        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "DELETE_SKILL_FAILED"))

    def list_skills(self) -> List[Dict[str, any]]:
        """
        列出所有Skills

        功能：
        - 扫描目录
        - 返回Skills列表

        出参：
            list: Skills列表
            [
                {
                    "skill_name": "xxx",
                    "version": "xxx",
                    "created_at": "xxx"
                }
            ]

        异常：
            SkillsManagerError: 列出失败时抛出
        """
        try:
            skills_list = []

            if not os.path.exists(self.skills_dir):
                return skills_list

            for filename in os.listdir(self.skills_dir):
                filepath = os.path.join(self.skills_dir, filename)

                if not os.path.isfile(filepath):
                    continue

                if not (filepath.endswith('.json') or filepath.endswith('.md')):
                    continue

                if filename in ['heartbeat_stats.json', 'version_cache.json']:
                    continue

                try:
                    skill_name = os.path.splitext(filename)[0]
                    version = self._extract_version(skill_name)
                    created_at = self._get_file_created_time(filepath)

                    skills_list.append({
                        "skill_name": skill_name,
                        "version": version,
                        "created_at": created_at
                    })

                except Exception as e:
                    print(f"处理Skill文件'{filename}'失败: {str(e)}")
                    continue

            return skills_list

        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "LIST_SKILLS_FAILED"))

    def get_version_info(self) -> Dict[str, any]:
        """
        获取Skills版本信息

        功能：
        - 读取Skills目录中的版本信息
        - 返回版本号、更新时间、Skills数量等

        出参：
            dict: 版本信息
            {
                "version": "1.0",
                "last_updated": "2026-03-29",
                "skills_count": 10,
                "latest_check_time": "2026-03-29 10:30:00"
            }

        异常：
            SkillsManagerError: 获取失败时抛出
        """
        try:
            skills_list = self.list_skills()
            skills_count = len(skills_list)

            version_info = {
                "version": "1.0",
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "skills_count": skills_count,
                "latest_check_time": ""
            }

            try:
                version_cache_path = os.path.join(self.skills_dir, "version_cache.json")
                if os.path.exists(version_cache_path):
                    with open(version_cache_path, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        version_info["latest_check_time"] = cache_data.get("check_time", "")
            except Exception:
                pass

            return version_info

        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "GET_VERSION_INFO_FAILED"))

    def check_updates(self, offline_mode: bool = False) -> Dict[str, any]:
        """
        检查Skills版本更新

        功能：
        - 比对本地版本和远程版本
        - 返回更新信息
        - 支持offline模式，网络不可用时不阻塞

        入参：
            offline_mode: 是否使用离线模式（默认False）

        出参：
            dict: 更新信息
            {
                "has_update": true,
                "current_version": "1.0",
                "latest_version": "1.1",
                "update_url": "https://github.com/xxx/releases/v1.1",
                "changelog": "修复了xxx问题，新增了xxx功能",
                "is_critical": false,
                "check_time": "2026-03-29 10:30:00",
                "offline_mode": false
            }

        异常：
            SkillsManagerError: 检查失败时抛出
        """
        try:
            current_version = "1.0"
            check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if offline_mode:
                return {
                    "has_update": False,
                    "current_version": current_version,
                    "latest_version": current_version,
                    "update_url": "",
                    "changelog": "",
                    "is_critical": False,
                    "check_time": check_time,
                    "offline_mode": True
                }

            try:
                request = Request(
                    "https://api.github.com/repos/zkeviny/MGC-Blackbox/releases/latest",
                    headers={'User-Agent': 'MirginCipher/1.0'}
                )
                
                with urlopen(request, timeout=5) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    latest_version = data.get("tag_name", "").lstrip('v')
                    changelog = data.get("body", "")
                    html_url = data.get("html_url", "")
                    is_critical = False

                    has_update = self._compare_versions(current_version, latest_version) < 0

                    result = {
                        "has_update": has_update,
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "update_url": html_url,
                        "changelog": changelog,
                        "is_critical": is_critical,
                        "check_time": check_time,
                        "offline_mode": False
                    }

                    try:
                        with open(VERSION_CACHE_FILE, 'w', encoding='utf-8') as f:
                            json.dump({
                                "check_time": check_time,
                                "latest_version": latest_version,
                                "has_update": has_update
                            }, f, indent=2)
                    except Exception:
                        pass

                    return result

            except (URLError, HTTPError, json.JSONDecodeError, Exception) as e:
                return {
                    "has_update": False,
                    "current_version": current_version,
                    "latest_version": current_version,
                    "update_url": "",
                    "changelog": "",
                    "is_critical": False,
                    "check_time": check_time,
                    "offline_mode": True
                }

        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "CHECK_UPDATES_FAILED"))

    def record_heartbeat(self, skill_name: str) -> Dict[str, any]:
        """
        记录Skill心跳

        功能：
        - 记录Skill使用统计
        - 更新最后使用时间
        - 增加使用计数

        入参：
            skill_name: Skill名称

        出参：
            dict: 心跳记录结果
            {
                "success": true,
                "skill_name": "mgc_encrypt",
                "last_used": "2026-03-29 10:30:00",
                "usage_count": 101
            }

        异常：
            SkillsManagerError: 记录失败时抛出
        """
        try:
            if not skill_name:
                raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "SKILL_NAME_CANNOT_BE_EMPTY"))

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            stats = {}
            try:
                heartbeat_stats_path = os.path.join(self.skills_dir, "heartbeat_stats.json")
                if os.path.exists(heartbeat_stats_path):
                    with open(heartbeat_stats_path, 'r', encoding='utf-8') as f:
                        stats = json.load(f)
            except Exception:
                pass

            if skill_name not in stats:
                stats[skill_name] = {
                    "count": 0,
                    "last_used": "",
                    "actions": {}
                }

            stats[skill_name]["count"] += 1
            stats[skill_name]["last_used"] = current_time

            self._cleanup_old_stats(stats)

            try:
                heartbeat_stats_path = os.path.join(self.skills_dir, "heartbeat_stats.json")
                self._write_with_lock(heartbeat_stats_path, stats)
            except Exception as e:
                print(f"Failed to write heartbeat stats: {str(e)}")

            return {
                "success": True,
                "skill_name": skill_name,
                "last_used": current_time,
                "usage_count": stats[skill_name]["count"]
            }

        except SkillsManagerError:
            raise
        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "RECORD_HEARTBEAT_FAILED"))

    def get_heartbeat_stats(self) -> Dict[str, any]:
        """
        获取心跳统计

        功能：
        - 返回Skills使用统计
        - 返回活跃度信息

        出参：
            dict: 统计信息
            {
                "total_skills": 10,
                "active_skills": 5,
                "most_used_skill": "mgc_encrypt",
                "total_usage_count": 1000,
                "skills_usage": [
                    {
                        "skill_name": "mgc_encrypt",
                        "count": 500,
                        "last_used": "2026-03-29 10:30:00"
                    }
                ]
            }

        异常：
            SkillsManagerError: 获取失败时抛出
        """
        try:
            stats = {}
            try:
                heartbeat_stats_path = os.path.join(self.skills_dir, "heartbeat_stats.json")
                if os.path.exists(heartbeat_stats_path):
                    with open(heartbeat_stats_path, 'r', encoding='utf-8') as f:
                        stats = json.load(f)
            except Exception:
                pass

            total_skills = len(stats)
            total_usage_count = sum(skill["count"] for skill in stats.values())

            seven_days_ago = datetime.now() - timedelta(days=7)
            active_skills = sum(
                1 for skill in stats.values()
                if skill.get("last_used") and datetime.strptime(skill["last_used"], "%Y-%m-%d %H:%M:%S") > seven_days_ago
            )

            most_used_skill = ""
            max_count = 0
            for skill_name, skill_data in stats.items():
                if skill_data["count"] > max_count:
                    max_count = skill_data["count"]
                    most_used_skill = skill_name

            skills_usage = [
                {
                    "skill_name": skill_name,
                    "count": skill_data["count"],
                    "last_used": skill_data.get("last_used", "")
                }
                for skill_name, skill_data in stats.items()
            ]

            skills_usage.sort(key=lambda x: x["count"], reverse=True)

            return {
                "total_skills": total_skills,
                "active_skills": active_skills,
                "most_used_skill": most_used_skill,
                "total_usage_count": total_usage_count,
                "skills_usage": skills_usage
            }

        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "GET_HEARTBEAT_STATS_FAILED"))

    def prepare_uninstall(self) -> Dict[str, any]:
        """
        准备卸载

        功能：
        - 备份Skills数据
        - 清理临时文件
        - 准备卸载清单
        - 注意：此功能仅作为数据管理，实际卸载由系统级卸载工具处理

        出参：
            dict: 卸载准备信息
            {
                "backup_path": "/path/to/backup",
                "backup_time": "2026-03-29 10:30:00",
                "skills_to_remove": ["skill1", "skill2", "skill3"],
                "cleanup_files": ["temp1", "temp2"],
                "estimated_time": "2 seconds",
                "data_size": "1.5 MB",
                "note": "此功能仅备份数据，实际卸载请使用pip uninstall mirgincipher"
            }

        异常：
            SkillsManagerError: 准备失败时抛出
        """
        try:
            from mgc.config.path_config import TEMP_DIR
            import shutil

            backup_dir = TEMP_DIR / "skills_backup"
            backup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            backup_path = backup_dir / f"backup_{backup_time.replace(':', '-').replace(' ', '_')}"

            backup_path.mkdir(parents=True, exist_ok=True)

            skills_to_remove = []
            data_size = 0

            for filename in os.listdir(self.skills_dir):
                filepath = os.path.join(self.skills_dir, filename)
                if os.path.isfile(filepath):
                    try:
                        shutil.copy2(filepath, backup_path / filename)
                        data_size += os.path.getsize(filepath)
                        if filename.endswith('.json') or filename.endswith('.md'):
                            skills_to_remove.append(os.path.splitext(filename)[0])
                    except Exception as e:
                        print(f"Failed to backup file '{filename}': {str(e)}")

            cleanup_files = []
            if os.path.exists(HEARTBEAT_STATS_FILE):
                cleanup_files.append("heartbeat_stats.json")
            if os.path.exists(VERSION_CACHE_FILE):
                cleanup_files.append("version_cache.json")

            data_size_mb = round(data_size / (1024 * 1024), 2)

            return {
                "backup_path": str(backup_path),
                "backup_time": backup_time,
                "skills_to_remove": skills_to_remove,
                "cleanup_files": cleanup_files,
                "estimated_time": "2 seconds",
                "data_size": f"{data_size_mb} MB",
                "note": "This function only backs up data, actual uninstallation please use: pip uninstall mirgincipher"
            }

        except Exception as e:
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "PREPARE_UNINSTALL_FAILED"))

    def _write_with_lock(self, filepath: str, data: dict):
        """
        使用文件锁写入数据

        入参：
            filepath: 文件路径
            data: 要写入的数据
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                if sys.platform == 'win32':
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                finally:
                    if sys.platform == 'win32':
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (IOError, BlockingIOError, OSError):
            raise SkillsManagerError(get_exception_message(Messages.SkillsManager, "FILE_LOCK_TIMEOUT"))

    def _cleanup_old_stats(self, stats: dict):
        """
        清理过期的统计数据

        入参：
            stats: 统计数据字典
        """
        thirty_days_ago = datetime.now() - timedelta(days=30)
        skills_to_remove = []

        for skill_name, skill_data in stats.items():
            if skill_data.get("last_used"):
                try:
                    last_used = datetime.strptime(skill_data["last_used"], "%Y-%m-%d %H:%M:%S")
                    if last_used < thirty_days_ago:
                        skills_to_remove.append(skill_name)
                except Exception:
                    pass

        for skill_name in skills_to_remove:
            del stats[skill_name]

    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        比较版本号

        入参：
            version1: 版本号1
            version2: 版本号2

        出参：
            int: -1表示version1 < version2，0表示相等，1表示version1 > version2
        """
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]

        for v1, v2 in zip(v1_parts, v2_parts):
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1

        if len(v1_parts) < len(v2_parts):
            return -1
        elif len(v1_parts) > len(v2_parts):
            return 1

        return 0

    def _load_skill_file(self, filepath: str) -> Optional[Dict[str, any]]:
        """
        加载Skill文件

        入参：
            filepath: 文件路径

        出参：
            dict: Skill内容
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            if filepath.endswith('.json'):
                return json.loads(content)
            elif filepath.endswith('.md'):
                return {
                    "prompt": content,
                    "format": "markdown",
                    "examples": []
                }
            else:
                return None

        except json.JSONDecodeError:
            return None
        except Exception:
            return None

    def _save_skill_file(self, filepath: str, skill_content: Dict[str, any]):
        """
        保存Skill文件

        入参：
            filepath: 文件路径
            skill_content: Skill内容
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(skill_content, f, indent=2, ensure_ascii=False)

    def _extract_version(self, skill_name: str) -> str:
        """
        提取Skill版本

        入参：
            skill_name: Skill名称

        出参：
            str: 版本号
        """
        if '_v' in skill_name:
            parts = skill_name.split('_v')
            if len(parts) > 1:
                return parts[-1]

        return "1.0"

    def _get_file_created_time(self, filepath: str) -> str:
        """
        获取文件创建时间

        入参：
            filepath: 文件路径

        出参：
            str: 创建时间字符串
        """
        try:
            timestamp = os.path.getctime(filepath)
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ""
