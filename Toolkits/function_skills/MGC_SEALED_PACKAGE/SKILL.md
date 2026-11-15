---
usk: 3.0
id: seal-and-license-workflow-skills
version: 1.0.0
name: Seal and License Workflows or Skill Packages (Anti‑Piracy, Node‑Authorized Delivery)
name_zh: 技能包/工作流防盗版授权（加密交付、节点授权）
description: Seal skill packages and workflow folders so they execute only on authorized nodes — no read, no modify, no resell. 100% local, single‑node bound, zero‑exposure IP protection powered by MGC Blackbox 1.5.0+.
author: MirginCipher Team
license: MIT
tags: security, encryption, zero-exposure, ip-protection, sealed-package, anti-piracy, node-authorized, encrypted-delivery, workflow-licensing, skill-licensing, single-node-license, no-resell, mgc, blackbox
platform_compatibility: windows, macos, linux
mcp_tools: mgc_save, mgc_save_file, mgc_get, mgc_run, mgc_find, mgc_list, mgc_seal, mgc_seal_package, mgc_package, mgc_open_webui
requirements:
  mgc_version: ">=1.5.0"
install: pip install mgc-blackbox
runtime: mgc
port: 57219
changelog:
  - version: 1.0.0
    changes:
      - Initial release — teaching skill for sealing and licensing skill packages / workflows
      - Covers author side and consumer side workflows
      - Defines three critical rules for IP-safe cross-node delivery
---

# 1. Overview

**Seal and License Workflows or Skill Packages** is a teaching skill that explains how to use MGC Blackbox 1.5.0+ to ship a skill package or workflow folder to a target node — **without giving away the source**.

The target node can **execute** your work. It **cannot read, modify, or resell** the plaintext.

---

# 2. The Three Promises

Once your skill package is sealed and delivered to an authorized node:

- **No read** — the plaintext source never leaves your device in cleartext
- **No modify** — the capsule cannot be edited without breaking the AES signature
- **No resell** — the AES key is bound to the target node's RSA public key, so the capsule cannot be re‑sealed for a third party

---

# 3. Local‑First Guarantee

- All encryption happens **locally** on the author's device using MGC Blackbox.
- All decryption happens **locally** on the consumer's device.
- **No data is uploaded to any cloud.** The capsule can be hand‑delivered by email, USB, or any channel of your choice.
- MGC itself runs as a local service (`mgc` on `http://127.0.0.1:57219`); it has no external endpoint.

This makes the workflow suitable for **air‑gapped, regulated, or privacy‑sensitive environments**.

---

# 4. Prerequisites

- **MGC Blackbox 1.5.0+** (required for `mgc_save_file`, `mgc_seal_package`, `mgc_package`)
- Python 3.10+ (Python 3.12 on macOS Apple Silicon is **not** supported)
- Install: `pip install mgc-blackbox`
- Start: `mgc` (API at `http://127.0.0.1:57219`, WebUI at `http://127.0.0.1:57218`)
- An MCP‑compatible agent runtime on both author and consumer side

---

# 5. Author Side — Seal a Skill Package or Workflow

Three steps to ship your work as an encrypted, single‑node‑bound capsule.

### Step 1 — Prepare the folder

```
my_skill/
├── manifest.json      ← workflow metadata (plaintext)
├── SKILL.md           ← agent routing instructions (plaintext, see Rule 1)
├── run.py             ← entry script
├── helpers/
│   ├── fetch.py
│   └── parse.py
└── config/
    └── settings.json
```

**Plaintext by design**: only `manifest.json` and `SKILL.md` stay readable. Scripts and configs are encrypted.

### Step 2 — Get the consumer node's public key

```python
# On the consumer's MGC node
mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")
# → returns a PEM public key string
```

Hand this PEM string to the author through any secure channel (the PEM is **not secret** — it is a public key).

### Step 3 — Save and seal

```python
# On the author's MGC node
mgc_save_file(
    path="./my_skill",
    info_owner="my_skill",
    diff_2="my_skill",
)

mgc_seal_package(
    info_owner="my_skill",
    diff_2="my_skill",
    ext04="<consumer node PEM public key>",
)
# → a sealed capsule (.mgc_file)
```

Hand the `.mgc_file` to the consumer through **any** channel (email, USB, cloud drive). The capsule is safe even if intercepted.

---

# 6. Consumer Side — Run a Sealed Package

Three steps to import and execute a sealed capsule you received.

### Step 1 — Import

```python
mgc_save_file(path="./received.mgc_file")
# MGC unpacks the capsule into local entries
```

### Step 2 — Discover and read

```python
mgc_find(info_owner="my_skill", diff_2="my_skill")
# → list of entries inside the package

mgc_get(info_type="file", info_owner="my_skill", diff_2="my_skill")
# → read the manifest (plaintext)
```

Read `SKILL.md` (plaintext) to understand which scripts to call in which order.

### Step 3 — Execute

```python
mgc_run(info_owner="my_skill", diff_2="my_skill")
# → starts the entry script
```

The agent never sees the script source. Output flows back to the consumer's MGC runtime.

---

# 7. Three Critical Rules

These rules are **non‑negotiable**. Breaking them defeats sealing.

### Rule 1 — Scripts must call each other via the MGC API, never via filesystem paths

If your scripts have a chain (A calls B calls C), they **must** invoke each other through the MGC REST API by `info_type` + `info_owner` + `diff_*`. They **must not** rely on local paths, because the local path on the consumer's machine may not match the author's layout.

```python
# inside run.py — call another stored script by MGC location
def call_script(info_owner, ext02=None, diff_1=""):
    payload = {
        "info_type": "script",
        "info_owner": info_owner,
        "diff_1": diff_1,
        "action": "run",
        "ext01": "python",
    }
    if ext02:
        payload["ext02"] = ext02
    r = requests.post(
        "http://127.0.0.1:57219/api/mgc/sensitive/get",
        headers={"X-MGC-Token": MGC_TOKEN},
        json=payload,
    )
    return r.json()
```

### Rule 2 — The author's SKILL.md stays plaintext

The author's SKILL.md (the one shipped **inside** the package) is **plaintext by design** — it tells the consumer's agent *which* scripts to call and *when*. Without it, the agent has no routing instructions.

This is fine: the SKILL.md is the **public API contract**, not the **implementation**.

### Rule 3 — Core logic lives in scripts, not in the prompt

Prompts and SKILL.md are plaintext — anyone can read them. Therefore:

- **Do** put core algorithms, business logic, and proprietary workflows **inside scripts** (which get sealed)
- **Do not** put them in the SKILL.md prompt (which stays plaintext)
- The SKILL.md should be a **thin routing layer**: "call script X with args Y when condition Z"

---

# 8. Security Mechanism (Quick View)

| Layer | What it does |
|-------|--------------|
| **AES‑256** | Encrypts each script body and config file in the package |
| **RSA‑2048** | Wraps the AES key with the **target node's public key** (from `__NODE_PUB__`) |
| **Single‑node binding** | The wrapped AES key can only be unwrapped by the target node's private key |
| **No re‑seal** | The consumer node cannot re‑wrap the AES key for another node |
| **Local execution** | Decryption and execution both happen inside the consumer's MGC runtime; the plaintext is never written to disk in cleartext |

For full details, see the MGC_META_SKILL skill.

---

# 9. When NOT to Use

This skill is **not** the right tool if:

- ❌ You want to publish an **open‑source** skill (use plain `mgc_save` instead)
- ❌ You need to distribute to **many** nodes simultaneously (one capsule = one node; for multi‑node, seal once per node)
- ❌ Your workflow logic is so simple it can fit in a SKILL.md prompt (just write it directly)
- ❌ Your scripts cannot be refactored to call each other via the MGC API (chains that depend on local paths will break)

---

# 10. Related Skills

- **MGC Blackbox (META_SKILL)** — full reference for all MGC tools, fields, and security model. Read this first if you are new to MGC.
- **MGC Script Execution Auth (Cross‑Device)** — sealing model for **single** scripts (lighter‑weight than this folder‑level skill).

---

# 11. Coming Next

We are preparing a batch chain authorization feature. Send your node_pub to mirgincipher@outlook.com to claim a free first-batch trial.