"""Sealed package importer.

按 [技能授权需求实施计划.md §四 4.2](../../document/1.5需求文档/1.5.0需求计划/技能授权需求实施计划.md)
解压 .mgc_file，按 MGCFILE.json 字段映射生成 sealed record 列表。

关键决策：
- P0-2：完整还原 ext01-07，对密封脚本绝不重新解析（不走 enrich_script_fields）
- P0-4：archive_path 走 validate_relative_posix_path 拒绝 zip-slip 类攻击
- R8：MGCFILE.json 与 zip entries 一致性校验 + archive_path 唯一性
- B3：script content 保持密文字节（bytes），不还原为明文

依赖：
- mgc.utils.mgc_file_format：validate_mgcfile_json
- mgc.service.folder_parser_service：validate_relative_posix_path
"""

from __future__ import annotations

import json
import logging
import os
import zipfile
from typing import Any, Dict, List

from mgc.service.folder_parser_service import validate_relative_posix_path
from mgc.utils.mgc_file_format import validate_mgcfile_json

_logger = logging.getLogger(__name__)


# 错误码占位（与 PR-1/PR-2/PR-3 一致；正式错误码字典在 §八 统一落地）
ERROR_INVALID_MGC_FILE = "INVALID_MGC_FILE"


def _error(code: str, message: str, **extra: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {"error": code, "message": message}
    data.update(extra)
    return {"code": 400, "msg": code, "hint": message, "data": data}


def _success(records: List[dict]) -> Dict[str, Any]:
    return {
        "code": 200,
        "msg": "OPERATION_SUCCESSFUL",
        "hint": f"Sealed package parsed. {len(records)} record(s) extracted.",
        "data": {"records": records, "count": len(records)},
    }


def import_sealed_package(mgc_file_path: str) -> Dict[str, Any]:
    """解压 .mgc_file，按 MGCFILE.json 字段映射生成 sealed record 列表。

    Args:
        mgc_file_path: .mgc_file 本机路径

    Returns:
        标准 API 响应 dict，data.records 为 SealedRecord 字典列表：
            每条 record 含 info_owner / info_type / diff_1 / diff_2 / diff_3 /
            archive_path / content (bytes) / ext01-ext07
    """
    if not mgc_file_path:
        return _error(ERROR_INVALID_MGC_FILE, "mgc_file_path is required")
    if not os.path.isfile(mgc_file_path):
        return _error(ERROR_INVALID_MGC_FILE, f"file not found: {mgc_file_path}")

    try:
        with zipfile.ZipFile(mgc_file_path, "r") as zf:
            # 1. 校验 zip entries 与 MGCFILE.json 一致性（R8）
            entries = set(zf.namelist())
            if "MGCFILE.json" not in entries:
                return _error(ERROR_INVALID_MGC_FILE, "missing MGCFILE.json in zip")

            # 2. 读 MGCFILE.json
            try:
                mgcfile_json = json.loads(zf.read("MGCFILE.json"))
            except json.JSONDecodeError as e:
                return _error(ERROR_INVALID_MGC_FILE, f"invalid MGCFILE.json: {e}")

            # 3. schema 校验（含 archive_path 唯一性 + 必填字段）
            if not validate_mgcfile_json(mgcfile_json):
                return _error(ERROR_INVALID_MGC_FILE, "MGCFILE.json schema validation failed")

            records_meta = mgcfile_json["records"]

            # 4. 逐条：路径安全校验 + 读 archive_path 内容
            sealed_records: List[dict] = []
            for meta in records_meta:
                archive_path = meta.get("archive_path", "")
                # P0-4：复用 validate_relative_posix_path 防 zip-slip
                if not validate_relative_posix_path(archive_path):
                    return _error(
                        ERROR_INVALID_MGC_FILE,
                        f"unsafe archive_path: {archive_path!r}",
                    )
                if archive_path not in entries:
                    return _error(
                        ERROR_INVALID_MGC_FILE,
                        f"missing entry in zip: {archive_path}",
                    )

                # B3：content 保持原始字节（密文/明文均不重新解析）
                content_bytes = zf.read(archive_path)
                sealed_records.append({
                    "info_owner": meta.get("info_owner", ""),
                    "info_type": meta.get("info_type", ""),
                    "diff_1": meta.get("diff_1", ""),
                    "diff_2": meta.get("diff_2", ""),
                    "diff_3": meta.get("diff_3", ""),
                    "archive_path": archive_path,
                    "content": content_bytes,
                    # P0-2：完整还原 ext01-07，绝不重新解析
                    # 1.5.1 Sprint 1：同步还原 ext08（callgraph JSON）
                    # 1.5.4：同步还原 ext09（seal policy：p2p/free/chain mode）
                    "ext01": meta.get("ext01", ""),
                    "ext02": meta.get("ext02", ""),
                    "ext03": meta.get("ext03", ""),
                    "ext05": meta.get("ext05", ""),
                    "ext06": meta.get("ext06", ""),
                    "ext07": meta.get("ext07", ""),
                    "ext08": meta.get("ext08", ""),
                    "ext09": meta.get("ext09", ""),
                })
    except zipfile.BadZipFile as e:
        return _error(ERROR_INVALID_MGC_FILE, f"bad zip file: {e}")
    except OSError as e:
        return _error(ERROR_INVALID_MGC_FILE, f"read failed: {e}")

    return _success(sealed_records)