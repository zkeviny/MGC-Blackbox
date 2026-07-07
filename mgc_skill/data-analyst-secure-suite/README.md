# Secure Data Analyst Skill Suite

A mixed-form skill suite combining **workflow prompts + an Agent system prompt template**, designed to help data analysts safely manage scripts, credentials, collaboration, and knowledge using **MGC Blackbox**.

---

## What This Skill Suite Provides

This suite enables data analysts to securely manage their end-to-end workflow **on their local machine**, including:

- **Credential management** — encrypted, zero-exposure storage
- **User-owned scripts** — safe application of query, cleaning, and analysis scripts
- **Script sealing & collaboration** — encrypted sharing across teams
- **Knowledge management** — store analysis frameworks and reusable prompts
- **Optional Agent template** — build a safe Data Analyst Agent that follows strict authorization rules

All sensitive operations require explicit user authorization.
This suite does **not** provide any automated data access capabilities.

---

## Prerequisites

- Python 3.10+
- Install MGC Blackbox:
  ```
  pip install mgc-blackbox
  ```
- Start MGC:
  ```
  mgc
  ```
  - WebUI: `http://127.0.0.1:57218` (Visual Interface)
  - API: `http://127.0.0.1:57219` (API Interface)
  - Token Required: Header "X-MGC-Token"
  - Token File: `~/.mgc/database/mgc_black_box/.mgc_token`

---

## Intended Users

- Data analysts working with sensitive business data
- Teams requiring secure script collaboration
- Organizations protecting local data assets
- Users building safe data-analysis Agents

---

## Secure Workflow Overview

```
┌──────────────────────────────────────────────┐
│           Secure Data Analysis              │
├──────────────────────────────────────────────┤
│                                              │
│  Credential → User Query Scripts → Cleaning │
│                                              │
│  → Analysis → Secure Delivery → Knowledge   │
│                                              │
└──────────────────────────────────────────────┘
```

All scripts are user-owned, all applications completed via MGC locally, AI cannot see scripts or credentials.

---

## Core Components

### 1. Credential Management (Zero-Exposure)

Users store database credentials via MGC WebUI:

```
info_type: "credential"
info_owner: "db_connection_name"
content: Encrypted credentials (user-owned)
```

AI cannot see credentials.

---

### 2. Query Scripts (User-Owned)

Users store their query scripts in MGC:

```
info_type: "script"
info_owner: "query_monthly_orders"
ext01: "python"
content: User-owned script
```

Apply script (requires user authorization):

```python
result = mgc_get(
    info_type="script",
    info_owner="query_monthly_orders",
    action="run"
)
```

---

### 3. Cleaning Scripts (User-Owned)

Cleaning scripts are also provided by the user:

```python
result = mgc_get(
    info_type="script",
    info_owner: "cleaning_standardize_date",
    action="run",
    ext02=input_data
)
```

---

### 4. Analysis Scripts (User-Owned)

Analysis scripts can use credentials stored in MGC locally (AI cannot see):

```python
result = mgc_get(
    info_type="script",
    info_owner: "analysis_monthly_summary",
    action="run"
)
```

---

### 5. Secure Delivery

Three delivery methods supported:

- Local export
- Sealed results (for collaboration)
- Credential-based access (team sharing)

All transmission must be completed manually by user; this suite does not provide automatic transmission capabilities.

---

### 6. Knowledge Management (Analysis Frameworks / Prompts / Methodologies)

Users can store analysis frameworks in MGC:

```python
mgc_save(
    info_type="prompt",
    info_owner: "framework_monthly_sales",
    content: "Analysis framework content"
)
```

AI can read frameworks for analysis after user authorization.

---

## Security Boundaries (Must Follow)

### This Suite Provides:

- Local encrypted credential storage
- Zero-exposure application of user-owned scripts
- Script sealing & collaboration authorization
- Encrypted knowledge management

### This Suite Does NOT Provide:

- Automated data access
- Automated cleaning or analysis
- Automated transmission
- Cross-organization data transmission
- Script generation or modification

All scripts must be provided by the user and comply with organizational policies.

---

## MCP Tools Reference

| Tool | Description |
|------|-------------|
| mgc_save | Store credentials, scripts, prompts |
| mgc_get | Apply scripts after user authorization |
| mgc_seal | Seal scripts for collaboration |
| mgc_list | List stored items |
| mgc_open_webui | Open MGC WebUI |

---

## Prompt Templates (Skill Suite Section)

Located in `prompts/` directory:

- `credential_management.md` — Credential management workflow
- `script_management.md` — Script management workflow
- `knowledge_management.md` — Knowledge management workflow

---

## Agent Template (Hybrid Enhancement)

This skill suite includes an optional **Data Analyst Agent system prompt template**:

### agent_system_prompt.md

Used to build a safe data analysis Agent. The Agent will:

- Request user authorization before each sensitive operation
- Apply scripts via MGC after user authorization
- Must not view script content
- Must not access credentials
- Must not automatically execute workflows
- Must not auto-select script names (info_owner must be provided by user)

### How to Use Agent Template

1. When creating an Agent, use `agent_system_prompt.md` as the system prompt
2. Configure MCP tools: mgc_save / mgc_get / mgc_seal / mgc_list / mgc_open_webui
3. Agent can reference prompts in `prompts/` directory for workflow nodes

Agent is an optional enhancement, not a required component.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Script application fails | Check if credentials stored correctly |
| Sealing fails | Ensure target node has MGC 1.4.6+ |
| Workflow interrupted | Check if user authorization is missing |

---

## Contact

- Issues: https://github.com/zkeviny/MGC-Blackbox/issues
- Email: mirgincipher@outlook.com

---

## License

MIT License

---

# Complete Note

This skill suite is for secure workflow management.
All sensitive operations require user authorization.
This suite does not provide any automated data access capabilities. All scripts must be provided by the user and comply with organizational policies.

---
