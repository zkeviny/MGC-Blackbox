"""usk/3.0 yaml writer for sealed package README.

按 [技能授权需求实施计划.md §四 4.7](../../document/1.5需求文档/1.5.0需求计划/技能授权需求实施计划.md)
生成 usk/3.0 yaml + 文档内容。

关键决策：
- D1：yaml header 加 source_node_pub 明文字段（来源标识，未做签名验证，非防盗签名）；
- D1：正文显式 Security Notice 警示，避免用户误解；
- B3：description 不加密（仅元数据）；
- P0-5：yaml 文件清单透出 ext05/ext06/ext07 关键元数据；
- 按需求 §2.4.2.3 L130 yaml 模板结构。

依赖：
- 无（纯文本生成，不引入 PyYAML 等依赖）
- 与 mgc.utils.mgc_file_format 配合：传入 records 通常是 build_mgcfile_json 输出
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional


# ---- 默认模板 ----
DEFAULT_REQUIRED_MGC_TOOLS = ["mgc_get", "mgc_run"]

SECURITY_NOTICE = """
## ⚠️ Security Notice

`source_node_pub` and `ext07` in this README are stored in **plaintext** as a
source identifier only. Verify the `source_node_pub` against a trusted
channel from the package author before importing; do not rely on
point-to-point transfers from untrusted third parties. MGC cannot guarantee
the trustworthiness of a sealed script's author — once unsealed on a node,
its behavior is solely that author's responsibility.
"""

# 1.5.4：精简为一行兼容性提示——只告诉被授权方"1.5.4+ 才能解"。
CAPABILITY_NOTICE = """
## Compatibility

This package requires **mgc 1.5.4+** to import and run. Receivers running
older versions cannot unseal it (link-authorization errors). Install
`mgc-blackbox>=1.5.4` before importing.
"""

USAGE_SECTION_HEAD = """
## Usage

This package contains a `.mgc_file` (zip archive) with encrypted scripts and
plaintext metadata. Import it into your local MGC Blackbox via `mgc_save_file`,
then use `mgc_get` / `mgc_run` to access each file.

### Import the package

Use the **exact `mgc_save` call below** with the four tuple fields
hard-coded — deviating from these values will break subsequent `mgc_get` /
`mgc_run` lookups (the package will be stored under a different identity):

```
"""


USAGE_SECTION_TAIL = """

```

The four tuple fields (`info_owner` / `diff_1` / `diff_2`) identify this
sealed folder in the local MGC store; `info_type="file"` is fixed at import
time because the package itself is a file archive — individual records
inside it carry their own `info_type` (see `files:` above).

### Prerequisites

Before running the script(s), confirm:

- **mgc blackbox version**: install MGC Blackbox ≥ `suggest_mgc_blackbox_version`
  in the yaml header (matches the author's `mgc_protocol_version`); e.g.
  `pip install --upgrade mgc-blackbox>=1.5.4`. Since mgc 1.5.4, every sealed
  package (p2p or free mode) requires the receiver to run ≥ 1.5.4 to unseal
  — older versions will fail with link-authorization errors.
- **dependencies** (see yaml header) are installed on the target node; if a
  required package is missing, install it first (or contact the package
  author for a version that bundles the dependency)
- **platforms** (see yaml header) include your current OS; otherwise contact
  the package author for a variant that supports your platform

### Locating the imported records

This package was sealed under `info_owner` `<PACKAGE_OWNER>`.

Records inside a sealed PACKAGE keep that owner after import — the
`info_owner` you pass to `mgc_save_file` applies to the package group
(the folder triple) only, NOT to the individual records. This is required
for cross-script sealed execution: the 5+1 check demands that the caller
and the target script share one `info_owner`, so per-record owners must
stay as recorded when the package was sealed.

Locate the imported files with the owner recorded in this package:

- `mgc_find(info_owner="<PACKAGE_OWNER>", diff_2="<DIFF_2>")`

Do NOT look them up with a different owner — a sealed package always keeps
its original per-record owner.

### Access the files

After import, locate files via `mgc_find`, read individual content via
`mgc_get`, and execute scripts via `mgc_run`:

- `mgc_find` — locate files in the imported folder (fuzzy search by
  `info_owner` / `diff_2` / `diff_3`; returns metadata only)
- `mgc_get` — read a single file's content (e.g. `SKILL.md`, `config.json`,
  `manifest.json`)
- `mgc_run` — execute a sealed script (MGC will unseal the ciphertext
  in-memory using the wrapped AES key, then run the script with `ext01` as
  the launch command)

Files in the package:

- Non-script files (e.g. `SKILL.md`, `config.json`, `manifest.json`) are
  stored **in plaintext** — read them directly via `mgc_get`.
- Script files are stored as ciphertext and decrypted in-memory at
  execution time. `mgc_run` handles all decryption — script source is
  NEVER written to disk on the receiving node, and you do not need to
  (or be able to) decrypt manually.

After installing MGC, save this README.md into the agent's skill manager
(agent-managed, not MGC's boundary) so the agent can identify the package
(identity above), call the entry script (see `files:` below), and locate
individual files (via `mgc_find`).

### API reference

For sandboxed agents or external scripts that cannot use MCP tools, MGC
also exposes a local REST API. See the local `skill_spec.md` bundled with
your MGC Blackbox installation for endpoint details.
"""


# 1.5.4 PM Q6：Free Mode Installation 段；render() 在 mode=="free mode" 时选择性注入。
# p2p 包不渲染该段。
FREE_MODE_INSTALLATION_NOTICE = """

### Free Mode Installation

This package was sealed in **free mode** (see `seal_mode: "free mode"` in
the yaml header). Any mgc 1.5.4+ node can import it and run the scripts —
no specific recipient is required, and no prior key exchange is needed.

Install `mgc-blackbox>=1.5.4` before importing if you have not done so
already.
"""


def usage_section(info_owner: str, diff_1: str, diff_2: str, file_name: str) -> str:
    """渲染 ## Usage 段，注入当前密封包的 info_owner / diff_1 / diff_2 / file_name。

    1.5.0 usage_revamp：占位符直接替换为实际值，避免 agent 误传不一致的字段。
    1.5.1 task1：示例代码改为 ``mgc_save_file(path=...)``（强调 path → content 自动填充），
    并在示例下方追加 ``mgc_find`` 调用示例（用实际 owner/diff_2 注入），便于 agent
    存入后立即验证可查。
    """
    # 1.5.1 task1：示例从 mgc_save(...) 迁移到 mgc_save_file(path=...)。
    # agent 只需传入 path，MGC 会自动填充 content 字段，无需手动读取文件内容。
    save_file_code = (
        'mgc_save_file(\n'
        f'    path="/path/to/{file_name}",\n'
        f'    info_owner="{info_owner}",\n'
        f'    diff_1="{diff_1}",\n'
        f'    diff_2="{diff_2}",\n'
        ')'
    )

    # 1.5.1 task1：mgc_find 调用示例，用同一 owner/diff_2 让 agent 立刻可以验证包已存入。
    find_example_code = (
        'mgc_find(\n'
        f'    info_owner="{info_owner}",\n'
        f'    diff_2="{diff_2}",\n'
        ')'
    )

    # 构造完整的 usage 段：USAGE_SECTION_HEAD 提供 ``` 代码块开头；示例 + 注释 +
    # find 示例 + USAGE_SECTION_TAIL 提供 ``` 闭合 + 后续说明。
    # 直接拼接到 USAGE_SECTION_HEAD 末尾（``` 之后）和 USAGE_SECTION_TAIL 开头（``` 之前）之间。
    head = USAGE_SECTION_HEAD
    tail = USAGE_SECTION_TAIL

    # 取出 head 中 ``` 之后的引导语，拼接 save_file 示例 + mgc_find 示例，再接 tail。
    # head 与 tail 都以换行结尾且 tail 以换行开头 ```，因此直接拼接即可。
    inner = (
        save_file_code
        + "\n```\n\n"
        + "Pass only `path` to `mgc_save_file` — MGC will read the file content\n"
        + "and auto-fill the `content` field for you. The four tuple fields\n"
        + "(`info_owner` / `diff_1` / `diff_2`) identify this sealed folder in the\n"
        + "local MGC store; `info_type` is fixed at import time because the package\n"
        + "itself is a file archive — individual records inside it carry their own\n"
        + "`info_type` (see `files:` above). Deviating from these values will break\n"
        + "subsequent `mgc_get` / `mgc_run` lookups (the package will be stored\n"
        + "under a different identity).\n\n"
        + "### Verify the import\n\n"
        + "After `mgc_save_file` succeeds, verify the package is queryable with\n"
        + "`mgc_find` using the same `info_owner` and `diff_2`:\n\n"
        + "```\n"
        + find_example_code
        + "\n```\n\n"
        + "If `mgc_find` returns the expected files in this package, the import is\n"
        + "successful. If it returns nothing, double-check the four tuple fields\n"
        + "above — even a single character mismatch will store the package under a\n"
        + "different identity.\n\n"
        + "### Prerequisites\n\n"
    )

    # 把 tail 中 "### Prerequisites" 之前的"```\n\nThe four tuple fields..."段去掉，
    # 因为本函数已经在 inner 中重写了 Prerequisites 之前的引导语。
    # 简化做法：直接截断 tail 到 "### Prerequisites" 之后继续。
    prereq_marker = "### Prerequisites"
    if prereq_marker in tail:
        tail_after_prereq = tail.split(prereq_marker, 1)[1]
    else:
        tail_after_prereq = tail

    # 1.6.0：把 "Locating the imported records" 段里的占位符替换成实际值。
    # 受密文保护的包内记录级 owner 原样保留（跨脚本 5+1 校验的硬前提），
    # 接收方必须用包内 owner 查，这里把真实值直接写进 README。
    tail_after_prereq = tail_after_prereq.replace(
        "<PACKAGE_OWNER>", info_owner
    ).replace("<DIFF_2>", diff_2)

    return head + inner + tail_after_prereq


def _str_value(v: Any) -> str:
    """把任意值安全转成 yaml 标量字符串。

    规则：
    - None / 空 → ""
    - bool → "true" / "false"
    - 其它 → str(v)
    """
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return str(v)


def _yaml_quote_if_needed(v: str) -> str:
    """如果值含 yaml 特殊字符或为空，用双引号包。"""
    if v == "":
        return '""'
    # 含特殊字符或前导特殊字符则双引号
    special_chars = set(":#@&*!|>'\"%`,[]{}?")
    if any(c in special_chars for c in v) or v[0] in ("-", " ", "\t") or v[-1] == " ":
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return v


def _collect_dependencies(records: List[Dict[str, Any]]) -> List[str]:
    """聚合所有 record 的 ext05（依赖项），去重后排序。

    ext05 格式约定为 JSON 数组字符串（如 ["config","helper","pandas","pymysql"]）；
    兼容旧的 CSV 格式（无方括号时按逗号拆分），所有失败或非 list 形态直接跳过。
    返回按字母升序的去重列表。
    """
    deps: set = set()
    for r in records:
        ext05 = _str_value(r.get("ext05", ""))
        if not ext05:
            continue
        # 优先按 JSON 数组解析（当前实际格式）
        tokens: List[str] = []
        try:
            parsed = json.loads(ext05)
            if isinstance(parsed, list):
                tokens = [t for t in parsed if isinstance(t, str) and t]
            elif isinstance(parsed, str):
                # 单字符串也认作一项依赖
                tokens = [parsed]
        except (ValueError, TypeError):
            # 回退：旧版 CSV "pkg1,pkg2" 格式（无方括号）
            tokens = [t.strip() for t in ext05.split(",") if t.strip()]
        for t in tokens:
            deps.add(t)
    return sorted(deps)


def _collect_platforms(records: List[Dict[str, Any]]) -> List[str]:
    """聚合所有 record 的 ext06（可运行平台），去重后按固定顺序返回。

    ext06 约定为 JSON 数组字符串，如 ["windows","macos","linux"]；
    返回顺序与 MGC 默认 scheme 一致：macos > linux > windows。
    """
    order = ["macos", "linux", "windows"]
    seen: set = set()
    for r in records:
        ext06 = _str_value(r.get("ext06", ""))
        if not ext06:
            continue
        try:
            arr = json.loads(ext06)
        except (ValueError, TypeError):
            continue
        if not isinstance(arr, list):
            continue
        for p in arr:
            if isinstance(p, str) and p:
                seen.add(p)
    return [p for p in order if p in seen] + sorted(seen - set(order))


def _format_yaml_list(values: List[str]) -> str:
    """把 list 格式化成 YAML flow 数组字符串，例如 [a, b, c]。"""
    return "[" + ", ".join(values) + "]"


def _record_yaml_block(rec: Dict[str, Any]) -> List[str]:
    """把单条 record 渲染成 yaml 缩进块（3 个空格对齐 files 下）。

    1.5.0 readme_revamp：精简为只输出 name + info_type + diff_3，
    去除 info_owner / diff_1 / diff_2 / ext01-07 等冗余字段，保持 README
    对 agent 简洁可读。MGCFILE.json 仍然保留全字段，不受此影响。
    """
    lines: List[str] = []

    # name 使用 diff_3 basename（按实施计划 §4.7）
    diff_3 = rec.get("diff_3", "")
    name = diff_3.rsplit("/", 1)[-1] if diff_3 else ""
    info_type = rec.get("info_type", "")

    lines.append(f"   - name: {_yaml_quote_if_needed(name)}")
    lines.append(f"     info_type: {_yaml_quote_if_needed(_str_value(info_type))}")
    lines.append(f"     diff_3: {_yaml_quote_if_needed(_str_value(diff_3))}")
    return lines


def render(
    records: Iterable[Dict[str, Any]],
    source_node_pub: str = "",
    pkg_name: Optional[str] = None,
    description: Optional[str] = None,
    required_mgc_tools: Optional[List[str]] = None,
    include_security_notice: bool = True,
    include_usage: bool = True,
    mode: str = "p2p mode",
    package_file_name: str = "",
) -> str:
    """渲染 usk/3.0 yaml + 文档内容。

    Args:
        records: 已 validate_mgcfile_json + build_mgcfile_json 标准化的 record dict 列表
        source_node_pub: D1 明文来源标识
        pkg_name: 包名（默认取第一条 record 的 "{info_owner}-{diff_2}"）
        description: 包描述（默认 "Sealed package for {diff_2}."）
        required_mgc_tools: 必填 mgc 工具列表（默认 ["mgc_get", "mgc_run"]）
        include_security_notice: 是否包含 D1 Security Notice（默认 True）
        include_usage: 是否包含 Usage 章节（默认 True）
        mode: 1.5.4 seal policy；"free mode" 时额外渲染 Free Mode Installation 段
        package_file_name: 1.6.0 chain mode 子包文件名（如 "<owner>__<diff_2>__01.mgc_file"）。
            为空时 Usage 段回退到默认的 "{diff_2}.mgc_file"。

    Returns:
        完整 README.md 字符串（含尾部换行）
    """
    materialized = list(records)
    if not materialized:
        # 空 records：输出仅含安全提示的最小 README
        return (
            "---\n"
            f"source_node_pub: {_yaml_quote_if_needed(_str_value(source_node_pub))}  # plaintext, NOT signed\n"
            "files: []\n"
            "---\n"
            + (SECURITY_NOTICE if include_security_notice else "")
            + (usage_section("", "", "", "<file>.mgc_file") if include_usage else "")
        )

    first = materialized[0]
    owner = _str_value(first.get("info_owner", ""))
    diff_1 = _str_value(first.get("diff_1", ""))
    diff_2 = _str_value(first.get("diff_2", ""))

    # 1.6.0：name 去重——owner 与 diff_2 相同时不重复拼接
    #（PM 反馈：owner == diff_2 == "QD运营技能集合full" 时得到
    #  "QD运营技能集合full-QD运营技能集合full"，冗余难读）
    if pkg_name is not None:
        name = pkg_name
    elif owner and diff_2:
        name = owner if owner == diff_2 else f"{owner}-{diff_2}"
    elif owner or diff_2:
        name = owner or diff_2
    else:
        name = "sealed-package"
    # 1.6.0：chain mode 子包文件名（"<owner>__<diff_2>__NN.mgc_file"）——
    # 用于 description 与 Usage 段，避免出现与实际文件名不符的占位名。
    actual_pkg_file = package_file_name or f"{diff_2}.mgc_file"
    # 1.5.4：description 按 mode 分文案（p2p mode 与 free mode 权限模型不同）
    if description is not None:
        desc = description
    elif mode == "free mode":
        desc = (
            f"Free-mode sealed package for '{diff_2}'. Import the .mgc_file into "
            f"MGC Blackbox via mgc_save_file to view and use each file with "
            f"mgc_get / mgc_run. You may also save this README.md into your "
            f"agent's skill manager for later reuse. Any mgc 1.5.4+ node can "
            f"import and run this package, but the script source code is NEVER "
            f"visible on the receiving node — it is decrypted only in-memory at "
            f"execution time. Do not redistribute this package to nodes "
            f"running mgc below 1.5.4."
        )
    elif mode == "chain mode":
        desc = (
            f"Chain-mode sealed task package '{actual_pkg_file}' for this node. "
            f"Import {actual_pkg_file} into MGC Blackbox via mgc_save_file "
            f"to view and use each file with mgc_get / mgc_run. Scripts in this "
            f"package are sealed with AES + RSA against THIS node's node_pub — "
            f"only the node holding the matching node_priv can unseal them. The "
            f"script source code is NEVER visible on disk; it is decrypted only "
            f"in-memory at execution time. Non-script files in this package stay "
            f"in plaintext. Do not redistribute this package."
        )
    else:  # p2p mode (default)
        desc = (
            f"P2P-mode sealed package for '{diff_2}'. Import the .mgc_file into "
            f"MGC Blackbox via mgc_save_file to view and use each file with "
            f"mgc_get / mgc_run. You may also save this README.md into your "
            f"agent's skill manager for later reuse. Scripts are sealed with "
            f"AES + RSA — only the node whose node_priv matches the ext04 "
            f"public key can unseal them. The script source code is NEVER "
            f"visible on disk; it is decrypted only in-memory at execution time. "
            f"Do not redistribute this package to unauthorized nodes."
        )
    tools = required_mgc_tools if required_mgc_tools is not None else list(DEFAULT_REQUIRED_MGC_TOOLS)

    # ---- 1.5.0 schema_prereq：从 records 聚合依赖 + 平台去重集合 ----
    dependencies = _collect_dependencies(materialized)
    platforms = _collect_platforms(materialized)

    # ---- YAML header ----
    # P0-1 修复（2026-08-30）：头部显式声明 usk_version: "3.0" + format: mgc-sealed-package，
    # 让消费者一眼识别这是 usk/3.0 标准的 MGC 密封包描述文件。
    lines: List[str] = ["---"]
    lines.append('usk_version: "3.0"')
    lines.append('format: "mgc-sealed-package"')
    # 1.6.0：协议版本升级到 1.6.0（chain mode 拆包分发 + 机器可读分发索引）
    # 加密/封装格式本身自 1.5.4 起未变，接收端 1.5.4+ 仍可解
    lines.append('mgc_protocol_version: "1.6.0"')
    # 1.5.4：yaml 头显式声明 seal_mode，便于 reader / agent 一眼识别
    lines.append(f'seal_mode: "{mode}"')
    lines.append(f"name: {_yaml_quote_if_needed(name)}")
    lines.append(f"description: {_yaml_quote_if_needed(desc)}")
    lines.append(
        f"source_node_pub: {_yaml_quote_if_needed(_str_value(source_node_pub))}  # plaintext, NOT signed, NOT anti-tamper"
    )
    lines.append("required_mgc_tools:")
    for tool in tools:
        lines.append(f"  - {_yaml_quote_if_needed(tool)}")
    # 1.5.0 schema_prereq：依赖 + 平台摘要（去重聚合自 records 的 ext05 / ext06）
    lines.append(f"dependencies: {_format_yaml_list(dependencies) if dependencies else '[]'}")
    lines.append(f"platforms: {_format_yaml_list(platforms) if platforms else '[]'}")
    # 1.5.4 mgc_version_dep：所有 1.5.4 生成的包（含 link authorization）都需要 1.5.4+ 才能解
    # 1.6.0 保持 1.5.4+ 不变：chain mode 只改变「打包/分发侧」，加密与封装格式未变，
    # 接收端 1.5.4+ 仍可解（V-B5 test_chain_mode_compat_154 已验证）
    lines.append('suggest_mgc_blackbox_version: "1.5.4+"')
    lines.append("files:")
    for rec in materialized:
        lines.extend(_record_yaml_block(rec))
    lines.append("---")

    # ---- 文档正文 ----
    # 1.5.0 readme_revamp：正文顺序改为 Description -> Usage -> Security Notice。
    # Security Notice 移至最下方，因为 PM 决策其属于"读者警示"而非"导入指引"。
    body_parts: List[str] = [
        # Description 段：与 yaml.description 文案一致，便于读者一目了然
        "",
        f"## Description\n\n{desc}",
        "",
    ]
    if include_usage:
        # 1.5.0 usage_revamp：Usage 段注入实际字段值（owner / diff_1 / diff_2），
        # 文件名默认取 {diff_2}.mgc_file，与 sealed_package_exporter 输出一致。
        body_parts.append(usage_section(owner, diff_1, diff_2, actual_pkg_file))
    # 1.5.4 PM Q6：仅 free mode 包渲染 Free Mode Installation 段
    if mode == "free mode":
        body_parts.append(FREE_MODE_INSTALLATION_NOTICE)
    # 1.5.1+ Capability Notice：每个版本都注入一段，说明该版本的特性 + 低版本 receiver
    # 会遇到的行为降级。放在 Usage 之后、Security Notice 之前 —— reader 先看到能力，
    # 再看到安全提示。
    body_parts.append(CAPABILITY_NOTICE)
    if include_security_notice:
        body_parts.append(SECURITY_NOTICE)

    return "\n".join(lines) + "\n" + "\n".join(body_parts)