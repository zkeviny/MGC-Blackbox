spec: usk/3.0
id: data-analyst-secure-suite
version: 1.3.0
name: Secure Data Analyst Skill Suite
description: A secure data analysis workflow suite based on MGC Blackbox 1.5.2+, providing credential protection, zero-exposure script & workflow application, sealed-package collaboration, and knowledge management. Supports MGC 1.5.2 workflow auto-recognition (import / from-import / relative paths / subprocess runtime routing). Includes a Data Analyst Agent system prompt template.
author: MirginCipher Team
license: MIT
tags: security, data analysis, mgc, zero-exposure, local sandbox, credential management, workflow management, sealed collaboration, knowledge management, agent template, fuzzy search, auto-recognized workflow, sealed cross-script
platform_compatibility: windows, macos, linux
requires:
  mgc_blackbox: ">=1.5.2"
changelog:
  - version: 1.3.0
    changes:
      - Upgraded to MGC 1.5.2+: added mgc_save_file (workflow folder storage), mgc_seal_package (workflow sealing), mgc_package (plaintext packaging).
      - Script management refactor: upgraded from single-script to workflow-folder mode, with import / from-import / relative-path / subprocess auto-recognition.
      - Credential management: unified info_type from 'credential' to 'token' to align with skill_spec.
      - Added prompts/collaboration_management.md: dedicated workflow / skill-package sealed-authorization guide.
      - Agent template: workflow examples upgraded from 5-step manual chain to find -> save_file -> run pattern.
      - Added sealed-collaboration chapter (mgc_seal_package one-click seal of an entire workflow).
      - Added recognizable cross-script patterns table (from-import / import / Path / subprocess).
      - MCP tools list expanded to 10 (added mgc_save_file, mgc_seal_package, mgc_package).
  - version: 1.2.0
    changes:
      - Synced with MGC Blackbox 1.4.10: added mgc_find (fuzzy search) and mgc_run (preferred over mgc_get action=run).
      - Script management: replaced mgc_get(action='run') with dedicated mgc_run tool.
      - Script management: added mgc_find workflow for locating scripts by name.
      - Script sealing: clarified ext04 must be a multi-line PEM public key.
      - Credential management: added mgc_find workflow.
      - Knowledge management: added mgc_find workflow.
      - Agent system prompt: documented the find -> get/run workflow pattern.
  - version: 1.1.1
    changes:
      - Optimized documentation structure per review report
      - Added 'Anti-patterns and pitfalls' chapter
      - Added 'Complete use cases' chapter
      - Unified prompt file-name references
  - version: 1.1.0
    changes:
      - Consolidated prompts into three core modules: credential, script, knowledge management
      - Added agent_system_prompt.md as a Data Analyst Agent system-prompt template
      - Strengthened document structure and clarified each module's scenario and invocation
  - version: 1.0.0
    changes:
      - Initial release
---

# Overview

**Secure Data Analyst Skill Suite** is a documentation skill suite built on **MGC Blackbox 1.5.2+** that helps data analysts securely manage, on the local machine:

- Sensitive credentials
- User-owned scripts and workflows
- Workflow / skill-package sealed authorization collaboration
- Analysis frameworks and knowledge

This suite uses a **hybrid design**:

- **Skill prompts (under `prompts/`)**: four core capabilities — credential management, workflow management, sealed-collaboration, knowledge management
- **Agent system-prompt template (`agent_system_prompt.md`)**: builds a Data Analyst Agent that obeys strict security boundaries

All sensitive operations require explicit user authorization. This suite provides no automated data-access capability.

---

# Scenarios

This suite is suitable for:

- In-house enterprise data analysis
- Scenarios requiring sensitive-data protection
- Secure sharing of scripts / workflows in team collaboration
- Safe use of vendor scripts
- Building a secure Data Analyst Agent
- Building a knowledge accumulation system (can pair with a Self-Improving Agent)

---

# Prerequisites

1. Install MGC Blackbox (≥ 1.5.2):
   ```
   pip install mgc-blackbox
   ```
2. Start the MGC service:
   ```
   mgc
   ```
3. Available MCP tools: mgc_save, mgc_save_file, mgc_get, mgc_run, mgc_seal, mgc_seal_package, mgc_package, mgc_list, mgc_find, mgc_open_webui
4. Token file: `~/.mgc/database/mgc_black_box/.mgc_token`

---

# Core capabilities

## 1. Credential management (`credential_management.md`)

Securely manage sensitive credentials such as database keys and API tokens.

### Scenarios
- Need to connect to databases or external services
- Scripts need safe access to credentials
- Team members share database/service **access rights** (not the data itself)
- Team members share **analysis methods and scripts** across the team and outside (via workflow sealed authorization)

### What it provides
- Local encrypted storage
- AI never sees credential content
- Scripts can call credentials with zero exposure
- All accesses require user authorization

### How the agent uses it
After user authorization, the agent reads credentials but never sees plaintext.

---

## 2. Workflow management (`script_management.md`)

Manage user-owned query / clean / analyze scripts — both single-script and workflow-folder modes.

### Scenarios
- User wants to apply their own scripts or workflows
- Scripts need safe access to credentials
- Multi-script workflows need auto-recognition of import / subprocess call relationships (1.5.2+)
- Workflows need cross-team collaboration (sealed)
- Need to build a complete data-analysis chain (query → clean → analyze)

### What it provides
- Single-script encrypted storage (`mgc_save`)
- Workflow-folder encrypted storage with auto-recognition of import / subprocess (`mgc_save_file`, 1.5.2+)
- AI never sees script content
- Scripts call credentials with zero exposure
- Supports single-script sealing (`mgc_seal`) and workflow sealing (`mgc_seal_package`)
- All applications require user authorization

### How the agent uses it
After user authorization, the agent runs scripts or workflows through MGC. In workflow mode, MGC auto-recognizes the import chain — no manual parameter chaining needed.

---

## 3. Sealed-authorization collaboration (`collaboration_management.md`)

Seal-authorize workflows and skill packages to other nodes, enabling "usable but not readable, runnable but not resellable" cross-team / cross-organization collaboration.

### Scenarios
- Data team seals an analysis workflow to a business team (run only, no source access)
- Vendor analyst seals an analysis solution to a client
- Cross-department sharing of analysis methodologies while protecting core logic
- Independent license per client

### What it provides
- Workflow sealing (`mgc_seal_package`): seal the entire workflow in one call, AES-256 encryption
- Skill-package sealing: seal a complete skill package (with SKILL.md); receiving AI can read the instructions but cannot see source code
- Node binding: AES key bound to the target node's RSA public key; cannot be re-sealed
- One-key-per-node: each client receives an independent key
- No cloud: all encryption / decryption / execution happens locally

### How the agent uses it
After user authorization, the agent performs the sealing operation. The sealed package is delivered by the user manually — the agent does not participate in transport.

---

## 4. Knowledge management (`knowledge_management.md`)

Manage knowledge assets: analysis frameworks, prompt templates, methodologies, business rules, and more.

### Scenarios
- Build standardized analysis frameworks
- Reuse prompt templates
- Share analysis methods across the team
- Build a knowledge accumulation system
- Pair with a Self-Improving Agent for automatic knowledge capture

### What it provides
- Encrypted storage of knowledge content
- Agent reads knowledge with explicit user authorization
- Knowledge sealed collaboration supported
- Used to build analysis-report structure

### How the agent uses it
After user authorization, the agent reads knowledge and uses it to guide analysis structure or generate prompts.

---

# Security boundary

## This suite provides

- Local encrypted credential storage
- Zero-exposure application of user-owned scripts
- Workflow auto-recognition and sealed routing (1.5.2+, including subprocess literal-list runtime routing)
- Sealed-authorization collaboration for workflows / skill packages (1.5.2+)
- Knowledge encryption management

## This suite does NOT provide

- Automated data access
- Automated cleaning or analysis
- Automated transport
- Script generation or modification

All scripts must be user-provided and comply with organizational policy.

---

# File structure

```
data-analyst-secure-suite/
├── SKILL.md                    # main document (this file)
├── README.md                   # detailed usage guide
├── manifest.json               # skill metadata
├── agent_system_prompt.md      # Agent system-prompt template
└── prompts/
    ├── credential_management.md    # credential management
    ├── script_management.md        # workflow & script management
    ├── collaboration_management.md # sealed collaboration
    └── knowledge_management.md     # knowledge management
```

---

# Usage modes

## Mode 1 — Skill mode

The AI can read the four core prompts under `prompts/`:

| Document | When to use | Triggered by |
|----------|-------------|--------------|
| `credential_management.md` | Need to store or access credentials | user or agent |
| `script_management.md` | Need to store or run a script/workflow | user or agent |
| `collaboration_management.md` | Need to seal a workflow / skill package to another node | user or agent |
| `knowledge_management.md` | Need to store or read knowledge | user or agent |

The AI cites the matching document on user request and asks for authorization before every sensitive operation.

---

## Mode 2 — Agent template mode

Set `agent_system_prompt.md` as the system prompt for an AI Agent.

The agent will automatically enforce:

- Request user authorization before every sensitive operation
- Only apply scripts or workflows through MGC Blackbox
- Never view script content or credentials
- Never automate workflow execution
- Never auto-select a script name (`info_owner` must be supplied by the user)

After authorization, the agent may cite documents under `prompts/` as workflow guidance.

---

# MCP tools reference

| Tool | Description | Authorization required |
|------|-------------|------------------------|
| `mgc_save` | Store credentials, single scripts, prompts | yes |
| `mgc_save_file` | Store workflow folders (auto-recognize import / subprocess) | yes |
| `mgc_get` | Retrieve a value / fetch node_pub | yes |
| `mgc_run` | Run a script or workflow (black-box) | yes |
| `mgc_seal` | Seal a single script for collaboration | yes |
| `mgc_seal_package` | Seal an entire workflow folder | yes |
| `mgc_package` | Plaintext packaging within the same trust zone | yes |
| `mgc_list` | List stored entries (exact match) | optional |
| `mgc_find` | Fuzzy-search entries by name | optional |
| `mgc_open_webui` | Open MGC WebUI | no |

---

# Security notes

1. **Zero exposure**: scripts and credentials execute locally; the AI receives only run status
2. **Encrypted storage**: all content encrypted at rest
3. **No plaintext leak**: the AI never sees script or credential content
4. **Auto-recognized workflows**: import / from-import / relative-path / subprocess call chains auto-routed; nothing lands on disk (1.5.2+)
5. **Sealed workflows / skill packages**: entire workflow or skill package sealed to the target node in one call; node-bound; cannot be resold (1.5.2+)

---

# Contact

- Issues: https://github.com/zkeviny/MGC-Blackbox/issues
- Email: mirgincipher@outlook.com

---

> **Reminder**: This suite is for secure workflow management. All sensitive operations must have explicit user authorization. All scripts are user-owned; all execution happens locally through MGC Blackbox.