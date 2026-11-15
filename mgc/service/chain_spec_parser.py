"""chain mode 的 ext04 规格解析器（1.6.0）。

契约见 [1.6.0 实施计划 §2.1](../../document/1.6需求文档/1.6.0需求计划/chain_mode实施计划.md)：

- ext04 = JSON **数组** → chain mode；每个元素是一个 target
- target = {"node_pub": "<被授权节点 PEM>", "files": ["<diff_3>", ...]}
- ext04 = "@<本地文件路径>" → 读取该文件内容按同一契约解析
- 解析失败一律报错，**禁止静默降级**为 p2p / free

关键决策：
- D1：MGC 不生成 node_pub、不校验归属、不落库、不随包传递——只做形态校验
- D2：mode 由 ext04 形态决定，不新增任何请求字段
- R3：解析失败即报错，代码层无 fallback 分支（降级 = 授权降级）
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Tuple

_logger = logging.getLogger(__name__)


# ---- seal mode 常量（与 seal_service.EXT09_* 对齐）----
CHAIN_MODE = "chain mode"
P2P_MODE = "p2p mode"
FREE_MODE = "free mode"


# ---- 错误码 ----
ERROR_EXT04_JSON_INVALID = "EXT04_JSON_INVALID"
ERROR_EXT04_FILE_UNREADABLE = "EXT04_FILE_UNREADABLE"
ERROR_EXT04_TARGET_INVALID = "EXT04_TARGET_INVALID"
ERROR_EXT04_TARGET_EMPTY = "EXT04_TARGET_EMPTY"
ERROR_EXT04_FILE_NOT_FOUND = "EXT04_FILE_NOT_FOUND"


def detect_mode(ext04: str) -> str:
    """按 D2 判据决定 seal mode。

    判据（不新增请求字段，纯看 ext04 形态）：
    - 空 → free mode（任何 1.5.4+ 节点可解）
    - 以 "@" 开头 → chain mode（本地文件路径）
    - 以 "[" 开头 → chain mode（inline JSON 数组）
    - 其余 → p2p mode（单节点 PEM）

    Args:
        ext04: 调用方传入的 ext04 原值

    Returns:
        "chain mode" / "p2p mode" / "free mode"
    """
    raw = (ext04 or "").strip()
    if not raw:
        return FREE_MODE
    if raw.startswith("@"):
        return CHAIN_MODE
    if raw.startswith("["):
        return CHAIN_MODE
    return P2P_MODE


def _read_spec_file(path: str) -> Tuple[str, str]:
    """读取 "@<路径>" 指向的本地规格文件。

    Returns:
        (content, error_code)；成功时 error_code 为 ""，失败时 content 为 ""
    """
    raw_path = (path or "").strip()
    if not raw_path:
        return "", ERROR_EXT04_FILE_UNREADABLE
    # 必须是本机绝对路径——相对路径依赖调用方 cwd，跨进程不可靠
    if not os.path.isabs(raw_path):
        return "", ERROR_EXT04_FILE_UNREADABLE
    if not os.path.isfile(raw_path):
        return "", ERROR_EXT04_FILE_UNREADABLE
    try:
        with open(raw_path, "r", encoding="utf-8") as f:
            return f.read(), ""
    except OSError as e:
        _logger.warning("chain_spec_parser: read spec file failed: %s", e)
        return "", ERROR_EXT04_FILE_UNREADABLE


def _validate_target(target: Any, index: int) -> Tuple[Dict[str, Any], str]:
    """校验单个 target 的形态。

    Returns:
        (target_dict, error_message)；成功时 error_message 为 ""
    """
    if not isinstance(target, dict):
        return {}, f"target #{index} is not a JSON object"

    node_pub = target.get("node_pub", "")
    if not isinstance(node_pub, str) or not node_pub.strip():
        return {}, f"target #{index} is missing 'node_pub'"
    # 宽松 PEM 形态校验（严格校验由 SealService 完成）
    if "-----BEGIN" not in node_pub or "-----END" not in node_pub:
        return {}, f"target #{index} 'node_pub' is not a PEM public key"

    files = target.get("files", [])
    if not isinstance(files, list) or not files:
        return {}, f"target #{index} 'files' must be a non-empty array"
    for f in files:
        if not isinstance(f, str) or not f.strip():
            return {}, f"target #{index} 'files' contains a non-string or empty entry"

    return {
        "node_pub": node_pub,
        "files": [f for f in files],
    }, ""


def load_chain_targets(ext04: str) -> Tuple[List[Dict[str, Any]], str]:
    """解析 ext04 → ([{node_pub, files}], 错误消息)。

    校验项：
    1. "@路径" 文件可读（本机绝对路径）
    2. JSON 合法且顶层为数组
    3. 每个 target 必须含 node_pub（PEM 形态）与 files（非空字符串数组）
    4. 数组至少有一个 target

    **不校验 node_pub 归属**：MGC 无从判断某 PEM 属于哪个节点
    （A2A 组网在 MGC 之外），仅做形态校验。

    **绝不静默降级**：任何失败都返回错误消息，由调用方直接报错。

    Args:
        ext04: chain spec 原值（inline JSON 或 "@路径"）

    Returns:
        (targets, error_message)；成功时 error_message 为 ""
    """
    raw = (ext04 or "").strip()
    if not raw:
        return [], "chain spec is empty"

    if raw.startswith("@"):
        spec_path = raw[1:]
        content, err = _read_spec_file(spec_path)
        if err:
            return [], (
                f"cannot read chain spec file {spec_path!r}: "
                f"it must be an existing local file with an absolute path"
            )
        raw = content.strip()
        if not raw:
            return [], f"chain spec file {spec_path!r} is empty"

    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as e:
        return [], f"chain spec is not valid JSON: {e}"

    if not isinstance(data, list):
        return [], "chain spec must be a JSON array of targets"

    if not data:
        return [], "chain spec array is empty (no targets)"

    targets: List[Dict[str, Any]] = []
    for i, raw_target in enumerate(data, start=1):
        target, err = _validate_target(raw_target, i)
        if err:
            return [], err
        targets.append(target)

    return targets, ""


def collect_requested_files(targets: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    """统计每个 diff_3 被哪些 target（按 1-based 序号）指名。

    用于检测「同一文件被多个节点同时指名」（PM D3 的连带项）——
    因 diff_2 不承载序号，同一 diff_3 若落到同一节点会因五元组命中而覆盖。

    Args:
        targets: load_chain_targets 的返回

    Returns:
        {diff_3: [target_index, ...]}；未被重复指名的文件不在结果中
    """
    seen: Dict[str, List[int]] = {}
    for idx, target in enumerate(targets, start=1):
        for f in target.get("files", []):
            seen.setdefault(f, []).append(idx)
    return {f: idxs for f, idxs in seen.items() if len(idxs) > 1}
