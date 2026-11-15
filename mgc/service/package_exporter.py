"""Package exporter service (plain folder export).

按 [技能授权需求实施计划.md §四 4.4](../../document/1.5需求文档/1.5.0需求计划/技能授权需求实施计划.md)
从 mgc 导出关联文件夹到本地路径。

关键决策：
- P0-1：函数参数加 diff_1；无 diff_1 时若多集合命中返回 AMBIGUOUS_FOLDER
- P0-4：复用 validate_relative_posix_path；导出目标必须在 folder_path 内（防 zip-slip 类攻击）
- 不修改 mgc 内部数据，只读 + 写本地
- diff_3 是相对 posix 路径，转回本机分隔符
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from mgc.service.folder_parser_service import validate_relative_posix_path

_logger = logging.getLogger(__name__)


# 错误码占位（与 PR-1 一致；正式错误码字典与 PR-2 一起在 §八 落地）
ERROR_MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"
ERROR_PATH_NOT_LOCAL = "PATH_NOT_LOCAL"
ERROR_INVALID_DIFF3 = "INVALID_MGC_FILE"
ERROR_AMBIGUOUS_FOLDER = "AMBIGUOUS_FOLDER"


def _error(code: str, message: str, **extra: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {"error": code, "message": message}
    data.update(extra)
    return {"code": 400, "msg": code, "hint": message, "data": data}


def _success(folder_path: str, written: List[str]) -> Dict[str, Any]:
    return {
        "code": 200,
        "msg": "OPERATION_SUCCESSFUL",
        "hint": f"Folder exported to {folder_path}. {len(written)} file(s) written.",
        "data": {"folder_path": folder_path, "written": written, "count": len(written)},
    }


def _write_file(target: str, content: str) -> None:
    """写文件；父目录自动创建。

    newline="" 禁止平台换行符转换：Windows 下Python 会把 "\\n"
    自动写成 "\\r\\n"，导致导出内容与源文件不再逐字节一致。
    """
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def export_folder(
    info_owner: str,
    diff_2: str,
    output_dir: str,
    diff_1: str = "",
    query_callback: Optional[Callable[[str, str, str], List[dict]]] = None,
) -> Dict[str, Any]:
    """从 mgc 导出关联文件夹到本地路径。

    Args:
        info_owner: 必传
        diff_2: 必传，文件夹名
        output_dir: 本机输出根目录
        diff_1: 可选；空表示跨 diff_1 集合匹配（此时若多命中则报错）
        query_callback: 查询回调，签名 (info_owner, diff_2, diff_1) -> list[dict]
            每个 dict 至少含 info_type / info_owner / diff_1 / diff_2 / diff_3 / content 字段。
            PR-2 测试用 mock；PR-5 接入时由 api_router 注入具体 SQL 查询实现。

    Returns:
        标准 API 响应 dict
    """
    if not info_owner:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "info_owner required")
    if not diff_2:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "diff_2 required")
    if not output_dir:
        return _error(ERROR_PATH_NOT_LOCAL, "output_dir required")
    if query_callback is None:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "query_callback not injected")

    # P0-4：output_dir 必须在本机，且 folder_path 必须落在 output_dir 下
    output_root = os.path.realpath(output_dir)
    folder_path = os.path.realpath(os.path.join(output_root, diff_2))
    if folder_path != output_root and not folder_path.startswith(output_root + os.sep):
        return _error(ERROR_PATH_NOT_LOCAL, "output_dir must be a local safe root")

    # P0-1：查询（diff_1 可为空 → 跨集合匹配）
    try:
        records = query_callback(info_owner, diff_2, diff_1)
    except Exception as e:
        _logger.warning("export_folder query failed: %s", e)
        return _error(ERROR_MISSING_REQUIRED_FIELDS, f"query failed: {e}")

    if not records:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "no records found")

    # P0-1：无 diff_1 时校验唯一 (info_owner, diff_1, diff_2) 集合
    if not diff_1:
        seen_sets = {(r.get("info_owner", ""), r.get("diff_1", ""), r.get("diff_2", "")) for r in records}
        if len(seen_sets) > 1:
            return _error(
                ERROR_AMBIGUOUS_FOLDER,
                f"Multiple folders match owner={info_owner} diff_2={diff_2}. "
                f"Please provide diff_1 to disambiguate.",
                **{"candidates": sorted(s[2] + "/" + s[1] for s in seen_sets)},
            )

    written: List[str] = []
    for rec in records:
        diff_3 = rec.get("diff_3", "")
        # P0-4：每条记录的 diff_3 必须仍是相对 posix 路径
        if not validate_relative_posix_path(diff_3):
            return _error(ERROR_INVALID_DIFF3, f"unsafe diff_3: {diff_3!r}")

        rel_path = diff_3
        target = os.path.realpath(os.path.join(folder_path, rel_path.replace("/", os.sep)))
        # P0-4：导出目标必须在 folder_path 内（防 zip-slip 类攻击）
        if target != folder_path and not target.startswith(folder_path + os.sep):
            return _error(ERROR_INVALID_DIFF3, f"unsafe export target: {target}")

        try:
            _write_file(target, rec.get("content", "") or "")
            written.append(diff_3)
        except OSError as e:
            _logger.warning("export_folder write %s failed: %s", target, e)
            return _error(ERROR_PATH_NOT_LOCAL, f"write failed: {e}")

    return _success(folder_path, written)