# **MirginCipher Blackbox (MGC)**

MirginCipher Blackbox (MGC) is a **Local Encrypted Execution Layer** designed to protect sensitive human intent and enable secure, deterministic AI execution.  
MGC provides a trusted device‑level encrypted boundary for agents — **it is not an agent itself**.

---

## Architecture

![MGC Architecture](./assets/architecture.png)

---

## **Authorization**
Integration into any third‑party products or AI agents is free of charge,  
but requires official authorization to ensure ecosystem integrity and security.

For authorization requests:  
**zkeviny@icloud.com**

---

## **Core Capabilities**

- **Local encrypted storage**  
  All sensitive data stays on the device and is never uploaded to the cloud.

- **Encrypted execution**  
  Scripts run inside the encrypted boundary; plaintext is never exposed to AI or external systems.

- **Store‑once authorization**  
  Once stored, an item can be reused within the same device environment without repeated confirmation.

- **Environment migration**  
  If hardware changes, access can be restored using a user‑defined migration key.

- **Cross‑agent availability**  
  Any agent platform supporting Skills / MCP can integrate with MGC with zero additional development.

- **Cross‑platform support**  
  Distributed as a Python package with security‑critical components compiled via Cython.

- **No delete function**  
  MGC treats all stored info as user assets.  
  To delete: use WebUI → Database Audit → manually delete via DB Browser.

- **NEW: Script Sealing (Cross‑Node Execution Rights)**  
  MGC can **seal scripts** into non‑readable execution capsules.  
  - Ownership remains with the user  
  - Execution rights can be granted to trusted external nodes  
  - Only the target node can decrypt and execute  
  - No one (including the sender) can read the sealed script  
  This enables **secure cross‑node execution without unauthorized plaintext exposure**.

---

## **Installation**

```bash
pip install mgc-blackbox
```

---

## **Start the Local Encrypted Execution Service**

```bash
mgc
```

Default WebUI port: **57218**  
If the port is occupied, MGC automatically decrements (`57217`, `57216`, …).

WebUI URL:

```
http://127.0.0.1:<port>
```

---

## **Usage Overview**

MGC can be used in two ways:

---

### **1. Through AI agents (Skills / MCP)**  
Agents can:

- Store sensitive information  
- Retrieve encrypted items  
- Execute stored scripts  
- **Seal scripts for trusted nodes (external / local)**  
- All without unauthorized plaintext access  

MCP configuration:  
See `mcp_config.json` in the installation directory.

---

### **2. Through system scripts (REST API)**  
External scripts can fetch encrypted items at runtime.  
Plaintext is never exposed to AI logs or external systems.

For detailed usage:  
**MGC_GUIDE.md**

---

## **Security Model**

- All data remains local  
- No cloud upload  
- No plaintext logging  
- Deterministic execution  
- User‑controlled authorization  
- Protection Mode for high‑security environments  
- Minimal network usage (only version & health checks)

For safety details:  
`docs/user_notice.md`

---

## **AI Skill Specification**

For AI behavior boundaries and tool definitions:  
`docs/skill_spec.md`

---

## **License**

See the LICENSE file for full terms.

© 2026 MirginCipher Team. All rights reserved.

---
