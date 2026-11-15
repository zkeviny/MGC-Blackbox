"""Backend callback adapter (formerly mgc.service.pr5_integration).

按 [技能授权需求实施计划.md §五 §六](../../document/1.5需求文档/1.5.0需求计划/技能授权需求实施计划.md)
为 7 个新模块（folder_parser / folder_save_orchestrator / package_exporter /
sealed_package_exporter / sealed_package_importer / mgc_file_format /
usk3_yaml_writer）提供统一接入点。

本文件**不触碰** api_router / sensitive_service / mcp_server / SealService 内部实现，
仅通过依赖注入把"真实存储 / 查询 / 密封能力"封装为新模块所需的回调形式。

设计动机：
- 测试：新模块已通过 mock 单元测，本文件保证 mock → 真实实现的桥接可单测
- 解耦：新模块对外接口稳定，未来后端存储更换只改本文件
- 渐进接入：PR-5 仅交付桥接层与单元测；api_router / mcp_server 真正调用本文件留待 PR-6 之后端到端联调

历史命名：本文件原名 pr5_integration.py，2026-08-28 按职责重命名为 backend_callback_adapter.py
（PR-5 桥接语义保留，模块内函数名 make_query_callback / make_seal_callback /
make_self_node_pub_getter 保持不变）。备份：backups/2026-08-28_rename_pr5_integration/。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

_logger = logging.getLogger(__name__)


def make_query_callback(
    sensitive_service: Any,
    info_type: str = "file",
) -> Callable[[str, str, str], List[dict]]:
    """生成 query_callback：(info_owner, diff_2, diff_1) -> list[dict]。

    适配 package_exporter / sealed_package_exporter 的批量查询。
    字段：info_type / info_owner / diff_1 / diff_2 / diff_3 / content / ext01-07

    实现要点：
    - 第一步用 get_info_list 拿 records metadata（无 content 解密）
    - 第二步逐条调 get_sensitive 拿解密后的 plain_text（避免把密文写出去）

    Args:
        sensitive_service: 真实 SensitiveService 实例
        info_type: 查询类型，默认 "file"（PR-2/3b 都查 folder 类）

    Returns:
        query_callback 闭包
    """
    def _callback(info_owner: str, diff_2: str, diff_1: str) -> List[dict]:
        try:
            raw_list = sensitive_service.get_info_list(
                info_type=info_type,
                info_owner=info_owner,
                diff_1=diff_1 or None,
                diff_2=diff_2 or None,
            )
        except Exception as e:
            _logger.warning("query_callback list failed: %s", e)
            return []

        results: List[dict] = []
        for row in raw_list or []:
            r_type = row.get("info_type", "")
            r_owner = row.get("info_owner", "")
            r_diff1 = row.get("diff_1") or ""
            r_diff2 = row.get("diff_2") or ""
            r_diff3 = row.get("diff_3") or ""

            # 用 get_sensitive 拿解密后的明文（不能直接用 info_plaintext，那是密文）
            try:
                sensitive_rows = sensitive_service.get_sensitive(
                    info_type=r_type,
                    info_owner=r_owner,
                    diff_1=r_diff1 or None,
                    diff_2=r_diff2 or None,
                    diff_3=r_diff3 or None,
                )
            except Exception as e:
                _logger.warning("query_callback get_sensitive failed for %s/%s: %s",
                                r_owner, r_diff3, e)
                continue

            if not sensitive_rows:
                continue
            s = sensitive_rows[0]
            results.append({
                "info_type": r_type,
                "info_owner": r_owner,
                "diff_1": r_diff1,
                "diff_2": r_diff2,
                "diff_3": r_diff3,
                "content": s.get("plain_text", "") or "",
                "ext01": s.get("ext01", "") or "",
                "ext02": s.get("ext02", "") or "",
                "ext03": s.get("ext03", "") or "",
                "ext05": s.get("ext05", "") or "",
                "ext06": s.get("ext06", "") or "",
                "ext07": s.get("ext07", "") or "",
                # 1.5.1 Sprint 1：透传 ext08（callgraph JSON），让密封包导入时保留依赖图
                "ext08": s.get("ext08", "") or "",
            })
        return results

    return _callback


def make_seal_callback(seal_service: Any) -> Callable[..., Dict[str, Any]]:
    """生成 seal_callback：1.5.4+ 期望 (content, ext04, mode, source_node_pub)。

    适配 sealed_package_exporter 的逐条 seal_script 调用。

    适配说明：
    - 真实 SealService.seal_script(content, out_node_pub, mode, source_node_pub) -> {content, ext03, ext07, ext09}
    - 本适配器把 ciphertext str → bytes 以满足 sealed_package_exporter 写入 zip 需求

    Args:
        seal_service: 真实 SealService 实例（含 seal_script 方法）

    Returns:
        seal_callback 闭包
    """
    import inspect
    _seal_sig = None
    try:
        _seal_sig = inspect.signature(seal_service.seal_script)
    except Exception:
        pass

    def _callback(
        content: str,
        ext04: str,
        mode: str = "p2p mode",
        source_node_pub: str = "",
    ) -> Dict[str, Any]:
        # 1.5.4：透传 4 参数；老 SealService（2 参数）走 fallback
        try:
            if _seal_sig and len(_seal_sig.parameters) >= 4:
                result = seal_service.seal_script(
                    content, ext04, mode, source_node_pub,
                )
            else:
                result = seal_service.seal_script(content, ext04)
        except TypeError:
            # 老 SealService 不接受 4 参数时降级到 2 参数
            result = seal_service.seal_script(content, ext04)

        ct = result.get("content", "") or result.get("ciphertext", "")
        ext03 = result.get("ext03", "") or result.get("ext_03", "")
        ext07 = result.get("ext07", "") or result.get("ext_07", "")
        ext09 = result.get("ext09", "") or result.get("ext_09", "")
        if isinstance(ct, str):
            ct_bytes = ct.encode("utf-8")
        else:
            ct_bytes = bytes(ct)
        return {
            "ciphertext": ct_bytes,
            "ext03": ext03,
            # 1.5.4：把 ext07 / ext09 透传出来，让 exporter 写入 manifest
            "ext07": ext07,
            "ext09": ext09,
        }

    return _callback


def make_self_node_pub_getter(node_key_service: Any) -> Callable[[], str]:
    """生成本节点 node_pub 取值器 () -> str（D1 明文来源标识）。

    P0-2 修复（2026-08-28）：
    - NodeKeyService 实际公开方法为 get_public_key()，不存在 get_self_node_pub()
    - 原调用会导致 AttributeError → 退回空串 → MGCFILE.json 顶层 source_node_pub
      与每条 record.ext07 一直为空，评审 D1 来源标识失效
    - 改为 get_public_key()，与 NodeKeyService 公开签名一致
    """
    def _getter() -> str:
        try:
            return node_key_service.get_public_key() if node_key_service else ""
        except Exception as e:
            _logger.warning("get_self_node_pub (via get_public_key) failed: %s", e)
            return ""
    return _getter
