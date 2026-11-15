"""Record save helper for PR-5 folder / sealed import.

按评审 §7.3 + §7.4 抽公共适配层：
- normalise_record_content: 唯一 bytes→str 边界，严格 UTF-8 校验
- save_folder_record: 单条 record 入库，sealed=True/False 决定 ext 透传白名单

设计动机（评审 P5B）：
- 去除 backend_callback_adapter.make_save_callback 的无差别 base64 编码（B-01/B-02 根因）
  （历史命名：本文件原引用 pr5_integration.py，2026-08-28 改名 backend_callback_adapter.py）
- 统一 plain folder / sealed package 两条 save 路径
- 评审 §7.2 决策：不传 update_if_exists（save_code_sensitive 公开签名没有该参数，
  避免被收入 **ext_fields 后混入加密 payload）

依赖：
- sensitive_service.save_code_sensitive (mgc.core.mgc_service.sensitive_service)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

_logger = logging.getLogger(__name__)


def normalise_record_content(record: Dict[str, Any]) -> str:
    """record.content → str 的唯一边界。

    规则（评审 §7.3）：
    - str: 原样返回
    - bytes: 严格 decode("utf-8")，失败抛 ValueError
    - 其它类型: 失败

    不允许 errors="ignore" 或 base64 fallback——保证"密封脚本 ciphertext 是 base64
    文本，入库时保持单层 base64"成为可测试契约。

    Args:
        record: 标准化后的 record dict（含 content 字段）

    Returns:
        解码后的 str

    Raises:
        ValueError: content 类型不支持或 UTF-8 解码失败
    """
    content = record.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, bytes):
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(
                f"INVALID_MGC_FILE: record content not valid UTF-8: {e}"
            )
    raise ValueError(
        f"UNSUPPORTED_CONTENT_TYPE: {type(content).__name__}"
    )


def save_folder_record(
    sensitive_service: Any,
    record: Dict[str, Any],
    *,
    sealed: bool,
) -> Dict[str, Any]:
    """单条 record 入库（PR-5 folder/sealed 共用，评审 §7.4）。

    Args:
        sensitive_service: SensitiveService 实例
        record: 标准化后的 record dict
            - info_type / info_owner / diff_1 / diff_2 / diff_3 / content
            - 可选 ext01 / ext02 / ext03 / ext05 / ext06 / ext07
        sealed: True=sealed import（白名单 ext01/ext02/ext03/ext05/ext06/ext07/ext08）
                False=plain folder（白名单 ext01/ext02/ext05/ext06/ext08；ext03 不透传）

    Returns:
        API 响应 dict：{"code": 2xx/4xx/5xx, "msg": ..., "data": {"diff_3": ..., "ok": bool}}

    Notes:
        - 不传 update_if_exists（评审 §7.2 决策）
        - sealed=True 时绝不重新解析脚本字段（避免覆盖 manifest 元数据）
    """
    diff_3 = record.get("diff_3", "")

    # 1. UTF-8 规范化
    try:
        content_str = normalise_record_content(record)
    except ValueError as e:
        return {"code": 400, "msg": str(e), "data": {"diff_3": diff_3, "ok": False}}

    # 2. ext 字段白名单透传（评审 §7.4）
    # 1.5.1 Sprint 1：ext08 加入白名单
    #   - sealed=True：sealed 包导入时直接落库（ext08 由 sealed manifest 携带，不重算）
    #   - sealed=False：plain folder 保存期调用 callgraph_service.analyze_callgraph 生成 ext08
    if sealed:
        # Sealed records persist link-authorization metadata (ext07/ext09)
        # and the sealed payload key (ext03) alongside the runtime fields.
        ext_keys = ("ext01", "ext02", "ext03", "ext05", "ext06", "ext07", "ext08", "ext09", "ext10")
    else:
        # Plain records persist only the runtime fields needed for
        # cross-script call routing and mgc_run compatibility checking.
        ext_keys = ("ext01", "ext02", "ext05", "ext06", "ext08", "ext10")
    ext_kwargs: Dict[str, str] = {}
    for k in ext_keys:
        v = record.get(k, "")
        if v:
            ext_kwargs[k] = v

    # 3. 调 sensitive_service.save_code_sensitive（不传 update_if_exists）
    try:
        ok = sensitive_service.save_code_sensitive(
            info_type=record["info_type"],
            info_owner=record.get("info_owner", ""),
            diff_1=record.get("diff_1") or None,
            diff_2=record.get("diff_2") or None,
            diff_3=diff_3 or None,
            content=content_str,
            **ext_kwargs,
        )
    except Exception as e:
        _logger.warning("save_folder_record failed: %s/%s: %s",
                        record.get("info_owner", ""), diff_3, e)
        return {
            "code": 500,
            "msg": f"SAVE_FAILED: {type(e).__name__}: {e}",
            "data": {"diff_3": diff_3, "ok": False},
        }

    if ok:
        return {
            "code": 200,
            "msg": "OPERATION_SUCCESSFUL",
            "data": {"diff_3": diff_3, "ok": True},
        }
    return {
        "code": 500,
        "msg": "SAVE_RETURNED_FALSE",
        "data": {"diff_3": diff_3, "ok": False},
    }