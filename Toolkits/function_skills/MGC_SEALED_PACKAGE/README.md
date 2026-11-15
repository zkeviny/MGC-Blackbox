# Seal and License Workflows or Skill Packages (Anti‑Piracy, Node‑Authorized Delivery)

> 技能包/工作流防盗版授权（加密交付、节点授权） · **Version 1.0.0**

A teaching skill for shipping skill packages and workflow folders to a target node **without giving away the source**. Powered by MGC Blackbox 1.5.0+.

---

## What This Skill Does

Teach an AI agent (or a human developer) how to:

1. **Seal** a skill package or workflow folder as a single encrypted capsule
2. **Bind** the capsule to exactly one authorized node's RSA public key
3. **Deliver** the capsule through any channel — even an untrusted one
4. **Execute** the capsule on the target node without ever exposing plaintext

The result: **no read, no modify, no resell** for the consumer.

---

## The Three Promises

- **No read** — plaintext source never leaves the author's device in cleartext
- **No modify** — the capsule cannot be edited without breaking the AES signature
- **No resell** — the AES key is bound to one node's RSA key, so the capsule cannot be re‑sealed for a third party

---

## Local‑First Guarantee

- All encryption happens **locally** on the author's device
- All decryption happens **locally** on the consumer's device
- **No cloud, no upload.** Capsule can be hand‑delivered by email, USB, or any channel
- MGC runs as a local service — it has **no external endpoint**

---

## Prerequisites

- **MGC Blackbox 1.5.0+** (required)
- Python 3.10+ (Python 3.12 on macOS Apple Silicon is **not** supported)
- Install: `pip install mgc-blackbox`
- Start: `mgc` (API at `http://127.0.0.1:57219`, WebUI at `http://127.0.0.1:57218`)

---

## Quick Start (Author Side)

```python
# Step 1 — Save the folder into MGC
mgc_save_file(
    path="./my_skill",
    info_owner="my_skill",
    diff_2="my_skill",
)

# Step 2 — Get the consumer's PEM public key (out-of-band hand-off)
# consumer side:
#   mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")

# Step 3 — Seal to that node
mgc_seal_package(
    info_owner="my_skill",
    diff_2="my_skill",
    ext04="<consumer node PEM public key>",
)
# → sealed .mgc_file capsule
```

## Quick Start (Consumer Side)

```python
# Step 1 — Import
mgc_save_file(path="./received.mgc_file")

# Step 2 — Discover
mgc_find(info_owner="my_skill", diff_2="my_skill")

# Step 3 — Run (never sees source)
mgc_run(info_owner="my_skill", diff_2="my_skill")
```

For full step‑by‑step, three‑critical‑rules, and security mechanism details, see **[SKILL.md](SKILL.md)**.

---

## When to Use / When NOT to Use

| Use this skill when | Don't use it when |
|---------------------|-------------------|
| You want to **sell or license** a valuable workflow | The workflow is open‑source |
| You need **single‑node** authorization | You need to distribute to many nodes (seal once per node instead) |
| You want **IP‑safe** cross‑device delivery | Your scripts can't be refactored to call via MGC API |
| You need **air‑gapped** delivery (USB, email) | Plaintext prompt is enough |

---

## Links

- **Main Repo**: https://github.com/zkeviny/MGC-Blackbox
- **Issues**: https://github.com/zkeviny/MGC-Blackbox/issues
- **Contact**: mirgincipher@outlook.com

---

## Related Skills (Zero‑Exposure Ecosystem)

- **MGC Blackbox (META_SKILL)** — full MGC reference. Read this first.
- **MGC Script Execution Auth** — sealing for **single** scripts (lighter than folder‑level sealing).
- **MGC Secure Mail Sender**, **MGC Database Security**, **MGC Webhook Security**, **MGC Key‑Safe Generator** — domain skills that follow the same zero‑exposure pattern.
