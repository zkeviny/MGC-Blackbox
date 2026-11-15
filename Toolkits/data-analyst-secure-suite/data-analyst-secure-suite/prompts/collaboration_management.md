# Workflow & Skill Package Sealed Collaboration

This document guides data analysts on how to securely seal and deliver workflows or skill packages to other nodes in **MGC Blackbox ≥ 1.5.2**, enabling "usable but unreadable, runnable but unresellable" cross-team / cross-organization collaboration.

All sensitive operations must be explicitly authorized by the user before proceeding.

---

# 1. Why Sealed Collaboration Is Needed

Common collaboration pain points in data analysis workflows:

| Scenario | Pain Point | MGC Solution |
|----------|-----------|--------------|
| Data team delivers analysis workflow to business team | Don't want business team to see source code or modify logic | After workflow sealing, recipient can only run, never read |
| External analyst delivers analysis package to customer | Customer resells source to peers after delivery | AES key bound to customer node, cannot re-seal |
| Cross-department sharing of analysis methodology | Worry about core algorithm leakage | Seal the entire workflow at once, core algorithms locked inside scripts |
| Delivering to multiple customers | Each customer needs independent authorization | One key per customer, each customer has independent key |

> **Core principle**: Delivery equals authorization. After sealing, the recipient can only run — cannot read, modify, or resell.

---

# 2. Workflow Sealing vs Skill Package Sealing

MGC supports two sealed collaboration modes:

| Dimension | Workflow Sealing | Skill Package Sealing |
|-----------|------------------|------------------------|
| **Sealing Target** | Analysis script folder (run.py + helpers/) | Complete skill package with SKILL.md |
| **Sealing Tool** | `mgc_seal_package` | `mgc_seal_package` |
| **Recipient Usage** | `mgc_run` directly invokes entry script | AI reads SKILL.md instructions and calls corresponding scripts |
| **Use Case** | Deliver a "one-click run" analysis tool to business team | Deliver a complete "AI-understandable usage guide" package to client |
| **SKILL.md Included?** | Not required | Required (recipient AI's usage manual) |
| **Recipient AI Visibility** | Sees only run status | Can read SKILL.md (plaintext), but cannot see script source code |

> **Selection guidance**:
> - If the recipient only needs to "execute your analysis", use **Workflow Sealing**
> - If the recipient needs AI to autonomously call different scripts per your package, use **Skill Package Sealing**

---

# 3. End-to-End Collaboration Flow

## 3.1 Complete Flow

```
Author Node                                         Recipient Node (Client / Team)
───────────                                        ──────────────────────

1. Save workflow / skill package
   mgc_save_file(path="./my_workflow")
   → MGC auto-recognizes import / subprocess relationships

2. Recipient fetches their own public key            mgc_get(info_type="__NODE_PUB__",
   (Public key is not secret; any channel OK)         info_owner="__NODE_PUB__")
                                                    → Send PEM public key to author

3. Seal with recipient's public key
   mgc_seal_package(
       info_owner="my_workflow",
       diff_2="my_workflow",
       ext04=recipient_PEM_pubkey,
       output_dir="./delivery",          # REQUIRED in 1.5.2+
   )
   → Generates .mgc_file encrypted package

4. Deliver by any channel                            5. Import sealed package
   (email / USB / IM / cloud drive)                     mgc_save_file(
                                                          path="./received.mgc_file",
                                                          info_owner="my_workflow",
                                                          diff_2="my_workflow",
                                                       )

                                                   6. Run
                                                      mgc_run(info_owner="my_workflow",
                                                              diff_2="my_workflow")
                                                      → Sealed execution, no plaintext on disk
```

## 3.2 Security Features

- **AES-256 encryption**: Each script file encrypted independently
- **RSA-2048 key exchange**: AES key encrypted with recipient node's public key, only recipient can decrypt
- **Node binding**: Key bound to target node, recipient cannot re-seal to a third party
- **No cloud**: All encryption / decryption / execution happens locally, MGC connects to no cloud
- **Any delivery channel**: Encrypted package can be sent via email, USB, IM, cloud drive — even if intercepted, cannot decrypt

---

# 4. Workflow Sealing Walkthrough

## 4.1 Prepare the Workflow Folder

```
my_analysis/
├── manifest.json
├── run.py              # Entry script
├── helpers/
│   ├── query.py        # Query module
│   ├── clean.py        # Cleaning module
│   └── analyze.py      # Analysis module
└── config/
    └── settings.json
```

## 4.2 Save to MGC

```python
mgc_save_file(
    path="./my_analysis",
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)
# MGC auto-recognizes import / subprocess call relationships
```

## 4.3 Seal to Target Node

```python
# Target node's public key (recipient fetches via mgc_get and sends to you)
recipient_pub = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"""

mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04=recipient_pub,
    output_dir="./delivery",  # REQUIRED in 1.5.2+
)
# → Generates .mgc_file encrypted package
```

> **Note**: `ext04` MUST contain real newline characters `\n`. Do NOT pass PEM as a single concatenated line.

## 4.4 Recipient Imports and Runs

```python
# Recipient imports the sealed package
mgc_save_file(
    path="./received.mgc_file",
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)

# Recipient runs (sealed execution, no plaintext on disk)
mgc_run(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)
# → {"pid": 12345, "status": "started"}
```

---

# 5. Skill Package Sealing Walkthrough

The difference between a skill package and a workflow: it includes `SKILL.md` as the recipient AI's usage manual.

## 5.1 Prepare Skill Package Folder

```
my_skill_package/
├── manifest.json
├── SKILL.md             # ← Required for skill packages; recipient AI's usage manual (plaintext)
├── run_query.py          # Query script
├── run_clean.py          # Cleaning script
├── run_analyze.py        # Analysis script
└── helpers/
    ├── db_connect.py
    └── stats.py
```

## 5.2 Role of SKILL.md

`SKILL.md` is **plaintext** — the recipient AI needs to read it to understand:
- Which scripts are available
- Which script to call in which scenario
- What parameters to pass
- In what order

> **Key rule**: `SKILL.md` describes "how to use"; core algorithms live in scripts. Recipient AI can read SKILL.md but cannot read script source.

## 5.3 Save and Seal

```python
# Save skill package
mgc_save_file(
    path="./my_skill_package",
    info_owner="sales_analysis_suite",
    diff_2="sales_analysis_suite",
)

# Seal to target node
mgc_seal_package(
    info_owner="sales_analysis_suite",
    diff_2="sales_analysis_suite",
    ext04=recipient_pub,
    output_dir="./delivery",  # REQUIRED in 1.5.2+
)
# → Generates .mgc_file encrypted package
```

## 5.4 Recipient Imports and Uses

```python
# Recipient imports
mgc_save_file(
    path="./received.mgc_file",
    info_owner="sales_analysis_suite",
    diff_2="sales_analysis_suite",
)

# Recipient AI reads SKILL.md (plaintext, learns how to use)
mgc_get(
    info_type="file",
    info_owner="sales_analysis_suite",
    diff_2="sales_analysis_suite",
    diff_3="SKILL.md",
)

# Recipient AI follows SKILL.md instructions to invoke corresponding scripts
mgc_run(
    info_owner="sales_analysis_suite",
    diff_2="sales_analysis_suite",
)
```

---

# 6. Independent Authorization per Customer

Each customer needs to be sealed independently — one key binds to one node:

```python
# Seal for customer A
mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04=client_a_pub,
    output_dir="./delivery_a",
)
# → Generates .mgc_file for customer A

# Seal for customer B (same workflow, different key)
mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04=client_b_pub,
    output_dir="./delivery_b",
)
# → Generates .mgc_file for customer B
```

**Security features**:
- Customer A's package cannot run on Customer B's machine (key mismatch)
- Customer A cannot re-seal their package to Customer C (AES key bound to A's node)
- Each customer's sealed package is independent, no cross-impact

---

# 7. Authorization Template (AI Must Ask)

### Before sealing a workflow:

```
Workflow Name: monthly_sales_analysis
Target Node Public Key: {first 16 chars of node_pub}...
Operation: Seal Workflow
Authorization Required: YES

Do you authorize sealing this workflow? Reply "yes" to proceed, or "no" to cancel.
```

### Before sealing a skill package:

```
Skill Package Name: sales_analysis_suite
Target Node Public Key: {first 16 chars of node_pub}...
Operation: Seal Skill Package
Authorization Required: YES

Do you authorize sealing this skill package? Reply "yes" to proceed, or "no" to cancel.
```

---

# 8. Best Practices

### ✔ 1. Put Core Algorithms in Scripts, Not in SKILL.md
SKILL.md is plaintext; the recipient can read it. The algorithm is your "product" — it must be locked inside scripts.

### ✔ 2. SKILL.md Only Describes Routing
Specify "which scenario calls which script, with what parameters"; do not write business logic details.

### ✔ 3. Seal Independently for Each Customer
Do not try to deliver one sealed package to multiple customers — each customer's key binds to their own node.

### ✔ 4. Write Results to Specified Files
After a sealed package runs, MGC will not return plaintext. Workflow output must explicitly target a file path, or be written to a database or MGC itself.

### ✔ 5. Delivery Channel Is Unrestricted
Encrypted packages can be sent via email, USB, IM, or cloud drive. Even if intercepted, without the corresponding node's private key it cannot be decrypted.

---

# 9. FAQ

| Issue | Solution |
|-------|----------|
| Sealing failed | Check whether `ext04` is a multi-line PEM public key (preserving `\n`) |
| Recipient run fails | Check whether dependencies in `ext05` are installed on recipient side |
| Recipient import fails | Ensure all scripts are within the same `mgc_save_file` package |
| Platform incompatible | Check whether `ext06` contains the recipient's OS |
| Customer says "it doesn't work on another machine" | This is by design — node binding prevents resale |

---

# 10. Summary

This sealed collaboration document provides:

- Workflow sealing (`mgc_seal_package`) and skill package sealing
- End-to-end authorized collaboration flow (node_pub → seal → import → run)
- Multi-customer independent authorization (one key per seal, one node per key)
- IP protection: "usable but unreadable, runnable but unresellable"

This is the core capability of secure data analyst collaboration workflows.