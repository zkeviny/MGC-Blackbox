# 📘 **MGC Blackbox — Skill Specification**  

---

# 1. Overview — What MGC Blackbox Is  
**MGC Blackbox is a local encrypted execution layer.**  
It allows AI agents, system scripts, and human users to **store, execute, and delegate sensitive information or scripts without ever exposing plaintext**.

Core capabilities:

- Store sensitive data (tokens, passwords, configs)  
- Store scripts (logic, workflows, automation)  
- Execute stored scripts with optional parameters  
- Seal scripts for delegated execution (ownership retained)  
- List stored entries (metadata only)  
- Open WebUI for human operations  

All data is encrypted locally.  
**AI can execute but can never read plaintext.**

---

# 2. Installation & Runtime — How to Install and Run MGC

## 2.1 Install MGC Blackbox

**Via pip (recommended):**
```bash
pip install mgc-blackbox
```

Ensure installation happens in the same Python environment where your MCP agent runs.

---

## 2.2 Run MGC in normal mode

Start MGC as a standalone local service:

```bash
mgc
```

Default behavior:

- Starts HTTP server at `http://127.0.0.1:57219`  
- Initializes encrypted database on first run  
- Generates access token at:  
  `~/.mgc/database/mgc_black_box/.mgc_token`

This token is required for all REST API calls.

---

## 2.3 Run MGC as an MCP server

If your agent supports MCP, configure:

```json
{
  "mcpServers": {
    "mgc-blackbox": {
      "command": "mgc",
      "args": ["--mcp"]
    }
  }
}
```

In MCP mode:

- MGC exposes tools:  
  `mgc_save`, `mgc_get`, `mgc_list`, `mgc_seal`, `mgc_open_webui`  
- AI interacts **only** through MCP tools  
- REST API is still available for system scripts

---

## 2.4 WebUI access

When MGC is running, WebUI is available at:

```
http://127.0.0.1:57218
```

⚠️ **Port conflict resolution**: If port 57218 is occupied, MGC will automatically try 57217, 57216... sequentially.

**Tip**: Check the WebUI address in the MGC startup output for the exact URL.

Used for:

- Initialization  
- Manual storage  
- Metadata inspection  
- Database Audit (for manual deletion)  
- Logs & settings  

---

## **Ext Field Protocol — MGC Parameter Agreement**

| Field | Usage | Description |
|-------|-------|-------------|
| **ext01** | Startup Platform | Script execution command, e.g., "python" |
| **ext02** | Runtime Args | Parameters passed at script runtime |
| **ext03** | Sealed Key | RSA-encrypted AES key for sealed script |
| **ext04** | Node Pub | Target node RSA public key (used in seal) |

### Usage Rules
- All ext fields (ext01-ext30) are dynamically passed via MCP/API/WebUI
- ext02 takes effect only when action=run
- ext04 is required only when action=SEAL (target node public key)

---

# 3. Invocation Model — Who Uses MGC and How

### **① AI Invocation (via MCP Tools)**  
Used when AI needs to:

- Store sensitive information  
- Retrieve sensitive information (encrypted execution)  
- Execute stored scripts  
- Seal scripts for other nodes  
- List stored entries  
- Open the WebUI  

---

### **② System / Script Invocation (via REST API)**  
Used when:

- External scripts need sensitive data at runtime  
- Automated workflows need to execute stored scripts  
- System-level integrations require secure credential access  

---

### **③ Human Invocation (via WebUI)**  
Used for:

- First-time initialization  
- Manual storage  
- Metadata inspection  
- Manual deletion (via DB Audit)  
- Viewing logs  

---

# 4. MCP Tools — AI-Callable Interfaces

---

## **mgc_save — Store Sensitive Data or Scripts**

**Arguments:**  
```json
{
  "info_type": "token | script | config | ...",
  "info_owner": "unique identifier",
  "diff_1": "optional - identifier for multi-entry scenarios",
  "diff_2": "optional",
  "diff_3": "optional",
  "ext01": "startup command (e.g., python) - required for executable scripts",
  "ext02": "default script runtime parameters (used when action=run)",
  "ext03": "optional - target node RSA public key (for sealing)",
  "content": "plaintext to store"
}
```

Note: `ext01` is auto-detected by WebUI. For MCP/API, explicitly set it (e.g., "python"). All ext01-ext30 fields are dynamically passed to API.

---

## **mgc_get — Retrieve Sensitive Data or Execute Scripts**

**Arguments:**  
```json
{
  "info_type": "token | script | ...",
  "info_owner": "unique identifier",
  "diff_1": "optional",
  "diff_2": "optional",
  "diff_3": "optional",
  "action": "run",   // optional: executes script, returns start status only
  "params": {},      // optional: override runtime parameters (supersedes ext02)
  "ext01": "startup command (auto-retrieved from storage)",
  "ext02": "runtime parameters (defaults from storage)",
  "ext03": "stored sealed RSA key",
  "ext04": "target node RSA public key (for sealed script runtime)"
}
```

Note: For script execution, MGC returns only "success/failure". All parameters are dynamically passed to API.

### 🔹 **MGC 1.4 Behavior: Partial Matching Returns Filtered List**  
If parameters match multiple entries:

- No sensitive content is returned  
- A filtered metadata list is returned  
- AI must ask user to refine selection  

---

## **mgc_list — List Stored Entries (Metadata Only)**

**Arguments:**  
```json
{
  "info_type": "optional",
  "info_owner": "optional",
  "diff_1": "optional",
  "diff_2": "optional",
  "diff_3": "optional"
}
```

---

## **mgc_seal — Seal Script for Delegated Execution**

### **Prerequisite: Retrieve target node’s public key**

```json
{
  "name": "mgc_get",
  "arguments": {
    "info_type": "__NODE_PUB__",
    "info_owner": "__NODE_PUB__"
  }
}
```

Returned `content` contains PEM public key.

### **Seal Arguments:**  
```json
{
  "info_owner": "script identifier",
  "ext04": "target node public key (PEM) - stored in ext03 after seal",
  "info_type": "script",
  "diff_1": "optional",
  "diff_2": "optional",
  "diff_3": "optional"
}
```

---

## **mgc_open_webui — Open Local WebUI**

Opens WebUI in the default browser. Default port is 57218 (or lower if occupied).

```json
{}
```

---

# 5. REST API — System / Script Integration

**Base URL:**  
```
http://127.0.0.1:57219
```

**Header:**  
```
X-MGC-Token: <token>
```

Token file:  
```
~/.mgc/database/mgc_black_box/.mgc_token
```

---

## **POST /api/mgc/sensitive/save**

**Request:**
```json
{
  "info_type": "...",
  "info_owner": "...",
  "content": "...",
  "update_if_exists": true
}
```

---

## **POST /api/mgc/sensitive/get**

Retrieve sensitive data or execute scripts.

**Request:**
```json
{
  "info_type": "...",
  "info_owner": "...",
  "action": "run"
}
```

**Response:**
```json
{
  "code": 200,
  "msg": "Operation successful",
  "hint": "Decrypted from MGC. Burn after use.",
  "data": "decrypted content"
}
```

---

## **POST /api/mgc/sensitive/get (empty body)**  

List all stored entries (metadata only).

**Request:**
```json
{}
```

---

# 6. Trigger Rules — When AI Should Use Which Tool

- “Save this token/password/script” → **mgc_save**  
- “Run my script X” → **mgc_get (action=run)**  
- “What do I have stored?” → **mgc_list**  
- “Seal this script for node B” → **mgc_seal**  
- “Open the interface” → **mgc_open_webui**  

---

# 7. Security Model — How MGC Protects Data

- All data is encrypted locally  
- AI can execute but never read plaintext  
- Seal is irreversible  
- Execution rights ≠ ownership  
- Content never leaves the device in plaintext  
- Script execution happens inside the encrypted boundary  

---

# 8. Delete Policy (MGC 1.4)

**MGC considers all info stored in the Blackbox as the user’s valuable assets,  
so delete functionality is NOT provided.**

To delete manually:

1. Open WebUI → Database Audit  
2. Retrieve the database key  
3. Use DB Browser to manually delete entries  

This prevents:

- Accidental deletion  
- AI-triggered deletion  
- Unauthorized deletion  

---

# 9. Error Handling

| Status | Meaning | AI Action |
|--------|---------|-----------|
| NOT_FOUND | Entry not found | Use mgc_list or ask user |
| MULTIPLE_MATCHES | Partial match | Present filtered list |
| Connection failed | MGC not running | MCP auto-starts |
| Initialization required | First-time setup | Call mgc_open_webui |

---
