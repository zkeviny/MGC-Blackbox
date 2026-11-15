"""
Provides MGC Blackbox MCP Server implementation.
Calls REST API via HTTP to provide sensitive information services.
Supports auto-start MGC REST API (if not running).
"""

import json
import sys
import os
import time
import webbrowser
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import requests

# === Encoding fix for Windows + stdio MCP clients ===
# Force PYTHONIOENCODING=utf-8 to avoid surrogate issues with non-ASCII text
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Reconfigure stdin/stdout/stderr to UTF-8 to prevent encoding errors on Windows.
# Use 'replace' for stdout/stderr to survive any unexpected surrogate input;
# use 'strict' for stdin to fail fast on malformed input.
try:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # Some embedded Python runtimes (e.g. older IDEs) may not support reconfigure
    pass
# === End encoding fix ===

from mgc.config.mcp_config import (
    MGC_API_BASE_URL,
    MGC_WEBUI_URL,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION,
    MCP_PROTOCOL_VERSION,
    MCP_STARTUP_TIMEOUT,
    MCP_STARTUP_CHECK_INTERVAL,
)
from mgc.config.path_config import SKILLS_DIR


def _ensure_mcp_config():
    """Ensures mcp_config.json exists, regenerate on each startup (avoid stale config)"""
    config_file = SKILLS_DIR / "mcp_config.json"

    config_data = {
        "mcpServers": {
            MCP_SERVER_NAME: {
                "command": "mgc",
                "args": ["--mcp"],
                # Inject PYTHONIOENCODING=utf-8 for Windows stdio MCP clients
                # (Codex/Cursor/TRAE) to avoid surrogate encoding errors.
                "env": {
                    "PYTHONIOENCODING": "utf-8"
                }
            }
        }
    }
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config_data, indent=2, ensure_ascii=False))


# 1.5.4 phase6 friction fix: 调用方常把 p2p 的目标公钥写成直觉名称。
# 这些名字不在 schema 里，会被静默丢弃 → 误产出 free mode 制品（以为做了
# 节点绑定，实际任何 1.5.4+ 节点都能解封）。检测到就明确报错。
_EXT04_ALIASES = (
    "node_pub", "target_node_pub", "target_pub", "target_public_key",
    "public_key", "pub_key", "node_pubkey", "node_public_key", "pem",
)


@dataclass
class ToolResult:
    """Tool call result"""
    success: bool
    content: str
    hint: Optional[str] = None
    error: Optional[str] = None
    warning: Optional[str] = None  # v1.4: pass through warning from save/runner API
    # 1.5.0: list of structured advisory entries from the run response.
    # Each entry is a dict with keys: code, message, details.
    # Populated by mgc_run / mgc_get action=run from response.data.warnings.
    warnings: Optional[list] = None
    # 1.5.0 (2026-09-03 方案A MCP 透传): folder save 完整 saved 列表
    # 每项含 diff_3 / info_type / ext01 / ext02 / ext05 / ext06 / warnings
    saved: Optional[list] = None
    # folder save 时 diff_3 列表（向后兼容字段）
    saved_diff3: Optional[list] = None
    # folder save 时 failed 列表
    failed: Optional[list] = None
    # folder save 业务码（BATCH_PARTIAL_SUCCESS / BATCH_PARTIAL_FAILURE / OPERATION_SUCCESSFUL）
    response_msg: Optional[str] = None
    # 1.5.0 (PR-7): 已识别的 --flag 列表（写入了 ext02）
    recognized_arg_names: Optional[list] = None
    # 1.5.0 (PR-7): 未识别的 --flag 列表（动态默认 / 跳过 / degraded）
    unrecognized_arg_names: Optional[list] = None


class MgcServer:
    """MGC MCP Server - calls REST API via HTTP"""

    TOOLS = [
        {
            "name": "mgc_save",
            "description": "Store one entry in MGC. Pass `content` as a verbatim string — for most `info_type` values (script, config, text, password, token, api_key, phone, etc.) this is the literal data to store.\n\nException: when `info_type='file'`, `content` is a local filesystem path (bulk folder import or `.mgc_file` sealed package import).\n\nIf you have a path on disk and want MGC to read it for you (auto-detects single file vs folder vs `.mgc_file`), use `mgc_save_file` instead.\n\n**Storing a sealed capsule (mgc 1.5.4+)**: pass the entire capsule JSON as `content` — no need to forward any ext field. MGC auto-detects the payload and stores info_type / diff_* / ext01..ext30 / content as-is. `info_type` is still REQUIRED here (schema-enforced) even though the capsule body repeats it — pass `'script'`. `info_owner` is also required: pass your own value to choose the owner; the capsule's own `info_owner` is used ONLY when you pass an empty string. Prefer `mgc_save_file(path=...)` instead — it needs fewer arguments and infers the type automatically. IMPORTANT: saving under the SAME info_owner on the SAME node overwrites the source record — pass a different `info_owner` to keep both.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "description": "Type of information: password, token, api_key, phone, script, config, file (folder or .mgc_file when content is a local path)"
                    },
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description in format 'who + which platform', e.g., 'user's GitHub', 'Amy's Aliyun'. Required. For a sealed CAPSULE, pass YOUR OWN value — an empty string falls back to the capsule's own (source node's) info_owner. (This applies to a single sealed CAPSULE. Sealed PACKAGES are imported with mgc_save_file, where per-record owners always stay as recorded in the package.)"
                    },
                    "content": {
                        "type": "string",
                        "description": "The string to store. For most info_type values this is the verbatim content (e.g. the full script source). For `info_type='file'` this is a local folder or `.mgc_file` path. If you have a local file path and want MGC to read it for you, use `mgc_save_file` instead. For a sealed capsule, pass the ENTIRE capsule JSON verbatim — do not extract or set any ext field yourself."
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "First differentiation field (optional, for multiple entries of same type). when importing a folder, this is propagated to every record under the folder."
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Second differentiation field (optional). Folder import uses the folder basename automatically."
                    },
                    "diff_3": {
                        "type": "string",
                        "description": "Third differentiation field (optional)"
                    },
                    "update_if_exists": {
                        "type": "boolean",
                        "description": "If true, update the entry when a duplicate exists (based on info_type + info_owner + diff fields). Default is false, which returns error. Folder / sealed package imports default to true."
                    },
                    "ext01": {
                        "type": "string",
                        "description": "Startup command for script type (required when info_type is 'script', e.g., 'python -c')"
                    },
                    "ext02": {
                        "type": "string",
                        "description": "Runtime parameters for script as a JSON array string, e.g. '[\"--start\", \"2026-08-08 00:00:00\", \"--verbose\"]'. Optional for script entries — MGC will auto-extract and assemble from argparse definitions in the script body. Manual entry must be a valid JSON array string (a legacy string is also accepted but will use split() fallback at runtime)."
                    },
                    "ext03": {
                        "type": "string",
                        "description": "Sealed key material for a sealed script. Only needed when storing a sealed script WITHOUT passing the whole capsule JSON as content — in that case pass ext03 together with ext07 and ext09 unchanged (values exactly as they appear in the capsule). When you pass the entire capsule JSON as `content`, MGC extracts all ext fields automatically and you must NOT set them here. Never construct this value yourself — it comes from a sealed capsule. Omit for plain scripts and folder packages."
                    }
                },
                "required": ["info_type", "info_owner", "content"]
            }
        },
        # ---- PR-6 (1.5.0 phase2 / 技能授权) — file-path-aware save ----
        {
            "name": "mgc_save_file",
            "description": "Save by a local file/folder path. Auto-detects the path type:\n- folder or `.mgc_file` → imported as `info_type='file'`\n- single file → stored under the inferred `info_type` based on extension\n\n MGC automatically detects how scripts inside the folder call each other (`import`, `from-import`, relative-path subprocess). At run time, those cross-script calls route through sealed execution — no rewrites, no plaintext on disk. Subsequent `mgc_run` on any entry script of the folder runs the whole workflow transparently.\n\n**Usage rules:**\n- `info_type` must be `'file'` (or omitted) for folder / .mgc_file import. For single files, the type is inferred from extension and may be left omitted.\n- `path` must be a local absolute path to an existing file, folder, or .mgc_file. Use `mgc_save` to store text or JSON content directly.\n\n**Importing a sealed capsule (mgc 1.5.4+) — PREFERRED over `mgc_save`:** pass the `sealed_capsule.json` path plus your own `info_owner`. the capsule is recognised automatically and stored as `info_type='script'` with every ext field extracted — you do NOT need to pass `info_type`, and you do NOT need to forward any ext field. This is the lowest-friction import path: `mgc_save_file(path='<capsule>.json', info_owner='<your owner>')`.\n\n**Receiving a sealed package from another node (chain mode, 1.6.0+):** a chain-mode delivery contains ONE sub-package per target node — check the main `README.md` (or `distribution_index.json`) mapping to find the sub-package addressed to THIS node, download that `.mgc_file` to local disk FIRST, then import it here. Two hard rules:\n- **Keep the `.mgc_file` extension.** MGC dispatches sealed-package import by filename suffix. If the file is renamed (e.g. to `.zip`), MGC reads it as a single text file and stores it as a text record — the scripts are NOT imported and the run will fail. Save it as `<owner>__<diff_2>__NN.mgc_file`.\n- **Size limit: 100 files / 50 MB per package** (MGC hard limit). Over it the package is rejected with `TOO_MANY_FILES` / `PACKAGE_TOO_LARGE`.\n- The file on disk is a **ciphertext container** — no plaintext is written, so a temporary file is safe to keep and delete after import.\n\nUse this when you have a path on disk and want MGC to figure out the rest.\n\nThis tool runs on the node that hosts MGC — it is not a remote file transfer.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Local absolute filesystem path to a file, folder, or .mgc_file. Required. Must point to an existing path on the machine running MGC / MCP. For a sealed package received from another node, the filename MUST keep the `.mgc_file` extension — MGC dispatches sealed-package import by suffix, so renaming it breaks the import."
                    },
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description in format 'who + which platform', e.g., 'user's GitHub'. Required for folder / .mgc_file; for single script it becomes the record's info_owner.\n\nIMPORTANT — the two sealed-import shapes behave differently:\n- Single sealed CAPSULE (sealed_capsule.json): your info_owner IS applied to the stored record. Pass your own value to avoid overwriting the source record.\n- Sealed PACKAGE (.mgc_file): your info_owner applies to the PACKAGE GROUP only (the folder triple). Every record inside keeps the owner recorded in the package — this is REQUIRED for cross-script sealed execution (the 5+1 check requires caller and target to share the same info_owner). After import, locate records by the owner recorded INSIDE the package, e.g. mgc_find(info_owner=\"<the package's own info_owner>\")."
                    },
                    "info_type": {
                        "type": "string",
                        "description": "Optional. For folder / .mgc_file import, must be 'file' (or omitted). For single files, omitted lets MGC infer the type from extension (.py/.sh → 'script', .json/.yaml → 'config', else 'text'). Pass 'password' / 'token' / 'api_key' / 'phone' explicitly when needed."
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "First differentiation field (optional). For single-file save, propagated to the record. For folder import, propagated to every record under the folder."
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Second differentiation field (optional). For folder import, defaults to the folder basename."
                    },
                    "diff_3": {
                        "type": "string",
                        "description": "Third differentiation field (optional). For single-file save, defaults to the file basename (stem), which makes it easier to identify the record by filename."
                    },
                    "update_if_exists": {
                        "type": "boolean",
                        "description": "If true, update the entry when a duplicate exists. Default: true for folder / .mgc_file, false for single file."
                    },
                    "ext01": {
                        "type": "string",
                        "description": "Startup command for script type (required only when info_type is 'script' and you want to override the inferred value, e.g., 'python3')."
                    },
                    "ext02": {
                        "type": "string",
                        "description": "Runtime parameters for script as a JSON array string (optional)."
                    }
                },
                "required": ["path", "info_owner"]
            }
        },
        {
            "name": "mgc_skill",
            "description": "Learn how MGC enables zero-exposure usage and sealed cross-node delivery of secrets, scripts, skill folders, and workflows.\n\nCalling this tool returns the full skill document (capabilities, decision flow, tool usage, sealing modes) — read it when you are confused.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "mgc_get",
            "description": "Retrieve an entry, list all entries (omit info_type + info_owner), or perform an action: `run` (script, prefer mgc_run), `package` / `seal_package` (folder, prefer mgc_package / mgc_seal_package). To generate a sealed capsule for a single script, use mgc_seal.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "description": "Type of information to retrieve (optional, omit to get list). Use 'file' for folder / package actions. NOTE: node public key must be queried as info_type='__NODE_PUB__'."
                    },
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description (optional, omit to get list). Required for package / seal_package actions. For node public key queries, this MUST be '__NODE_PUB__' (identical to info_type) — any other value matches no record."
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "First differentiation field. Folder: optional disambiguation for package / seal_package actions."
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Second differentiation field. Folder: folder name for package / seal_package actions."
                    },
                    "diff_3": {
                        "type": "string",
                        "description": "Third differentiation field"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action to perform: 'run' to execute script (when info_type is 'script'); 'package' to export a folder (plain); 'seal_package' to generate a .mgc_file. Use dedicated tools mgc_package / mgc_seal_package when possible — they take the same arguments and also require `output_dir`."
                    },
                    "ext04": {
                        "type": "string",
                        "description": "Sealing target spec for action='seal_package'. Omit or leave empty for **free mode**; pass a multi-line PEM for **p2p mode**; pass a JSON **array** of `{\"node_pub\": \"<PEM>\", \"files\": [\"<relative path>\", ...]}` targets (or '@<abs path>') for **chain mode** (1.6.0+)."
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Local output root directory for package / seal_package actions. REQUIRED for both actions since 1.5.4 — there is no default location. Pass an absolute path; MGC creates '<output_dir>/<diff_2>/' inside it (in chain mode: '<output_dir>/<info_owner>__<diff_2>/' with one task_package_NN/ per target)."
                    },
                    "ext02": {
                        "type": "string",
                        "description": "Runtime parameters for script execution (optional)"
                    }
                }
            }
        },
        {
            "name": "mgc_run",
            "description": "Execute a stored script (info_type='script') in MGC Blackbox sandbox. Returns pid + status only. For a plain script, observe results via its stdout / files / external services. For a SEALED script, stdout is not returned — observe results via files / external side effects only.\n\n**Passing runtime args (`ext02`):** ext02 must be a STRING containing a JSON array — e.g. ext02='[\"--flag\",\"value\"]'. Passing a real JSON array (not a string) is rejected by schema validation before MGC is called. If the stored ext02 is not a JSON array, MGC falls back to split() automatically.\n\n**For scripts inside a saved folder (1.5.1+):** cross-script calls (`import`, `from-import`, relative-path subprocess) are automatically intercepted and routed through sealed child execution — the script runs as a coherent workflow without leaking source to disk.\n\nResponse may include `data.warnings: [{code, message, details}]`. Codes: `DEP_MISSING`, `PLATFORM_INCOMPAT`, `DIFF2_MISMATCH` (cross-script target not in same workflow package). Warnings do not change execution status.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "description": "Must be 'script'"
                    },
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description, e.g., 'project / build script'"
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "First differentiation field (optional). Folder-import scripts usually store empty diff_1 — passing it is not required. If omitted and multiple scripts match the given info_owner + diff_2 + diff_3, MGC returns AMBIGUOUS_SCRIPT with a hint redirecting the caller to mgc_find first."
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Second differentiation field (optional). Folder name for folder-import scripts — passing it narrows the lookup. For folder-imported scripts this is REQUIRED in practice: without it several scripts under the same info_owner may match, and MGC returns AMBIGUOUS_SCRIPT instead of guessing."
                    },
                    "diff_3": {
                        "type": "string",
                        "description": "Third differentiation field (optional). The script's relative path inside a folder — passing it identifies a single record on its own, so it is the most reliable way to run one specific script of a folder."
                    },
                    "ext02": {
                        "type": "string",
                        "description": "Runtime parameters override (optional). MUST be a string containing a JSON array — correct form: '[\"--flag\",\"value\"]' (a string). Wrong form: a real JSON array ([\"--flag\",\"value\"]) — that is rejected by schema validation before MGC is called. Never wrap it in another object or array. When the stored ext02 is not a JSON array, MGC falls back to split() automatically."
                    }
                },
                "required": ["info_owner"]
            }
        },
        {
            "name": "mgc_seal",
            "description": "Generate a sealed execution capsule for a single script (mgc 1.5.4+) and write it to disk as a self-describing JSON file.\n\n**Sealing mode** is decided by whether you pass `ext04`:\n- Pass `ext04` (target node's PEM public key) -> **p2p mode**: only the node whose private key matches `ext04` can unseal and run.\n- Omit `ext04` -> **free mode**: any mgc 1.5.4+ node can unseal and run, but script source remains invisible (encrypted, decrypted only in-memory at execution time).\n\nTo fetch a target node's PEM, use `mgc_get(info_type='__NODE_PUB__', info_owner='__NODE_PUB__')` on that node (both fields identical).\n\n**Persistence**: the capsule JSON carries info_type / info_owner / diff_1..3 / every non-empty ext field / content. `output_dir` is REQUIRED — there is no desktop fallback because the desktop location differs across platforms.\n\nTo store it, use EITHER of these (never forward ext fields one by one):\n- `mgc_save_file(path='<capsule_path>', info_owner='<your owner>')` — PREFERRED, fewest arguments. `info_type` is inferred automatically from the capsule; do not pass it.\n- `mgc_save(content=<entire capsule JSON>, info_type='script', info_owner='<your owner>')` — `info_type` is REQUIRED by this tool's schema even though the capsule body repeats it.\n\nIn both cases MGC auto-parses the capsule and stores info_type / diff_* / ext01..ext30 / content as-is. Pass a DIFFERENT info_owner than the source to keep both records; using the original owner on the SAME node overwrites the source record.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description of the script to seal (required)"
                    },
                    "info_type": {
                        "type": "string",
                        "description": "Type of information (optional, default: 'script')"
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "First differentiation field (optional)"
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Second differentiation field (optional)"
                    },
                    "diff_3": {
                        "type": "string",
                        "description": "Third differentiation field (optional)"
                    },
                    "ext04": {
                        "type": "string",
                        "default": "",
                        "description": "Target node's PEM public key. Omit or leave empty for **free mode**; pass the multi-line PEM for **p2p mode**. When present, MUST be a multi-line PEM with REAL newline characters between header, base64 lines, and footer (e.g. '-----BEGIN PUBLIC KEY-----\\n<base64 lines>\\n-----END PUBLIC KEY-----'). DO NOT pass as a single concatenated line. Use `mgc_get(info_type='__NODE_PUB__', info_owner='__NODE_PUB__')` to fetch the canonical multi-line PEM."
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Absolute directory to write the capsule into (required). MGC creates a timestamped subfolder '<info_owner>_<YYYYMMDD_HHMMSS>/sealed_capsule.json' inside it. There is NO desktop fallback -- the desktop location differs across platforms, so you must pass an explicit path."
                    }
                },
                "required": ["info_owner", "output_dir"]
            }
        },
        {
            "name": "mgc_list",
            "description": "List all stored entries (metadata only, no content). Returns a compact index: each entry shows only its identifying fields (info_owner / info_type / diff_1..3). For fuzzy search use mgc_find; to read content or the full details of one record use mgc_get.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "mgc_find",
            "description": "Fuzzy-search stored entries by info_owner / diff_1..3; returns metadata only (use mgc_get for content). For exact-match queries, use mgc_list. For exact lookup of one record, use mgc_get.\n\nTo list all scripts inside a saved workflow folder, query by its `info_owner` (or `diff_2`) — useful when you don't know the entry script's name.\n\nThis tool does NOT accept `info_type` as a filter — pass `info_owner` (or diff fields) only.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_owner": {
                        "type": "string",
                        "description": "Fuzzy match on info_owner (substring by default). E.g. 'test' matches 'parser_smoke_test', 'test_1_4_10_e2e', etc."
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "Fuzzy match on diff_1 field."
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Fuzzy match on diff_2 field."
                    },
                    "diff_3": {
                        "type": "string",
                        "description": "Fuzzy match on diff_3 field."
                    },
                    "match_mode": {
                        "type": "string",
                        "enum": ["substring", "prefix", "suffix", "exact"],
                        "default": "substring",
                        "description": "Wildcard style applied to each filter field: substring=%x%, prefix=x%, suffix=%x, exact=x. Default is substring."
                    },
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "description": "Maximum number of entries to return. Default 100."
                    }
                }
            }
        },
        {
            "name": "mgc_open_webui",
            "description": "Open MGC Blackbox WebUI in the default browser for visual management.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        # ---- PR-5 (1.5.0 phase2 / 技能授权) ----
        {
            "name": "mgc_package",
            "description": "Export a stored folder (`info_type='file'` under same `info_owner + diff_2`) as plaintext to `output_dir/<diff_2>/`. For sealed export, use mgc_seal_package.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description (required)"
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Folder name (required, identifies which folder to export)"
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "Optional disambiguation when multiple (info_owner, diff_2) sets exist. If omitted and multiple sets match, MGC returns AMBIGUOUS_FOLDER."
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Local output root directory. The folder will be written under output_dir/<diff_2>/."
                    }
                },
                "required": ["info_owner", "diff_2", "output_dir"]
            }
        },
        {
            "name": "mgc_seal_package",
            "description": "Generate a sealed package for a stored folder (mgc 1.5.4+). The output is written to `output_dir/<diff_2>_delivery/` and contains two files:\n- `<diff_2>.mgc_file` -- the ciphertext container holding the sealed scripts.\n- `README.md` -- documentation describing the package, its dependencies, and how to import it.\n\n**Sealing mode** is decided by the shape of `ext04`:\n- Omit `ext04` -> **free mode**: any mgc 1.5.4+ node can unseal and run, but script source remains invisible (encrypted, decrypted only in-memory at execution time).\n- Pass a multi-line PEM -> **p2p mode**: only the node whose private key matches `ext04` can unseal and run.\n- Pass a JSON **array** of targets (or `@<abs path to that JSON>`) -> **chain mode** (1.6.0+): the package is split into one `.mgc_file` + `README.md` per target under `output_dir/<info_owner>__<diff_2>/task_package_NN/`, each sealed against that target's own node_pub, plus a main `README.md` with the node_pub mapping and all warnings. Each element of the array is `{\"node_pub\": \"<that node's PEM>\", \"files\": [\"<relative path>\", ...]}`; `files` entries must match the stored relative paths (diff_3) EXACTLY.\n\n**Chain mode also writes `distribution_index.json`** (1.6.0+) next to the main README — the machine-readable counterpart of the human-readable mapping table. It tells a dispatch script which sub-package goes to which node (node_pub + fingerprint), the sha256 and size of each `.mgc_file`, and every warning. Use it to automate distribution instead of parsing the README. The response field `data.distribution_index_path` points at it.\n\n**Cross-node sealed execution (1.5.1+):** After delivery, the target node saves the package with `mgc_save_file(.mgc_file)` then runs `mgc_run` -- cross-script calls inside the package are recognized and routed through sealed execution locally, so the receiving node runs the whole workflow without the source being readable.\n\nLimits: max 100 files / max 50 MB. A folder without scripts can still be sealed in every mode (p2p / free / chain): only scripts are encrypted, all other files stay plaintext in the package (1.6.0+ removed the previous `NO_SCRIPT_TO_SEAL` restriction for p2p / free mode as well).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description (required)"
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Folder name (required)"
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "Optional disambiguation when multiple (info_owner, diff_2) sets exist."
                    },
                    "ext04": {
                        "type": "string",
                        "default": "",
                        "description": "Sealing target spec. Three forms:\n"
                        "1) Omit or leave empty -> **free mode** (any mgc 1.5.4+ node can unseal).\n"
                        "2) A multi-line PEM -> **p2p mode** (only the matching node_priv can unseal). MUST be a multi-line PEM with REAL newline characters (e.g. '-----BEGIN PUBLIC KEY-----\\n<base64>\\n-----END PUBLIC KEY-----'). Use `mgc_get(info_type='__NODE_PUB__', info_owner='__NODE_PUB__')` to fetch the canonical multi-line PEM.\n"
                        "3) A JSON **array** of targets -> **chain mode** (1.6.0+). Each element: {\"node_pub\": \"<that target node's PEM>\", \"files\": [\"<relative path>\", ...]}. 'files' entries must match the stored relative paths (diff_3) EXACTLY. MGC splits the package into one .mgc_file + README per target, each sealed against that target's node_pub. Prefix with '@' to load the JSON from a local file instead of inline (e.g. '@/abs/path/targets.json') — recommended for long specs."
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Local output root directory. In p2p / free mode the package is written under output_dir/<diff_2>_delivery/. In chain mode a main folder output_dir/<info_owner>__<diff_2>/ is created, containing one task_package_NN/ sub-folder per target (each with its own .mgc_file + README.md) plus a main README.md describing the node_pub mapping."
                    }
                },
                "required": ["info_owner", "diff_2", "output_dir"]
            }
        },
        # ---- mgc_delete (single-record exact-match or folder-level delete) ----
        {
            "name": "mgc_delete",
            "description": "Delete record(s) from MGC. By default operates in **single-record mode** (strict 6-tuple match). When the supplied 6-tuple matches multiple records (i.e. the (info_type, info_owner, diff_2) triple defines a folder with several records), the tool refuses to act and asks the AI to confirm with the user first — see Folder-level delete below.\n\n"
                           "**Required:** info_type, info_owner. diff_1, diff_2, diff_3 are optional — pass empty string when not used.\n\n"
                           "**Single-record mode (default):**\n"
                           "- 0 records match the 6-tuple — no deletion. Response carries `hint=NOT_FOUND`; run `mgc_find` to locate the exact record.\n"
                           "- 1 record matches — deletion happens. Response carries `code=200` and `deleted_count=1`.\n"
                           "- 2+ records share the (info_type, info_owner, diff_2) folder — no deletion. Response carries `hint=MULTIPLE_MATCHES` and a `candidates` list. Explicit user confirmation is required before escalating to a folder-level delete — the user must read the candidate list and approve, after which the caller re-invokes with `confirm_folder_delete=\"true\"` (string, not boolean). The caller must never auto-confirm.\n\n"
                           "**Folder-level delete (after explicit user confirmation):**\n"
                           "Set `confirm_folder_delete=\"true\"` (the STRING value, not JSON boolean) only after the candidate list has been presented and deletion has been explicitly approved. The backend removes every record under the (info_type, info_owner, diff_2) triple (matching the WebUI's Delete Folder behavior). The response carries the actual list of deleted records.\n\n"
                           "Note: the flag is a STRING, not a JSON boolean — `\"true\"` / `\"True\"` / `\"TRUE\"` / `\"1\"` are accepted; anything else is treated as not-confirmed. The value must still be set only after explicit approval — the caller must never set it on its own.\n\n"
                           "**Deleting a folder takes one call per `info_type` present in it.** A folder's records are stored under separate types (`script` for code, `text` for docs, etc.), so `info_type='file'` returns `NOT_FOUND` even when the folder exists. Call `mgc_list` first to see which types exist, then delete each one — e.g. a folder holding both scripts and docs needs `mgc_delete(info_type='script', ...)` AND `mgc_delete(info_type='text', ...)`. A single-call folder wipe across types is not supported.\n\n"
                           "**Protected records:** info_type in (\"__NODE_PUB__\", \"__NODE_PRIV__\", \"__DEFAULT_NODE_PUB__\", \"__DEFAULT_NODE_PRIV__\") is refused with `error=PROTECTED_RECORD` — these are node credentials and cannot be deleted by anyone.\n\n"
                           "**Audit:** Every successful deletion is recorded in MGC's operation log.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "description": "Record type (required). Examples: 'token', 'script', 'api_key', 'file', 'config', 'text'. Cannot be a node-credential type."
                    },
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership location (required)."
                    },
                    "diff_1": {
                        "type": "string",
                        "default": "",
                        "description": "First differentiation field. Pass empty string when not used."
                    },
                    "diff_2": {
                        "type": "string",
                        "default": "",
                        "description": "Second differentiation field. Pass empty string when not used."
                    },
                    "diff_3": {
                        "type": "string",
                        "default": "",
                        "description": "Third differentiation field. Pass empty string when not used."
                    },
                    "confirm_folder_delete": {
                        "type": "string",
                        "default": "",
                        "description": "REQUIRED to escalate to a folder-level delete (when 2+ records share the same info_type + info_owner + diff_2). Pass the STRING value \"true\" (or any of \"True\" / \"TRUE\" / \"1\") only after explicit approval of the deletion. Pass empty string / \"false\" / anything else to indicate NOT confirmed (default). The caller must never set this value on its own — approval must be obtained first. Note: this field is encoded as a string (not a JSON boolean) to avoid a type-coercion issue at schema validation time — see \"Why a string...\" above."
                    }
                },
                "required": ["info_type", "info_owner"]
            }
        }
    ]

    def __init__(self, api_base_url: str = None):
        """
      # Initialize MGC MCP Server
        Args:
            api_base_url: REST API base URL, default from config
        """
        _ensure_mcp_config()
        self.api_base_url = api_base_url or MGC_API_BASE_URL
        self.token = self._load_token()
        self._mgc_process: Optional[subprocess.Popen] = None
        self._last_error: str = ""

    def _load_token(self) -> str:
        """Load MGC Token"""
        try:
            token_path = Path.home() / ".mgc/database/mgc_black_box/.mgc_token"
            if token_path.exists():
                return token_path.read_text().strip()
            return ""
        except Exception:
            return ""

    def _is_mgc_running(self) -> bool:
        """Check if MGC REST API is running"""
        try:
            response = requests.get(f"{self.api_base_url}/api/mgc/status", timeout=1)
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            return False
        except Exception:
            return False

    import sys

    def _start_mgc(self) -> bool:
        """Start MGC REST API as subprocess"""
        if self._mgc_process is not None:
            return True

        launch_cmd = os.environ.get("MGC_LAUNCH_CMD")
        if launch_cmd:
            cmd = launch_cmd.split()
        else:
            cmd = [sys.executable, "-m", "mgc.main"]

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            self._mgc_process = subprocess.Popen(
                cmd,
                stdin=None,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )

            for _ in range(int(MCP_STARTUP_TIMEOUT / MCP_STARTUP_CHECK_INTERVAL)):
                if self._is_mgc_running():
                    return True
                time.sleep(MCP_STARTUP_CHECK_INTERVAL)

            print(f"MCP start check: process={self._mgc_process}, returncode={self._mgc_process.poll()}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"MCP _start_mgc failed: {e}", file=sys.stderr)
            return False

    def _ensure_mgc_running(self) -> bool:
        """Ensure MGC REST API is running, auto-start if needed"""
        if self._is_mgc_running():
            return True
        try:
            return self._start_mgc()
        except Exception as e:
            self._last_error = str(e)
            return False

    def _make_request(self, method: str, endpoint: str, json_data: Dict = None) -> Dict:
        """Send HTTP request to REST API"""
        import json
        self.token = self._load_token()
        url = f"{self.api_base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json; charset=utf-8",
            "X-MGC-Token": self.token
        }
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            body = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
            response = requests.post(url, headers=headers, data=body)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        # Handle non-JSON responses
        try:
            result = response.json()
        except Exception as e:
            return f"HTTP {response.status_code}: {response.text}"
        
        return result

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        # Handle JSON-RPC request

        Args:
            request: JSON-RPC request object

        Returns:
            dict: JSON-RPC response object
        """
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "tools/list":
            return self._list_tools(request_id)
        elif method == "tools/call":
            return self._call_tool(params, request_id)
        elif method == "initialize":
            return self._initialize(params, request_id)
        elif method == "notifications/initialized":
            response = {"jsonrpc": "2.0"}
            if request_id is not None:
                response["id"] = request_id
            return response
        else:
            response = {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Unknown method: {method}"}}
            if request_id is not None:
                response["id"] = request_id
            return response

    def _initialize(self, params: Dict[str, Any], request_id: Optional[Any]) -> Dict[str, Any]:
        """Handle initialize request"""
        response = {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": MCP_SERVER_NAME,
                    "version": MCP_SERVER_VERSION
                }
            }
        }
        if request_id is not None:
            response["id"] = request_id
        return response

    def _list_tools(self, request_id: Optional[Any]) -> Dict[str, Any]:
        """Handle tools/list request"""
        response = {"jsonrpc": "2.0", "result": {"tools": self.TOOLS}}
        if request_id is not None:
            response["id"] = request_id
        return response

    def _call_tool(self, params: Dict[str, Any], request_id: Optional[Any]) -> Dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        result = self._execute_tool(tool_name, arguments)

        # 1.5.0: render structured advisory warnings to MCP text output.
        # We append a "Warnings: ..." block listing each code + message so
        # downstream agents see the advisories without breaking v1.4 hint/warning
        # string formatting. Empty list is rendered as nothing (avoids noise).
        #
        # If the REST API's hint already embeds a "Warnings:" block (e.g. for
        # mgc_run the backend pre-renders it via _attach_warnings), we skip
        # the duplicate render here. Detection is "Warnings:\n" at the
        # boundary between a fresh newline and the keyword.
        warning_text = ""
        if result.warnings and not (result.hint and "Warnings:\n" in result.hint):
            try:
                lines = []
                for w in result.warnings:
                    if not isinstance(w, dict):
                        continue
                    code = w.get("code") or "WARNING"
                    msg = w.get("message") or ""
                    details = w.get("details") or []
                    line = f"- [{code}] {msg}"
                    if details:
                        line += f" ({', '.join(str(d) for d in details)})"
                    lines.append(line)
                if lines:
                    warning_text = "\nWarnings:\n" + "\n".join(lines)
            except Exception:
                warning_text = ""

        if result.success:
            text = result.content
            if result.hint:
                text = f"{result.content}\nHint: {result.hint}" if result.content else result.hint
            if warning_text:
                text = (text + warning_text) if text else warning_text.lstrip("\n")
            # 1.5.0 (方案A MCP 透传): folder save 的 saved/failed 列表追加渲染
            extra = _render_folder_save_extras(result)
            if extra:
                text = (text + extra) if text else extra.lstrip("\n")
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ],
                    "isError": False
                }
            }
        else:
            text = f"Error: {result.error}"
            if result.hint:
                text += f"\nHint: {result.hint}"
            if warning_text:
                text += warning_text
            # 1.5.0 (方案A MCP 透传): error 分支同样渲染 saved/failed
            extra = _render_folder_save_extras(result)
            if extra:
                text += extra
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ],
                    "isError": True
                }
            }
        if request_id is not None:
            response["id"] = request_id
        return response

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Execute tool and return result"""
        if not self._ensure_mgc_running():
            hint = f"Run 'mgc' or 'python -m mgc.main' to start MGC."
            if self._last_error:
                hint += f" Error: {self._last_error}"
            return ToolResult(
                success=False,
                content="",
                error="Failed to start MGC Blackbox. Please start MGC manually.",
                hint=hint
            )

        try:
            if tool_name == "mgc_save":
                return self._do_save(args)
            elif tool_name == "mgc_save_file":
                # 1.5.0 (PR-6): path-aware save; resolves single file vs folder
                # vs .mgc_file and delegates to mgc_save internally.
                return self._do_save_file(args)
            elif tool_name == "mgc_skill":
                return self._do_skill(args)
            elif tool_name == "mgc_get":
                return self._do_get(args)
            elif tool_name == "mgc_run":
                # Dedicated wrapper: inject action=run and reuse mgc_get HTTP path.
                # This keeps the underlying API endpoint unchanged for backward compatibility.
                # mgc_run operates exclusively on script records — clients may omit
                # info_type or accidentally pass a non-script type; we silently inject
                # info_type='script' server-side so the run path always matches
                # api_router's `request.info_type == "script"` guard (api_router:1496).
                # See phase7 #6 (2026-09-23): silent fall-through to find index caused
                # 7.5 case to return record metadata instead of script execution.
                run_args = dict(args)
                run_args["info_type"] = "script"
                run_args["action"] = "run"
                return self._do_get(run_args)
            elif tool_name == "mgc_seal":
                return self._do_seal(args)
            elif tool_name == "mgc_package":
                # 复用 mgc_get HTTP 路径，但显式注入 info_type=file + action=package
                # 让 api_router 的分发条件 (info_type='file' AND action in ('package','seal_package')) 命中。
                pkg_args = dict(args)
                pkg_args["info_type"] = "file"
                pkg_args["action"] = "package"
                return self._do_get(pkg_args)
            elif tool_name == "mgc_seal_package":
                # 1.5.4 phase6 friction fix: ext04 写错会静默降级为 free mode
                alias_hit = self._detect_ext04_alias(args, "mgc_seal_package")
                if alias_hit:
                    return alias_hit
                # 复用 mgc_get HTTP 路径，但显式注入 info_type=file + action=seal_package
                # 让 api_router 的分发条件 (info_type='file' AND action in ('package','seal_package')) 命中。
                pkg_args = dict(args)
                pkg_args["info_type"] = "file"
                pkg_args["action"] = "seal_package"
                return self._do_get(pkg_args)
            elif tool_name == "mgc_list":
                return self._do_list(args)
            elif tool_name == "mgc_find":
                return self._do_find(args)
            elif tool_name == "mgc_open_webui":
                return self._do_open_webui()
            elif tool_name == "mgc_delete":
                return self._do_delete(args)
            else:
                return ToolResult(success=False, content="", error=f"Unknown tool: {tool_name}")
        except requests.exceptions.ConnectionError:
            return ToolResult(
                success=False,
                content="",
                error="MGC Blackbox connection failed. Please restart MGC.",
                hint="Run 'mgc' or 'python -m mgc.main' to start MGC."
            )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Error: {str(e)}")

    def _do_save(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_save"""
        # Filter out None values and reserved MCP field "name", pass all others to API
        data = {
            k: v for k, v in args.items()
            if v is not None and k != "name"
        }

        # Ensure required fields exist
        if not data.get("info_type") or not data.get("info_owner"):
            return ToolResult(success=False, content="", hint="Missing info_type or info_owner")

        response = self._make_request("POST", "/api/mgc/sensitive/save", data)
        code = response.get("code")
        warning = response.get("warning")

        # v1.4.10: Convert warning code to English user-facing message
        warning_text = self._format_save_warning(warning)

        # 1.5.0: pass through structured advisory warnings (same shape as _do_get).
        response_data = response.get("data") or {}
        structured_warnings = (
            response_data.get("warnings")
            if isinstance(response_data, dict) else None
        )

        # 1.5.0 (方案A MCP 透传): folder save 返回结构扩展
        # 从 response.data 读取 saved / saved_diff3 / failed / response_msg 字段
        # 这些字段由 folder_save_orchestrator 在服务端填充
        saved_list = (
            response_data.get("saved")
            if isinstance(response_data, dict) else None
        )
        saved_diff3 = (
            response_data.get("saved_diff3")
            if isinstance(response_data, dict) else None
        )
        failed_list = (
            response_data.get("failed")
            if isinstance(response_data, dict) else None
        )
        response_msg = response.get("msg", "")

        # 1.5.0 (PR-7): 透传 args 识别结构化信息
        recognized_list = (
            response_data.get("recognized_arg_names")
            if isinstance(response_data, dict) else None
        )
        unrecognized_list = (
            response_data.get("unrecognized_arg_names")
            if isinstance(response_data, dict) else None
        )
        # 把 args 识别摘要拼到 content（让人/agent 直接看到）
        args_summary = ""
        if recognized_list or unrecognized_list:
            parts = []
            if recognized_list:
                parts.append(f"recognized args ({len(recognized_list)}): {recognized_list}")
            if unrecognized_list:
                parts.append(f"unrecognized args ({len(unrecognized_list)}): {unrecognized_list} — supply ext02 manually")
            args_summary = "\n\n" + "\n".join(parts)

        # 1.5.4 phase6 friction fix: 回显存入的地址三元组 + 关键 ext，
        # agent 下次调用可直接照抄，不用猜 diff_* 落在哪。
        meta_summary = ""
        stored_meta = (
            response_data.get("stored_meta")
            if isinstance(response_data, dict) else None
        )
        if stored_meta:
            identity = {
                k: v for k, v in stored_meta.items() if not k.startswith("ext")
            }
            exts = {
                k: v for k, v in stored_meta.items()
                if k.startswith("ext") and v
            }
            meta_summary = "\n\nstored: " + json.dumps(
                identity, ensure_ascii=False
            )
            if exts:
                meta_summary += "\nstored ext: " + json.dumps(
                    exts, ensure_ascii=False
                )

        if code == 200:
            content = response.get("msg", "Save successful")
            if warning_text:
                content = f"{content}\n\n{warning_text}"
            content += args_summary
            content += meta_summary
            return ToolResult(
                success=True,
                content=content,
                hint=response.get("hint"),
                warning=warning,
                warnings=structured_warnings,
                saved=saved_list,
                saved_diff3=saved_diff3,
                failed=failed_list,
                response_msg=response_msg,
                recognized_arg_names=recognized_list,
                unrecognized_arg_names=unrecognized_list,
            )
        else:
            return ToolResult(
                success=False,
                content="",
                error=response.get("msg", "Save failed"),
                hint=response.get("hint"),
                warning=warning,
                warnings=structured_warnings,
                saved=saved_list,
                saved_diff3=saved_diff3,
                failed=failed_list,
                response_msg=response_msg,
                recognized_arg_names=recognized_list,
                unrecognized_arg_names=unrecognized_list,
            )

    def _do_save_file(self, args: Dict[str, Any]) -> ToolResult:
        """1.5.0 (PR-6) — path-aware save entry.

        Accepts a local filesystem path (`path`) and dispatches to `mgc_save`
        with the correct `info_type` / `content` so the caller does not have
        to know whether the path is a single file, a folder, or a .mgc_file.

        Detection rules (executed in this order):
        1. If `path` ends with `.mgc_file` → treat as sealed package import,
           force `info_type='file'`, pass `path` directly to mgc_save.
        2. Else if `path` is a directory → treat as folder bulk plain import,
           force `info_type='file'`, pass `path` directly to mgc_save.
        3. Else (single file):
           - Read the file content with utf-8 (errors='replace') so non-text
             binaries degrade gracefully instead of crashing the MCP call.
           - Infer `info_type` from the file extension when caller did not pass
             one explicitly: .py/.sh → 'script', .json → 'config',
             .yaml/.yml/.toml/.ini → 'config', else 'text'.
           - Pass the actual content string to mgc_save.

        Validation:
        - Missing `path` / `info_owner` → ToolResult(error=...) without
          touching the network.
        - Path does not exist → ToolResult(error=...) without touching the
          network.

        Notes:
        - The class structure is preserved by placing this method as a
          sibling of `_do_save`, _inside_ the MgcServer class.
        - All folder / .mgc_file handling is delegated; the MCP layer is a
          thin dispatcher and never tries to read folder content itself.
        - Single-file save default for `update_if_exists` is False (i.e.,
          "fail if duplicate"), matching mgc_save's default. Folder / .mgc_file
          default is True (mirroring mgc_save's "Folder / sealed package
          imports default to true" rule).
        - `diff_3` defaults to the file stem for single-file save (so the
          record is identifiable by filename), matching how folder save
          uses the file basename.
        """
        path = args.get("path")
        info_owner = args.get("info_owner")
        explicit_info_type = args.get("info_type")

        # --- Required fields ---
        if not path:
            return ToolResult(
                success=False,
                content="",
                error="Missing required param: path",
                hint=(
                    "mgc_save_file requires a local file / folder / .mgc_file path. "
                    "If you want to save text or JSON content directly, use mgc_save instead."
                ),
            )
        if not info_owner:
            return ToolResult(
                success=False,
                content="",
                error="Missing required param: info_owner",
                hint="mgc_save_file requires info_owner in format 'who + which platform'.",
            )

        path_obj = Path(path)

        # When a folder path contains a .mgc_file at the top level, refuse and
        # instruct the caller to pass the .mgc_file path directly. Folder
        # save stores skill files; .mgc_file import is a separate operation
        # (unzip + parse MGCFILE.json). Mixing the two paths would cause
        # the .mgc_file to be persisted as an opaque binary.
        if path_obj.is_dir():
            try:
                mgc_files_in_folder = [
                    item for item in path_obj.iterdir()
                    if item.is_file() and item.suffix.lower() == ".mgc_file"
                ]
            except Exception:
                mgc_files_in_folder = []
            if mgc_files_in_folder:
                file_list = [str(f) for f in mgc_files_in_folder]
                if len(file_list) == 1:
                    return ToolResult(
                        success=False,
                        content="",
                        error="FOLDER_CONTAINS_MGC_FILE",
                        hint=(
                            "Detected .mgc_file in folder. "
                            "Pass the .mgc_file path directly instead of its parent directory."
                        ),
                    )
                else:
                    return ToolResult(
                        success=False,
                        content="",
                        error="FOLDER_CONTAINS_MULTIPLE_MGC_FILES",
                        hint=(
                            f"Folder contains {len(file_list)} .mgc_file. "
                            "Import them one by one by passing each .mgc_file path directly."
                        ),
                    )

        # --- Existence check (avoids network round-trip for bad paths) ---
        if not path_obj.exists():
            return ToolResult(
                success=False,
                content="",
                error=f"Path does not exist: {path}",
                hint=(
                    "Verify the path is accessible from the machine running MGC / MCP. "
                    "If you intended to save text/JSON content directly, use mgc_save."
                ),
            )

        # --- phase6 (1.5.1) — strict info_type / path semantics ---
        # When the path is a folder or .mgc_file, info_type MUST be exactly 'file'
        # (or omitted, which we then normalize to 'file'). Any other value is
        # rejected so callers cannot accidentally pass type='folder'/'text'/'script'.
        # Single-file save still permits explicit info_type override (e.g. 'password').
        if path_obj.is_dir() or path_obj.suffix.lower() == ".mgc_file":
            if explicit_info_type is not None and explicit_info_type != "file":
                return ToolResult(
                    success=False,
                    content="",
                    error=(
                        f"info_type='{explicit_info_type}' is not valid for folder / "
                        f".mgc_file save. Must be exactly 'file' (or omitted)."
                    ),
                    hint=(
                        "Folder / .mgc_file import is always stored as info_type='file'. "
                        "If you intended to store text or JSON content directly, "
                        "use the mgc_save tool instead of mgc_save_file."
                    ),
                )

        # --- Build the mgc_save dispatch args ---
        save_args: Dict[str, Any] = {
            "info_owner": info_owner,
            "diff_1": args.get("diff_1"),
            "diff_2": args.get("diff_2"),
            "diff_3": args.get("diff_3"),
            "ext01": args.get("ext01"),
            "ext02": args.get("ext02"),
        }
        explicit_update = args.get("update_if_exists")

        # Case 1: .mgc_file → sealed package import (info_type='file')
        if path_obj.is_file() and path_obj.suffix.lower() == ".mgc_file":
            save_args["info_type"] = "file"
            save_args["content"] = str(path_obj)
            if explicit_update is not None:
                save_args["update_if_exists"] = explicit_update
            else:
                save_args["update_if_exists"] = True  # folder/sealed default
            return self._do_save(save_args)

        # Case 2: folder → bulk plain import (info_type='file')
        if path_obj.is_dir():
            save_args["info_type"] = "file"
            save_args["content"] = str(path_obj)
            if explicit_update is not None:
                save_args["update_if_exists"] = explicit_update
            else:
                save_args["update_if_exists"] = True  # folder default
            return self._do_save(save_args)

        # Case 3: single file → read content + infer info_type
        try:
            content_str = path_obj.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Failed to read file: {path} ({e})",
                hint="Ensure the file is readable and not locked by another process.",
            )

        # Infer info_type from extension if caller did not pass one.
        if explicit_info_type:
            # Single-file save does NOT accept info_type values that imply
            # "path semantics" (e.g. 'folder' / '.mgc_file'). These belong
            # to folder / package save (which we already handle above) — if
            # we reach here the caller mis-routed a path-based save into
            # the single-file branch. Reject with a friendly error.
            if explicit_info_type.lower() in ("folder", ".mgc_file"):
                return ToolResult(
                    success=False,
                    content="",
                    error=(
                        f"info_type='{explicit_info_type}' is reserved for folder / "
                        f"package save, but the supplied path is a single file."
                    ),
                    hint=(
                        "For folder / .mgc_file import, leave info_type omitted "
                        "(or set it to 'file'). For single files, omit info_type "
                        "so it is inferred from extension, or pass a content type "
                        "like 'password' / 'token' / 'api_key' / 'config' / 'text'."
                    ),
                )
            inferred_type = explicit_info_type
            is_capsule = (
                path_obj.suffix.lower() == ".json"
                and self._is_sealed_capsule_file(path_obj)
            )
        else:
            ext = path_obj.suffix.lower()
            # 1.5.4 phase6：密封胶囊必然是 .json，且带 ext03 + base64 密文 content。
            # 先探测再决定类型，避免把胶囊当成普通 config 存进去导致无法解封。
            # friction fix: 探测结果留着复用，别读两遍文件。
            is_capsule = ext == ".json" and self._is_sealed_capsule_file(path_obj)
            if is_capsule:
                inferred_type = "script"
            elif ext in (".py", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd"):
                inferred_type = "script"
            elif ext in (".json", ".yaml", ".yml", ".toml", ".ini", ".conf"):
                inferred_type = "config"
            elif ext in (".md", ".txt", ".log", ".csv"):
                inferred_type = "text"
            else:
                inferred_type = "text"

        save_args["info_type"] = inferred_type
        save_args["content"] = content_str
        # 1.5.4 phase6：单文件默认把文件名写进 diff_1（而非 diff_3），这样胶囊
        # 自带的 diff_2 / diff_3 不会被文件名覆盖掉。
        # friction fix: 胶囊的 diff_* 来自源记录，不该被本地文件名污染——
        # diff_1 的语义是业务描述，文件名属于 diff_3。填错会让 mgc_run 按
        # diff_1 定位时错位（实测报NOT_FOUND）。
        if inferred_type == "script":
            if not is_capsule and not save_args.get("diff_1"):
                save_args["diff_1"] = path_obj.stem
            if not save_args.get("diff_3"):
                save_args["diff_3"] = path_obj.stem
        else:
            # Default diff_3 to the file name (including extension) so the record is
            # identifiable, and so detect_script_platform's file_suffix fallback
            # branch can match by extension.
            if not save_args.get("diff_3"):
                save_args["diff_3"] = path_obj.name
        if explicit_update is not None:
            save_args["update_if_exists"] = explicit_update
        else:
            save_args["update_if_exists"] = False  # single-file default (matches mgc_save)

        return self._do_save(save_args)

    @staticmethod
    def _is_sealed_capsule_file(path_obj) -> bool:
        """1.5.4 phase6: does this file hold a sealed capsule payload?

        Uses the same parser the API uses, so save_file classifies a capsule
        exactly the way mgc_save would.
        """
        from mgc.core.mgc_service.sealed_payload_parser import parse_sealed_payload
        try:
            raw = path_obj.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        return parse_sealed_payload(raw) is not None

    @staticmethod
    def _format_save_warning(warning: Optional[str]) -> str:
        """
        Convert API warning code to English user-facing message.

        Message text presents each entry as `extNN(<business name>): <detail>`
        so callers can map the warning directly to the stored field without
        consulting an external legend. The dict key (`ext02`) and warning
        code (`args`) remain unchanged.
        """
        if not warning:
            return ""
        mapping = {
            "args_recognized": "ext02(args): auto-recognized from script.",
            "args_not_recognized": (
                "ext02(args): dynamic defaults could not be auto-recognized from the script. "
                "Re-save this script via mgc_save (update mode) with static "
                "argparse default values, so mgc_run can carry forward the args."
            ),
            "dynamic_args_detected": (
                "ext02(args): script contains dynamic defaults that MGC cannot extract. "
                "Re-save this script via mgc_save (update mode) after replacing the "
                "dynamic defaults with static literals, to enable mgc_run with custom args."
            ),
            "ext05_missing": "ext05(depends): no dependency analysis available for this record.",
            "ext06_missing": "ext06(platform): no platform list available for this record.",
        }
        return mapping.get(warning, "")

    def _do_skill(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_skill - Return the full skill document (markdown).

        Tries the WebUI endpoint first (same source the human sees on /skill);
        falls back to local file paths if WebUI is not running.
        """
        # 1) Try WebUI
        webui_text = self._fetch_skill_from_webui()
        if webui_text is not None:
            return ToolResult(
                success=True,
                content=webui_text,
                hint="Source: WebUI /api/skill/content",
            )

        # 2) Fallback: read directly from disk
        try:
            from mgc.config.path_config import DOCS_DIR, REPO_ROOT, SKILLS_DIR
        except ImportError:
            return ToolResult(
                success=False,
                error="Cannot resolve skill document paths (path_config unavailable).",
            )
        candidates = [
            SKILLS_DIR / "mgc_skill.md",               # runtime copy (synced at startup)
            DOCS_DIR / "skill_spec.md",                 # runtime docs
            REPO_ROOT / "docs" / "skill_spec.md",       # source package (dev env)
        ]
        for path in candidates:
            try:
                if path.exists():
                    return ToolResult(
                        success=True,
                        content=path.read_text(encoding="utf-8"),
                        hint=f"Source: {path}",
                    )
            except OSError:
                continue
        return ToolResult(
            success=False,
            content="",
            error="skill_spec.md not found in SKILLS_DIR, DOCS_DIR, or REPO_ROOT/docs.",
        )

    def _fetch_skill_from_webui(self) -> Optional[str]:
        """Try fetching /api/skill/content from WebUI; return None if unreachable."""
        import socket
        port: Optional[int] = None
        for candidate in range(57218, 57199, -1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.3)
                    s.connect(("127.0.0.1", candidate))
                    port = candidate
                    break
            except (OSError, socket.timeout):
                continue
        if port is None:
            return None
        try:
            r = requests.get(
                f"http://127.0.0.1:{port}/api/skill/content",
                timeout=3,
            )
            r.raise_for_status()
            return r.text
        except Exception:
            return None

    def _do_get(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_get"""
        # Pass all parameters like mgc_save does
        data = {
            k: v for k, v in args.items()
            if v is not None and k != "name"
        }
        response = self._make_request("POST", "/api/mgc/sensitive/get", data)

        # Handle string response (e.g., error messages)
        if isinstance(response, str):
            return ToolResult(
                success=False,
                content=response,
                error="API returned string instead of dict"
            )

        code = response.get("code")
        # v1.4 新增: 透传 warning 字段（save/runner api 返回的提示）
        warning = response.get("warning")
        # 1.5.0: pass through structured advisory warnings from response.data.warnings
        # (see mgc.core.mgc_service.api_router._attach_warnings).
        data = response.get("data")
        if isinstance(data, dict):
            structured_warnings = data.get("warnings")
            # Serialize the data dict as JSON so MCP clients see a
            # human-readable JSON string instead of Python repr().
            content_str = json.dumps(data, ensure_ascii=False)
        elif data is None:
            structured_warnings = None
            content_str = ""
        else:
            structured_warnings = None
            content_str = str(data)
        if code == 200:
            return ToolResult(
                success=True,
                content=content_str,
                hint=response.get("hint"),
                warning=warning,
                warnings=structured_warnings,
            )
        elif code == 201:
            return ToolResult(
                success=True,
                content=str(response.get("data", [])),
                hint=response.get("hint"),
                warning=warning,
                warnings=structured_warnings,
            )
        elif code == 404:
            return ToolResult(
                success=False,
                content="",
                error="NOT_FOUND",
                hint=response.get("hint"),
                warning=warning,
                warnings=structured_warnings,
            )
        else:
            return ToolResult(
                success=False,
                content="",
                error=response.get("msg", "Get failed"),
                hint=response.get("hint"),
                warning=warning,
                warnings=structured_warnings,
            )

    @staticmethod
    def _detect_ext04_alias(args: Dict[str, Any], tool_name: str) -> Optional[ToolResult]:
        """1.5.4 phase6 friction fix: 检出 ext04 的常见错拼别名。

        ext04 是 p2p / free mode 的唯一开关。别名不在 schema 里，会被静默
        丢弃 —— 调用方以为做了节点绑定，实际产出free mode 制品，任何
        1.5.4+ 节点都能解封。这里改成显式报错，不做自动映射：别名表永远
        补不完，且"忘了传"与"故意用别名"必须区分开。
        """
        for alias in _EXT04_ALIASES:
            if not args.get(alias):
                continue
            return ToolResult(
                success=False,
                content="",
                error=f"UNKNOWN_PARAM: {alias}",
                hint=(
                    f"'{alias}' is not a parameter of {tool_name} and was ignored. "
                    f"Did you mean 'ext04'? Pass the target node's PEM public key as "
                    f"ext04 to produce a p2p-mode artifact. Omitting ext04 produces a "
                    f"FREE-MODE artifact, which ANY MGC 1.5.4+ node can unseal and run. "
                    f"Fetch the canonical multi-line PEM with mgc_get("
                    f"info_type='__NODE_PUB__', info_owner='__NODE_PUB__') on the "
                    f"target node."
                ),
            )
        return None

    def _do_seal(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_seal - Seal a script for external node execution."""
        # Pass all parameters like mgc_save does
        data = {
            k: v for k, v in args.items()
            if v is not None and k != "name"
        }
        data["action"] = "SEAL"
        data = {k: v for k, v in data.items() if v is not None}

        # info_type defaults to 'script' — the schema promises this default,
        # but the backend has no default handling: an empty info_type makes
        # api_router treat the request as a LIST query (LIST_RETRIEVED) and
        # the SEAL branch is never reached. Fill it in here, mirroring
        # mgc_run's server-side injection (see call_tool 'mgc_run').
        if not str(data.get("info_type") or "").strip():
            data["info_type"] = "script"

        # Validate required params
        if not data.get("info_owner"):
            return ToolResult(
                success=False,
                content="",
                error="Missing required param: info_owner"
            )
        # 1.5.4 phase6: output_dir is required -- the desktop location differs
        # across platforms, so there is no safe fallback path.
        if not str(data.get("output_dir") or "").strip():
            return ToolResult(
                success=False,
                content="",
                error="Missing required param: output_dir",
                hint=(
                    "output_dir is required: pass an absolute directory to write the "
                    "sealed capsule into. MGC creates a timestamped subfolder "
                    "'<info_owner>_<YYYYMMDD_HHMMSS>/sealed_capsule.json' inside it. "
                    "There is no desktop fallback because the desktop location "
                    "differs across platforms."
                ),
            )
        # ext04 is optional: empty string (or omitted) means free mode.
        # The backend's SealRequest.ext04 is Optional[str] and routes to
        # p2p / free mode automatically.
        alias_hit = self._detect_ext04_alias(args, "mgc_seal")
        if alias_hit:
            return alias_hit

        response = self._make_request("POST", "/api/mgc/sensitive/get", data)
        
        # Handle string response (e.g., error messages)
        if isinstance(response, str):
            return ToolResult(
                success=False,
                content=response,
                error="API returned string instead of dict"
            )
        
        code = response.get("code")
        if code == 200 and response.get("data"):
            sealed = response.get("data", {})
            # 1.5.4 phase6: the capsule is self-describing -- identity triple
            # plus every ext field plus the encrypted body. Forward all of it.
            result_json = {"content": sealed.get("content", "")}
            for field in ("info_type", "info_owner", "diff_1", "diff_2", "diff_3"):
                if field in sealed:
                    result_json[field] = sealed[field]
            for i in range(1, 31):
                ext_key = f"ext{i:02d}"
                if ext_key in sealed:
                    result_json[ext_key] = sealed[ext_key]
            # delivery_path / capsule_path are local filesystem pointers, not
            # part of the portable payload.
            capsule_path = sealed.get("capsule_path", "")
            if capsule_path:
                result_json["capsule_path"] = capsule_path
            import json
            result_str = json.dumps(result_json, indent=2, ensure_ascii=False)
            return ToolResult(
                success=True,
                content=result_str,
                hint=response.get("hint") or (
                    "Sealed capsule written to disk. To persist it, call "
                    "mgc_save_file(path=<capsule_path>, info_owner='<your owner>') "
                    "-- MGC auto-parses every field and infers the type; no ext "
                    "field needs forwarding. Pass a different info_owner than the "
                    "source if you want to keep the source record on this node."
                ),
            )
        else:
            # Detect common PEM formatting errors and provide a clearer hint
            err_msg = response.get("msg", "Seal failed")
            hint = response.get("hint", "Extract content and ext fields from result JSON and use mgc_save with info_type=script to persist sealed data. The receiving node needs ext05/ext06 (auto-identified dependency list and compatible-platform list) for runtime advisory.")
            if "PEM" in err_msg or "pre boundary" in err_msg or "RSA" in err_msg:
                hint = (
                    "ext04 (PEM public key) format looks invalid. "
                    "The key MUST be a multi-line PEM with REAL newline characters "
                    "between the header, each base64 line, and the footer. "
                    "Do NOT pass as a single concatenated line. "
                    "Use mgc_get with info_type='__NODE_PUB__' AND info_owner='__NODE_PUB__' to fetch the canonical multi-line PEM, "
                    "then pass it verbatim to ext04."
                )
            return ToolResult(
                success=False,
                content="",
                error=err_msg,
                hint=hint
            )

    def _do_list(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_list with optional search params (LIKE wildcards supported).

        1.4.10 update: prefers LIKE exact or pattern matching (users may write
        %test%). For new code, mgc_find is recommended — it auto-applies
        wildcards via match_mode and does not require manual % syntax.
        """
        data = {
            "info_type": args.get("info_type"),
            "info_owner": args.get("info_owner"),
            "diff_1": args.get("diff_1"),
            "diff_2": args.get("diff_2"),
            "diff_3": args.get("diff_3")
        }
        data = {k: v for k, v in data.items() if v is not None}
        response = self._make_request("POST", "/api/mgc/sensitive/get", data)
        code = response.get("code")
        if code == 201:
            info_list = response.get("data", {}).get("info_list", [])
            # 1.6.0：mgc_list 只返回定位字段（info_owner/info_type/diff_1..3）。
            # ext03/ext07 等长字段对「列出有哪些记录」无用却占 60% 体积。
            filtered_list = self._filter_index_fields(info_list)
            hint = response.get("hint")
            if hint is None:
                hint = "For fuzzy / substring search use mgc_find."
            # 说明这是精简索引，避免 agent 误以为 ext 字段缺失
            hint = (
                f"{hint} "
                "Only identifying fields are listed (info_owner / info_type / "
                "diff_1..3). Use mgc_get with an exact info_type + info_owner "
                "to read content or ext fields of one record."
            )
            return ToolResult(
                success=True,
                content=str(filtered_list),
                hint=hint
            )
        else:
            return ToolResult(
                success=False,
                content="",
                error=response.get("msg", "List failed"),
                hint=response.get("hint")
            )

    def _do_find(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_find with fuzzy search (auto-applies LIKE wildcards).

        1.4.10 MCP tool: fuzzy search counterpart to mgc_list. Applies
        LIKE wildcards based on match_mode (substring/prefix/suffix/exact)
        so users do not need to write % explicitly. limit defaults to 100.
        """
        match_mode = args.get("match_mode", "substring")
        limit = args.get("limit", 100)

        # Per-field LIKE pattern based on match_mode
        def _apply_pattern(value: str) -> str:
            if match_mode == "prefix":
                return f"{value}%"
            elif match_mode == "suffix":
                return f"%{value}"
            elif match_mode == "exact":
                return value
            else:  # substring (default)
                return f"%{value}%"

        data = {}
        # 1.5.0 (PR-7): mgc_find no longer accepts info_type. Pass info_owner / diff_1..3 only.
        for field in ("info_owner", "diff_1", "diff_2", "diff_3"):
            val = args.get(field)
            if val is not None:
                data[field] = _apply_pattern(val)
        # Note: API doesn't accept a "limit" param directly; we'll truncate client-side.
        response = self._make_request("POST", "/api/mgc/sensitive/get", data)
        code = response.get("code")
        if code == 201:
            info_list = response.get("data", {}).get("info_list", [])
            filtered_list = self._filter_empty_fields(info_list)
            if limit and len(filtered_list) > limit:
                filtered_list = filtered_list[:limit]
            return ToolResult(
                success=True,
                content=str(filtered_list),
                hint=response.get("hint")
            )
        else:
            err = response.get("msg", "Find failed")
            hint = response.get("hint")
            # 1.5.0 (PR-7): if the agent didn't pass info_owner at all,
            # nudge it explicitly so it picks the right tool.
            if "info_owner" not in args or not args.get("info_owner"):
                hint = (
                    "mgc_find requires `info_owner` (or diff_1..3). "
                    "It does NOT accept `info_type` as a filter. "
                    "To list by info_type, use mgc_list or mgc_get (omit info_owner)."
                )
            return ToolResult(
                success=False,
                content="",
                error=err,
                hint=hint
            )

    def _filter_empty_fields(self, items: list) -> list:
        """Filter empty fields, keep original structure"""
        from typing import List, Dict
        filtered = []
        for item in items:
            filtered_item = {}
            for key, value in item.items():
                if key in ("info_type", "info_owner"):
                    filtered_item[key] = value
                elif value not in ("", None, "None"):
                    filtered_item[key] = value
            filtered.append(filtered_item)
        return filtered

    # 1.6.0：MCP 索引查询（mgc_list）只返回「定位记录所需的定位字段」。
    #
    # 背景：ext03（RSA 包裹的 AES 密钥材料，实测 ~195 bytes/条）与
    # ext07（源节点 PEM 公钥，~188 bytes/条）合计占列表返回体积的 60%，
    # 但对「列出有哪些记录」这个用途完全无用 —— agent 要读内容或 ext 字段
    # 时会用 mgc_get 精确取单条。
    #
    # 只做 MCP 展示层裁剪：REST API 与 WebUI 仍返回完整记录，不受影响。
    _INDEX_FIELDS = ("info_owner", "info_type", "diff_1", "diff_2", "diff_3")

    def _filter_index_fields(self, items: list) -> list:
        """索引查询结果瘦身：只保留定位字段的非空值。

        白名单模式（而非只剔除空值）：ext03 / ext07 / ext08 等长字段
        对「找记录」无用却占绝大部分体积。

        Args:
            items: API 返回的 info_list

        Returns:
            每条只含 info_owner / info_type / diff_1..3 中非空字段的列表
        """
        filtered = []
        for item in items:
            if not isinstance(item, dict):
                continue
            filtered.append({
                key: item[key]
                for key in self._INDEX_FIELDS
                if key in item and item[key] not in ("", None, "None")
            })
        return filtered

    def _do_open_webui(self) -> ToolResult:
        """Execute mgc_open_webui - Open WebUI"""
        import socket

        def find_webui_port() -> Optional[int]:
            """Find WebUI port by scanning downward from 57218"""
            for port in range(57218, 57199, -1):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(0.5)
                        s.connect(("127.0.0.1", port))
                        return port
                except (OSError, socket.timeout):
                    continue
            return None

        def start_webui() -> int:
            """Start WebUI and return port"""
            from mgc.presentation.interaction.webui_dialog import WebuiDialog
            dialog = WebuiDialog()
            dialog._start_webui_service()
            return dialog._port

        try:
            port = find_webui_port()
            if port is None:
                port = start_webui()

            webbrowser.open(f"http://127.0.0.1:{port}/")
            return ToolResult(
                success=True,
                content=f"WebUI opened at http://127.0.0.1:{port}",
                hint="You can manage stored information visually in the browser. Close the browser tab when done."
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Failed to open WebUI: {str(e)}"
            )

    # mgc_delete — single-record exact-match or folder-level delete.
    #
    # Strategy:
    #   1. Validate required fields (info_type, info_owner).
    #   2. Reject protected node-credential types client-side (the backend
    #      also refuses; this gives a friendlier error and avoids a DB roundtrip).
    #   3. Use the same listing path as mgc_list with the exact (non-LIKE)
    #      address to count matches, mirroring the WebUI's delete behaviour.
    #   4. If exactly 1 match — call /api/mgc/sensitive/delete and report
    #      deleted_count=1 with the matched record's metadata.
    #   5. If 0 — return code=200 + deleted_count=0 + a NOT_FOUND hint.
    #   6. If ≥2 — refuse in single-record mode. The backend's folder-level
    #      delete removes every record matching the (info_type, info_owner,
    #      diff_2) triple, so escalation requires explicit approval of the
    #      candidate list and a re-call with `confirm_folder_delete="true"`
    #      (the STRING value, see schema).
    _PROTECTED_INFO_TYPES = (
        "__NODE_PUB__",
        "__NODE_PRIV__",
        "__DEFAULT_NODE_PUB__",
        "__DEFAULT_NODE_PRIV__",
    )

    def _do_delete(self, args: Dict[str, Any]) -> ToolResult:
        info_type = (args.get("info_type") or "").strip()
        info_owner = (args.get("info_owner") or "").strip()
        diff_1 = args.get("diff_1") or ""
        diff_2 = args.get("diff_2") or ""
        diff_3 = args.get("diff_3") or ""
        # Explicit user-confirmed folder-level delete. Must be the STRING "true"
        # (or any case-insensitive variant / "1") to delete more than 1 record
        # at once. Approval of the candidate list must be obtained first;
        # never set this to "true" on the caller's own.
        #
        # Encoding the flag as a string (default "") avoids a type-coercion
        # issue at schema validation. See confirm_folder_delete schema
        # description for the accepted value set.
        confirm_folder_delete_raw = str(
            args.get("confirm_folder_delete", "") or ""
        ).strip().lower()
        confirm_folder_delete = confirm_folder_delete_raw in ("true", "1")

        # 1) Required fields
        if not info_type or not info_owner:
            return ToolResult(
                success=False,
                content="",
                error="MISSING_REQUIRED_FIELDS",
                hint="mgc_delete requires `info_type` and `info_owner` (both non-empty strings). diff_1, diff_2, diff_3 are optional — pass empty string when not used.",
            )

        # 2) Protected node credentials — refused early with friendly message.
        if info_type in self._PROTECTED_INFO_TYPES:
            return ToolResult(
                success=False,
                content="",
                error="PROTECTED_RECORD",
                hint=f"info_type='{info_type}' is a node-credential record and cannot be deleted via mgc_delete. These are auto-generated at mgc initialization and protected.",
            )

        # 3) Count matches via the list endpoint.
        # We intentionally OMIT `info_type` from the list payload so the
        # backend's `/api/mgc/sensitive/get` routes to its LIST branch (code=201).
        # When BOTH info_type and info_owner are non-empty, the backend falls into
        # its single-record DECRYPT branch (code=200, "Decrypted from MGC") instead.
        # We re-apply the info_type filter in-memory on the returned candidates.
        list_payload = {
            "info_owner": info_owner,
            "diff_1": diff_1,
            "diff_2": diff_2,
            "diff_3": diff_3,
        }
        list_resp = self._make_request("POST", "/api/mgc/sensitive/get", list_payload)
        # _make_request may return a string error on non-JSON responses
        if isinstance(list_resp, str):
            return ToolResult(
                success=False,
                content="",
                error="LIST_QUERY_FAILED",
                hint=f"Could not verify unique match: {list_resp}",
            )
        if list_resp.get("code") != 201:
            return ToolResult(
                success=False,
                content="",
                error=list_resp.get("msg", "LIST_QUERY_FAILED"),
                hint=list_resp.get("hint"),
            )
        raw_candidates = (
            list_resp.get("data", {}).get("info_list", [])
            if isinstance(list_resp.get("data"), dict)
            else []
        )
        # Apply the requested info_type AND info_owner filters in-memory so the
        # match count reflects the user-supplied (info_type, info_owner,
        # diff_*) tuple. info_owner is filtered with STRICT equality here
        # even though the backend uses LIKE, otherwise candidates can include
        # records from a similarly-named owner.
        candidates = [
            c for c in raw_candidates
            if isinstance(c, dict)
            and c.get("info_type") == info_type
            and c.get("info_owner") == info_owner
        ]

        # 4) Decide based on match count.
        if len(candidates) == 0:
            return ToolResult(
                success=True,
                content="",
                hint=(
                    "NOT_FOUND — 0 records matched the supplied 6-tuple "
                    "(info_type, info_owner, diff_1, diff_2, diff_3). "
                    "No deletion happened. Run mgc_find to locate similar entries, "
                    "then retry mgc_delete with the exact address fields. "
                    "If you were trying to delete a FOLDER, note that its records "
                    "are stored under separate info_types — call mgc_list to see "
                    "which ones exist, then delete each type separately."
                ),
            )
        if len(candidates) > 1:
            # Ambiguous: the (info_type, info_owner, diff_2) triple defines a
            # folder with multiple records. Escalation requires explicit
            # approval of the candidate list and a re-call with
            # confirm_folder_delete="true" (the STRING value, see schema).
            if not confirm_folder_delete:
                candidate_summary = [
                    {
                        "diff_3": c.get("diff_3", ""),
                        "diff_1": c.get("diff_1", ""),
                    }
                    for c in candidates
                ]
                return ToolResult(
                    success=True,
                    content="",
                    error="FOLDER_DELETE_REQUIRES_USER_CONFIRMATION",
                    hint=(
                        f"MULTIPLE_MATCHES — {len(candidates)} records share the same "
                        f"(info_type='{info_type}', info_owner='{info_owner}', "
                        f"diff_2='{diff_2}') folder. The backend's delete is folder-level "
                        f"(it removes every record under this triple), so mgc_delete refuses "
                        f"to act without explicit approval. "
                        f"Present the candidate list and request approval to delete all "
                        f"{len(candidates)} records under this folder; after approval, re-call "
                        f"mgc_delete with the same info_type / info_owner / diff_2 and add "
                        f"`confirm_folder_delete=\"true\"` (the STRING value, not a JSON boolean). "
                        f"The flag must never be set on the caller's own."
                    ),
                    saved=candidate_summary,
                )
            # confirm_folder_delete == "true" → approval received. Proceed with folder-level delete.
            del_payload = {
                "info_type": info_type,
                "info_owner": info_owner,
                "diff_1": diff_1,
                "diff_2": diff_2,
                "diff_3": diff_3,
            }
            del_resp = self._make_request("POST", "/api/mgc/sensitive/delete", del_payload)
            if isinstance(del_resp, str):
                return ToolResult(
                    success=False,
                    content="",
                    error="DELETE_REQUEST_FAILED",
                    hint=f"Delete call failed: {del_resp}",
                )
            code = del_resp.get("code")
            if code in (200, 201):
                deleted_payloads = [
                    {
                        "info_type": info_type,
                        "info_owner": info_owner,
                        "diff_1": c.get("diff_1", diff_1),
                        "diff_2": c.get("diff_2", diff_2),
                        "diff_3": c.get("diff_3", diff_3),
                    }
                    for c in candidates
                ]
                return ToolResult(
                    success=True,
                    content=f"Folder-level delete: removed {len(deleted_payloads)} records under (info_type='{info_type}', info_owner='{info_owner}', diff_2='{diff_2}').",
                    hint=(
                        "Folder-level delete is complete. Every record under "
                        "the (info_type, info_owner, diff_2) triple has been removed "
                        "from MGC; each deletion is recorded in mgc_operation_logs "
                        "(operation_type='DELETE'). The saved[] list below shows what was removed."
                    ),
                    saved=deleted_payloads,
                )
            return ToolResult(
                success=False,
                content="",
                error=del_resp.get("msg", "DELETE_FAILED"),
                hint=del_resp.get("hint"),
            )

        # 6) Exactly 1 match → perform the single-record deletion.
        matched = candidates[0]
        del_payload = {
            "info_type": info_type,
            "info_owner": info_owner,
            "diff_1": diff_1,
            "diff_2": diff_2,
            "diff_3": diff_3,
        }
        del_resp = self._make_request("POST", "/api/mgc/sensitive/delete", del_payload)
        if isinstance(del_resp, str):
            return ToolResult(
                success=False,
                content="",
                error="DELETE_REQUEST_FAILED",
                hint=f"Delete call failed: {del_resp}",
            )
        code = del_resp.get("code")
        if code in (200, 201):
            deleted_payload = {
                "info_type": info_type,
                "info_owner": info_owner,
                "diff_1": matched.get("diff_1", diff_1),
                "diff_2": matched.get("diff_2", diff_2),
                "diff_3": matched.get("diff_3", diff_3),
            }
            return ToolResult(
                success=True,
                content="Deleted 1 record.",
                hint=(
                    "Deletion is permanent. The record has been removed from MGC "
                    "and recorded in mgc_operation_logs (operation_type='DELETE')."
                ),
                # Reuse the saved list shape so callers can inspect what was deleted.
                saved=[deleted_payload],
            )

        # Backend refused (shouldn't happen often given the upfront checks).
        return ToolResult(
            success=False,
            content="",
            error=del_resp.get("msg", "DELETE_FAILED"),
            hint=del_resp.get("hint"),
        )


def _render_folder_save_extras(result: "ToolResult") -> str:
    """1.5.0 (2026-09-03 方案A MCP 透传)：把 folder save 的 saved/failed 渲染到 MCP 文本输出。

    渲染规则：
    - 如果 result.saved 是 List[dict]（folder save 新结构），则追加紧凑 JSON
      （每条记录中的空字符串字段会被过滤掉，避免噪音）
    - 如果 result.saved_diff3 是 List[str]，则同时追加 diff_3 列表（向后兼容）
    - 如果 result.failed 是 List[dict]，追加 failed 列表（同样过滤空字段）
    - 如果 saved 中有 warnings 含 "dynamic_args_detected" 或 "args_not_recognized"，
      追加英文提示，告知用户手动重新存入脚本并将 args 写入 ext02

    Args:
        result: _do_save 返回的 ToolResult

    Returns:
        拼接好的字符串（以换行开头），无内容时返回 ""
    """

    def _strip_empty(items):
        """对 List[dict] 应用空字段过滤（与 _filter_empty_fields 一致：保留
        非空 value；list/dict 非空保留，空 list/dict 过滤）。
        """
        if not items:
            return items
        cleaned = []
        for item in items:
            if not isinstance(item, dict):
                cleaned.append(item)
                continue
            entry = {}
            for k, v in item.items():
                # list / dict：空则过滤；非空保留（warnings 列表即使为空 [] 也过滤掉）
                if isinstance(v, (list, dict)):
                    if v:  # truthy: non-empty list/dict
                        entry[k] = v
                elif v in ("", None, "None"):
                    continue
                else:
                    entry[k] = v
            cleaned.append(entry)
        return cleaned

    parts: List[str] = []

    # 1. saved 列表（含每条记录的 ext01-06 / warnings）— 过滤空字段
    if result.saved:
        try:
            saved_stripped = _strip_empty(result.saved)
            saved_json = json.dumps(saved_stripped, ensure_ascii=False, indent=2)
            parts.append("\nSaved records (with ext01/ext02/ext05/ext06/warnings):")
            parts.append(saved_json)
        except Exception:
            parts.append(f"\nSaved records: {result.saved}")

    # 2. saved_diff3 向后兼容字段
    if result.saved_diff3:
        parts.append(f"\nSaved diff_3 (backward compatible): {result.saved_diff3}")

    # 3. failed 列表 — 过滤空字段
    if result.failed:
        try:
            failed_stripped = _strip_empty(result.failed)
            failed_json = json.dumps(failed_stripped, ensure_ascii=False, indent=2)
            parts.append("\nFailed records:")
            parts.append(failed_json)
        except Exception:
            parts.append(f"\nFailed records: {result.failed}")

    # 4. 检测 dynamic_args_detected / args_not_recognized 时追加用户引导
    has_dynamic = False
    has_unrecognized = False
    if result.saved:
        for rec in result.saved:
            if not isinstance(rec, dict):
                continue
            warnings = rec.get("warnings") or []
            if "dynamic_args_detected" in warnings:
                has_dynamic = True
            if "args_not_recognized" in warnings:
                has_unrecognized = True
    if has_dynamic or has_unrecognized:
        advice = (
            "\nAdvisory: One or more scripts have dynamic or unrecognized args. "
            "If a script supports args, please re-save it via mgc_save "
            "(info_type='script', update_if_exists=true) with the real args "
            "written into ext02 as a JSON array string."
        )
        parts.append(advice)

    return "\n".join(parts)


def run_stdio():
    """Stdio transport main loop"""
    server = MgcServer()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = server.handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    run_stdio()