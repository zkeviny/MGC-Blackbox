---

spec: usk/3.0
id: key_safe_skill_generator
version: 1.3.0
name: Key‑Safe Skill Generator
description: A documentation‑only meta‑skill that teaches AI agents how to generate secure, zero‑exposure skills using MGC Blackbox 1.4.10. Credentials are stored encrypted; local scripts read them via HTTP API at runtime, while AI agents never touch plaintext.
author: MirginCipher Team
license: MIT
tags: zero-exposure, mgc, security, credential-management, skill-generator, meta-skill, mgc_run, mgc_find
platform_compatibility: windows, macos, linux
changelog:
  - version: 1.3.0
    changes:
      - Upgraded to adapt to MGC 1.4.10
      - Refactored zero-exposure flow (mgc_run + HTTP API; credentials never enter AI context)
      - Replaced mgc_get with mgc_run for sealed-script execution (1.4.7+ blackbox)
      - Added mgc_find (1.4.10 fuzzy search) and mgc_open_webui; removed mgc_get
      - Documented mgc_seal returning dict, ext02 auto-parse, multi-line PEM for ext04
      - Added update_if_exists=true for credential updates
      - Fixed Invalid key format troubleshooting
      - Added 1.4.9 sandbox mode note
      - Updated MGC main skill doc reference to WebUI MGC Skills button (1.4.7+) and mgc --status
      - Templates updated with parse_known_args and HTTP API pattern
      - Added two anti-patterns (AI calling mgc_get, password as ext02)
  - version: 1.1.0
    changes:
      - Added complete example section with copy‑and‑paste templates
      - Added comprehensive FAQ section
      - Added anti‑patterns section with correct practices
      - Added troubleshooting section
      - Added when to use / when not to use sections
      - Restructured to recommended format
  - version: 1.0.1
    changes:
      - Updated to emphasize MCP tools over CLI
  - version: 1.0.0
    changes:
      - Initial release with conceptual workflow and USK v3 structure

---

# Overview

Key‑Safe Skill Generator is a **meta‑skill** that teaches AI agents how to generate secure skills that interact with external services requiring credentials (email, APIs, tokens, SSH keys, etc.).
It provides a **design pattern**, **structural templates**, and **conceptual workflows** for building skills that never expose secrets to AI models.

This skill contains **no executable code** and is safe for automatic approval.

---

# ⚠️ Critical: True Zero‑Exposure Means AI Never Sees Credentials

The wrong way (breaks zero‑exposure):

```
AI → mgc_get(config) → returns plaintext JSON (incl. password) → AI uses password
```

The right way (1.4.10 true zero‑exposure):

```
User → mgc_save(config with credentials)
User / Script Agent → mgc_save(script that reads config via HTTP API)
Executor Agent → mgc_run(script) → MGC blackbox executes
                              └─ script reads credentials via HTTP API
                              └─ script performs the sensitive operation
                              └─ script writes result to file
                              └─ MGC returns only {pid, status}
AI → reads result file → only sees operation result, NEVER password
```

> **Never call `mgc_get` from AI**. `mgc_get` returns plaintext and breaks zero‑exposure. Use `mgc_run` for blackbox execution instead.

---

# What This Skill Enables

After reading this documentation, an AI agent will understand how to:

- Build new skills that interact with external services **without exposing credentials**
- Use **MGC Blackbox** as the secure storage and runtime provider
- Structure a Zero‑Exposure skill using **USK v3 conventions**
- Guide users to prepare and store credentials safely
- Generate a complete skill package (SKILL.md + README + local script)
- Ensure all sensitive operations happen **outside the AI model** (via `mgc_run` blackbox)

---

# When to Use Key‑Safe

Use Key‑Safe in the following scenarios:

## Must Use Cases

1. **AI needs credentials but must not see them**
   - Example: AI needs to send emails via SMTP but should never see the password
   - Solution: Store credentials in MGC, retrieve via local script through `mgc_run` blackbox

2. **Multi‑node collaboration**
   - Example: Node A creates a script, Node B executes it
   - Solution: Use `mgc_seal` to encrypt the script with Node B's public key; Node B calls `mgc_run`

3. **Automation tasks requiring credentials**
   - Example: Scheduled tasks that need API keys
   - Solution: Credentials stored in MGC, accessed by local scripts via `mgc_run`

4. **Sensitive script execution**
   - Example: Scripts that perform privileged operations
   - Solution: Credentials never passed through AI, retrieved by scripts inside `mgc_run` blackbox

## Example Triggers

- "I need to send an email using my SMTP server"
- "Call a GitHub API with my personal access token"
- "Push code to my repository"
- "Execute a script that needs database credentials"
- "Create a skill that uses external APIs securely"

---

# When NOT to Use Key‑Safe

Key‑Safe is not needed in these scenarios:

1. **Public APIs without authentication**
2. **Demo / testing environments** (mock credentials)
3. **Skills that only read public data**
4. **Manual operations where user provides credentials each time**

---

# Prerequisites for Zero‑Exposure Skills

To build a Zero‑Exposure skill, users must:

1. Install MGC Blackbox 1.4.10+: `pip install mgc-blackbox`
2. Start the MGC service: `mgc` (API at http://127.0.0.1:57219, WebUI at 57218)
3. Use **MCP tools** (`mgc_save`, `mgc_run`, `mgc_list`, `mgc_find`, `mgc_seal`, `mgc_open_webui`) for credential management
4. Store credentials in MGC under a chosen identifier (`info_type="config"`, `info_owner="<name>"`)
5. Write a local script that retrieves credentials via HTTP API and performs sensitive operations
6. AI invokes the script via `mgc_run` (blackbox) — AI never touches credential plaintext

> **Important:** AI agents should only use `mgc_save`, `mgc_run`, `mgc_list`, `mgc_find`, `mgc_seal`, `mgc_open_webui`. **Never use `mgc_get` from AI** — it returns plaintext.

> **Sandbox mode (1.4.9+)**: When running inside a sandbox Agent (Trae Work / Workbuddy), install MGC in the system environment; otherwise MCP operations may be limited — in that case, call FastAPI directly at `/api/mgc/sensitive/run`.

---

# Full Example: Complete Zero‑Exposure Workflow

## Step 1: Store Credentials in MGC

User stores credentials (via WebUI or `mgc_save` on explicit instruction):

```
Tool: mgc_save
Parameters:
  info_type:   "config"           # Type of stored data
  info_owner:  "smtp_server"      # Identifier for this credential set
  content:     "{
    \"host\": \"smtp.example.com\",
    \"port\": 587,
    \"username\": \"your_email@example.com\",
    \"password\": \"your_app_password\",
    \"use_tls\": true
  }"
```

> **Updating credentials**: call `mgc_save` again with the same `info_type`/`info_owner` AND `update_if_exists=true`. The old entry is replaced.

## Step 2: Reference Credentials in Your Skill

```markdown
# In your SKILL.md or local script template:

credential_reference:
  info_type:  "config"
  info_owner: "smtp_server"

# AI references the identifier only — never embeds credentials.
```

## Step 3: Local Script Retrieves Credentials via HTTP API

```python
import os
import json
import requests

MGC_BASE_URL = "http://127.0.0.1:57219"
TOKEN_FILE = os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")


def get_credentials(info_owner, info_type="config"):
    """Read credentials via HTTP API. Script-internal only; AI never calls this."""
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError("MGC token file missing")
    with open(TOKEN_FILE, "r") as f:
        token = f.read().strip()
    url = f"{MGC_BASE_URL}/api/mgc/sensitive/get"
    headers = {"X-MGC-Token": token, "Content-Type": "application/json"}
    resp = requests.post(
        url,
        json={"info_type": info_type, "info_owner": info_owner, "action": "run"},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    if isinstance(result, str):
        return json.loads(result)
    return result.get("data", {}).get("data_field", {})
```

## Step 4: Local Script Performs Sensitive Operation

```python
import argparse
import datetime
import smtplib
import os


def main():
    # ✅ Literal defaults only — MGC 1.4.10 auto-parses into ext02
    parser = argparse.ArgumentParser()
    parser.add_argument("--credential_ref", default="smtp_server")
    parser.add_argument("--to", default="")
    parser.add_argument("--subject", default="")
    parser.add_argument("--body", default="")
    args, _ = parser.parse_known_args()  # ✅ parse_known_args avoids exit on unknown params

    creds = get_credentials(args.credential_ref)

    msg = f"Subject: {args.subject}\n\n{args.body}".encode("utf-8")
    with smtplib.SMTP(creds["host"], creds["port"]) as s:
        s.starttls()
        s.login(creds["username"], creds["password"])
        s.sendmail(creds["username"], [args.to], msg)

    # Write result to file so AI can read it (mgc_run returns pid+status)
    out_dir = os.path.expanduser("~/mgc_outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir, f"email_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Email sent to {args.to}\n")
    print(f"RESULT_FILE:{out_path}")
```

## Step 5: Store Script and Execute via `mgc_run`

```python
# 5a. Script Agent stores the script in MGC
mgc_save(
    info_type="script",
    info_owner="send_email_via_mgc",
    ext01="python",
    content="<script body from steps 3-4>",
    update_if_exists=True
)
# MGC 1.4.10 auto-parses argparse literal defaults into ext02

# 5b. Executor Agent runs the script (1.4.7+ blackbox)
result = mgc_run(
    info_type="script",
    info_owner="send_email_via_mgc",
    diff_1="send_email_via_mgc",  # schema 必填的区分字段；多条同 owner 时消歧，单条时任意非空字符串均可
    ext02='["--to", "user@example.com", "--subject", "Hi", "--body", "Hello"]'
)
# Returns: {"pid": 12345, "status": "started"}
# AI reads the result file printed on stdout (mgc returned it via the file output convention).
# AI never sees the SMTP password.
```

---

# Multi‑Node Example: Sealing Scripts for Other Nodes (1.4.10)

### Node A: Seal the script

```python
# Get Node B's public key (multi-line PEM, real \n)
node_pub = mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")

# Store original script first
mgc_save(
    info_type="script",
    info_owner="send_email_via_mgc",
    ext01="python",
    content="<script body>"
)
# 1.4.10 auto-fills ext02 from argparse literal defaults

# Seal with Node B's public key
sealed = mgc_seal(
    info_owner="send_email_via_mgc",
    ext04=node_pub
)
# sealed = {content, ext_01, ext_02, ext_03}
# ⚠️ ext04 MUST be multi-line PEM with real newlines
```

### Node B: Store and execute the sealed capsule

```python
# Store the sealed capsule (must include ext02 from source)
mgc_save(
    info_type="script",
    info_owner="send_email_via_mgc",
    ext01=sealed["ext_01"],
    ext02=sealed["ext_02"],            # default args from source argparse
    content=sealed["content"],
    ext03=sealed["ext_03"],            # RSA-encrypted AES key (only Node B can decrypt)
    update_if_exists=True
)

# Execute via mgc_run (1.4.7+ blackbox)
mgc_run(
    info_type="script",
    info_owner="send_email_via_mgc",
    diff_1="send_email_via_mgc",
    ext02='["--to", "user@example.com"]'
)
# Node B executes with its own private key; credentials are read from Node B's local MGC.
```

> **Credential consistency**: Node B must also store the SMTP credential with the **same `info_type`/`info_owner`** as Node A. Otherwise the sealed script will fail to find credentials.

---

# MCP Tools Reference

| Tool | Purpose | Notes |
|------|---------|-------|
| `mgc_save` | Store credentials / scripts | `info_type="config"` for credentials, `"script"` for scripts |
| `mgc_run` | Blackbox script execution (1.4.7+) | `ext02` MUST be a JSON array string; `diff_1` is schema-required (any non-empty string for a single entry) |
| `mgc_list` | List entries (exact match) | metadata only, no plaintext |
| `mgc_find` | Fuzzy search (1.4.10) | `match_mode`: substring/prefix/suffix/exact |
| `mgc_seal` | Seal script for target node | returns dict `{content, ext_01, ext_02, ext_03}`; `ext04` MUST be multi-line PEM with real newlines |
| `mgc_open_webui` | Open WebUI for user to store credentials | browser opens automatically |
| ~~`mgc_get`~~ | ~~DO NOT USE FROM AI~~ | Returns plaintext — breaks zero‑exposure |

---

# Quick Reference: AI Behaviour Rules

When this skill is active, the AI MUST:

- ✅ **Use `mgc_run`** to execute sensitive scripts; AI never touches plaintext
- ✅ **Use `mgc_find`** to locate available scripts (`match_mode="substring"`)
- ✅ **Use `mgc_open_webui`** to help user store credentials
- ✅ Reference scripts/credentials by `info_owner` only; never include passwords in prompts
- ❌ **Never call `mgc_get`** — returns plaintext
- ❌ **Never embed credentials** in SKILL.md, prompts, or AI context
- ❌ **Never ask the user** to paste the password in chat

---

# FAQ

## MGC Related

**Q: What if MGC is not installed?**
A: `pip install mgc-blackbox>=1.4.9`. Requires Python 3.10+.

**Q: What if MGC is not running?**
A: Start with `mgc`. WebUI at http://127.0.0.1:57218, API at http://127.0.0.1:57219.

**Q: How do I check MGC version?**
A: `mgc --status` (1.4.9+). Also shown in WebUI's Settings panel.

**Q: Port 57219 is already in use?**
A: Stop other apps on that port, or run MGC with a different port.

**Q: Where can I read the MGC main skill documentation?**
A: WebUI → MGC Skills button (1.4.7+) or `~/.mgc/database/mgc_black_box/.mgc_skills/`.

## Credential Management

**Q: What if credentials are not found?**
A: 1) Verify `info_owner` exactly (case-sensitive); 2) `mgc_find(info_owner="...", match_mode="substring")`; 3) `mgc_list()`.

**Q: How should I name info_type and info_owner?**
A: `info_type` = category (`"config"`, `"credential"`, `"script"`, `"api_key"`); `info_owner` = unique purpose identifier (good: `"smtp_gmail"`, bad: `"test"`).

**Q: How do I update stored credentials?**
A: `mgc_save` with same `info_type`/`info_owner` AND `update_if_exists=true`.

**Q: How do I delete stored credentials?**
A: Use WebUI delete (info_type + diff_1/2/3 conditions) — MCP delete is intentionally not supported to prevent AI-triggered deletion.

## ext01 / ext02 Fields

**Q: What should I put in ext01?**
A: Programming language or script type: `"python"`, `"bash"`, `"javascript"`.

**Q: What should I put in ext02?**
A: Runtime parameters as a JSON array string `["--flag","value"]`. Since 1.4.10, MGC **auto-fills** ext02 from argparse literal defaults when storing a script — you only need to set it when calling `mgc_run` to override defaults. Dynamic defaults (`datetime.now()`, `os.path.expanduser()`) trigger `dynamic_args_detected` warning; use literal defaults instead.

**Q: What is ext04 used for?**
A: Target node's public key when using `mgc_seal`. **Never put credentials here in.** Must be multi-line PEM with real newlines.

## Security

**Q: How do I ensure AI never exposes keys?**
A: 1) Never include credentials in SKILL.md prompts; 2) Never pass credentials as parameters to AI; 3) Always use MGC to store credentials; 4) Local scripts retrieve credentials via HTTP API inside `mgc_run` blackbox; 5) AI only receives non-sensitive operation results.

**Q: Can AI read credentials from MGC?**
A: **No — never call `mgc_get` from AI.** `mgc_get` returns plaintext and breaks zero-exposure. Credentials must be read by local scripts via HTTP API inside MGC blackbox execution.

**Q: What if AI accidentally logs credentials?**
A: Local scripts must: never `print`/`log` password values; only log non-sensitive info (host, recipient, etc.).

## Multi-Node Scenarios

**Q: How to share a script across nodes?**
A: 1) Node A stores script; 2) `mgc_seal(info_owner=..., ext04=node_b_pubkey)`; 3) Node B stores capsule with `ext02`/`ext03`; 4) Node B calls `mgc_run`.

**Q: Can I seal for multiple nodes?**
A: Not in one call — seal separately for each node. Use `mgc_find` to track which nodes have copies.

**Q: What if a node's private key is compromised?**
A: Regenerate the key pair and redistribute the new public key. Any previously sealed scripts must be re-sealed.

---

# Anti-Patterns

## ❌ Anti-Pattern 1: AI calling mgc_get to retrieve credentials

```python
# WRONG — breaks zero-exposure, password enters AI context
creds = mgc_get(info_type="config", info_owner="smtp_server")
print(creds["password"])  # NEVER
```

**Correct**: AI only calls `mgc_run`; the script internally uses HTTP API.

---

## ❌ Anti-Pattern 2: Embedding Keys in Scripts

```python
# WRONG
def send_email():
    password = "my_secret_password"  # Exposed!
    smtp.login("user@example.com", password)
```

**Correct**: Read from MGC via HTTP API inside `mgc_run` blackbox; password is never in source code.

---

## ❌ Anti-Pattern 3: AI Directly Reading Keys

```markdown
# WRONG — In SKILL.md
Use the following credentials:
- Username: user@example.com
- Password: secret123
```

**Correct**:
```markdown
Credentials are stored encrypted in MGC.
Reference: info_owner="smtp_server"
AI references the identifier only; local script reads via HTTP API inside mgc_run.
```

---

## ❌ Anti-Pattern 4: Putting Password in ext04

```json
// WRONG
{
  "info_owner": "my_api",
  "ext04": "password=secret123"  // ext04 is for public keys only
}
```

**Correct**:
```json
{
  "info_owner": "my_script",
  "info_type": "script",
  "ext04": "-----BEGIN PUBLIC KEY-----\nNodeB_Public_Key...\n-----END PUBLIC KEY-----"
}
```

---

## ❌ Anti-Pattern 5: Passing Password as mgc_run ext02

```python
# WRONG — password enters AI context via ext02 string
mgc_run(
    info_owner="send_email_via_mgc",
    ext02=json.dumps(["--password", "my_secret"])  # NEVER
)
```

**Correct**: Password is `info_type="config"` stored separately; script reads via HTTP API inside blackbox. `ext02` only carries non-sensitive runtime args (`--to`, `--subject`, `--body`).

---

## ❌ Anti-Pattern 6: Storing Keys in Plain Text Files

```bash
# WRONG
echo "password=secret" > credentials.txt
```

**Correct**: Store in MGC; never write credentials to plain files.

---

## ❌ Anti-Pattern 7: Passing Credentials as Prompt Parameters

```markdown
# WRONG
Send an email using password: {user_password}
```

**Correct**:
```markdown
Send an email using credentials stored in MGC.
Reference: info_owner="smtp_gmail"
The local script handles credential retrieval.
```

---

## ❌ Anti-Pattern 8: Logging Credentials

```python
# WRONG
print(f"Using password: {credentials['password']}")  # Exposed!
```

**Correct**:
```python
logger.info("Connecting to SMTP server...")  # No credentials logged
```

---

# Troubleshooting

## Error: "Credential not found"

1. Verify `info_owner` matches exactly (case-sensitive)
2. `mgc_find(info_owner="...", match_mode="substring")` to locate
3. `mgc_list()` to enumerate all entries

## Error: "Update not allowed" / "Entry exists"

`mgc_save` requires `update_if_exists=true` to overwrite by default (1.4.10 strictness).

## Error: "Invalid PEM format" (during mgc_seal)

`ext04` must be **multi-line PEM with real newlines**. Copy verbatim from `mgc_get(info_type='__NODE_PUB__')`. Do NOT concatenate into a single line.

## Error: "dynamic_args_detected" (when saving script)

Script uses dynamic argparse defaults (`datetime.now()`, `os.path.expanduser()`). Switch to literal defaults or pass `ext02` manually when calling `mgc_run`.

## Error: "args_not_recognized" (during mgc_run)

Source script's argparse did not recognize the args passed via `ext02`. Check `add_argument` definitions and the `ext02` JSON array.

## Error: "MGC not running"

1. `mgc` in a terminal
2. Check http://127.0.0.1:57219 responds
3. Verify token file: `~/.mgc/database/mgc_black_box/.mgc_token`

## Error: "MCP tool call failed"

1. Confirm MGC ≥ 1.4.9; upgrade via WebUI Settings or `pip install --upgrade mgc-blackbox`
2. Verify MCP server config has `PYTHONIOENCODING=utf-8` env (Windows)

---

# Zero-Exposure Workflow (Conceptual)

A Zero-Exposure skill follows this pattern:

1. **User stores credentials in MGC** (`info_type="config"`, `info_owner="<name>"`)
2. **Script Agent stores a local script in MGC** (`info_type="script"`)
3. **Executor Agent invokes the script via `mgc_run`** — script runs inside blackbox
4. **Script reads credentials via HTTP API** (localhost, MGC token required)
5. **Script performs the sensitive operation** (SMTP, API call, etc.)
6. **AI receives only the result** (via result file or stdout path)

---

# Common Zero-Exposure Patterns

## Email Sender

- User stores SMTP credentials in MGC
- Local script retrieves them via HTTP API inside `mgc_run` blackbox
- Script sends email
- AI provides only subject/body/recipient (non-sensitive args)

## API Client

- User stores API key in MGC
- Local script retrieves it via HTTP API
- Script performs authenticated request
- AI provides endpoint and payload

## Git Automation

- User stores GitHub token in MGC
- Local script retrieves it via HTTP API
- Script performs push/pull/commit
- AI provides commit message

---

# Security Notes

## What This Skill Guarantees

- **No credentials in prompts**: AI never receives credential values
- **No credentials in code**: Scripts retrieve from MGC via HTTP API inside `mgc_run`
- **No credentials in logs**: Only non-sensitive information logged
- **No credentials in memory**: Credentials stay in MGC, not AI context
- **Encrypted storage**: All credentials encrypted at rest

## Critical Rules

1. **Never** include actual credentials in SKILL.md
2. **Never** pass credentials as prompt parameters or `ext02`
3. **Always** use MGC for credential storage
4. **Always** use local scripts via `mgc_run` for credential retrieval
5. **Never** log credential values
6. **Always** validate credential references, not values

---

# Entrypoint

This skill has **no runtime entrypoint**.
It is a documentation-only instructional skill.

---

# Template: Zero-Exposure SKILL.md Structure

When creating a new skill using Key-Safe patterns, use this structure:

```markdown
---

spec: usk/3.0
id: your_skill_id
version: 1.0.0
name: Your Skill Name
description: Brief description
author: Your Name
license: MIT
tags: zero-exposure, mgc, your_tags
platform_compatibility: windows, macos, linux

---

# Overview

What this skill does.

# Prerequisites

- MGC Blackbox ≥ 1.4.9
- Store credentials in MGC (info_type: "config", info_owner: "your_reference")
- Install required dependencies

# Usage

How to use this skill via mgc_run.

# Credentials

- info_type: "config"
- info_owner: "your_reference"
- Required fields: [list]

# Security

This skill uses Zero-Exposure design.
Credentials are stored encrypted in MGC and read by local scripts via HTTP API inside mgc_run blackbox execution. AI agents never touch plaintext.

# Entrypoint

Describe how to use this skill.
```

---

# Template: Zero-Exposure Local Script Structure

When creating a local script for your skill, store it as an MGC script and invoke via `mgc_run`:

```python
"""Zero-Exposure script template. Store in MGC; execute via mgc_run."""

import os
import json
import argparse
import requests
import datetime

MGC_BASE_URL = "http://127.0.0.1:57219"
TOKEN_FILE = os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")


def get_credentials(info_owner, info_type="config"):
    """Read credentials from MGC via HTTP API. Script-internal only."""
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError("MGC token file missing")
    with open(TOKEN_FILE, "r") as f:
        token = f.read().strip()
    url = f"{MGC_BASE_URL}/api/mgc/sensitive/get"
    headers = {"X-MGC-Token": token, "Content-Type": "application/json"}
    resp = requests.post(
        url,
        json={"info_type": info_type, "info_owner": info_owner, "action": "run"},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    if isinstance(result, str):
        return json.loads(result)
    return result.get("data", {}).get("data_field", {})


def perform_sensitive_operation(credentials, operation_params):
    """Use credentials to perform the operation. NEVER log credential values."""
    # Replace this with your actual logic
    raise NotImplementedError


def main():
    # ✅ Literal defaults only — MGC 1.4.10 auto-parses into ext02
    parser = argparse.ArgumentParser()
    parser.add_argument("--credential_ref", default="your_reference")
    parser.add_argument("--param", default="default")
    args, _ = parser.parse_known_args()  # ✅ parse_known_args

    creds = get_credentials(args.credential_ref)

    result = perform_sensitive_operation(creds, {"param": args.param})

    out_dir = os.path.expanduser("~/mgc_outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir, f"result_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(str(result))
    print(f"RESULT_FILE:{out_path}")


if __name__ == "__main__":
    main()
```

> This template is meant to be stored in MGC as a script (`mgc_save`) and executed by AI via `mgc_run`. The AI provides non-sensitive args via `ext02` JSON array string; credentials are read inside MGC blackbox; AI only sees the result file.

---

# License

MIT