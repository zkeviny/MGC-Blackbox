"""Sealed package exporter.

按 [技能授权需求实施计划.md §四 4.5](../../document/1.5需求文档/1.5.0需求计划/技能授权需求实施计划.md)
生成 .mgc_file + README.md + MGCFILE.json + 外层交付目录。

关键决策：
- P0-1：函数参数加 diff_1；无 diff_1 时歧义返回 AMBIGUOUS_FOLDER
- P0-2：先逐条 seal_script() 得到最终 ciphertext + ext03，再生成 manifest
- P0-3：返回外层交付目录 {diff_2}_delivery/，含 {diff_2}.mgc_file + README.md
- B2：限 100 文件 / 50 MB
- B3：只加密 script 内容；README.md / MGCFILE.json / file 类内容均明文
- D1：ext07 明文（来源标识）；self_pub 明文写入顶层 source_node_pub + 每条 record.ext07
- B4 / R3：ext04 必传且必须是 PEM 格式

依赖：
- mgc.utils.mgc_file_format：build_mgcfile_json / check_size_limits / dumps_mgcfile_json
- mgc.service.usk3_yaml_writer（PR-3c 交付后引用，本文件先以最小占位 README 渲染）
- SealService.seal_script（PR-5 接入；本文件用 seal_callback 注入）
"""

from __future__ import annotations

import copy
import json
import logging
import os
import zipfile
from typing import Any, Callable, Dict, List, Optional

from mgc.core.mgc_service.sealed_payload_parser import (
    collapse_underscores,
    sanitize_path_segment,
)
from mgc.service.chain_spec_parser import (
    CHAIN_MODE,
    ERROR_EXT04_FILE_NOT_FOUND,
    ERROR_EXT04_JSON_INVALID,
    ERROR_EXT04_TARGET_INVALID,
    collect_requested_files,
    load_chain_targets,
)
from mgc.utils.chain_distribution_index import (
    build_distribution_index,
    write_distribution_index,
)
from mgc.utils.chain_readme_writer import (
    node_pub_fingerprint,
    render_chain_main_readme,
)
from mgc.utils.mgc_file_format import (
    build_mgcfile_json,
    check_size_limits,
    dumps_mgcfile_json,
)
from mgc.utils.usk3_yaml_writer import render as usk3_render

_logger = logging.getLogger(__name__)


# 错误码占位
ERROR_MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"
ERROR_INVALID_EXT04 = "SEAL_NODE_PUB_INVALID"
# 1.6.0：deprecated —— 三个 mode 已统一放宽「无脚本即报错」，此码不再返回
ERROR_NO_SCRIPT_TO_SEAL = "NO_SCRIPT_TO_SEAL"
ERROR_AMBIGUOUS_FOLDER = "AMBIGUOUS_FOLDER"
ERROR_PATH_NOT_LOCAL = "PATH_NOT_LOCAL"
ERROR_SIZE = {
    "TOO_MANY_FILES": "TOO_MANY_FILES",
    "PACKAGE_TOO_LARGE": "PACKAGE_TOO_LARGE",
}

# 1.6.0 chain mode 专用错误码
ERROR_CHAIN_SPEC_INVALID = "CHAIN_SPEC_INVALID"
ERROR_CHAIN_DELIVERY_EXISTS = "CHAIN_DELIVERY_EXISTS"


def _error(code: str, message: str, **extra: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {"error": code, "message": message}
    data.update(extra)
    return {"code": 400, "msg": code, "hint": message, "data": data}


def _success(data: Dict[str, Any], warnings: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """生成 200 响应。

    1.5.1+ 改造：可选 warnings 列表。结构与 mgc_run 的 data.warnings 形状一致：
    [{code, message, details}]。当 sealed 包包含 1.5.1+ 特性（如 auto-recognized
    workflow / ext08）时，提示导出方"低版本 receiver 可能不支持"。
    """
    payload: Dict[str, Any] = dict(data)
    if warnings:
        payload["warnings"] = list(warnings)
    return {
        "code": 200,
        "msg": "OPERATION_SUCCESSFUL",
        "hint": f"Sealed package generated. {data.get('file_count', 0)} file(s) packaged.",
        "data": payload,
    }


def is_valid_pem(pem: str) -> bool:
    """R3 决策：ext04 必须是 PEM 格式公钥。

    判定宽松：仅检查是否含 PEM 头/尾标记（"-----BEGIN" / "-----END"）。
    严格校验由 SealService 在 PR-5 接入时完成。
    """
    if not pem or not isinstance(pem, str):
        return False
    return "-----BEGIN" in pem and "-----END" in pem


def export_sealed_package(
    info_owner: str,
    diff_2: str,
    ext04: str,
    output_dir: str,
    diff_1: str = "",
    query_callback: Optional[Callable[[str, str, str], List[dict]]] = None,
    seal_callback: Optional[Callable[..., Dict[str, Any]]] = None,
    self_node_pub: str = "",
    readme_renderer: Optional[Callable[[List[dict], str], str]] = None,
    mode: str = "p2p mode",
) -> Dict[str, Any]:
    """生成 .mgc_file + README.md + MGCFILE.json + 外层交付目录。

    Args:
        info_owner: 必传
        diff_2: 必传，文件夹名
        ext04: 目标节点 PEM 公钥（B3 / R3）。1.5.4 free mode 可为空。
        output_dir: 本机输出根目录
        diff_1: 可选（P0-1）
        query_callback: 查询回调 (info_owner, diff_2, diff_1) -> list[dict]
        seal_callback: 1.5.4 期望 4 参数 (content, out_pub, mode, source_node_pub)
            老调用方 2 参数 (content, out_pub) 也能跑（走 legacy 单层）。
        self_node_pub: 本节点 PEM 公钥（D1 明文）
        readme_renderer: README 渲染回调
        mode: 1.5.4 新增。"p2p mode" / "free mode" / "chain mode"（占位）

    Returns:
        标准 API 响应 dict
    """
    # ---- 1.5.4 mode 参数校验 ----
    valid_modes = ("p2p mode", "free mode", "chain mode")
    if mode not in valid_modes:
        return _error(
            ERROR_INVALID_EXT04,
            f"invalid mode {mode!r}; expected one of {valid_modes}",
        )
    # ---- 基本校验 ----
    if not info_owner:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "info_owner required")
    if not diff_2:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "diff_2 required")
    # 1.5.4：free mode 允许 ext04 为空（PM Q5 决策）；p2p mode 仍要求 ext04
    if mode == "p2p mode":
        if not ext04:
            return _error(ERROR_MISSING_REQUIRED_FIELDS, "ext04 required for p2p mode")
        if not is_valid_pem(ext04):
            return _error(ERROR_INVALID_EXT04, "ext04 is not a valid PEM public key")
    if not output_dir:
        return _error(ERROR_PATH_NOT_LOCAL, "output_dir required")
    if query_callback is None:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "query_callback not injected")
    if seal_callback is None:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "seal_callback not injected")

    # ---- 1.6.0：chain mode 分流（p2p / free 路径以下完全不变）----
    if mode == CHAIN_MODE:
        return export_chain_package(
            info_owner=info_owner,
            diff_2=diff_2,
            ext04=ext04,
            output_dir=output_dir,
            diff_1=diff_1,
            query_callback=query_callback,
            seal_callback=seal_callback,
            self_node_pub=self_node_pub,
        )

    # ---- 查询 ----
    try:
        records = query_callback(info_owner, diff_2, diff_1)
    except Exception as e:
        _logger.warning("export_sealed_package query failed: %s", e)
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

    # ---- B2 容量上限 ----
    limit_err = check_size_limits(records)
    if limit_err == "TOO_MANY_FILES":
        return _error(ERROR_SIZE["TOO_MANY_FILES"], "Sealed package max 100 files.")
    if limit_err == "PACKAGE_TOO_LARGE":
        return _error(ERROR_SIZE["PACKAGE_TOO_LARGE"], "Sealed package max 50 MB.")

    # ---- D1：本节点 self_pub 明文写入每条 record.ext07 ----
    for r in records:
        r["ext07"] = self_node_pub
        # 1.5.4：写入 ext09（seal policy：p2p / free / chain mode）
        r["ext09"] = mode

    # ---- P0-2：先逐条 seal_script()，得到 ciphertext + ext03，再 build manifest ----
    # 1.5.4：seal_callback 现在接收 (content, out_node_pub, mode, source_node_pub)
    # 兼容老调用方（仍只传 content, out_node_pub）：callbacks 是 backend_callback_adapter.make_seal_callback
    # 已经接 SealService，新版 SealService 会自动把 mode / source_node_pub 透传。
    for r in records:
        if r.get("info_type") == "script":
            try:
                # 检查 callback 是否支持 4 参数（新），否则降级 2 参数（旧）
                import inspect
                sig = inspect.signature(seal_callback)
                if len(sig.parameters) >= 4:
                    sealed = seal_callback(
                        r.get("content", "") or "",
                        ext04,
                        mode,
                        self_node_pub,
                    )
                else:
                    sealed = seal_callback(r.get("content", "") or "", ext04)
            except Exception as e:
                _logger.warning("seal_script failed for %s: %s", r.get("diff_3"), e)
                return _error(ERROR_INVALID_EXT04, f"seal failed: {e}")
            r["content"] = sealed["ciphertext"]
            r["ext03"] = sealed.get("ext03", "")
            # Accept either the 1.5.4 unprefixed key or the legacy underscored
            # alias in case an older callback returns the old shape.
            r["ext07"] = sealed.get("ext07", "") or sealed.get("ext_07", "")
            r["ext09"] = sealed.get("ext09", "") or sealed.get("ext_09", "")

    # ---- 生成 MGCFILE.json ----
    mgcfile_json = build_mgcfile_json(records, source_node_pub=self_node_pub)

    # ---- 生成 README（默认用 usk3_yaml_writer；可由 readme_renderer 覆盖） ----
    renderer = readme_renderer or usk3_render
    # 1.5.4：传 mode 给 renderer，让 free mode 时渲染 Free Mode Installation 段。
    # 对老 readme_renderer（2 参数签名）做安全 fallback，避免破坏现有自定义渲染器。
    import inspect
    try:
        renderer_params = inspect.signature(renderer).parameters
    except (TypeError, ValueError):
        renderer_params = None
    if renderer_params and "mode" in renderer_params:
        readme_md = renderer(mgcfile_json["records"], self_node_pub, mode=mode)
    else:
        readme_md = renderer(mgcfile_json["records"], self_node_pub)

    # ---- P0-3：外层交付目录 {diff_2}_delivery/ ----
    delivery_dir = os.path.join(output_dir, diff_2 + "_delivery")
    os.makedirs(delivery_dir, exist_ok=True)
    mgc_file_path = os.path.join(delivery_dir, f"{diff_2}.mgc_file")
    readme_path = os.path.join(delivery_dir, "README.md")

    # ---- 打包 .mgc_file（zip） ----
    # 注：写 zip 使用 sealed records（即已就地修改 content 的原始 records），
    # 而非 mgcfile_json["records"]，因为 manifest schema 不含 content 字段。
    # archive_path 从 manifest 拿（已 validate），内容从 sealed records 拿（已 seal）。
    archive_paths_by_diff3 = {r["diff_3"]: r["archive_path"] for r in mgcfile_json["records"]}
    try:
        with zipfile.ZipFile(mgc_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("MGCFILE.json", dumps_mgcfile_json(mgcfile_json))
            for rec in records:
                archive_path = archive_paths_by_diff3.get(rec.get("diff_3", ""), rec.get("diff_3", ""))
                content = rec.get("content", b"") or b""
                if isinstance(content, str):
                    content = content.encode("utf-8")
                zf.writestr(archive_path, content)
    except OSError as e:
        _logger.warning("export_sealed_package zip write failed: %s", e)
        return _error(ERROR_PATH_NOT_LOCAL, f"output_dir not writable: {e}")

    # ---- README 写到外层目录 ----
    try:
        # newline="" 禁止 Windows 下自动转成 CRLF，保持 README 与源一致
        with open(readme_path, "w", encoding="utf-8", newline="") as f:
            f.write(readme_md)
    except OSError as e:
        _logger.warning("export_sealed_package readme write failed: %s", e)
        return _error(ERROR_PATH_NOT_LOCAL, f"readme write failed: {e}")

    # ---- 1.5.1+ cross-node version warning ----
    # 若 package 包含 1.5.1 引入的特性（auto-recognized workflow / ext08），
    # 显式告知导出方：receiver 节点若 < 1.5.1 将无法使用此特性。
    warnings = _build_cross_node_warnings(materialized_records=records)
    return _success({
        "delivery_path": delivery_dir,
        "mgc_file_path": mgc_file_path,
        "readme_path": readme_path,
        "file_count": len(mgcfile_json["records"]),
    }, warnings=warnings)


def _build_cross_node_warnings(materialized_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """若 records 含 ext08（非空字符串 / 非空 list / 非空 JSON），生成跨节点版本警告。

    1.5.1 之前 MGC 没有 ext08 字段；receiver 若 < 1.5.1：
    - sealed 包仍可正常导入 + 落库（importer 还原所有字段，ext08 字段被忽略）
    - 但跨包 import / from-import / 相对路径 subprocess **不会被 sealed execution 路由**
    - 用户会看到 ModuleNotFoundError 或 subprocess 跑通但未密封

    返回 warnings 列表（与 mgc_run 的 data.warnings 形状一致），调用方可选择性展示。
    """
    has_ext08 = False
    for r in materialized_records:
        ext08 = r.get("ext08", "")
        if isinstance(ext08, str):
            # ext08 可能是 JSON 字符串、空字符串、或 list/dict 序列化结果
            if ext08.strip() and ext08.strip() not in ("[]", "{}", "null"):
                has_ext08 = True
                break
        elif isinstance(ext08, (list, dict)) and len(ext08) > 0:
            has_ext08 = True
            break

    if not has_ext08:
        return []

    return [{
        "code": "TARGET_NODE_MAY_NOT_SUPPORT_AUTO_WORKFLOW",
        "message": (
            "This package includes auto-recognized cross-script relationships "
            "(ext08). Receivers running mgc below 1.5.2 will import the "
            "package successfully but will NOT route cross-script calls "
            "through sealed execution — they will fail with "
            "ModuleNotFoundError (import) or run as ordinary subprocesses "
            "without sealing."
        ),
        "details": {
            "min_target_version": "1.5.2",
            "feature": "auto-recognized workflow execution (import hook + ext08)",
        },
    }]


# ============================================================
# 1.6.0 chain mode
# ============================================================

def _parse_ext08_calls(ext08: Any) -> List[Dict[str, Any]]:
    """解析 record 的 ext08（callgraph JSON），取出 calls[] 列表。

    ext08 可能是 JSON 字符串 / list / dict / 空。解析失败一律返回空列表
    —— 检查是**提示性**的，绝不因 ext08 畸形而中断打包。
    """
    if not ext08:
        return []
    data: Any = ext08
    if isinstance(ext08, str):
        raw = ext08.strip()
        if not raw or raw in ("[]", "{}", "null"):
            return []
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
    if isinstance(data, dict):
        data = data.get("calls", [])
    if not isinstance(data, list):
        return []
    return [c for c in data if isinstance(c, dict)]


def _build_chain_name_parts(info_owner: str, diff_2: str) -> tuple:
    """生成 chain mode 的路径片段。

    主文件夹 = <owner_slug>__<diff_2_slug>
    子包文件名 = <owner_slug>__<diff_2_slug>__<序号>.mgc_file

    清洗规则复用 sealed_payload_parser.sanitize_path_segment（跨平台安全），
    段内连续下划线归一为单个，保证两级分隔符可无歧义切分（Q4）。

    Returns:
        (owner_slug, diff_2_slug)
    """
    owner_slug = collapse_underscores(sanitize_path_segment(info_owner, fallback="task"))
    diff2_slug = collapse_underscores(sanitize_path_segment(diff_2, fallback="package"))
    return owner_slug, diff2_slug


def export_chain_package(
    info_owner: str,
    diff_2: str,
    ext04: str,
    output_dir: str,
    diff_1: str = "",
    query_callback: Optional[Callable[[str, str, str], List[dict]]] = None,
    seal_callback: Optional[Callable[..., Dict[str, Any]]] = None,
    self_node_pub: str = "",
) -> Dict[str, Any]:
    """chain mode 拆包：按 node_pub 把任务包拆成多个 .mgc_file + readme。

    产物结构：

        output_dir/
        └── <owner>__<diff_2>/
            ├── README.md                      ← 主 readme（node_pub ↔ 子目录映射 + warning）
            ├── task_package_01/
            │   ├── README.md                  ← 子包 readme
            │   └── <owner>__<diff_2>__01.mgc_file
            └── ...

    关键决策：
    - D3：record 的 diff_2 **保持主任务原值**，拆解序号只落文件系统命名
    - D4：只封 script，非脚本内容明文随该节点子包走
    - L61：依赖未指名 / 文件重复指名均**不阻断**打包，仅提示

    Args:
        info_owner: 主任务名
        diff_2: 主任务包名
        ext04: chain spec（inline JSON 或 "@路径"）
        output_dir: 本机输出根目录
        diff_1: 可选
        query_callback: 查询回调 (info_owner, diff_2, diff_1) -> list[dict]
        seal_callback: 密封回调 (content, out_node_pub, mode, source_node_pub)
        self_node_pub: 本节点 PEM 公钥

    Returns:
        标准 API 响应 dict
    """
    # ---- 1. 解析 chain spec（失败即报错，绝不降级）----
    targets, spec_err = load_chain_targets(ext04)
    if spec_err:
        return _error(
            ERROR_CHAIN_SPEC_INVALID,
            f"invalid chain spec: {spec_err}. "
            f"NOTE: MGC did NOT fall back to p2p / free mode — "
            f"a chain spec must be a JSON array of "
            f'{{"node_pub": "<PEM>", "files": ["<diff_3>", ...]}} targets.',
            **{"chain_spec_error": spec_err},
        )

    if not info_owner:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "info_owner required")
    if not diff_2:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "diff_2 required")
    if not output_dir:
        return _error(ERROR_PATH_NOT_LOCAL, "output_dir required")
    if query_callback is None:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "query_callback not injected")
    if seal_callback is None:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "seal_callback not injected")

    # ---- 2. 查询 records ----
    try:
        records = query_callback(info_owner, diff_2, diff_1)
    except Exception as e:
        _logger.warning("export_chain_package query failed: %s", e)
        return _error(ERROR_MISSING_REQUIRED_FIELDS, f"query failed: {e}")

    if not records:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "no records found")

    # ---- 3. 歧义校验（与 p2p 路径一致）----
    if not diff_1:
        seen_sets = {(r.get("info_owner", ""), r.get("diff_1", ""), r.get("diff_2", "")) for r in records}
        if len(seen_sets) > 1:
            return _error(
                ERROR_AMBIGUOUS_FOLDER,
                f"Multiple folders match owner={info_owner} diff_2={diff_2}. "
                f"Please provide diff_1 to disambiguate.",
                **{"candidates": sorted(s[2] + "/" + s[1] for s in seen_sets)},
            )

    # ---- 4. B2 容量上限 ----
    limit_err = check_size_limits(records)
    if limit_err == "TOO_MANY_FILES":
        return _error(ERROR_SIZE["TOO_MANY_FILES"], "Sealed package max 100 files.")
    if limit_err == "PACKAGE_TOO_LARGE":
        return _error(ERROR_SIZE["PACKAGE_TOO_LARGE"], "Sealed package max 50 MB.")

    # ---- 5. 建 diff_3 索引 + 校验 target.files 命中 ----
    by_diff_3: Dict[str, dict] = {}
    for r in records:
        by_diff_3.setdefault(r.get("diff_3", ""), r)

    missing_all: List[str] = []
    for i, target in enumerate(targets, start=1):
        missing = [f for f in target["files"] if f not in by_diff_3]
        if missing:
            missing_all.append(f"target #{i}: {', '.join(missing)}")
    if missing_all:
        return _error(
            ERROR_EXT04_FILE_NOT_FOUND,
            "chain spec references files that do not exist in this task package: "
            + "; ".join(missing_all),
            **{"missing_files": missing_all},
        )

    # ---- 6. 未被指名的文件 + 重复指名检测 ----
    named_all = set()
    for target in targets:
        named_all.update(target["files"])
    unnamed_files = sorted(f for f in by_diff_3 if f not in named_all)
    duplicated_files = collect_requested_files(targets)

    # ---- 7. 主文件夹 / 子包命名 ----
    owner_slug, diff2_slug = _build_chain_name_parts(info_owner, diff_2)
    delivery_dir = os.path.join(output_dir, f"{owner_slug}__{diff2_slug}")
    if os.path.exists(delivery_dir):
        return _error(
            ERROR_CHAIN_DELIVERY_EXISTS,
            f"delivery folder already exists: {delivery_dir}. "
            f"Refusing to overwrite an existing chain package.",
            **{"delivery_path": delivery_dir},
        )
    os.makedirs(delivery_dir, exist_ok=False)

    packages: List[Dict[str, Any]] = []
    orphan_dependencies: List[Dict[str, Any]] = []

    for idx, target in enumerate(targets, start=1):
        target_files = target["files"]
        # 本 target 的 records —— **record 的 diff_2 保持原值**（D3）
        # 1.6.0 fix：同一文件被多个 target 指名时，必须各自持有独立副本。
        # 密封会原地覆盖 rec["content"]（明文 → 密文字节），共享同一 dict
        # 会让第二个 target 拿到已加密的 bytes 再加密，报
        # "'bytes' object has no attribute 'encode'"。
        target_records = [
            copy.deepcopy(by_diff_3[f]) for f in target_files if f in by_diff_3
        ]

        # ---- 7a. 依赖未指名检查（不阻断）----
        granted = set(target_files)
        for rec in target_records:
            for call in _parse_ext08_calls(rec.get("ext08", "")):
                dep = call.get("target_diff_3", "")
                if dep and dep not in granted:
                    orphan_dependencies.append({
                        "node_index": idx,
                        "diff_3": rec.get("diff_3", ""),
                        "missing_dependency": dep,
                        "kind": call.get("kind", ""),
                    })

        # ---- 7b. 逐 record 密封（per-record 传该 target 的 node_pub）----
        for rec in target_records:
            rec["ext07"] = self_node_pub
            rec["ext09"] = CHAIN_MODE
            if rec.get("info_type") != "script":
                # D4：非脚本内容保持明文，不做加密
                continue
            try:
                sealed = seal_callback(
                    rec.get("content", "") or "",
                    target["node_pub"],   # ← per-record：目标节点的 node_pub
                    CHAIN_MODE,
                    self_node_pub,
                )
            except Exception as e:
                _logger.warning("chain seal failed for %s: %s", rec.get("diff_3"), e)
                return _error(
                    ERROR_INVALID_EXT04,
                    f"seal failed for target #{idx} / {rec.get('diff_3', '')}: {e}",
                )
            rec["content"] = sealed["ciphertext"]
            rec["ext03"] = sealed.get("ext03", "")
            rec["ext07"] = sealed.get("ext07", "") or sealed.get("ext_07", "") or self_node_pub
            rec["ext09"] = sealed.get("ext09", "") or sealed.get("ext_09", "") or CHAIN_MODE

        # ---- 7c. 写子包 ----
        dir_name = f"task_package_{idx:02d}"
        pkg_file_name = f"{owner_slug}__{diff2_slug}__{idx:02d}.mgc_file"
        pkg_dir = os.path.join(delivery_dir, dir_name)
        os.makedirs(pkg_dir, exist_ok=False)
        mgc_file_path = os.path.join(pkg_dir, pkg_file_name)
        readme_path = os.path.join(pkg_dir, "README.md")

        mgcfile_json = build_mgcfile_json(target_records, source_node_pub=self_node_pub)
        archive_paths_by_diff3 = {
            r["diff_3"]: r["archive_path"] for r in mgcfile_json["records"]
        }
        try:
            with zipfile.ZipFile(mgc_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("MGCFILE.json", dumps_mgcfile_json(mgcfile_json))
                for rec in target_records:
                    archive_path = archive_paths_by_diff3.get(
                        rec.get("diff_3", ""), rec.get("diff_3", "")
                    )
                    content = rec.get("content", b"") or b""
                    if isinstance(content, str):
                        content = content.encode("utf-8")
                    zf.writestr(archive_path, content)
        except OSError as e:
            _logger.warning("chain package zip write failed: %s", e)
            return _error(ERROR_PATH_NOT_LOCAL, f"output_dir not writable: {e}")

        # ---- 7d. 子包 readme ----
        readme_md = usk3_render(
            mgcfile_json["records"],
            self_node_pub,
            mode=CHAIN_MODE,
            package_file_name=pkg_file_name,
        )
        try:
            with open(readme_path, "w", encoding="utf-8", newline="") as f:
                f.write(readme_md)
        except OSError as e:
            _logger.warning("chain sub-package readme write failed: %s", e)
            return _error(ERROR_PATH_NOT_LOCAL, f"readme write failed: {e}")

        packages.append({
            "package_index": idx,
            "dir_name": dir_name,
            "package_file_name": pkg_file_name,
            "mgc_file_path": mgc_file_path,
            "readme_path": readme_path,
            "node_pub_fingerprint": node_pub_fingerprint(target["node_pub"]),
            "file_count": len(target_records),
            "files": list(target_files),
            "node_pub": target["node_pub"],
        })

    # ---- 8. warnings ----
    warnings: List[Dict[str, Any]] = []
    if orphan_dependencies:
        warnings.append({
            "code": "CHAIN_DEPENDENCY_NOT_GRANTED",
            "message": (
                f"{len(orphan_dependencies)} dependency reference(s) point to files "
                f"not granted to the same node. MGC packaged everything exactly as "
                f"the chain spec instructed — see the main README.md for details."
            ),
            "details": {"count": len(orphan_dependencies)},
        })
    if unnamed_files:
        warnings.append({
            "code": "CHAIN_FILES_NOT_GRANTED",
            "message": (
                f"{len(unnamed_files)} file(s) were not named by any target and are "
                f"not included in any sub-package — see the main README.md."
            ),
            "details": {"count": len(unnamed_files), "files": unnamed_files},
        })
    if duplicated_files:
        warnings.append({
            "code": "CHAIN_FILE_GRANTED_TO_MULTIPLE_NODES",
            "message": (
                f"{len(duplicated_files)} file(s) were named by multiple targets. "
                f"If two sub-packages land on the same node, the later import "
                f"overwrites the earlier one — please confirm the distribution scope."
            ),
            "details": {"count": len(duplicated_files), "files": sorted(duplicated_files.keys())},
        })
    warnings.extend(_build_cross_node_warnings(materialized_records=records))

    # ---- 9. 主 readme ----
    readme_path = os.path.join(delivery_dir, "README.md")
    main_readme_md = render_chain_main_readme(
        info_owner=info_owner,
        diff_2=diff_2,
        source_node_pub=self_node_pub,
        packages=packages,
        warnings=None,
        unnamed_files=unnamed_files,
        orphan_dependencies=orphan_dependencies,
        duplicated_files=duplicated_files,
    )
    try:
        with open(readme_path, "w", encoding="utf-8", newline="") as f:
            f.write(main_readme_md)
    except OSError as e:
        _logger.warning("chain main readme write failed: %s", e)
        return _error(ERROR_PATH_NOT_LOCAL, f"main readme write failed: {e}")

    # ---- 9b. 机器可读分发索引（1.6.0 W-B4）----
    # 主 readme 给人看，索引给脚本看：分发方据此决定「哪个子包发给哪个节点」，
    # 无需解析 markdown。索引与主 readme 同级，一次拷贝带走。
    distribution_index = build_distribution_index(
        info_owner=info_owner,
        diff_2=diff_2,
        diff_1=diff_1,
        source_node_pub=self_node_pub,
        packages=packages,
        delivery_dir=delivery_dir,
        warnings=warnings,
        unnamed_files=unnamed_files,
        orphan_dependencies=orphan_dependencies,
        duplicated_files=duplicated_files,
    )
    try:
        index_path = write_distribution_index(distribution_index, delivery_dir)
    except OSError as e:
        _logger.warning("chain distribution index write failed: %s", e)
        return _error(ERROR_PATH_NOT_LOCAL, f"distribution index write failed: {e}")

    # ---- 10. 返回体 ----
    total_files = sum(p["file_count"] for p in packages)
    return _success({
        "delivery_path": delivery_dir,
        "readme_path": readme_path,
        "distribution_index_path": index_path,
        "info_owner": info_owner,
        "diff_2": diff_2,
        "packages": packages,
        "mapping": [
            {
                "package_index": p["package_index"],
                "dir_name": p["dir_name"],
                "package_file_name": p["package_file_name"],
                "mgc_file_path": p["mgc_file_path"],
                "node_pub_fingerprint": p["node_pub_fingerprint"],
                "file_count": p["file_count"],
            }
            for p in packages
        ],
        "targets": [
            {"package_index": p["package_index"], "node_pub": p["node_pub"]}
            for p in packages
        ],
        "file_count": total_files,
        "package_count": len(packages),
    }, warnings=warnings)