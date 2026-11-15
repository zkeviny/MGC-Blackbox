"""Folder save orchestrator.

按 [技能授权需求实施计划.md §四 4.3](../../document/1.5需求文档/1.5.0需求计划/技能授权需求实施计划.md)
编排：识别路径 → 解析 → 批量 save。

关键决策：
- B1：folder save 部分成功（不改为事务，全失败 → BATCH_PARTIAL_FAILURE；部分失败 → partial_success）
- B4：sealed 导入默认 update=true 覆盖（本函数仅处理 plain_folder，sealed 由 importer 处理）
- P0-2：明文 folder 走 enrich_script_fields，密封包走 sealed_package_importer（密封包路径由 PR-4 接入，本文件不处理）
- update_if_exists 默认 true
- 复用现有 script_save_orchestrator.enrich_script_fields

评审 P5B 改造（2026-08-28）：
- 移除 save_callback 抽象，save_folder 直接接 sensitive_service
- 内部用 save_folder_record(sensitive_service, rec, sealed=False) 单条入库
- 不再需要 update_if_exists 透传（评审 §7.2 决策）

方案A 改造（2026-09-02，需求 1.5.0技能工作流优化需求2.md）：
- 对 script 类 record 自动调用 parse_script_to_ext02 提取 args
- 检测到 has_dynamic_args 时记录 warning
- 返回结构扩展为 List[dict]，每条 dict 包含 diff_3 / info_type / ext01 / ext02 / ext05 / ext06 / warnings
- 同时保留 data.saved_diff3 向后兼容旧 Agent
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from mgc.service import script_save_orchestrator
from mgc.service.folder_parser_service import parse_folder
from mgc.service.record_save_helper import save_folder_record
from mgc.service.script_callgraph_service import analyze_callgraph, _detect_sealed_unsafe_patterns, UNSAFE_PATTERNS
from mgc.core.mgc_service.api_router import detect_script_platform, get_run_command

_logger = logging.getLogger(__name__)


def _strip_same_pkg_deps(
    ext05: str,
    callgraph_map: Dict[str, str],
    records: List[Dict[str, Any]],
) -> str:
    """Remove same-package basenames from ext05.

    Walks every script's ext08.calls.target_diff_3 to build a set of
    same-package module basenames (e.g. "helper", "config"), then drops
    any matching entry from the JSON-encoded ext05 list.

    Args:
        ext05: JSON array string (or "") as currently produced by
            script_dependency_service.
        callgraph_map: {diff_3: ext08_json_str} from analyze_callgraph.
        records: the same parse_folder record list (used as fallback to
            enumerate all diff_3 even if callgraph did not produce calls).

    Returns:
        Filtered JSON array string (or original "" if input is empty).
    """
    if not ext05:
        return ext05
    try:
        deps: List[str] = json.loads(ext05)
    except Exception:
        return ext05
    if not isinstance(deps, list):
        return ext05

    # Build same-pkg basenames from the call graph.
    same_pkg: Set[str] = set()
    for _d3, _ext08 in callgraph_map.items():
        if not _ext08:
            continue
        try:
            _obj = json.loads(_ext08)
        except Exception:
            continue
        for _call in _obj.get("calls", []) or []:
            _tgt = _call.get("target_diff_3", "")
            if not _tgt:
                continue
            same_pkg.add(Path(_tgt).stem)

    # Also include every script basename in the package (e.g. `加车数据`)
    # so imports referring to other scripts in the same pkg are also
    # filtered out.
    for _rec in records:
        _d3 = _rec.get("diff_3", "")
        if _d3:
            same_pkg.add(Path(_d3).stem)

    filtered = [d for d in deps if d not in same_pkg]
    if len(filtered) == len(deps):
        return ext05
    return json.dumps(filtered, ensure_ascii=False)


# 错误码占位（PR-1 范围内就地返回 dict，不引入新的错误码常量；正式错误码字典在 §八）
ERROR_MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"
ERROR_PATH_NOT_LOCAL = "PATH_NOT_LOCAL"
ERROR_BATCH_PARTIAL_FAILURE = "BATCH_PARTIAL_FAILURE"


def _error(code: str, message: str, **extra: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {"error": code, "message": message}
    data.update(extra)
    return {"code": 400, "msg": code, "hint": message, "data": data}


def _success(saved_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """全成功响应。

    saved_records: 每项含 diff_3 / info_type / ext01 / ext02 / ext05 / ext06 / warnings
    """
    diff3_list = [r["diff_3"] for r in saved_records]
    # Surface unsupported (mgc_run-incompatible) records in the hint so the
    # caller can review them. Detection happens during static analysis on save.
    unsupported = [r for r in saved_records
                  if r.get("ext10") == "unsupported"]
    base_hint = f"Folder saved. {len(saved_records)} record(s) processed."
    if unsupported:
        base_hint += (
            f" {len(unsupported)} record(s) are not fully supported by MGC's internal execution. "
            f"Call `mgc_skill` (MCP tool) for the supported / unsupported pattern list, "
            f"then refactor accordingly. Unsupported records: "
            + ", ".join(f"\"{r.get('diff_3', '')}\"" for r in unsupported)
            + "."
        )
    return {
        "code": 200,
        "msg": "OPERATION_SUCCESSFUL",
        "hint": base_hint,
        "data": {
            "saved": saved_records,
            "saved_diff3": diff3_list,  # 向后兼容：旧 Agent 仅读取 diff_3 列表
            "failed": [],
            "count": len(saved_records),
        },
    }


def _partial_success(
    saved_records: List[Dict[str, Any]],
    failed: List[Tuple[str, str]],
) -> Dict[str, Any]:
    diff3_list = [r["diff_3"] for r in saved_records]
    # Same unsupported-record surfacing as the all-success branch — partial
    # success callers also need to know which entries failed the mgc_run check.
    unsupported = [r for r in saved_records
                  if r.get("ext10") == "unsupported"]
    base_hint = f"Folder partially saved: {len(saved_records)} ok, {len(failed)} failed."
    if unsupported:
        base_hint += (
            f" {len(unsupported)} record(s) are not fully supported by MGC's internal execution. "
            f"Call `mgc_skill` (MCP tool) for the supported / unsupported pattern list, "
            f"then refactor accordingly. Unsupported records: "
            + ", ".join(f"\"{r.get('diff_3', '')}\"" for r in unsupported)
            + "."
        )
    return {
        "code": 200,
        "msg": "BATCH_PARTIAL_SUCCESS",
        "hint": base_hint,
        "data": {
            "saved": saved_records,
            "saved_diff3": diff3_list,
            "failed": [{"diff_3": d, "error": e} for d, e in failed],
            "count": len(saved_records),
        },
    }


def _success_with_hint(saved_records: List[Dict[str, Any]], hint: str, **extra: Any) -> Dict[str, Any]:
    diff3_list = [r["diff_3"] for r in saved_records]
    data: Dict[str, Any] = {
        "saved": saved_records,
        "saved_diff3": diff3_list,
        "failed": [],
        "count": len(saved_records),
    }
    data.update(extra)
    return {"code": 200, "msg": "OPERATION_SUCCESSFUL", "hint": hint, "data": data}


def _extract_ext02_for_script(rec: Dict[str, Any]) -> Tuple[str, List[str]]:
    """对 info_type='script' 的 record 调用 parse_script_to_ext02。

    Returns:
        (auto_ext02, warnings)
        - auto_ext02: 解析得到的 ext02（可能为 ""），仅在用户未传时使用
        - warnings: 本次解析产生的警告列表，可能含 "dynamic_args_detected" / "args_not_recognized" 等

    解析异常不会向外抛出，按"单文件失败不影响主流程"原则降级为空结果。

    PR-7: parse_script_to_ext02 升级为 6-tuple，新增 recognized/unrecognized 列表；
    warning 分类按 (has_dynamic_args, is_degraded, ext02 是否生成) 三态决定。
    """
    warnings: List[str] = []
    auto_ext02: str = ""
    try:
        from mgc.service.script_parser_service import parse_script_to_ext02
        (
            ext02,
            is_degraded,
            _degrade_reason,
            has_dynamic_args,
            _recognized_names,
            _unrecognized_names,
        ) = parse_script_to_ext02(rec.get("content", ""))
        if has_dynamic_args:
            # 检测到动态默认值（ast.Name/Call/Attribute 等非字面量）。
            # 即使 ext02 已生成（含部分静态 args），仍标记，让调用方决定是否手动调整。
            warnings.append("dynamic_args_detected")
        if ext02 is None:
            # 解析失败：无 add_argument / 全部 default 都是动态 → 需要用户手动录入
            if not has_dynamic_args:
                warnings.append("args_not_recognized")
        else:
            auto_ext02 = ext02
            if is_degraded and not has_dynamic_args:
                # 解析部分成功但部分写法未识别（如 action='extend'），
                # 与 dynamic_args_detected 互斥（同一 record 上二选一）
                warnings.append("args_partially_recognized")
    except Exception as parse_err:
        _logger.debug("parse_script_to_ext02 failed for %s: %s", rec.get("diff_3"), parse_err)
        warnings.append("args_not_recognized")
    return auto_ext02, warnings


def _compute_ext10(source_text: str) -> str:
    """Static-analysis result for mgc_run compatibility (string).

    Returns:
        "supported" | "unsupported"
    """
    if not source_text:
        return "supported"
    patterns = _detect_sealed_unsafe_patterns(source_text)
    if not patterns:
        return "supported"
    return "unsupported"


def _build_saved_entry(
    rec: Dict[str, Any],
    parse_warnings: List[str],
) -> Dict[str, Any]:
    """构造 data.saved 中的一条记录。"""
    # mgc_run compatibility — see _compute_ext10 for the supported/unsupported rules.
    ext10 = _compute_ext10(rec.get("ext_source_text", "") or "")
    return {
        "diff_3": rec.get("diff_3", ""),
        "info_type": rec.get("info_type", ""),
        "ext01": rec.get("ext01", "") or "",
        "ext02": rec.get("ext02", "") or "",
        "ext05": rec.get("ext05", "") or "",
        "ext06": rec.get("ext06", "") or "",
        "ext08": rec.get("ext08", "") or "",  # cross-script call graph (JSON)
        "ext10": ext10,  # mgc_run compatibility
        "warnings": parse_warnings,
    }


def save_folder(
    payload: Dict[str, Any],
    sensitive_service: Any,
) -> Dict[str, Any]:
    """PR-1 文件夹明文批量存入编排。

    Args:
        payload: 至少含 content / info_owner / diff_1
            - content: 本机文件夹绝对路径
            - info_owner: 必传
            - diff_1: 可选
            - update_if_exists: 可选，默认 True（仅作为业务信号保留，不透传给底层）
        sensitive_service: SensitiveService 实例（评审 P5B 替代 save_callback）
            内部调 save_folder_record(..., sealed=False)

    Returns:
        标准 API 响应 dict：
        - 全成功 / 全失败 / 部分失败分别走 _success / _error / _partial_success
        - 成功记录 data.saved 为 List[dict]（含 diff_3 / info_type / ext01/02/05/06 / warnings）
        - 同时保留 data.saved_diff3（List[str]）向后兼容
    """
    content = payload.get("content", "")
    info_owner = payload.get("info_owner", "")
    diff_1 = payload.get("diff_1", "")
    # update_if_exists 仅作业务信号保留；底层 save_folder_record 不透传该参数
    _ = bool(payload.get("update_if_exists", True))

    if not info_owner:
        return _error(ERROR_MISSING_REQUIRED_FIELDS, "info_owner required")

    if not content:
        return _error(ERROR_PATH_NOT_LOCAL, "content (folder path) is required")

    # PR-1 范围：仅处理明文文件夹（密封包 .mgc_file 路径由 PR-4 接入）
    # 此处保留扩展点：未来 sealed_package_importer 在 content.endswith(".mgc_file") 分支导入
    if content.endswith(".mgc_file"):
        return _error(
            "SEALED_PACKAGE_NOT_SUPPORTED_IN_PR1",
            "Sealed package import is handled by PR-4. PR-1 only handles plain folders.",
        )

    if not os.path.isdir(content):
        return _error(ERROR_PATH_NOT_LOCAL, f"content is not a local folder: {content}")

    records = parse_folder(content, info_owner, diff_1)

    saved_records: List[Dict[str, Any]] = []
    failed: List[Tuple[str, str]] = []
    # 临时字典，保留每条 record 的 parse warnings 供成功时打包返回
    parse_warnings_map: Dict[str, List[str]] = {}

    # === 1.5.1 Sprint 1.2 BEGIN ===
    # 静态 callgraph 分析（保存期），一次性对全部 record 计算，避免循环内重复 AST 扫描
    # 仅新保存触发；历史数据不重算（PM 化简决策）
    # sealed 包路径不动（Sprint 2/3 扩展 sealed_package_importer）
    _callgraph_map = analyze_callgraph(records)
    # === 1.5.1 Sprint 1.2 END ===

    for rec in records:
        try:
            if rec.get("info_type") == "script":
                # Run detect_script_platform before enrich_script_fields so that
                # ext05 (whose Python-family inference depends on ext01) is filled
                # correctly. Otherwise, when ext01 is empty, the dependency analyzer
                # cannot identify Python and ext05 stays blank.
                #
                # Pass file_suffix (from diff_3) so the heuristic priority is
                # shebang > extension > path pattern.
                if not rec.get("ext01"):
                    _suffix = Path(rec.get("diff_3", "")).suffix.lower() or None
                    platform = detect_script_platform(rec.get("content", ""), file_suffix=_suffix)
                    if platform:
                        rec["ext01"] = get_run_command(platform)

            # P0-2：仅 plain_folder 走 enrich_script_fields（fields_set=set() 让 auto-fill 生效）
            payload_for_orch = {
                "info_type": rec.get("info_type", ""),
                "content": rec.get("content", ""),
                "ext01": rec.get("ext01", ""),
            }
            script_save_orchestrator.enrich_script_fields(payload_for_orch, set())
            if rec.get("info_type") == "script":
                rec["ext05"] = payload_for_orch.get("ext05", "")
                rec["ext06"] = payload_for_orch.get("ext06", "")

                # === 1.5.1 Sprint 1.2: 回填 ext08（从预计算的 _callgraph_map 查表）===
                rec["ext08"] = _callgraph_map.get(rec["diff_3"], "")

                # Stash the source text so _compute_ext10 (and downstream callers) can
                # re-run the static analysis without re-reading the record body.
                rec["ext_source_text"] = rec.get("content", "") or ""
                # Compute ext10 and inject it into rec — the save helper
                # whitelists ext10 and persists it to the DB.
                rec["ext10"] = _compute_ext10(rec.get("content", "") or "")

                # Drop same-package basenames from ext05.
                # script_dependency_service._analyze_python only filters stdlib,
                # so `import helper` / `from config import` (same pkg) are
                # incorrectly listed as third-party deps. Use the ext08 call
                # graph (already computed above) to identify same-pkg modules
                # and remove them from ext05.
                rec["ext05"] = _strip_same_pkg_deps(
                    rec.get("ext05", ""), _callgraph_map, records,
                )

                # 方案A：自动提取 ext02（用户未传时填充解析结果，用户已传则保留）
                auto_ext02, parse_warnings = _extract_ext02_for_script(rec)
                if not rec.get("ext02"):
                    rec["ext02"] = auto_ext02
                parse_warnings_map[rec["diff_3"]] = parse_warnings

            # 评审 P5B：直调 save_folder_record(..., sealed=False)
            # sealed=False：白名单 ext01/ext02/ext05/ext06；ext03 不透传
            res = save_folder_record(sensitive_service, rec, sealed=False)
            code = res.get("code", 0)
            if 200 <= code < 300:
                warnings = parse_warnings_map.get(rec["diff_3"], [])
                saved_records.append(_build_saved_entry(rec, warnings))
            else:
                failed.append((rec["diff_3"], res.get("msg") or res.get("hint") or "save failed"))
        except Exception as e:
            _logger.warning("save_folder record %s failed: %s", rec.get("diff_3"), e)
            failed.append((rec.get("diff_3", ""), str(e)))

    if failed and not saved_records:
        return _error(
            ERROR_BATCH_PARTIAL_FAILURE,
            f"All {len(failed)} record(s) failed",
            **{
                "saved": saved_records,
                "failed": [{"diff_3": d, "error": e} for d, e in failed],
            },
        )
    if failed:
        return _partial_success(saved_records, failed)
    return _success(saved_records)