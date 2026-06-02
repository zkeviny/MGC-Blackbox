# 📘 **MGC Blackbox — AI Skill / User Guide**

## Version  
**1.4.3**

---

# Purpose  
Store / retrieve / run sensitive info or scripts **without unauthorized plaintext exposure**.  
All data is encrypted locally and executed inside a secure boundary.

---

# Environment Requirements (User Consent Required)

## Install
```bash
pip install mgc-blackbox
```

## Run
```bash
mgc
```

### WebUI Port  
- Default: **57218**  
- If occupied → automatically decrements (57217, 57216, …)  
- The actual port is shown in the startup log.

WebUI URL:
```
http://127.0.0.1:<port>
```

---

# Trigger Keywords for AI Skills

The skill activates when the user says:

- “Store into MGC Blackbox”
- “Save to MGC / Get from MGC”
- “Fetch from the Blackbox”
- “Put this into the Blackbox”
- “Retrieve my token/password/script”
- “Run this script inside the Blackbox”
- “Seal this script for another node”

---

# Quick Reference

| Scenario | Method | Tools |
|----------|--------|-------|
| AI stores/retrieves | MCP | mgc_save, mgc_get, mgc_list, mgc_seal, mgc_open_webui |
| Script runtime fetch | REST API | POST /api/mgc/sensitive/save/get |
| Human | WebUI | `http://127.0.0.1:<port>` |

MCP configuration: See `mcp_config.json` in installation directory.

---

# Parameters

**info_type**  
`password / token / api_key / script / config / ...`

**info_owner**  
“user’s GitHub” / “Amy’s Aliyun” (who + where)

**diff_1 / diff_2 / diff_3**  
Differentiate entries with same type + owner  
Example:  
- GitHub token (work)  
- GitHub token (personal)

---

# AI Usage — MCP Tools

## mgc_save  
Store sensitive information or scripts.

```
Tool: mgc_save
Arguments: {
  "info_type": "token",
  "info_owner": "user's GitHub",
  "content": "ghp_xxx"
}
```

MGC auto-detects script content and platform.

---

## mgc_get  
Retrieve sensitive info or execute scripts.

```
Tool: mgc_get
Arguments: {"info_type": "token", "info_owner": "user's GitHub"}
```

### List all entries  
```
Tool: mgc_get
Arguments: {}
```

### Run script  
```
Tool: mgc_get
Arguments: {
  "info_type": "script",
  "info_owner": "backup_script",
  "action": "run"
}
```

### 🔹 MGC 1.4 Behavior: Partial Match  
If parameters match multiple entries:

- No sensitive content returned  
- A filtered metadata list is returned  
- AI must ask user to choose  

---

## mgc_list  
```
Tool: mgc_list
Arguments: {}
```

---

## mgc_seal (New in 1.4)  
Seal a script for **trusted external node execution**.

### Step 1 — Retrieve target node’s public key  
```
Tool: mgc_get
Arguments: {
  "info_type": "__NODE_PUB__",
  "info_owner": "__NODE_PUB__"
}
```

### Step 2 — Seal script  
```
Tool: mgc_seal
Arguments: {
  "info_owner": "my_script",
  "ext02": "-----BEGIN PUBLIC KEY-----\n..."
}
```

### Seal Output  
Returned sealed data contains:

- `content` — AES‑encrypted script  
- `ext_01` — startup command  
- `ext_02` — original args  
- `ext_03` — RSA‑encrypted AES key  

**Store each field as separate MGC entries.**

### What Seal Enables  
- Execution rights can be granted to another node  
- Script logic remains unreadable  
- Only the target node can decrypt & execute  
- Seal is **irreversible** (ownership retained)

---

## mgc_open_webui  
```
Tool: mgc_open_webui
Arguments: {}
```

---

# Script Usage — REST API

Scripts can fetch sensitive credentials at runtime.  
**MGC must be running.**

### Base URL  
```
http://127.0.0.1:<port>
```

### Token  
```
~/.mgc/database/mgc_black_box/.mgc_token
```

---

## Python Example

```python
import requests, os

token = open(os.path.expanduser(
    "~/.mgc/database/mgc_black_box/.mgc_token"
)).read().strip()

base = "http://127.0.0.1:57218"  # replace with actual port
```

### Store
```python
requests.post(f"{base}/api/mgc/sensitive/save",
    headers={"X-MGC-Token": token},
    json={
        "info_type": "config",
        "info_owner": "user's QQ",
        "content": "{\"pwd\":\"xxx\"}"
    })
```

### Retrieve
```python
requests.post(f"{base}/api/mgc/sensitive/get",
    headers={"X-MGC-Token": token},
    json={"info_type": "config", "info_owner": "user's QQ"})
```

### List all
```python
requests.post(f"{base}/api/mgc/sensitive/get",
    headers={"X-MGC-Token": token},
    json={})
```

### Run script
```python
requests.post(f"{base}/api/mgc/sensitive/get",
    headers={"X-MGC-Token": token},
    json={"info_type": "script", "info_owner": "my_script", "action": "run"})
```

---

# Protection Mode

Requires root key on every startup.  
Save/get only allowed via MCP or API.

### Check mode
```python
requests.get(f"{base}/api/user/settings")
```

### Toggle mode
```python
requests.post(f"{base}/api/user/settings",
    headers={"X-MGC-Token": token},
    json={"protection_mode": True})
```

---

# AI Behavior Boundaries (Mandatory)

AI **must not**:

- Print plaintext  
- Repeat plaintext  
- Store plaintext in memory  
- Display script contents  
- Display internal encrypted data  

AI **may**:

- Call mgc_save / mgc_get / mgc_list / mgc_seal  
- Guide user to fill required fields  
- Use ephemeral plaintext for immediate tool calls  
- Present execution results  

---

# Delete Policy

**MGC considers all stored info as user assets.  
Delete functionality is NOT provided.**

To delete manually:

1. Open WebUI → Database Audit  
2. Retrieve DB key  
3. Delete via DB Browser  

---

# Error Handling

| Status | Meaning | AI Action |
|--------|---------|-----------|
| NOT_FOUND | Entry not found | Use mgc_list or ask user |
| MULTIPLE_MATCHES | Partial match | Ask user to choose |
| Connection failed | MGC not running | MCP auto-start (~15s) |

---
