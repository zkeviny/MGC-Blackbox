# 📘 **Doc‑as‑Skill #1: Sensitive Credentials Authorization**

## 🎯 Value Scenario  
Your scripts often require sensitive information such as:

- passwords  
- API tokens  
- private keys  

Traditionally you must:

- hard‑code the credential into the script, or  
- manually input it every time  

Both are insecure and inconvenient.

MGC solves this by providing:

> **Local encrypted storage + controlled access interface**  
> Your script can securely retrieve sensitive data at runtime without exposing it to AI, users, or other programs.

> **This document is also a skill — you can give it to your AI and let it follow the steps.**

---

## 🛠 How to Use (AI‑Executable Instructions)

> **Note:**  
> - These examples use MCP tools (`mgc_save`) for *writing* sensitive data.  
> - Retrieval uses the REST API to ensure the AI never sees the credential.  
> - Make sure MGC is installed (`pip install mgc-blackbox`) and running (`mgc`).

---

## **Step 1 — Store the credential in MGC (via MCP)**

```
mgc_save(
    info_type="token",
    info_owner="my_github",
    content="ghp_xxx..."
)
```

This stores the token in MGC’s encrypted local database.

---

## **Step 2 — Retrieve the credential inside your script (via REST API)**

> **Why REST API?**  
> MCP returns values to the AI.  
> REST API returns values only to your script — AI cannot see them.

### Python example:

```python
import os
import requests

# Read MGC token
with open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")) as f:
    mgc_token = f.read().strip()

# Retrieve sensitive data via REST API
resp = requests.post(
    "http://127.0.0.1:57219/api/mgc/sensitive/get",
    headers={"X-MGC-Token": mgc_token},
    json={
        "info_type": "token",
        "info_owner": "my_github"
    }
)

token = resp.json().get("data")
```

Now your script has the token — without exposing it to AI.

---

## **Step 3 — Run your external script**

Since the script is stored outside MGC:

```bash
python github_check.py
```

> For encrypted script storage and sealed execution, see  
> **Doc‑as‑Skill #2: Encrypted Cognitive Script Execution**.

---

## ⭐ Best Practices

- Use WebUI to store sensitive data if you don’t want AI to touch it  
- Never embed tokens in scripts  
- Never expose tokens to AI unless explicitly intended  
- Always retrieve sensitive data from MGC at runtime  
- MGC listens only on localhost and uses token‑based auth  

---

## 🔒 Security Boundary

- AI cannot read the credential  
- Users cannot read the credential  
- Local malware cannot directly access MGC  
- Sensitive data is only accessed at execution time  

---