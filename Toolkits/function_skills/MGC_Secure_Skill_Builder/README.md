# Credential‑Safe Skill Generator (MGC Secure Edition)

A documentation‑only meta‑skill that teaches AI agents how to generate secure, zero‑exposure skills using MGC Blackbox 1.4.10 for credential management.

This skill contains **no executable code**, **no plaintext credentials**, ensuring maximum safety and automatic approval in AI Skill Store.

---

## What's New in v1.2.0

- **True Zero‑Exposure**: AI calls `mgc_run` (blackbox execution); local scripts read credentials via HTTP API. **AI never sees plaintext.**
- **Removed `mgc_get` from AI flow** — credentials stay encrypted in MGC.
- **`mgc_find` fuzzy search** (1.4.10) — locate scripts/credentials by partial owner.
- **`update_if_exists=true`** — clean credential rotation.
- **Multi‑node sealing** updated for 1.4.10 `ext02`/`ext03` auto‑packaging.
- **Invalid key format** fixed** — multi-line PEM with real newlines (was incorrectly documented as single-line).
- **Sandbox mode note** for 1.4.9+.

## What This Skill Does

Credential‑Safe Skill Generator provides a complete conceptual framework for building secure skills that:

- Never expose credentials (API keys, tokens, passwords) to AI models
- Store sensitive data only inside **MGC Blackbox**
- Retrieve credentials securely via local script through `mgc_run` blackbox
- Keep all sensitive operations outside the AI model
- Follow the Zero‑Exposure design pattern for maximum safety
- Support multi‑node collaboration via `mgc_seal`

This skill itself **does not execute anything**.
It only teaches AI how to generate secure skills.

---

## Prerequisites

To build Zero‑Exposure skills, users should have:

- **MGC Blackbox installed**: `pip install mgc-blackbox>=1.4.9`
- **MGC service running**: `mgc` (API at http://127.0.0.1:57219, WebUI at 57218)
- **MCP tools available**: `mgc_save`, `mgc_run`, `mgc_list`, `mgc_find`, `mgc_seal`, `mgc_open_webui`

> **Important:** AI agents should use `mgc_save` / `mgc_run` / `mgc_list` / `mgc_find` / `mgc_seal` / `mgc_open_webui`. **Never use `mgc_get` from AI** — it returns plaintext and breaks zero‑exposure.

No additional installation is required for this skill.

---

## Quick Start (Conceptual)

1. **Store credentials securely in MGC Blackbox**
   Users prepare the credential data and store it via WebUI (or AI via `mgc_save` on explicit user instruction). AI never sees the credentials.

2. **Build a Zero‑Exposure skill**
   - Reference the MGC API Reference section
   - Follow the Zero‑Exposure workflow
   - Use the local script template (HTTP API + `parse_known_args` + `RESULT_FILE:` output)
   - Ensure no credentials appear in the skill files

3. **Run the skill via `mgc_run`**
   AI invokes the local script through `mgc_run` (blackbox execution). Script reads credentials via HTTP API; AI only receives the result file path.

---

## What's Inside

This skill includes:

- Zero‑Exposure design pattern
- MGC Blackbox MCP tools reference (mgc_save, mgc_run, mgc_list, mgc_find, mgc_seal, mgc_open_webui)
- Complete workflow examples
- Comprehensive FAQ section
- Anti‑patterns with correct practices
- Troubleshooting guide
- When to use / When not to use guidance
- Local script template (HTTP API + mgc_run pattern)
- Common credential usage patterns (SMTP, API, Git)
- Security best practices
- SKILL.md template for building new Zero‑Exposure skills

---

## When to Use This Skill

Use Key‑Safe when:

- AI needs credentials but must not see them
- Multi‑node collaboration is required
- Automation tasks need credentials
- Sensitive script execution is involved

See SKILL.md for complete details.

---

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

---

## Security Principles

This skill follows strict security rules:

- No plaintext credentials in AI context
- Credentials stored encrypted via MGC
- Local scripts retrieve credentials via HTTP API inside `mgc_run` blackbox
- Sensitive operations performed only by local scripts
- No executable code in this skill (safe for automatic approval)

This ensures the skill is safe for AI models and safe for distribution.

---

## License

MIT