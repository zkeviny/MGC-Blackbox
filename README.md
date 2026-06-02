# **MirginCipher Blackbox (MGC)** — Encrypted AI Agent Execution Layer

<p align="left">
  <a href="https://github.com/zkeviny/MGC-Blackbox/issues/4">
    <img src="https://img.shields.io/badge/Roadmap-2026-blue?style=flat-square" alt="Roadmap">
  </a>
  <a href="https://pypi.org/project/mgc-blackbox/">
    <img src="https://img.shields.io/pypi/v/mgc-blackbox?style=flat-square&color=brightgreen" alt="PyPI Version">
  </a>
  <a href="https://github.com/zkeviny/MGC-Blackbox/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-MGC--Custom--License-orange?style=flat-square" alt="License">
  </a>
  <img src="https://img.shields.io/badge/Platforms-MacOS%20%7C%20Linux%20%7C%20Windows-lightgrey?style=flat-square" alt="Platforms">
  <img src="https://img.shields.io/badge/MCP-Compatible-blueviolet?style=flat-square" alt="MCP Compatible">
  <a href="https://registry.modelcontextprotocol.io/servers/io.github.zkeviny/mgc-blackbox">
    <img src="https://img.shields.io/badge/MCP-Registry-000000?style=flat-square" alt="MCP Registry">
  </a>
</p>

A secure local execution layer for AI agents — encrypted storage, sealed scripts, zero plaintext leakage.  
Protect API keys, credentials, and scripts from AI agents with AES‑256 + RSA hybrid encryption and a Cython‑compiled secure core.

> 📌 **Roadmap:** [MGC Blackbox — 2026 Development Plan](https://github.com/zkeviny/MGC-Blackbox/issues/4)

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

- 🔐 **End‑to‑End Encrypted Storage**  
  AES‑256 encrypted vault for API keys, credentials, configs — never exposed to AI agents or external systems.

- 🧱 **Local‑First Security Boundary**  
  All execution and decryption happen on‑device. No cloud dependency, no plaintext leakage, no telemetry.

- 🧩 **Sealed Script Execution (Unique)**  
  Convert scripts into unreadable execution capsules.  
  Only trusted nodes can decrypt & run them — even the sender cannot read sealed scripts.

- ⚡ **Deterministic Local Execution**  
  Stable, reproducible behavior across macOS / Linux / Windows with a Cython‑compiled secure core.

- 🛠️ **Native MCP / Skill Integration**  
  Exposes mgc_save / mgc_get / mgc_list / mgc_seal / mgc_open_webui as standard MCP tools.  
  Works out‑of‑the‑box with Copilot, Claude, Trae, IDE Agents.

- 🔄 **Zero Integration Cost**  
  Any MCP‑compatible agent can immediately use MGC as its secure execution backend — no SDK, no custom code.

- 🛡️ **Designed for AI Agent Security**  
  Protects human intent, prevents agent overreach, and enforces strict execution boundaries.

---

## **Use Cases**

### **1. Protect API Keys & Credentials from AI Agents**  
Store secrets encrypted. Agents can use them, but never see plaintext.

### **2. Secure Local Automation**  
Run Python / Shell / Node scripts locally without exposing sensitive data to AI logs or cloud systems.

### **3. Sealed Script Distribution**  
Share scripts with collaborators or devices **without exposing source code** — they can execute but cannot read.

### **4. Cross‑Node Execution**  
Send sealed scripts to trusted remote nodes:
- Sender cannot read the sealed content  
- Recipient cannot read the sealed content  
- Only the target node can decrypt and execute  

### **5. Local‑First AI Agent Security Boundary**  
Provides a local security layer for Copilot / Claude / Trae / IDE Agents.

### **6. Privacy‑Preserving AI Workflows**  
Enables financial automation, personal data processing, and enterprise internal workflows with privacy protection.

---

## 📘 **Value Scenarios**

MGC Blackbox provides a **trusted, encrypted execution boundary** for different roles and environments.  
Detailed scenario documents:

- 🔐 **Sensitive Credentials Authorization**  
  [docs/Sensitive_Credentials_Authorization.md](docs/Sensitive_Credentials_Authorization.md)

- 🧠 **Encrypted Cognitive Script Execution**  
  [docs/Encrypted_Cognitive_Script_Execution.md](docs/Encrypted_Cognitive_Script_Execution.md)

- 🌐 **Cross‑Node Execution Grant (Encrypted Capability Sharing)**  
  [docs/Cross‑Node_Execution_Grant%20(Encrypted_Capability_Sharing).md](docs/Cross‑Node_Execution_Grant%20(Encrypted_Capability_Sharing).md)

---

## **Architecture**

<p align="center">
  <img src="./assets/architecture.png" width="90%">
</p>

---

## **Crypto Layer & Performance**

MGC uses a **hybrid cryptographic design**:

- **AES‑256‑GCM** — bulk data encryption  
- **RSA‑2048/4096** — key encapsulation & node authorization  

The crypto layer is **Cython‑compiled** to:

- Improve AES & RSA performance  
- Reduce Python overhead  
- Provide a sealed, tamper‑resistant execution boundary  
- Maintain deterministic behavior across nodes  

---

## **Features**

- Local encrypted storage  
- Encrypted execution  
- Store‑once authorization  
- Environment migration  
- Cross‑agent availability  
- Cross‑platform support  
- No delete function (manual DB deletion only)  
- Script sealing for cross‑node execution  

---

## **Quick Start**

### **1. Install**

```bash
pip install mgc-blackbox
```

### **2. Start Service**

```bash
mgc
```

### **3. Open WebUI**

```
http://127.0.0.1:57218
```

### **4. Store a Secret**

```python
from mgc import save
save("openai_key", "sk-xxxx")
```

### **5. Execute Scripts Securely**

Scripts run inside MGC's encrypted boundary.

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
- `mgc_seal`  
- `mgc_open_webui`  

Compatible with Copilot, Claude, Trae, IDE Agents.

---

## **Usage Overview**

### **1. Through AI agents (Skills / MCP)**  
Agents can store secrets, retrieve encrypted items, execute scripts, and seal scripts.

### **2. Through system scripts (REST API)**  
External scripts can fetch encrypted items at runtime.

---

## **Security Model**

- All data remains local  
- No cloud upload  
- No plaintext logging  
- Deterministic execution  
- User‑controlled authorization  

---

## **AI Skill Specification**

See: `docs/skill_spec.md`

---

## **Authorization**

Integration into any third‑party products or AI agents is free,  
but requires official authorization to ensure ecosystem integrity.

Contact: **zkeviny@icloud.com**

---

## **License**

See the LICENSE file for full terms.

© 2026 MirginCipher Team. All rights reserved.
```

---
