# Database Credential Security (Zero‑Exposure Edition)

Secure database credential management using MGC Blackbox 1.4.10. Supports MySQL, PostgreSQL, SQLite, MariaDB and more.

## What's New in v1.2.0

- **True Zero‑Exposure**: AI calls `mgc_run` (blackbox execution); local scripts read credentials via HTTP API. **AI never sees plaintext.**
- **Removed `mgc_get` from AI flow** — credentials stay encrypted in MGC.
- **`mgc_find` fuzzy search** (1.4.10) — locate scripts/credentials by partial owner.
- **`update_if_exists=true`** — clean credential rotation.
- **Multi‑node sealing** updated for 1.4.10 `ext02`/`ext03` auto‑packaging.
- **Sandbox mode note** for 1.4.9+.

## What This Skill Does

- Pattern for encrypted credential storage in MGC
- Pattern for local scripts retrieving credentials via HTTP API
- Pattern for `mgc_seal` cross‑node script distribution
- Anti‑patterns and security guidance

This skill is documentation‑only and contains **no executable code** (safe for automatic approval).

## Prerequisites

- Python 3.10+
- `pip install mgc-blackbox>=1.4.9`
- MGC service running (`mgc`)
- Database driver (`mysql-connector-python`, `psycopg2`, etc.)

## Quick Start

### 1. Install MGC

```bash
pip install mgc-blackbox>=1.4.9
mgc
```

### 2. Store Database Credentials (via WebUI)

Open WebUI → Add Entry → `info_type="config"`, `info_owner="my_mysql_prod"`, content is JSON with `host/port/database/user/password`.

Or AI can store on explicit user instruction via `mgc_save`.

### 3. Reference Credentials in Your Script

The script references the credential by `info_owner` only — never embeds the password.

### 4. Execute via `mgc_run`

```python
result = mgc_run(
    info_type="script",
    info_owner="mysql_query_v1",
    diff_1="v1",  # schema-required; any non-empty string works for a single entry
    ext02='["--sql", "SELECT 1"]'
)
# Returns pid+status; password NEVER enters AI context.
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `mgc_save` | Store credentials / scripts |
| `mgc_run` | Blackbox script execution (1.4.7+) |
| `mgc_list` | List entries (exact match) |
| `mgc_find` | Fuzzy search (1.4.10 new) |
| `mgc_seal` | Encrypt scripts for multi‑node execution |
| `mgc_open_webui` | Open WebUI for user to store credentials |

> ❌ AI must NOT call `mgc_get` — it returns plaintext and breaks zero‑exposure.

## When to Use This Skill

- Production environments with sensitive data
- Automation tasks requiring database access
- Multi‑node collaboration via `mgc_seal`
- AI needs DB access but must not see passwords

## When NOT to Use This Skill

- Public databases with no authentication
- Local development with mock data
- Interactive manual database access (DBeaver / MySQL Workbench)

## Security

- Credentials never exposed to AI
- Encrypted storage via MGC
- Local scripts retrieve credentials via HTTP API inside blackbox
- No plaintext in logs
- Separate credentials per environment

## License

MIT
