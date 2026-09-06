---
```yaml
name: MGC Blackbox (Multi-Agent Cross-Node Privacy Execution Base)
id: mgc-blackbox
usk: 3.0
version: 1.5.0
author: MirginCipher Team
description: Local encrypted execution base for multi-agent, cross-node, privacy-preserving task execution. Zero-exposure layer for storing tokens, passwords, configs, and scripts — including sealed script packages for cross-device delegation.
tags:
  - security
  - credentials
  - encryption
  - zero-exposure
  - multi-agent
  - cross-node
  - privacy
  - sealed-package
  - workflow-delegation
mcp_tools:
  - mgc_save
  - mgc_save_file
  - mgc_get
  - mgc_run
  - mgc_find
  - mgc_list
  - mgc_seal
  - mgc_seal_package
  - mgc_package
  - mgc_open_webui
install: pip install mgc-blackbox
runtime: mgc
port: 57219
keywords:
  - credential management
  - secret management
  - token storage
  - zero trust
  - encrypted execution
  - multi-agent execution base
  - cross-node task delegation
  - privacy-preserving AI
  - sealed script package
  - workflow authorization
```

---

# 1. Overview — What MGC Blackbox Is

**MGC Blackbox is a Multi-Agent Cross-Node Privacy Execution Base.**

It is the encrypted execution layer *underneath* AI agents — not an agent itself. It lets AI agents, system scripts, and human users **store, execute, and delegate sensitive information, scripts, and entire workflows across trusted nodes without ever exposing plaintext.**

The core promise:

- **Store** sensitive data (tokens, passwords, configs).scripts (logic, workflows, automation).
- **Execute** stored scripts with structured `argparse` parameters.
- **Seal** individual scripts for cross-node delegation — the original owner keeps control, the target node can only execute.
- **Package** a folder of scripts and configs as a single unit, then **seal the package** so a target node can import and run the whole workflow with one import — solving cross-device path and dependency drift.
- **List** stored entries (metadata only, never plaintext).
- **Open WebUI** for human operations.

All data is encrypted locally with AES-256. **AI can execute but can not read the plaintext.**

---

# 2. Typical Scenarios — Why You'd Use MGC

> Read this section first. These scenarios are the reason MGC exists.
> The rest of the document is the technical reference.

---

## Scenario A — Store Once, Call Without Exposure

The base capability: put sensitive values or scripts into MGC, and downstream callers (AI agent, system script) can use them **without ever seeing the plaintext**. Two concrete examples:

### A.1 — Secret value (API key)

Store the key once with `info_type="token"`. Your script retrieves it by name at runtime. The plaintext key never appears in the script source, working directory, or command line.

```python
import os, requests, openai

with open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")) as f:
    MGC_TOKEN = f.read().strip()

resp = requests.post(
    "http://127.0.0.1:57219/api/mgc/sensitive/get",
    headers={"X-MGC-Token": MGC_TOKEN},
    json={"info_type": "token", "info_owner": "openai_api_key"},
)
resp.raise_for_status()
key = resp.json()["data"]

client = openai.OpenAI(api_key=key)
client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hello"}])
```

### A.2 — Script callable by AI

Store the script with `info_type="script"`. MGC parses its `argparse` and auto-fills `ext02` (default args). The AI agent then calls `mgc_run` with just an owner name + runtime args — it never sees the script source or its embedded credentials.

```bash
# Step 1: store once
mgc_save(
    info_type="script",
    info_owner="weather_report",
    ext01="python",
    content='
import argparse, requests
parser = argparse.ArgumentParser()
parser.add_argument("--city", default="Beijing")
parser.add_argument("--api_key", default=__import__("os").environ["OPENAI_KEY"])
args = parser.parse_args()
print(requests.get(f"https://wttr.in/{args.city}?format=j1", headers={"X-API-Key": args.api_key}).text)
'
)
# MGC auto-fills ext02 with ["--city", "Beijing"]

# Step 2: AI agent calls it (anytime, zero visibility)
mgc_run(info_owner="weather_report", ext02='["--city", "Shanghai"]')
# → { "pid": 12345, "status": "started" }
```

**Shared principle**: the caller knows only the owner name + args it passed. The plaintext, the encryption, and the storage details stay inside MGC.

### A.3 — Script calling another stored script

If you want 
Sometimes the workflow logic itself lives inside a stored script (e.g. a long-running pipeline that must run unattended, or a script that orchestrates others). In that case, the calling script invokes the called script **by its MGC location** — never by a local filesystem path. The local path may not exist on the target node, and rewriting script bodies to inject paths would defeat sealing.

**Rule**: cross-script calls inside a stored script MUST go through the MGC API, addressed by `info_type` + `info_owner` + `diff_*`.

```python
import os, requests

with open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")) as f:
    MGC_TOKEN = f.read().strip()

def call_script(info_owner: str, diff_1: str = "", ext01: str = "python",
                ext02: str | None = None) -> dict:
    """Invoke a stored script by its MGC location."""
    payload = {
        "info_type": "script",
        "info_owner": info_owner,
        "diff_1": diff_1,
        "action": "run",
        "ext01": ext01,
    }
    if ext02 is not None:
        payload["ext02"] = ext02
    r = requests.post(
        "http://127.0.0.1:57219/api/mgc/sensitive/get",
        headers={"X-MGC-Token": MGC_TOKEN, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

# Example: the calling script invokes another stored script by MGC location:
call_script(
    info_owner="send_email_via_mgc",   # the called script's MGC location
    diff_1="send_email_via_mgc",
    ext02='["--to", "alice@example.com", "--subject", "report"]',
)
```

For agent-driven sequencing of independent scripts, see Scenario C (the recommended pattern).

---

## Scenario B — Distribute a Sealed script / Workflow (Folder Package) Across MGC Nodes

Encrypt a stored payload — one script or an entire workflow folder — so a target MGC node can **execute but cannot read, modify, or redistribute the plaintext**. Use this whenever the source node and the target node are in different trust boundaries.

### Common handshake (both variants)

```
You (Node A)                        Target Node B
─────────────                       ─────────────
                                    1. mgc_get(info_type="__NODE_PUB__")
                                       → returns Node B's own public key (PEM)

2. Send the PEM string
   to Node A via any channel

3. <seal call>                      (nothing to do on B yet)
                                     4. <save call>
                                     5. mgc_run
                                        → Node B decrypts and runs.
```

The seal call and save call depend on whether you are distributing a single script or a folder — see the two variants.

### B.1 — Variant: single sealed script

Use when you only need to ship one `.py` (or `.sh`, `.bat`, etc.) to the target node.

```
3. mgc_seal(
     info_owner="my_report",
     ext04=<Node B's PEM public key>,
     info_type="script",
   )
   → sealed capsule:
     - AES-encrypted script body
     - AES key wrapped with Node B's RSA public key

4. Hand over capsule

                                     6. mgc_save & mgc_run
```

**Key invariant**: the AES key is bound to Node B's RSA key, so Node B cannot re-seal for Node C.

### B.2 — Variant: sealed folder package

If you want to ship your skill / workflow folder to a trusted node,you can seal the folder via MGC.

```
1. Build a folder like:

   my_workflow/
   ├── manifest.json      ← describes the workflow
   ├── run.py             ← entry script
   ├── helpers/
   │   ├── fetch.py
   │   └── parse.py
   └── config/
       └── settings.json

2. mgc_save_file(                     (source node only — nothing to do on B yet)
     path="/Users/alice/projects/my_workflow",
     info_owner="my_workflow",
     diff_2="my_workflow",
   )

3. mgc_seal_package(
     info_owner="my_workflow",
     diff_2="my_workflow",
     ext04=<Node B's public key>,
   )
   → sealed package

4. Hand over the sealed package

                                     5. agent read the README.md,and use mgc_save_file
                                     6. agent runs the workflow:
                                        - mgc_find(info_owner="my_workflow",
                                                   diff_2="my_workflow")
                                          → find records in the folder
                                        - mgc_get
                                          → read SKILL.md / manifest.json
                                        - mgc_run
                                          → run the entry script
```

**Plaintext alternative**: use `mgc_package` (instead of `mgc_seal_package`) for backup or human review inside the same trust boundary. Not for cross-node delegation.

### Pre-run check (both variants)

Before `mgc_run` on the target node, verify:

- dependencies in `ext05` are installed
- the OS in `ext06` is in the supported list

Otherwise the script may fail at runtime.

---

## Scenario C — Agent-Orchestrated Workflows

When the work is split across multiple stored scripts, **the recommended pattern is for the agent (human or AI) to drive the workflow**: call each script independently in sequence. Each `mgc_run` is self-contained; the agent passes the relevant args and reads the result.

For unattended workflows where the orchestration must run inside a stored script, see **A.3 — Script calling another stored script**.

If the workflow should also be encrypted for cross-node distribution, see **B.2 — Variant: sealed folder package**.

---

# 3. Installation & Runtime — How to Install and Run MGC

## 3.1 Requirements

- An MCP-compatible agent runtime (Claude Desktop, Cursor, Trae, etc.) for AI integration.
- A modern browser for WebUI access — also used for first-time setup (entering the **root key** that encrypts the local database) and for changing the root key later.

### Supported Python × OS matrix

| OS | Python 3.10 | Python 3.11 | Python 3.12 |
|---|---|---|---|
| Windows | ✅ | ✅ | ✅ |
| Linux (Ubuntu) | ✅ | ✅ | ✅ |
| macOS 14+ (Apple Silicon) | ✅ | ✅ | ❌ not supported |

## 3.2 Install MGC Blackbox

```bash
pip install mgc-blackbox
```

Ensure installation happens in the same Python environment where your MCP agent runs.

## 3.3 Run MGC in normal mode

Start MGC as a standalone local service:

```bash
mgc
```

Default behavior:

- Starts HTTP server at `http://127.0.0.1:57219`
- Initializes encrypted database on first run
- Generates access token at `~/.mgc/database/mgc_black_box/.mgc_token`

This token is required for all REST API calls.

## 3.4 Run MGC as an MCP server

If your agent supports MCP, configure:

```json
{
  "mcpServers": {
    "mgc-blackbox": {
      "command": "mgc",
      "args": ["--mcp"],
      "env": { "PYTHONIOENCODING": "utf-8" }
    }
  }
}
```

In MCP mode, MGC exposes the tools listed in §6. The REST API remains available for system scripts.

### Sandbox mode

MGC supports sandboxed environments, but some sandbox agents run MCP in the system environment rather than inside the sandbox. To use the MCP tools, install MGC in the system environment, or call the FastAPI directly.

## 3.5 WebUI access

WebUI is available at:

```
http://127.0.0.1:57218
```

Use the WebUI for initialization, manual storage, metadata inspection, database audit, and logs.

---

# 4. Invocation Model — Who Uses MGC and How

| Caller | Channel | Typical use |
|--------|---------|-------------|
| AI agent | MCP tools | Store / retrieve / run / seal / seal-package via structured function calls |
| System script or Sandboxed agents | REST API | Embed MGC lookups in CI jobs, scheduled tasks, internal services |
| Human | WebUI | First-time setup, manual entry, audit, deletion, logs |

---

# 5. The `ext_*` Protocol — Field Meanings

| Field | Role |
|-------|------|
| **ext01** | Startup command (e.g. `"python"`). Required for scripts at `mgc_save`; consumed by `mgc_run`. |
| **ext02** | Runtime args as a JSON array string, e.g. `'["--start", "2026-08-08"]'`. Auto-filled by the `argparse` parser on `mgc_save`; can be overridden per `mgc_run`. Passed to `subprocess.run()` verbatim. |
| **ext03** | Sealed AES key (RSA-encrypted). Set by `mgc_save` after `mgc_seal` / `mgc_seal_package`; consumed by `mgc_run` for sealed scripts. |
| **ext04** | Target node public key (PEM). Required only when sealing (`mgc_seal` / `mgc_seal_package`). |
| **ext05** | Third-party dependency list (JSON array, e.g. `["requests","yaml"]`). Auto-filled from Python AST / Node.js imports for `info_type=script` and for every script inside a folder package; caller-supplied values take priority. **MGC does NOT install dependencies** — displayed as runtime advisory only. |
| **ext06** | Compatible platform list (JSON array, e.g. `["windows","macos","linux"]`). Auto-filled from path patterns + platform condition branches; static inference only. Same auto-fill rules as `ext05`. |
| **ext07** | Source node public key (PEM). Auto-populated by `mgc_seal_package` and recorded in `MGCFILE.json` for provenance. You do not set it manually. |

---

# 6. MCP Tools — Quick Reference

> For full argument schemas, field types, and return shapes, see the MCP server's auto-generated schema (every MCP client surfaces it; AI agents read it directly). 

## 6.1 REST API — System / Script Integration

For system scripts and CI integrations that cannot use MCP.

**Base URL:** `http://127.0.0.1:57219`
**Header:** `X-MGC-Token: <token>` (token file: `~/.mgc/database/mgc_black_box/.mgc_token`)

| Endpoint | Body / params | Purpose |
|----------|---------------|---------|
| `POST /api/mgc/sensitive/save` | `info_type`, `info_owner`, `content`, `ext01`-`ext07`, `diff_1`-`diff_3` | Store an entry. **`info_type="script"`** → `content` is the script body. **`info_type="file"`** → `content` is the **absolute path to a local folder** (MGC scans it and auto-fills per-script `ext01`/`ext02`/`ext05`/`ext06`). **`info_type="file"` + `content` ending in `.mgc_file`** → import a sealed package from another MGC node. **Path-aware "I have a file on disk" save is exposed only via the MCP tool `mgc_save_file`** (not as a separate REST endpoint); for direct API use, read the file yourself and POST to `/api/mgc/sensitive/save` with the actual content string. |
| `POST /api/mgc/sensitive/get` | `info_type`, `info_owner`, `diff_1`-`diff_3`, optional `action` | Retrieve / list / operate on an entry. See `action` values below. |
| `POST /api/mgc/sensitive/get` | empty body | List all stored entries (metadata only) |
| `POST /api/mgc/sensitive/get` | `action="run"` + `info_type="script"` | Execute a stored script (mirror of `mgc_run`). Returns `pid + status`. |
| `POST /api/mgc/sensitive/get` | `action="package"` + `info_type="file"` | Export a stored folder as a plaintext archive (mirror of `mgc_package`). |
| `POST /api/mgc/sensitive/get` | `action="seal_package"` + `info_type="file"` + `ext04=<target node PEM>` | Seal a folder package for another node (mirror of `mgc_seal_package`). |

> **No interactive API docs** — MGC explicitly disables `/docs` and `/redoc` for security. For full request / response shapes, see the MCP server schema (MCP clients surface it directly to AI agents; for direct API use, see the source code in `mgc/presentation/web/router/`).

---

# 7. Trigger Rules — When AI Should Use Which Tool

| User intent | Reach for |
|-------------|-----------|
| "Save this token / password / script body / config string" | `mgc_save` |
| "Save this script file / config file on disk" | `mgc_save_file` (single file path) |
| "Save this whole skill / workflow folder" | `mgc_save_file` (folder path → `info_type="file"`) |
| "Import a sealed package from another node" | `mgc_save_file` (`.mgc_file` path) |
| "Run my script X" | `mgc_run` (preferred) |
| "What do I have stored?" | `mgc_list` |
| "Find entries matching X" (fuzzy) | `mgc_find` |
| "Seal this script for node B" | `mgc_seal` |
| "Export this workflow folder" | `mgc_package` (plaintext archive) |
| "Hand off this workflow to another MGC node" | `mgc_seal_package` |
| "Open the interface" | `mgc_open_webui` |
| "Read the value of entry X" | `mgc_get` |

---

# 8. Script Args — Auto-extracted, Override When Needed

When you save a Python script with `info_type='script'`, **MGC automatically parses the script's `argparse` and assembles default args into `ext02`**. 

**Dynamic args need manual fill-in.** `ext02` must be a valid JSON array string. Each element is one argv token.

**At runtime**, override the stored args via:

- MCP: `mgc_run(info_owner=..., ext01=..., ext02='["--start", "2026-12-25"]')`
- WebUI: click the amber **Run with Args** button to edit JSON before launching

---

# 9. Security Model — How MGC Protects Data

- **All data is encrypted locally** (AES-256 at rest).
- **AI can execute but can not read sealed plaintext.**
- **Seal is irreversible**: once sealed, the original owner can re-seal with a new key but cannot extract the script back.
- **Execution rights ≠ ownership**: a sealed node can execute but cannot transfer the capsule to a third node.
- **Content never leaves the device in plaintext.**
- **Script execution happens inside the encrypted boundary** — subprocess inherits the encrypted state.
- **Folder packages inherit single-script guarantees**: every file in a `.mgc_file` is encrypted; the receiving node learns only the file *structure* (paths, dependencies, platforms) before running.

---

# 10. Delete Policy

Delete functionality is available **via WebUI only** to prevent accidental AI-driven deletion.

---

# 11. Error Handling

| Status | Meaning | AI action |
|--------|---------|-----------|
| `NOT_FOUND` | Entry not found | Use `mgc_list` or ask user |
| `MULTIPLE_MATCHES` | Partial match | Present filtered list to user, ask for refinement |
| Connection failed | MGC not running | MCP auto-starts (or instruct user to run `mgc`) |
| Initialization required | First-time setup | Call `mgc_open_webui` |
| `args_not_recognized` | Script `argparse` parser couldn't identify default args | Verify script has `add_argument(..., default=<literal>)` |
| `dynamic_args_detected` | Script has computed defaults MGC cannot statically evaluate | Re-save with literal defaults, or supply `ext02` manually |
| `MISSING_REQUIRED_FIELDS` (ext04) | `mgc_seal` or `mgc_seal_package` called without target node public key | First call `mgc_get(NODE_PUB)` on the target node to retrieve its PEM public key, then pass it as `ext04` |

---

# 12. Coming Next

We are preparing a batch chain authorization feature. Send your node_pub to mirgincipher@outlook.com to claim a free first-batch trial.
