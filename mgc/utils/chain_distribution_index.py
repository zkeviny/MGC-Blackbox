"""chain mode 机器可读分发索引（1.6.0 W-B4）。

主 readme 是**给人看**的（分发映射表 + warning 区 + node_pub 指纹）。
本模块产出**给机器看**的分发索引 —— 编排方 / 分发脚本可以据此
「把哪个子包发给哪个节点」，无需解析 markdown。

产物：`<delivery_dir>/distribution_index.json`

设计要点：
- 索引与主 readme 同级同目录 —— 一次拷贝带走，不漏文件
- **不重复密封包内容** —— 索引只描述「谁该拿哪个文件」
- node_pub **明文写出**：编排方需要它才能组装分发动作
  （密文安全由 ext03 保证，索引本身不是机密载体 —— 它描述的是
  「谁被授权」，而不是「授权凭据」）
- 每个子包给出 sha256 —— 分发后校验字节完整性（A2A 传输后必查）
- warnings 结构与 mgc_run 的 data.warnings 一致，脚本可直接消费
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

# 索引 schema 版本 —— 结构不兼容变更时递增
CHAIN_INDEX_VERSION = "1.0"

# 索引文件名（与主 readme 同级）
CHAIN_INDEX_FILENAME = "distribution_index.json"


def _sha256(path: str) -> str:
    """文件 sha256（十六进制）。读不到时返回空串，不抛异常。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 256), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def build_distribution_index(
    info_owner: str,
    diff_2: str,
    diff_1: str,
    source_node_pub: str,
    packages: List[Dict[str, Any]],
    delivery_dir: str,
    warnings: Optional[List[Dict[str, Any]]] = None,
    unnamed_files: Optional[List[str]] = None,
    orphan_dependencies: Optional[List[Dict[str, Any]]] = None,
    duplicated_files: Optional[Dict[str, List[int]]] = None,
) -> Dict[str, Any]:
    """构造分发索引 dict。

    Args:
        info_owner: 主任务名
        diff_2: 主任务包名（各子包共享）
        diff_1: 第一层区分（可空）
        source_node_pub: 编排方（密封方）node_pub
        packages: 子包清单，每项含 package_index / dir_name /
            package_file_name / mgc_file_path / readme_path /
            node_pub / node_pub_fingerprint / file_count / files
        delivery_dir: 交付根目录（用于算相对路径）
        warnings: warning 列表（形状同 mgc_run 的 data.warnings）
        unnamed_files: 未被任何 target 指名的文件
        orphan_dependencies: 依赖未指名的记录
        duplicated_files: 同一 diff_3 被多个 target 指名的映射

    Returns:
        索引 dict（可直接 json.dumps）
    """
    entries: List[Dict[str, Any]] = []
    for pkg in packages:
        mgc_file_path = pkg.get("mgc_file_path", "")
        readme_path = pkg.get("readme_path", "")
        dir_name = pkg.get("dir_name", "")

        def _rel(p: str) -> str:
            """相对 delivery_dir 的路径 —— 索引随目录一起搬动，路径需保持相对。"""
            if not p:
                return ""
            try:
                return os.path.relpath(p, delivery_dir).replace(os.sep, "/")
            except ValueError:
                return p

        entries.append({
            "package_index": pkg.get("package_index", 0),
            "dir_name": dir_name,
            "mgc_file": _rel(mgc_file_path),
            "package_file_name": pkg.get("package_file_name", ""),
            "readme": _rel(readme_path),
            "sha256": _sha256(mgc_file_path),
            "size_bytes": _file_size(mgc_file_path),
            "node_pub": pkg.get("node_pub", ""),
            "node_pub_fingerprint": pkg.get("node_pub_fingerprint", ""),
            "file_count": pkg.get("file_count", 0),
            "files": list(pkg.get("files", [])),
        })

    return {
        "schema": "mgc.chain-distribution-index/v1",
        "version": CHAIN_INDEX_VERSION,
        "task": {
            "info_owner": info_owner,
            "diff_1": diff_1,
            "diff_2": diff_2,
            "source_node_pub": source_node_pub,
        },
        "delivery_dir": os.path.basename(delivery_dir.rstrip(os.sep)),
        "packages": entries,
        "totals": {
            "package_count": len(entries),
            "file_count": sum(e["file_count"] for e in entries),
            "total_bytes": sum(e["size_bytes"] for e in entries),
        },
        "warnings": list(warnings or []),
        "unnamed_files": list(unnamed_files or []),
        "orphan_dependencies": list(orphan_dependencies or []),
        "duplicated_files": {
            k: list(v) for k, v in (duplicated_files or {}).items()
        },
    }


def _file_size(path: str) -> int:
    """文件字节数；读不到返回 0。"""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def write_distribution_index(index: Dict[str, Any], delivery_dir: str) -> str:
    """把索引写进交付目录，返回索引文件路径。"""
    os.makedirs(delivery_dir, exist_ok=True)
    path = os.path.join(delivery_dir, CHAIN_INDEX_FILENAME)
    with open(path, "w", encoding="utf-8", newline="") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def load_distribution_index(path: str) -> Dict[str, Any]:
    """读取分发索引。

    Raises:
        ValueError: 文件不存在或不是合法 JSON
    """
    if not os.path.isfile(path):
        raise ValueError(f"distribution index not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "packages" not in data:
        raise ValueError(f"not a valid distribution index: {path}")
    return data


def validate_distribution_index(index: Dict[str, Any]) -> List[str]:
    """校验分发索引结构。

    Returns:
        问题列表；空列表表示通过
    """
    problems: List[str] = []

    schema = index.get("schema", "")
    if schema != "mgc.chain-distribution-index/v1":
        problems.append(f"unexpected schema: {schema!r}")

    task = index.get("task")
    if not isinstance(task, dict):
        problems.append("missing task object")
    else:
        for key in ("info_owner", "diff_2"):
            if not task.get(key):
                problems.append(f"task.{key} is empty")

    packages = index.get("packages")
    if not isinstance(packages, list):
        problems.append("missing packages array")
        return problems

    if not packages:
        problems.append("packages is empty")

    seen_index: List[int] = []
    seen_sha: Dict[str, int] = {}
    for i, entry in enumerate(packages):
        if not isinstance(entry, dict):
            problems.append(f"packages[{i}] is not an object")
            continue
        idx = entry.get("package_index")
        if not isinstance(idx, int):
            problems.append(f"packages[{i}].package_index is not an int")
        elif idx in seen_index:
            problems.append(f"duplicate package_index: {idx}")
        else:
            seen_index.append(idx)

        if not entry.get("mgc_file"):
            problems.append(f"packages[{i}].mgc_file is empty")
        if not entry.get("node_pub"):
            problems.append(f"packages[{i}].node_pub is empty")

        sha = entry.get("sha256", "")
        if sha:
            if len(sha) != 64:
                problems.append(f"packages[{i}].sha256 is not a hex digest")
            elif sha in seen_sha:
                problems.append(
                    f"packages[{i}].sha256 duplicates packages[{seen_sha[sha]}]"
                )
            else:
                seen_sha[sha] = i
        else:
            problems.append(f"packages[{i}].sha256 is empty")

    return problems
