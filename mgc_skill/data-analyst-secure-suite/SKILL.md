---
spec: usk/3.0
id: data-analyst-secure-suite
version: 1.1.0
name: Secure Data Analyst Skill Suite
description: A secure data analysis workflow suite based on MGC Blackbox, providing credential protection, zero-exposure script application, script sealing collaboration, and knowledge management. Also includes a Data Analyst Agent system prompt template.
author: MirginCipher Team
license: MIT
tags: security, data analysis, mgc, zero-exposure, local sandbox, credential management, script management, knowledge management, agent template
platform_compatibility: windows, macos, linux
changelog:
  - version: 1.1.0
    changes:
      - Optimized prompts structure into three core modules: Credential Management, Script Management, Knowledge Management
      - Added agent_system_prompt.md as the Data Analyst Agent system prompt template
      - Enhanced documentation structure with clear usage scenarios and calling methods
  - version: 1.0.0
    changes:
      - Initial release
---

# Overview

**Secure Data Analyst Skill Suite** is a documentation skill suite based on **MGC Blackbox** that helps data analysts securely manage on their local machine:

- Sensitive credentials
- User-owned scripts
- Cross-team collaboration authorization
- Analysis frameworks and knowledge accumulation

This suite uses a **hybrid design**:

- **Skill Prompts (prompts/)**: Provides three core capabilities - Credential Management, Script Management, Knowledge Management
- **Agent System Prompt Template (agent_system_prompt.md)**: For building Data Analyst Agents that follow strict security boundaries

All sensitive operations require explicit user authorization. This suite does not provide any automated data access capabilities.

---

# Use Cases

This skill suite is suitable for:

- Enterprise internal data analysis
- Scenarios requiring sensitive data protection
- Teams needing secure script sharing
- Secure usage of vendor scripts
- Building secure data analysis Agents
- Building knowledge accumulation systems (can be combined with Self-Improving Agent)

---

# Prerequisites

1. Install MGC Blackbox:
   ```
   pip install mgc-blackbox
   ```
2. Start MGC service:
   ```
   mgc
   ```
3. MCP tools available: mgc_save, mgc_get, mgc_seal, mgc_list, mgc_open_webui
4. Token file: `~/.mgc/database/mgc_black_box/.mgc_token`

---

# Core Capabilities

## 1. Credential Management (credential_management.md)

For securely managing database keys, API tokens, and other sensitive credentials.

### Use Cases
- Need to connect to databases or external services
- Scripts need secure credential calls
- Team members need shared access (not data sharing)

### Capabilities
- Local encrypted storage
- AI cannot see credential content
- Scripts can call credentials with zero exposure
- All access requires user authorization

### How Agents Use This
Agents can read credentials after user authorization, but never see plaintext.

---

## 2. Script Management (script_management.md)

For managing user's own query scripts, cleaning scripts, analysis scripts, etc.

### Use Cases
- User needs to apply their own scripts
- Scripts need secure credential calls
- Scripts need cross-team collaboration (sealing)
- Need to build complete data analysis pipelines (query → cleaning → analysis)

### Capabilities
- Scripts stored encrypted
- AI cannot see script content
- Scripts can call credentials with zero exposure
- Script sealing for collaboration
- All applications require user authorization

### How Agents Use This
Agents apply scripts via MGC after user authorization, and can request authorization step-by-step in multi-step workflows.

---

## 3. Knowledge Management (knowledge_management.md)

For managing knowledge assets such as analysis frameworks, prompt templates, methodologies, business rules.

### Use Cases
- Building standardized analysis frameworks
- Reusing prompt templates
- Team sharing analysis methods
- Building knowledge accumulation systems
- Combining with Self-Improving Agent for automatic knowledge accumulation

### Capabilities
- Knowledge content stored encrypted
- AI can read knowledge after user authorization
- Supports knowledge sealing for collaboration
- Can be used to build analysis report structures

### How Agents Use This
Agents can read knowledge after user authorization and use it to guide analysis structures or generate prompts.

---

# Security Boundaries

## This Suite Provides

- Local encrypted credential storage
- Zero-exposure application of user-owned scripts
- Script sealing and collaboration authorization
- Encrypted knowledge management

## This Suite Does NOT Provide

- Automated data access
- Automated cleaning or analysis
- Automated transmission
- Script generation or modification

All scripts must be provided by the user and comply with organizational policies.

---

# File Structure

```
data-analyst-secure-suite/
├── SKILL.md                    # Main skill document (this file)
├── README.md                   # Detailed usage guide
├── manifest.json               # Skill metadata
├── agent_system_prompt.md      # Agent system prompt template
└── prompts/
    ├── credential_management.md    # Credential management
    ├── script_management.md        # Script management
    └── knowledge_management.md    # Knowledge management
```

---

# Usage

## Mode 1: As a Skill (Skill Mode)

AI can read the three core documents in prompts/:

| Document | Use Case | Triggered By |
|----------|----------|--------------|
| credential_management.md | Need to store or access credentials | User or Agent |
| script_management.md | Need to store or apply scripts | User or Agent |
| knowledge_management.md | Need to store or read knowledge | User or Agent |

AI will reference the corresponding document based on user requests and request authorization before each sensitive operation.

---

## Mode 2: As an Agent Template (Agent Mode)

Configure `agent_system_prompt.md` as the system prompt for the AI Agent.

The Agent will automatically follow these security boundaries:

- Request user authorization before each sensitive operation
- Apply scripts only via MGC Blackbox
- Must not view script content or credentials
- Must not automatically execute workflows
- Must not auto-select script names (info_owner must be provided by user)

The Agent can reference documents in prompts/ as workflow guidance after user authorization.

---

# MCP Tools Reference

| Tool | Description | Authorization Required |
|------|-------------|----------------------|
| mgc_save | Store credentials, scripts, prompts | Yes |
| mgc_get | Retrieve or apply scripts | Yes |
| mgc_seal | Seal scripts for collaboration | Yes |
| mgc_list | List stored items | Optional |
| mgc_open_webui | Open MGC WebUI | No |

---

# Security Notes

1. **Zero-exposure**: Scripts and credentials execute locally, AI only receives results
2. **Encrypted storage**: All content stored encrypted
3. **No plaintext leakage**: AI never sees script or credential content
4. **Script sealing**: Cross-node collaboration remains encrypted

---

# Contact

- Issues: https://github.com/zkeviny/MGC-Blackbox/issues
- Email: mirgincipher@outlook.com

---

> **Reminder**: This skill suite is for secure workflow management. All sensitive operations require explicit user authorization. All scripts are user-owned, and all execution is completed locally via MGC Blackbox.

---
