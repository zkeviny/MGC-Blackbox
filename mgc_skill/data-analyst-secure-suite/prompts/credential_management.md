# Credential Management Workflow

This document guides data analysts on how to securely manage database keys, API tokens, and other sensitive credentials in **MGC Blackbox**, and implement **zero-exposure calls** in scripts.

All sensitive operations must be explicitly authorized by the user before proceeding.

---

# Overview

MGC Blackbox provides local encrypted storage and zero-exposure access capabilities:

- Credentials never exposed to AI in plaintext
- Credentials decrypted only on user's local machine
- Scripts can safely call credentials, but AI cannot see content
- All access requires user authorization

---

# How to Securely Store Credentials

Credential storage is recommended via **MGC WebUI** or **mgc_save** tool.

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
info_type: "credential"
info_owner: "db_warehouse_prod"   # Custom name
content: <your database credentials>  # Encrypted locally
```

## Method 2: Via mgc_save

```python
mgc_save(
    info_type="credential",
    info_owner="db_warehouse_prod",
    content="postgres://user:password@host:5432/dbname"
)
```

## Security Notes

- Credentials stored encrypted locally
- AI cannot see credential content
- All access requires user authorization
- Credentials never leave user's machine

---

# How to Call Credentials with Zero Exposure (Core)

Scripts can safely access credentials, but AI can never see credential content.

Below is the **standard zero-exposure credential call pattern** (pseudocode):

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
        print("Token not found!")
        return None

    resp = requests.post(
        f"{BASE_URL}/api/mgc/sensitive/get",
        headers={"X-MGC-Token": token, "Content-Type": "application/json"},
        json={
            "info_type": "credential",
            "info_owner": "db_warehouse_prod"  # Credential name
        }
    )

    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 200:
            data_field = data.get("data")
            # data_field may be string or dict
            if isinstance(data_field, str):
                return json.loads(data_field)
            elif isinstance(data_field, dict):
                content = data_field.get("content")
                if content:
                    return json.loads(content)
    return None

# Using credential
def query_monthly_orders():
    credential = get_credential()
    # ... Use credential to connect and query
```

Note:
- This call is local only (127.0.0.1), AI cannot see credentials
- Token file path: `~/.mgc/database/mgc_black_box/.mgc_token`

## Security Features

- Credentials decrypted locally
- AI cannot see credential content
- Internal script calls do not expose credentials
- Authorization required before access

---

## Using Credentials in Scripts (Example)

```python
def query_monthly_orders():
    credential = get_db_credential()

    # Use credential to establish connection (example)
    conn = connect_to_database(credential)

    # Execute user's own query logic
    result = conn.execute("SELECT * FROM orders WHERE month = '2024-06'")
    return result
```

---

# How to Authorize Credential Access (User Must Confirm)

When AI needs to access credentials, it must ask the user:

```
Credential Name: db_warehouse_prod
Operation: Access Credential
Authorization Required: YES

Do you authorize accessing this credential? Reply "yes" to proceed or "no" to cancel.
```

AI must not access any credentials without user authorization.

---

# Best Practices

## 1. Use Descriptive info_owner
For example:
- `db_warehouse_prod`
- `api_salesforce_token`
- `redis_cache_credential`

## 2. Do Not Hardcode Credentials in Scripts
All credentials must be obtained via MGC.

## 3. Do Not Paste Credentials in AI Conversations
AI cannot protect plaintext credentials.

## 4. All Access Requires Authorization
AI must not automatically access credentials.

---

# FAQ

| Issue | Solution |
|-------|----------|
| Script cannot access credentials | Check if info_owner matches |
| Credentials empty | Check if WebUI stored correctly |
| Execution failed | Check if script dependencies are available locally |

---

# Summary

This credential management document provides:

- Local encrypted storage
- Zero-exposure calls
- User authorization mechanism
- Secure script writing guidelines

This is the foundational capability for secure data analyst workflows.

---
