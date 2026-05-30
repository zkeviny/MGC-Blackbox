# **MirginCipher Blackbox (MGC)**  
A secure local execution layer for AI agents — encrypted storage, sealed scripts, zero plaintext leakage.

![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-MacOS%20%7C%20Linux-blue)
![MCP](https://img.shields.io/badge/MCP-Compatible-orange)

---

## **What is MGC Blackbox?**

MirginCipher Blackbox (MGC) is a **Local Encrypted Execution Layer** designed to protect sensitive human intent and enable **secure, deterministic AI execution**.  
It provides a trusted device‑level encrypted boundary for agents — **MGC is not an agent itself**.

MGC ensures:

- Sensitive data never leaves the device  
- AI agents cannot access plaintext  
- Scripts execute inside a sealed, encrypted environment  
- Cross‑node execution is possible without exposing code  

---

## **Why MGC?**

- 🔐 End‑to‑End Encrypted Storage  
AES‑256 encrypted vault for API keys, credentials, configs — never exposed to AI agents or external systems.

- 🧱 Local‑First Security Boundary  
All execution and decryption happen on‑device. No cloud dependency, no plaintext leakage, no telemetry.

- 🧩 Sealed Script Execution (Unique)  
Convert scripts into unreadable execution capsules.
Only trusted nodes can decrypt & run them — even the sender cannot read sealed scripts.

- ⚡ Deterministic Local Execution  
Stable, reproducible behavior across macOS / Linux with a Cython‑compiled secure core.

- 🛠️ Native MCP / Skill Integration  
Exposes mgc_save / mgc_get / mgc_list / mgc_open_webui as standard MCP tools.
Works out‑of‑the‑box with Copilot, Claude, Trae, IDE Agents.

- 🔄 Zero Integration Cost  
Any MCP‑compatible agent can immediately use MGC as its secure execution backend — no SDK, no custom code.

- 🛡️ Designed for AI Agent Security  
Protects human intent, prevents agent overreach, and enforces strict execution boundaries. 

---

## **Architecture**

<p align="center">
  <img src="./assets/architecture.png" width="90%">
</p>

---

## **Features**

- **Local encrypted storage**  
  Sensitive data is encrypted and never uploaded to the cloud.

- **Encrypted execution**  
  Scripts run inside the encrypted boundary; plaintext is never exposed to AI or external systems.

- **Store‑once authorization**  
  Items can be reused within the same device environment without repeated confirmation.

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
  MGC can **seal scripts** into non‑readable execution capsules:  
  - Ownership remains with the user  
  - Execution rights can be granted to trusted external nodes  
  - Only the target node can decrypt & execute  
  - Sender cannot read sealed script contents  
  Enables **secure cross‑node execution without plaintext exposure**.

---

## **Quick Start**

```bash
pip install mgc-blackbox
mgc
```

WebUI URL:

```
http://127.0.0.1:<port>
```

Default port: **57218**  
If occupied, MGC automatically decrements (`57217`, `57216`, …).

---

## **Example: Save & Retrieve Secrets**

```python
from mgc import save, get

save("openai_key", "sk-xxxx")
print(get("openai_key"))
```

---

## **MCP Integration**

MGC exposes a local MCP tools interface:

- `mgc_save`
- `mgc_get`
- `mgc_list`
- `mgc_open_webui`

Compatible with:

- Copilot Agent  
- Claude Agent  
- Trae Agent  
- IDE Agents  
- Custom Agents  

MCP configuration file:  
`mcp_config.json` (auto‑generated on installation)

---

## **Usage Overview**

### **1. Through AI agents (Skills / MCP)**  
Agents can:

- Store sensitive information  
- Retrieve encrypted items  
- Execute stored scripts  
- **Seal scripts for trusted nodes (external / local)**  
- All without unauthorized plaintext access  

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

## **Authorization**

Integration into any third‑party products or AI agents is free of charge,  
but requires official authorization to ensure ecosystem integrity and security.

For authorization requests:  
**zkeviny@icloud.com**

---

## **License**

See the LICENSE file for full terms.

© 2026 MirginCipher Team. All rights reserved.
```

---
