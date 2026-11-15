"""chain mode 主 readme 渲染器（1.6.0）。

主 readme 的职责（需求 L56）：告知密封方**不同文件夹对应的是哪个 node_pub**，
以及全部 warning 项。编排方据此按节点分发。

设计要点：
- 五个区块：任务身份 / 分发映射表 / 分发指引 / warning 区 / node_pub 指纹
- node_pub 用短指纹（SHA256 前 12 位 hex）做表格内标识——完整 PEM 有 30+ 行，
  表格不可读；完整 PEM 由编排方在 ext04 原文中自留
- 拆解序号只体现在子目录名与子包文件名（PM D3），落库 diff_2 各子包相同，
  因此映射表**不设 diff_2 列**

依赖：
- mgc.core.mgc_service.sealed_payload_parser：sanitize_path_segment / collapse_underscores
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence


def node_pub_fingerprint(node_pub: str) -> str:
    """计算 node_pub 短指纹，便于人工核对分发映射。

    Args:
        node_pub: 目标节点 PEM

    Returns:
        12 位 hex 字符串；node_pub 为空时返回 ""
    """
    raw = (node_pub or "").strip()
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _fmt_file_list(files: Sequence[str], limit: int = 12) -> str:
    """把文件清单渲染成单行文本，超长时截断并注明剩余数量。"""
    items = list(files)
    if not items:
        return "-"
    shown = items[:limit]
    text = ", ".join(f"`{f}`" for f in shown)
    if len(items) > limit:
        text += f" … (+{len(items) - limit} more)"
    return text


def render_chain_main_readme(
    info_owner: str,
    diff_2: str,
    source_node_pub: str,
    packages: List[Dict[str, Any]],
    warnings: Optional[List[Dict[str, Any]]] = None,
    unnamed_files: Optional[List[str]] = None,
    orphan_dependencies: Optional[List[Dict[str, Any]]] = None,
    duplicated_files: Optional[Dict[str, List[int]]] = None,
) -> str:
    """渲染 chain mode 主 readme。

    Args:
        info_owner: 主任务名（info_owner）
        diff_2: 主任务包名（diff_2，各子包共享同一值）
        source_node_pub: 编排方（密封方）node_pub
        packages: 子包清单，每项含
            package_index / dir_name / package_file_name / mgc_file_path /
            readme_path / node_pub_fingerprint / file_count / files
        warnings: 其它警告（形状同 mgc_run 的 data.warnings）
        unnamed_files: 未被任何 target 指名的文件列表
        orphan_dependencies: 依赖未指名的记录，形状
            [{node_index, diff_3, missing_dependency, kind}]
        duplicated_files: 同一 diff_3 被多个 target 指名的映射
            {diff_3: [target_index, ...]}

    Returns:
        完整 README.md 字符串（含尾部换行）
    """
    lines: List[str] = []
    lines.append("# Chain-mode sealed task package")
    lines.append("")
    lines.append("## Task identity")
    lines.append("")
    lines.append(f"- `info_owner`: `{info_owner}`")
    lines.append(f"- `diff_2`: `{diff_2}`")
    lines.append(f"- `source_node_pub`: `{source_node_pub}`")
    lines.append(
        "- All sub-packages share the same `info_owner` / `diff_2` — they belong to "
        "one main task."
    )
    lines.append(
        "- The split index (拆解序号) lives only in the folder / file names "
        "(`task_package_NN` / `<owner>__<diff_2>__NN.mgc_file`). It is for the "
        "**distributor** to tell packages apart; the receiving node does not rely "
        "on it."
    )
    lines.append("")

    # ---- 区块 2：分发映射表 ----
    lines.append("## Distribution mapping")
    lines.append("")
    lines.append(
        "Send **one** sub-folder to each node — the `.mgc_file` is the sealed "
        "package, the `README.md` is its instruction sheet."
    )
    lines.append("")
    lines.append("| # | sub-folder | package file | node_pub fingerprint | files |")
    lines.append("|---|---|---|---|---|")
    for pkg in packages:
        idx = pkg.get("package_index", "")
        dir_name = pkg.get("dir_name", "")
        file_name = pkg.get("package_file_name", "")
        fp = pkg.get("node_pub_fingerprint", "")
        count = pkg.get("file_count", 0)
        files = pkg.get("files", []) or []
        lines.append(
            f"| {idx} | `{dir_name}` | `{file_name}` | `{fp}` | {count} — "
            f"{_fmt_file_list(files)} |"
        )
    lines.append("")

    # ---- 区块 3：分发指引 ----
    lines.append("## Distribution instructions")
    lines.append("")
    lines.append(
        "1. Read the mapping table above and pick the sub-folder whose node_pub "
        "fingerprint matches the target node."
    )
    lines.append(
        "2. Send that sub-folder's `.mgc_file` and `README.md` to the target "
        "node. Both may be attached as A2A FileParts verbatim (raw bytes, no "
        "format conversion)."
    )
    lines.append(
        "3. The receiving node imports the package with "
        "`mgc_save_file(path=<the .mgc_file>)`; the remaining flow is unchanged."
    )
    lines.append(
        "4. The receiving node runs scripts with "
        "`mgc_run(info_owner=..., diff_2=..., diff_3=...)`. Scripts are decrypted "
        "in memory at execution time only."
    )
    lines.append("")

    # ---- 区块 4：warning 区 ----
    lines.append("## Warnings")
    lines.append("")
    has_warning = False

    if unnamed_files:
        has_warning = True
        lines.append(
            f"- **{len(unnamed_files)} file(s) were not named by any target** and "
            "are therefore NOT included in any sub-package:"
        )
        for f in unnamed_files:
            lines.append(f"  - `{f}`")
        lines.append("")

    if orphan_dependencies:
        has_warning = True
        lines.append(
            f"- **{len(orphan_dependencies)} dependency reference(s) point to files "
            "not granted to the same node.** MGC packaged everything exactly as the "
            "chain spec instructed — the scheduling decision belongs to the "
            "orchestrator:"
        )
        for item in orphan_dependencies:
            kind = item.get("kind", "") or "dependency"
            lines.append(
                f"  - sub-package #{item.get('node_index', '')}: "
                f"`{item.get('diff_3', '')}` → missing `{item.get('missing_dependency', '')}`"
                f" (kind: {kind})"
            )
        lines.append("")

    if duplicated_files:
        has_warning = True
        lines.append(
            "- **The same file was named by multiple nodes.** If two sub-packages "
            "end up on the same node, the later import overwrites the earlier one "
            "(same info_owner / diff_2 / diff_3). Please confirm the distribution "
            "scope:"
        )
        for f, idxs in sorted(duplicated_files.items()):
            lines.append(f"  - `{f}` → sub-packages {', '.join(str(i) for i in idxs)}")
        lines.append("")

    lines.append(
        "- **Non-script files inside each sub-package stay in plaintext.** Only "
        "`script` records are encrypted."
    )
    lines.append(
        "- **Follow-up packages of the same main task must reuse the same "
        f"`info_owner` (`{info_owner}`)** so the receiving node can group them "
        "under one main task."
    )
    lines.append(
        "- The **orchestrating node** must be able to run mgc 1.6.0+ to produce "
        "chain packages; **receiving nodes** only need mgc 1.5.4+."
    )

    if warnings:
        has_warning = True
        lines.append("")
        lines.append("### Additional warnings")
        lines.append("")
        for w in warnings:
            code = w.get("code", "") or ""
            message = w.get("message", "") or ""
            lines.append(f"- `{code}`: {message}")

    lines.append("")
    return "\n".join(lines)
