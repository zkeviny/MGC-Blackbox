# Script Management Workflow

This document guides data analysts on how to securely manage query scripts, cleaning scripts, analysis scripts, and other **user-owned scripts** in **MGC Blackbox**, and implement **zero-exposure application** locally.

All sensitive operations must be explicitly authorized by the user before proceeding.

---

# Overview

MGC Blackbox provides local encrypted storage and zero-exposure script application:

- Script content never exposed to AI
- Scripts decrypted only on user's local machine
- Scripts can safely call credentials (zero-exposure)
- All applications require user authorization
- AI can only see execution results, not script logic

---

# Script Types (User-Owned)

This skill suite supports managing the following script types:

| Type | Description |
|------|-------------|
| Query Scripts | User's own data query logic |
| Cleaning Scripts | User's own data transformation logic |
| Analysis Scripts | User's own analysis logic |
| Delivery Scripts | User's own result processing logic |
| Collaboration Scripts | Scripts for cross-team collaboration (can be sealed) |

All scripts must be provided by the user; this suite does not generate scripts.

---

# How to Securely Store Scripts

Script storage is recommended via **MGC WebUI** or **mgc_save** tool.

## Method 1: Via WebUI (Recommended)

1. Start MGC:
   ```
   mgc
   ```
2. Open WebUI:
   ```
   http://127.0.0.1:57218
   ```
3. Navigate to **Save page**
4. Fill in fields:

```
info_type: "script"
info_owner: "analysis_monthly_summary"   # Custom script name
ext01: "python"
content: <your script content>
```

## Method 2: Via mgc_save

```python
mgc_save(
    info_type="script",
    info_owner="analysis_monthly_summary",
    ext01="python",
    content="<your script content>"
)
```

---

# How to Write Scripts for Zero-Exposure Credential Calls

Scripts can safely access credentials, but AI can never see credential content.

Below is the **standard zero-exposure credential call pattern** (pseudocode):

---

## Standard Example: Script Internally Accesses Credentials Safely

Scripts access credentials via MGC local API:

```python
import requests
import os
import json

BASE_URL = "http://127.0.0.1:57219"
TOKEN_PATH = os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")

def get_token():
    """Read local Token"""
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            return f.read().strip()
    return ""

def get_credential():
    """Get credential from MGC"""
    token = get_token()
    if not token:
        return None

    resp = requests.post(
        f"{BASE_URL}/api/mgc/sensitive/get",
        headers={"X-MGC-Token": token, "Content-Type": "application/json"},
        json={
            "info_type": "credential",
            "info_owner": "db_warehouse_prod"
        }
    )

    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 200:
            data_field = data.get("data")
            if isinstance(data_field, str):
                return json.loads(data_field)
            elif isinstance(data_field, dict):
                content = data_field.get("content")
                if content:
                    return json.loads(content)
    return None

# Using credential
def analyze_monthly_sales(input_data):
    credential = get_credential()
```

Note:
- This call is local only (127.0.0.1), AI cannot see credentials
- Token file path: `~/.mgc/database/mgc_black_box/.mgc_token`

## Security Features

- Credentials decrypted locally
- AI cannot see credential content
- Internal script calls do not expose credentials
- Authorization required before access

    # Use credential to establish connection (example)
    conn = connect_to_database(credential)

    # User's own analysis logic
    result = conn.execute("SELECT SUM(amount) FROM sales WHERE month='2024-06'")
    return result
```

---

# How to Safely Apply Scripts (Zero-Exposure)

Script application must be completed via MGC; AI cannot see script content.

---

## Standard Application Method (Requires User Authorization)

```python
result = mgc_get(
    info_type="script",
    info_owner="analysis_monthly_summary",
    action="run",
    ext02=input_data   # If passing previous step result
)
```

## Security Features

- AI cannot see script content
- AI cannot see credential content
- All execution completed locally
- All operations require user authorization

---

# Script Collaboration (Sealing)

Scripts can be securely shared with team members or external nodes via sealing.

---

## Sealing Script Example

```python
sealed_script = mgc_seal(
    info_type="script",
    info_owner="analysis_monthly_summary",
    ext04=recipient_public_key
)
```

## Security Features

- Sealed scripts always encrypted
- Recipient can apply scripts locally
- Script logic never exposed

---

# Authorization Template (AI Must Ask)

When AI needs to apply scripts, it must ask the user:

```
Script Name: analysis_monthly_summary
Operation: Apply Script (action="run")
Authorization Required: YES

Do you authorize this operation? Reply "yes" to proceed or "no" to cancel.
```

AI must not apply any scripts without user authorization.

---

# Best Practices

## 1. Use Descriptive Script Names
For example:
- `query_monthly_orders`
- `cleaning_standardize_date`
- `analysis_monthly_summary`

## 2. Do Not Hardcode Credentials in Scripts
All credentials must be obtained via MGC.

## 3. Do Not Paste Script Content in AI Conversations
AI cannot protect script logic.

## 4. All Applications Require Authorization
AI must not automatically apply scripts.

## 5. Scripts Should Output Locally
MGC internal execution does not automatically generate files.

---

# FAQ

| Issue | Solution |
|-------|----------|
| Script cannot be applied | Check if info_owner matches |
| Script dependencies missing | Check if dependencies are installed locally |
| Sealing failed | Check if target node has MGC 1.4.6+ |

---

# Summary

This script management document provides:

- Encrypted script storage
- Zero-exposure credential calls
- Zero-exposure script application
- User authorization mechanism
- Script collaboration and sealing

This is the core capability for secure data analyst workflows.

---
