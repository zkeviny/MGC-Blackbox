---
spec: usk/3.0
id: cross_node_script_auth
version: 1.1.0
name: Cross‑Device Encrypted Script Authorization (Zero‑Exposure)
description: Zero‑exposure cross‑device script authorization using MGC Blackbox seal functionality. Scripts are encrypted with target node's RSA public key, transferred as ciphertext, and decrypted only during execution on the authorized node. Adapted to MGC 1.4.10 with mgc_run blackbox execution and ext02 auto-parsing.
author: MirginCipher Team
license: MIT
tags: security, cross-device, encryption, zero-exposure, mgc, authorization, seal, RSA, blackbox execution
platform_compatibility: windows, macos, linux
changelog:
  - version: 1.1.0
    changes:
      - Upgraded to adapt to MGC 1.4.10
      - Replaced mgc_get(action=run) with mgc_run (1.4.7+) for executing sealed scripts
      - Documented ext02 auto-parsing (1.4.10): argparse defaults are bundled into ext_02 during sealing
      - Fixed mgc_seal required parameters: info_type is optional, ext04 must be multi-line PEM
      - Added mgc_find fuzzy search tool
      - Updated node_pub retrieval flow: WebUI Settings → Node Public Key
      - Added update_if_exists for overwriting same-name scripts
      - Added brief note on 1.4.9 sandbox mode
  - version: 1.0.1
    changes:
      - Clarified lazy generation mechanism differences for node_pub (MCP/API vs WebUI)
  - version: 1.0.0
    changes:
      - Initial release for cross-device encrypted script authorization
---

# Overview

Cross‑Device Encrypted Script Authorization is a documentation skill that teaches how to **authorize script execution across devices without exposing plaintext**.

This skill enables:
- Seal scripts using target node's RSA public key
- Transfer encrypted scripts to authorized nodes
- Run sealed scripts on the authorized node via **blackbox execution**
- Build cross‑device trust chains

This skill contains **no executable code** and is safe for automatic approval.

---

# What This Skill Enables

After reading this documentation, an AI agent will understand how to:

- Fetch target node's RSA public key (`__NODE_PUB__`)
- Seal scripts via `mgc_seal` (with auto-extracted default arguments)
- Safely transfer the sealed capsule to the target node
- Store sealed scripts on the target node (including `ext03` RSA-wrapped AES key and `ext02` default args)
- Execute sealed scripts via `mgc_run` (1.4.7+) in blackbox mode
- Handle dependency consistency (credentials, files, environment variables)

---

# Prerequisites

1. **Install MGC Blackbox**: `pip install mgc-blackbox` (1.4.10+ recommended)
2. **Start MGC service**: `mgc` (runs at http://127.0.0.1:57219, WebUI at 57218)
3. **MCP tools available**: `mgc_save`, `mgc_run`, `mgc_seal`, `mgc_list`, `mgc_find`, `mgc_open_webui`
4. **Two MGC nodes**: One owner node and one authorized node; a single node can self-verify the flow
5. **Token file**: `~/.mgc/database/mgc_black_box/.mgc_token`

> **Sandbox mode (1.4.9+)**: When running inside a sandbox Agent (Trae Work / Workbuddy), install MGC in the system environment; otherwise MCP tool calls may be intercepted. The sealing flow of this skill still works, but MCP operations may be limited — in that case, call FastAPI directly.

---

# Core Concept

## Why Cross‑Device Authorization?

```
Traditional: Script Owner → Send Script (plaintext) → Authorized Node
MGC Way:    Script Owner → Seal with node_pub → Ciphertext → Authorized Node
                                            ↓
                                Always encrypted, never exposed
```

The script remains encrypted throughout:
- After sealing on the source node
- During network transfer
- During storage on the authorized node
- Decrypted only briefly in memory during blackbox execution

Sealed capsule structure (MGC 1.4.10):
```
{
  "content":  "AES-256 encrypted script body",
  "ext_01":   "Original startup command (e.g. python)",
  "ext_02":   "Original script default args (JSON array, auto-parsed by 1.4.10)",
  "ext_03":   "RSA-encrypted AES key (only the target node can decrypt)"
}
```

---

# Use Cases

## Use Case 1: Cross‑Organization Script Sharing

Organization A wants to share scripts with Organization B without exposing script content.

1. Organization B installs MGC and provides its `node_pub`
2. Organization A seals the script with `node_pub`
3. Organization B stores the sealed script and executes it

## Use Case 2: Trusted Partner Automation

A company wants to deliver automation scripts to partners without revealing the script logic.

1. Partner installs MGC and provides `node_pub`
2. Company seals script with partner's `node_pub`
3. Partner runs the sealed script locally in blackbox mode

## Use Case 3: Delegated Task Execution

A central server delegates tasks to edge devices without exposing task logic.

1. Edge device provides `node_pub` to the central server
2. Central server seals the task script
3. Edge device executes the sealed task

---

# Workflow

## Step 1: Get Target Node Public Key

The node that will run the sealed script must provide its RSA public key.

**Option A: Trigger lazy generation via MCP/API**
```python
# Fetch node public key via MCP (auto-generates keypair on first call)
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
```

**Option B: View via WebUI (1.4.7+)**
Open WebUI → skill page → Settings dropdown → **Node Public Key** → Copy multi-line PEM.
On Safari the browser will download a `.pem` file instead.

> **Critical requirement**: `node_pub` **must** be a **multi-line PEM** with real newlines:
> ```
> -----BEGIN PUBLIC KEY-----
> MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
> ...(base64 lines)...
> -----END PUBLIC KEY-----
> ```
> Single-line concatenation triggers MGC's "Invalid PEM format" error; copy verbatim from the `mgc_get` response.

## Step 2: Seal Script on Owner Node

The owner node seals the script using the target node's public key.

```python
# 1. Store the original script first (ext01 required; ext02 optional — MGC auto-parses argparse)
mgc_save(
    info_type="script",
    info_owner="my_script",
    ext01="python",
    content="import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('--name', default='World')\nargs = parser.parse_args()\nprint(f'Hello {args.name}')"
)

# 2. Seal the script with target node's public key
sealed = mgc_seal(
    info_owner="my_script",        # required: script identifier to seal
    # info_type optional, defaults to "script"
    ext04=node_pub                 # required: target node's multi-line PEM
)

# sealed is now a dict:
# {
#   "content": "<AES-encrypted script body>",
#   "ext_01":  "python",
#   "ext_02":  '["--name", "World"]',   # auto-parsed and bundled in 1.4.10
#   "ext_03":  "<RSA-encrypted AES key>"
# }
```

## Step 3: Transfer Sealed Capsule

Send the complete capsule to the authorized node. **All four fields** (content / ext_01 / ext_02 / ext_03) must travel together; otherwise the target node cannot execute.

```python
import json
payload = json.dumps(sealed, ensure_ascii=False)
# Send payload via email / USB / IM — any trusted channel
```

> **Note**: The capsule is ciphertext, but please use a trusted channel; MGC does not protect against tampering — only confidentiality.

## Step 4: Store Sealed Script on Target Node

The authorized node stores the sealed capsule into its local MGC. **Must write content + ext01 + ext02 + ext03 together**:

```python
# On the target (authorized) node
mgc_save(
    info_type="script",
    info_owner="partner_script",     # script identifier, recommended to match source
    ext01=sealed["ext_01"],          # startup command, e.g. "python"
    ext02=sealed["ext_02"],          # default args (from source's argparse)
    content=sealed["content"],       # AES-encrypted body
    ext03=sealed["ext_03"],          # RSA-wrapped AES key (only this node can decrypt)
    update_if_exists=True            # 1.4.10 new: allow overwriting same-name script
)
```

> **Why ext02 is required**: `ext02` is the default arg list auto-extracted from the source script's `argparse` at seal time. If the target node omits `ext02`, `mgc_run` launches with empty args and argparse falls back to the in-script defaults. But if the source had dynamic defaults (e.g. `os.path.expanduser("~")`), MGC raises `dynamic_args_detected` and you should explicitly pass `ext02`.

## Step 5: Execute Sealed Script (Blackbox)

The authorized node uses `mgc_run` (1.4.7+, recommended) to execute the sealed script in blackbox mode:

```python
# ✅ 1.4.10 recommended: use mgc_run
result = mgc_run(
    info_owner="partner_script",
    diff_1="partner_script",          # schema-required differentiation field; disambiguates multiple entries with same owner, any non-empty string works for a single entry
    ext02='["--name", "Alice"]'       # optional: runtime override of default args (JSON array string)
)
# Returns: {"pid": 12345, "status": "started"}
# Script is never exposed; AI only sees the start status
```

> **Backward compatibility**: `mgc_get(info_type="script", info_owner="...", action="run")` still works, but since 1.4.10 `mgc_run` is preferred for clearer intent.
> **Execution output**: `mgc_run` returns only `pid + status`, not stdout. For detailed results, the sealed script should write to a file and print the path on stdout (see "Dependency Requirements" below).

## Step 6: (Optional) List / Find Sealed Scripts

1.4.10 introduces `mgc_find` for fuzzy search:

```python
# List all script entries whose info_owner contains "partner"
scripts = mgc_find(
    info_owner="partner",
    match_mode="substring",          # substring / prefix / suffix / exact
    limit=50
)
# Returns metadata list — **never includes content plaintext**
```

---

# Dependency Requirements

When the sealed script runs on the target node, ensure dependencies are consistent:

| Dependency | How to Handle |
|------------|---------------|
| **MGC credentials** | Target node must store credentials with same `info_type` / `info_owner`; format consistent but content may vary by node |
| **External files** | Paths must be consistent; recommended to also store in MGC and pull via MGC API at runtime |
| **Environment variables** | Must be set on the target node |
| **Python libraries** | Target node must install the same library versions (recommend bundling `requirements.txt`) |
| **Cross-platform differences** | Use `pathlib.Path` or `/` separators; avoid platform-specific APIs (see [skill_spec.md §2 Scenario C](file:///D:/MirginCipher/mgc/docs/skill_spec.md)) |

> **Important**: Dependency mismatch is the most common cause of sealed script failures. Verify `info_type`/`info_owner`, environment variables, and file paths match between source and target before sealing.

---

# Security Notes

1. **Zero exposure**: Script is encrypted at rest and during transfer; decrypted only briefly in memory on the target node
2. **Blackbox execution**: Sealed scripts run in MGC's sandbox; AI cannot see script content
3. **One‑way sealing**: Once sealed, only the target node (holding the matching `node_priv`) can decrypt at runtime; no other node (including source) can
4. **Execution right ≠ ownership**: Target node can only execute; it cannot re-seal for a third party (because the AES key is bound to the target node's RSA key)
5. **No root protection**: A malicious root can read the decrypted body during execution; ensure the target node is trusted before authorizing
6. **Transport safety**: MGC does not verify capsule integrity; use a trusted channel to prevent man-in-the-middle tampering

---

# MCP Tools Reference

## mgc_get

**Get node public key:**
```json
{
  "info_type": "__NODE_PUB__",
  "info_owner": "__NODE_PUB__"
}
```

## mgc_run (1.4.7+, recommended for execution)

**Required:** `info_type="script"`, `info_owner`, `diff_1` (schema-required differentiation field; disambiguates multiple entries with same owner, any non-empty string works for a single entry)

**Execute sealed script:**
```json
{
  "info_type": "script",
  "info_owner": "partner_script",
  "diff_1": "partner_script",
  "ext02": "[\"--name\", \"Alice\"]"
}
```

**Returns:** `{ "pid": <int>, "status": "started" }`

## mgc_seal

**Required:** `info_owner`, `ext04`

**Arguments:**
```json
{
  "info_owner": "my_script",
  "info_type": "script",
  "diff_1": "optional",
  "diff_2": "optional",
  "diff_3": "optional",
  "ext04": "<target_node_pub_multi_line_PEM>"
}
```

**Returns (dict):**
```json
{
  "content":  "<AES encrypted body>",
  "ext_01":   "python",
  "ext_02":   "[\"--name\", \"World\"]",
  "ext_03":   "<RSA encrypted AES key>"
}
```

> **PEM format requirement**: `ext04` must be a multi-line PEM with real newlines (`\n`). If you see "Invalid PEM format", copy the value verbatim from `mgc_get(info_type='__NODE_PUB__')`.

## mgc_save

**Store original script:**
```json
{
  "info_type": "script",
  "info_owner": "my_script",
  "ext01": "python",
  "ext02": "[\"--name\", \"World\"]",
  "content": "script plaintext"
}
```

**Store sealed script (target node):**
```json
{
  "info_type": "script",
  "info_owner": "partner_script",
  "ext01": "python",
  "ext02": "[\"--name\", \"World\"]",
  "content": "<sealed content>",
  "ext03": "<sealed AES key>",
  "update_if_exists": true
}
```

> **1.4.10 new** `update_if_exists`: Set `true` to overwrite when `info_type + info_owner + diff_1/2/3` collide; otherwise returns an error.

## mgc_list / mgc_find (1.4.10 new)

```python
# mgc_list: exact match, meta-only
scripts = mgc_list()  # all entries' metadata (no content)

# mgc_find: fuzzy search, match_mode auto-applies LIKE wildcards
scripts = mgc_find(info_owner="partner", match_mode="substring", limit=50)
# match_mode: substring (%x%) / prefix (x%) / suffix (%x) / exact (x)
```

---

# Troubleshooting

| Issue | Solution |
|-------|----------|
| `mgc_seal` returns "Invalid PEM format" | `ext04` must be multi-line PEM with real newlines; copy verbatim from `mgc_get(info_type='__NODE_PUB__')` |
| `mgc_run` returns "args_not_recognized" | Source script's `argparse` was not recognized; verify `add_argument` usage or pass `ext02` explicitly |
| `mgc_save` returns `dynamic_args_detected` warning | Source script has dynamic defaults (e.g. `datetime.now()`, `os.path.expanduser`); use literal defaults or pass `ext02` manually |
| Target node credential not found | Credential `info_type/info_owner` differs from source node; unify naming before sealing |
| `mgc_run` returns `pid + started` but no script output | Expected: `mgc_run` only returns startup status; sealed script should write results to a file and print the path on stdout |
| Target node save fails on duplicate name | Add `update_if_exists=true` to overwrite; or use `mgc_find` to check and rename |
| WebUI has no node_pub entry | Confirm MGC ≥ 1.4.7; the entry is in the Settings dropdown on the skill page |
| MCP tools unavailable in sandbox mode | Install MGC in system environment, or call FastAPI directly at `/api/mgc/sensitive/run` |

---

# Links

- **Main Repository**: https://github.com/zkeviny/MGC-Blackbox
- **Issues**: https://github.com/zkeviny/MGC-Blackbox/issues
- **Contact**: mirgincipher@outlook.com
