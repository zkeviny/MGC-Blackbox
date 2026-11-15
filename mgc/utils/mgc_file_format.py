"""MGCFILE.json / .mgc_file schema and validation.

按 [技能授权需求实施计划.md §四 4.6](../../document/1.5需求文档/1.5.0需求计划/技能授权需求实施计划.md)
定义 .mgc_file 密封包的 manifest schema 与校验函数。

关键决策：
- P0-2：MGCFILE.json 顶层字段固定包含 version / source_node_pub / records
- P0-2：每条 record 固定包含 archive_path + ext01-07 全集
- P0-2：archive_path 唯一性校验（防 records 内重复）
- P0-2：validate_mgcfile_zip_consistency 统一用 archive_path 反查 zip entries
- D1：顶层 source_node_pub 明文（来源标识，未做签名验证）
- B3：只加密 script 内容，README.md / MGCFILE.json / file 类内容均明文
- B2：MGC_FILE_MAX_RECORDS = 100 / MGC_FILE_MAX_TOTAL_BYTES = 50 * 1024 * 1024
"""

from __future__ import annotations

import json
import zipfile
from typing import Any, Dict, Iterable, List, Optional


# 顶层字段（P0-2）
MGCFILE_TOP_FIELDS = ["version", "source_node_pub", "records"]

# 每条 record 字段（P0-2：B6 含 ext07；1.5.1 Sprint 1 加 ext08）
MGCFILE_RECORD_FIELDS = [
    "info_owner",
    "info_type",
    "diff_1",
    "diff_2",
    "diff_3",
    "archive_path",      # P0-2：zip 内条目路径
    "ext01",
    "ext02",
    "ext03",
    "ext05",
    "ext06",
    "ext07",             # D1：source node pub
    "ext08",             # 1.5.1 Sprint 1：callgraph JSON（受管脚本依赖图）
]

# ext 默认值集合
# 1.5.4：新增 ext09（seal policy："" / "p2p mode" / "free mode" / "chain mode"）
EXT_KEYS_WITH_DEFAULT = ["ext01", "ext02", "ext03", "ext05", "ext06", "ext07", "ext08", "ext09"]

# 必填 record 字段（不含 archive_path，由 build 阶段统一填）
REQUIRED_RECORD_FIELDS = ["info_owner", "info_type", "diff_2", "diff_3", "archive_path"]

# 容量上限（B2 决策）
MGC_FILE_MAX_RECORDS = 100
MGC_FILE_MAX_TOTAL_BYTES = 50 * 1024 * 1024


def _default_record() -> Dict[str, str]:
    return {k: "" for k in MGCFILE_RECORD_FIELDS}


def validate_mgcfile_json(data: Any) -> bool:
    """校验 MGCFILE.json 字段完整性（P0-2）。

    校验项：
    1. 顶层必须含 version / records（source_node_pub 可选，缺省视为空）
    2. 每条 record 必须含 REQUIRED_RECORD_FIELDS（info_owner / info_type / diff_2 / diff_3 / archive_path）
    3. archive_path 必须在 records 内唯一
    4. ext01-03/05-07 缺省补空字符串（允许外部传入 records 时省略这些字段）

    Args:
        data: 已反序列化的 dict（顶层结构）

    Returns:
        True 表示合法；False 表示任意一项校验失败
    """
    if not isinstance(data, dict):
        return False
    if "version" not in data or "records" not in data:
        return False
    if not isinstance(data["records"], list):
        return False

    # 顶层 source_node_pub 缺省视为 ""
    data.setdefault("source_node_pub", "")

    # archive_path 唯一性 + 必填字段校验
    seen_archive_paths = set()
    for r in data["records"]:
        if not isinstance(r, dict):
            return False
        for k in REQUIRED_RECORD_FIELDS:
            if k not in r:
                return False
        ap = r.get("archive_path", "")
        if ap in seen_archive_paths:
            return False
        seen_archive_paths.add(ap)

    # ext 默认值补全
    for r in data["records"]:
        for k in EXT_KEYS_WITH_DEFAULT:
            r.setdefault(k, "")

    return True


def validate_mgcfile_zip_consistency(zf: zipfile.ZipFile, mgcfile_json: dict) -> bool:
    """校验 MGCFILE.json 与 zip entries 一致性（R8 + P0-2）。

    Args:
        zf: 已打开的 zipfile.ZipFile
        mgcfile_json: 已 validate_mgcfile_json 通过的 dict

    Returns:
        True 表示每条 record 的 archive_path 都在 zip entries 中
    """
    if not validate_mgcfile_json(mgcfile_json):
        return False
    entries = set(zf.namelist())
    for r in mgcfile_json["records"]:
        if r["archive_path"] not in entries:
            return False
    return True


def _record_from_object(r: Any) -> Dict[str, str]:
    """从 record dict / dataclass / namespace 生成标准化 record。

    支持：
    - dict：用 r[k] 取值
    - dataclass / SimpleNamespace / 任意带属性的对象：用 getattr 取值
    """
    rec = _default_record()

    def _get(key: str) -> str:
        # 优先 dict 形式
        if isinstance(r, dict):
            return r.get(key, "") or ""
        # 退回到 getattr
        return getattr(r, key, "") or ""

    rec["info_owner"] = _get("info_owner")
    rec["info_type"] = _get("info_type")
    rec["diff_1"] = _get("diff_1")
    rec["diff_2"] = _get("diff_2")
    rec["diff_3"] = _get("diff_3")
    # archive_path 默认等于 diff_3（保持现行实施策略；如有差异由调用方覆盖）
    rec["archive_path"] = _get("archive_path") or rec["diff_3"]
    # ext01-07
    for k in EXT_KEYS_WITH_DEFAULT:
        rec[k] = _get(k)
    return rec


def build_mgcfile_json(
    records: Iterable[Any],
    source_node_pub: str = "",
    version: str = "1.0",
) -> Dict[str, Any]:
    """生成 MGCFILE.json 完整结构（P0-2 + D1）。

    Args:
        records: record 列表，每个元素可以是 dict / dataclass / SimpleNamespace
                 至少含 info_owner / info_type / diff_2 / diff_3 / archive_path
                 以及可选的 ext01-ext07
        source_node_pub: D1 明文来源标识
        version: 协议版本，默认 "1.0"

    Returns:
        MGCFILE.json 顶层 dict
    """
    norm_records: List[Dict[str, str]] = []
    for r in records:
        norm_records.append(_record_from_object(r))

    return {
        "version": version,
        "source_node_pub": source_node_pub,
        "records": norm_records,
    }


def dumps_mgcfile_json(data: Dict[str, Any], indent: int = 2) -> bytes:
    """序列化 MGCFILE.json 为 UTF-8 bytes（json.dumps + indent）。"""
    return json.dumps(data, ensure_ascii=False, indent=indent).encode("utf-8")


def check_size_limits(records: Iterable[Any]) -> Optional[str]:
    """B2 决策：限 100 文件 + 50 MB。

    Args:
        records: record 列表（dict / dataclass / SimpleNamespace）

    Returns:
        None 表示通过；返回错误码字符串表示越界（"TOO_MANY_FILES" / "PACKAGE_TOO_LARGE"）
    """
    materialized = list(records)
    if len(materialized) > MGC_FILE_MAX_RECORDS:
        return "TOO_MANY_FILES"

    def _get_content(r: Any) -> Any:
        if isinstance(r, dict):
            return r.get("content", b"")
        return getattr(r, "content", b"")

    total = 0
    for r in materialized:
        content = _get_content(r) or b""
        if isinstance(content, str):
            content = content.encode("utf-8")
        total += len(content)
    if total > MGC_FILE_MAX_TOTAL_BYTES:
        return "PACKAGE_TOO_LARGE"
    return None