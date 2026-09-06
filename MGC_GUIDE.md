# 📘 MGC Blackbox — User Guide

**Version 1.5.0**

A local encrypted execution base for AI agents, system scripts, and human users to store, retrieve, run, and delegate sensitive data or scripts — without unauthorized plaintext exposure.

For the full specification, see [`mgc/docs/skill_spec.md`](mgc/docs/skill_spec.md). This guide covers the essentials only.

---

## Install & Run

```bash
pip install mgc-blackbox
mgc
```

WebUI starts at `http://127.0.0.1:57218` (auto-decrements if occupied; actual port shown in startup log).

**First-time setup**: open WebUI, set the **root key** (human-memorized phrase) that encrypts the local database.

---

## Three Invocation Channels

| Caller | Channel | Typical use |
|---|---|---|
| AI agent | MCP tools | Store / retrieve / run / seal / seal-package |
| System script | REST API | Embed in CI / cron / internal services |
| Human | WebUI | Setup, manual entry, audit |

All three share the same encrypted backend; no plaintext crosses the API surface for stored entries.

---

## MCP Tools (AI agent)

| Tool | Purpose |
|---|---|
| `mgc_save` | Store an entry (info_type + info_owner + content). For `info_type='file'`, content is a local folder path or a `.mgc_file` path. |
| `mgc_get` | Retrieve / list / run an entry. Actions: `run` (script), `package` / `seal_package` (folder). Prefer the dedicated tools below. |
| `mgc_run` | Execute a stored script. Returns `pid + status` only; observe results via stdout / files / external services. |
| `mgc_find` | Fuzzy-search entries. **Single-field only** — `info_type` cannot be combined with other filters. |
| `mgc_list` | List all entries (metadata only). |
| `mgc_seal` | Seal a single script for another node (RSA-wrapped AES key in `ext04`). |
| `mgc_package` | Export a stored folder as plaintext. |
| `mgc_seal_package` | Seal a folder into a `.mgc_file` (max 100 files / 50 MB). |
| `mgc_open_webui` | Open WebUI in browser. |

---

## REST API (system scripts)

**Base URL**: `http://127.0.0.1:57218`  
**Header**: `X-MGC-Token: <token>` (token at `~/.mgc/database/mgc_black_box/.mgc_token`)

| Endpoint | Purpose |
|---|---|
| `POST /api/mgc/sensitive/save` | Store an entry |
| `POST /api/mgc/sensitive/get` | Retrieve / list / run an entry (with `action` field) |
| `POST /api/mgc/proxy/get` | Package / seal-package a folder |

---

## Key Concepts

### Fields

- `info_type`: `password` / `token` / `api_key` / `script` / `config` / `file`
- `info_owner`: who + where (e.g. `"user's GitHub"`, `"Amy's Aliyun"`)
- `diff_1` / `diff_2` / `diff_3`: differentiate entries with same type + owner
- `ext01`–`ext07`: script-specific metadata; `ext03` carries RSA-wrapped AES key for sealed scripts; `ext05` lists dependencies; `ext06` lists compatible platforms; `ext07` records source node's public key for sealed packages

### Cross-node delegation

When Node A sends a sealed script / folder to Node B, **Node B's MGC decrypts and runs it locally**. No plaintext leaves Node B's boundary.

⚠️ Before running a sealed script on Node B, verify that:
- dependencies in `ext05` are installed on Node B (MGC does **not** install them automatically)
- the OS in `ext06` is supported on Node B

Otherwise `mgc_run` will return `DEP_MISSING` or `PLATFORM_INCOMPAT` warnings and the script may fail.

### Workflows by chained calls

A stored script can call MGC's HTTP API to invoke another stored script or read a stored config — so credentials never leave MGC. Any caller works: AI agent, CI job, system script, or another stored script.

---

## AI Behavior Boundaries

AI **must not**:
- Print, repeat, or store plaintext
- Display script contents or internal encrypted data

AI **may**:
- Call `mgc_save` / `mgc_get` / `mgc_run` / `mgc_find` / `mgc_list` / `mgc_seal` / `mgc_package` / `mgc_seal_package`
- Guide the user to fill required fields
- Present execution results (which the AI reads from stdout / files / external services, not from MGC's response)

---

## Error Handling

| Status | Meaning | Action |
|---|---|---|
| `NOT_FOUND` | Entry not found | Use `mgc_find` / `mgc_list` to discover |
| Connection failed | MGC not running | MCP auto-starts (~15s); retry |

For the full error code list, see `skill_spec.md`.
