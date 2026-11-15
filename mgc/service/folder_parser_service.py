"""Folder parser service.

按 [技能授权需求实施计划.md §四 4.1](../../document/1.5需求文档/1.5.0需求计划/技能授权需求实施计划.md)
扫描本机文件夹，按 save 记录字段映射生成 record 列表。

关键决策：
- B5：默认自动遍历子目录（os.walk 默认递归）
- B7：仅支持 regular file / directory / .mgc_file 三类，使用 lstat + S_ISREG 拒绝 symlink
- P0-1：diff_1 由调用方传入并原样保留，parser 不写为 rel_path
- P0-4：validate_relative_posix_path 拒绝绝对路径 / `..` / 空段 / NUL / 反斜杠 / Windows 驱动器
- R5：排除 .git / .DS_Store / __pycache__ / .vscode / node_modules
"""

from __future__ import annotations

import os
import stat
from typing import List


EXCLUDED_NAMES = {".git", ".DS_Store", "__pycache__", ".vscode", "node_modules"}

SCRIPT_SUFFIXES = {".py", ".js", ".sh", ".ps1", ".bat", ".cmd"}
TEXT_SUFFIXES = {".txt", ".md", ".json", ".yaml", ".yml", ".xml", ".csv", ".log", ".ini", ".conf", ".html", ".htm"}


def validate_relative_posix_path(rel_path: str) -> bool:
    """P0-4 评审：拒绝绝对路径 / `..` / 空段 / NUL / 反斜杠 / Windows 驱动器。

    用于 archive_path / diff_3 / 导出目标路径。
    """
    if not rel_path or "\x00" in rel_path or "\\" in rel_path:
        return False
    # 显式拒绝 Windows 盘符前缀（C:/ / D:\ 等）
    if len(rel_path) >= 2 and rel_path[1] == ":":
        return False
    # 显式拒绝绝对路径（首字符为 /）
    if rel_path.startswith("/"):
        return False
    # 按 / 拆段；纯字符串拆分才能识别 a//b 这类连续分隔产生的空段
    parts = rel_path.split("/")
    if not parts or any(seg in ("", ".", "..") for seg in parts):
        return False
    return True


def detect_info_type(full_path: str) -> str:
    """根据后缀判断 info_type。"""
    lower = full_path.lower()
    _, ext = os.path.splitext(lower)
    if ext in SCRIPT_SUFFIXES:
        return "script"
    if ext in TEXT_SUFFIXES:
        return "text"
    return "file"


def _read_text(full_path: str) -> str:
    """读取文件内容为 UTF-8 文本；读取失败返回空字符串。"""
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def parse_folder(folder_path: str, info_owner: str, diff_1: str = "") -> List[dict]:
    """扫描文件夹，生成 save record 字典列表。

    Args:
        folder_path: 本机文件夹绝对路径
        info_owner: 必传，归属标识
        diff_1: 可选，由调用方原样保留（不写为 rel_path，P0-1）

    Returns:
        record dict 列表，每个 record 含：
            info_owner, info_type, diff_1, diff_2, diff_3, content, ext07
        ext05/ext06 由调用方通过 enrich_script_fields 填充（仅 script）。
    """
    records: List[dict] = []
    if not folder_path or not os.path.isdir(folder_path):
        return records
    if not info_owner:
        return records

    folder_name = os.path.basename(os.path.normpath(folder_path)) or folder_path

    for root, dirs, files in os.walk(folder_path, followlinks=False):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_NAMES]
        for filename in files:
            if filename in EXCLUDED_NAMES:
                continue
            full_path = os.path.join(root, filename)
            try:
                st = os.lstat(full_path)
            except OSError:
                continue
            # B7：用 lstat + S_ISREG 拒绝 symlink / fifo / socket / block / character
            if not stat.S_ISREG(st.st_mode):
                continue
            rel_path = os.path.relpath(full_path, folder_path)
            posix_rel = rel_path.replace(os.sep, "/")
            # P0-4：路径安全校验
            if not validate_relative_posix_path(posix_rel):
                continue
            records.append({
                "info_owner": info_owner,
                "info_type": detect_info_type(full_path),
                "diff_1": diff_1,                              # P0-1：调用方原样传入
                "diff_2": folder_name,
                "diff_3": posix_rel,
                "content": _read_text(full_path),
                "ext07": "",                                   # D1：明文 source node pub，由 sealed_package_exporter 填
            })

    return records