# MGC Blackbox — AI Skill / User Guide

## version
1.2.0

---
## Purpose
Store/retrieve/run sensitive info/script **without exposing plaintext**. All data encrypted locally.

# Environment Requirements (User Consent Required)

- Install:
  ```
  pip install mgc-blackbox
  ```
- Run:
  ```
  mgc run
  ```
---
## Trigger Keywords for AI skills

The skill activates when the user says anything like:

- "Store into MGC Blackbox"
- "Save to MGC" / "Get from MGC" / "Fetch from the Blackbox"
- "Put this into the Blackbox" / "Retrieve from MGC Blackbox"
- "Write a script that automatically reads from the Blackbox"
- "Run this script inside the Blackbox"

---
## Quick Reference

| Scenario | Method | Tools |
|----------|--------|-------|
| AI stores/retrieves | MCP | mgc_save, mgc_get, mgc_list, mgc_open_webui |
| Script runtime fetch | REST API | POST /api/mgc/sensitive/save/get |
| Human | webui | Base URL: `http://127.0.0.1:57218`(default, if port is occupied, follow the MGC startup prompt) |

MCP configuration: See `mcp_config.json` in installation directory.

---
## Parameters

**info_type**: password / token / api_key / script / etc (see mgc_save example)

**info_owner**: "user's GitHub" / "Amy's Aliyun" (who + where)

**iff_1/2/3**: Differentiate same info_type + info_owner
- Example: Two GitHub tokens → diff_1="work" / diff_1="personal"
---

## AI Usage — MCP Tools

### mgc_save
Store sensitive information (type: token/password/api_key/script/prompt/task/config/etc):
```
Tool: mgc_save
Arguments: {"info_type": "token", "info_owner": "user's GitHub", "content": "ghp_xxx"}
```
MGC will auto-detect if the content is script and the platform.

### mgc_get
```
Tool: mgc_get
Arguments: {"info_type": "token", "info_owner": "user's GitHub"}
```
Empty args → list all entries.

Run script:
```
Tool: mgc_get
Arguments: {"info_type": "script", "info_owner": "backup_script", "action": "run"}
```

### mgc_list
```
Tool: mgc_list
Arguments: {}
```

### mgc_open_webui
```
Tool: mgc_open_webui
Arguments: {}
```
---

## Script Usage — REST API

When scripts need sensitive credentials at runtime, fetch from MGC.
**Note**: Script assumes MGC is running.

**Base URL**: `http://127.0.0.1:57219`
**Token**: `~/.mgc/database/mgc_black_box/.mgc_token`

```python
import requests, os
token = open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")).read().strip()

# Store
requests.post("http://127.0.0.1:57219/api/mgc/sensitive/save",
    headers={"X-MGC-Token": token},
    json={"info_type": "config", "info_owner": "user's QQ", "content": "{\"pwd\":\"xxx\"}"})

# Retrieve
requests.post("http://127.0.0.1:57219/api/mgc/sensitive/get",
    headers={"X-MGC-Token": token},
    json={"info_type": "config", "info_owner": "user's QQ"})

# List all
requests.post("http://127.0.0.1:57219/api/mgc/sensitive/get",
    headers={"X-MGC-Token": token},
    json={})

# Update: add "update_if_exists": true
```

### Run Script (action=run)

Execute stored script and return result.

```python
# Run script - returns pid and status
requests.post("http://127.0.0.1:57219/api/mgc/sensitive/get",
    headers={"X-MGC-Token": token},
    json={"info_type": "script", "info_owner": "my_script", "action": "run"})

# Response: {"code":200,"msg":"success","data":{"pid":1234,"status":"success"}}
```
---

### Toggle Protection Mode

**Note**: Protection mode requires root key on every startup. MGC save and get can only use via MCP/API.

```python
import requests, os
token = open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")).read().strip()

# Get current protection mode
resp = requests.get("http://127.0.0.1:57218/api/user/settings")
print(resp.json())  # {"protection_mode": False}

# Change protection mode
requests.post("http://127.0.0.1:57218/api/user/settings",
    headers={"X-MGC-Token": token, "Content-Type": "application/json"},
    json={"protection_mode": True})  # or False
```
---

# AI Behavior Boundaries (Mandatory)

AI **must not**:
- Print plaintext
- Repeat plaintext
- Store plaintext in memory
- Display Blackbox internal lists
- Display script contents

AI **may**:
- Call save / get
- Guide the user to fill fields
- Use ephemeral plaintext to complete a task
- Present execution results
---

## Error Handling

| Status | Meaning | AI Action |
|--------|---------|-----------|
| NOT_FOUND | Entry not found | Check mgc_list first; if unsure, confirm with user |
| Connection failed | MGC not running | MCP will auto-start (~15s) |
---