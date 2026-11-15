---
spec: usk/3.0
id: seal-workflow-licensing-en
version: 1.2.0
name: Seal and License Workflows or Skill Packages (Anti-Piracy, Node-Authorized Delivery)
description: For small-system and workflow local delivery scenarios: seal Python script collections into single-node-authorized local packages. Scripts keep their original code (import / relative paths / subprocess all supported) — MGC 1.5.2 auto-routes through sealed execution. Delivered packages cannot be read, modified, or resold. Zero cloud, zero exposure.
author: MirginCipher Team
license: MIT
tags: anti-piracy, encrypted-delivery, zero-exposure, workflow-licensing, local-delivery, node-authorized, sealed-cross-script, auto-recognized-workflow, script-sales, small-system-delivery, knowledge-products, mgc, blackbox
platform_compatibility: windows, macos, linux
mcp_tools: mgc_save, mgc_save_file, mgc_get, mgc_run, mgc_find, mgc_list, mgc_seal, mgc_seal_package, mgc_package, mgc_open_webui
requirements:
  mgc_version: ">=1.5.2"
install: pip install mgc-blackbox>=1.5.2
runtime: mgc
port: 57219
files:
  example_dir: example/
changelog:
  - version: 1.2.0
    changes:
      - Upgraded to MGC 1.5.2: included ext08 auto-recognition and sealed cross-script import
      - Added market scenario opener (script sales / small system delivery / workflow licensing / knowledge products)
      - Added problem-to-solution map (hardcoded paths, config dependencies, missing libraries, platform incompatibility)
      - Added error code handling (DIFF2_MISMATCH / DEP_MISSING / PLATFORM_INCOMPAT)
      - Rewrote Rule 1: changed from 'forbidden paths' to 'same-package paths auto-sealed'
      - Added tags/keywords: sealed-cross-script, auto-recognized-workflow, script-sales, small-system-delivery, local-delivery, one-key-per-node
  - version: 1.0.0
    changes:
      - Initial release. Based on MGC 1.5.0, introduces sealing & licensing of skill packages / workflow folders
---

# One-liner

**Seal Python small-systems / workflows into local packages — one AES key per node, no source code readable, no cloud, no exposure.**

---

# Who is this for?

| # | Scenario | Pain point |
|---|----------|------------|
| 1 | **Selling scripts / small tools** — Independent developer writes a data-processing / report / scraper script, wants to sell 100 copies | Fear of unlimited copying and reselling; a regular zip means gifting source |
| 2 | **Delivering internal small systems** — Vendor hands a small system built from scripts to a client | Client gets the source and may modify it or hand it to a third party |
| 3 | **Delivering enterprise automation** — Automation consultant packages a workflow for an enterprise | Each enterprise needs its own license; keys cannot be shared |
| 4 | **Paid knowledge products** — Selling an automation method as a content product | Let users run it, but cannot leak the core method |

> Common requirement: **delivery = authorization, and it must be one-key-per-node, one-node-per-key.**

---

# Three new selling points (unique to MGC 1.5.2)

## Selling point 1 — Zero rewrite

Write your workflow as you would normally:

- `from helpers.fetch import get_weather`
- `import config`
- `Path(__file__).parent / "settings.json"`
- `subprocess.run([sys.executable, "helper.py"])`

MGC 1.5.2's `ext08` **automatically recognizes** these `import` / `relative-path` / `subprocess` relationships. At runtime, execution is routed through sealed execution:

- ✅ Files **never land on the customer's disk**
- ✅ **No path on the customer's machine** can `cat` the source directly
- ✅ **No need to rewrite scripts as API-call patterns**

> Compared with traditional approaches: traditional schemes require you to rewrite scripts as "call by info_owner", turning 5 lines of calls into 50 lines. MGC 1.5.2 takes over for you.

## Selling point 2 — One key per node

Each customer receives an **independent AES key**:

- The key is **encrypted by the target node's RSA public key** (RSA-2048)
- AES-256 encrypts each script file
- Customer node has no private key = cannot get the content
- After decrypting, the customer node **cannot re-seal** for a third party (the key is bound to their node)

```
Author node                              Customer node
───────────                              ────────────
mgc_save_file(path="./workflow")
mgc_seal_package(ext04=customer_pub)
        │
        ▼
   encrypted package (.mgc_file)
        │
        └──── any channel ─────►        mgc_save_file(path="./received.mgc_file")
                                     mgc_run(...)
```

## Selling point 3 — Local delivery

- All encryption, decryption, and execution happen **locally**
- MGC connects to no cloud, has no external endpoints
- The encrypted package can be delivered by email, USB, IM, GitHub Releases, private cloud drive — **any way you like**
- Even if the package is intercepted, without the corresponding node's private key it cannot be decrypted

---

# Problem-to-solution map (market perspective)

| # | User pain | MGC 1.5.2 solution |
|---|-----------|---------------------|
| P1 | Customer can directly `cat` my `.py` files | Full AES-256 encryption, **no plaintext on disk** |
| P2 | Customer copies scripts to a colleague | AES key bound to their node RSA — **a different node cannot decrypt** |
| P3 | Multiple scripts use `import`; customer's machine changes paths | `ext08` auto-recognizes `import / Path / subprocess`, **runtime sealed routing**, no path dependency |
| P4 | Customer modifies my code and stops paying | AES signature verification, **any modification immediately invalidates** |
| P5 | I have to maintain a "runbook"; customers can't set up dependencies | `ext05` auto-infers dependency list from imports, `ext06` infers platforms |
| P6 | Re-sealing for each customer is tedious | `mgc_seal_package` handles folder-level sealing + node binding in one call |

---

# Prerequisites

- **Python 3.10+** (macOS 14+ Apple Silicon does NOT support Python 3.12)
- **MGC Blackbox ≥ 1.5.2** (workflow auto-recognition + subprocess literal list runtime routing are fully supported in 1.5.2)
- Install: `pip install mgc-blackbox`
- Run: `mgc` (API at `http://127.0.0.1:57219`, WebUI at `http://127.0.0.1:57218`)

---

# Three-step delivery (author side)

## Step 1 — Store the workflow folder into MGC

```
my_workflow/
├── manifest.json
├── SKILL.md
├── run.py
├── helpers/
│   ├── fetch.py
│   └── parse.py
└── config/
    └── settings.json
```

```python
mgc_save_file(
    path="./my_workflow",
    info_owner="my_workflow",
    diff_2="my_workflow",
)
```

This step automatically:
- Parses each script's `argparse` and writes `ext02`
- Scans imports and writes `ext05` (dependency list)
- Infers `ext06` (platform list)
- Builds `ext08` (cross-script call graph)

## Step 2 — Get the customer's RSA public key

```python
# Customer runs this on their own machine (WebUI or MCP)
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__",
)
# Customer sends you the multi-line PEM (public key is not secret; any channel works)
```

> **WebUI path (1.4.7+ recommended)**: WebUI → Skill page → Settings dropdown → Node Public Key → copy multi-line PEM.
>
> ⚠️ `ext04` must contain real `\n` newlines; do not concatenate into a single line.

## Step 3 — One-click seal

```python
mgc_seal_package(
    info_owner="my_workflow",
    diff_2="my_workflow",
    ext04=node_pub,         # customer's PEM
)
# → generates .mgc_file
```

Send the `.mgc_file` to the customer through any channel.

---

# Three-step receive (customer side)

## Step 1 — Import the encrypted package

```python
mgc_save_file(path="./received.mgc_file")
# MGC decrypts the package into local records
```

## Step 2 — Browse the structure

```python
# List package entries (metadata only, no plaintext)
mgc_find(info_owner="my_workflow", diff_2="my_workflow")

# Read manifest (plaintext, explains the workflow structure)
mgc_get(info_type="file", info_owner="my_workflow", diff_2="my_workflow")

# Read SKILL.md (plaintext, follow the instructions to call scripts)
mgc_get(info_type="file", info_owner="my_workflow", diff_2="my_workflow", diff_3="SKILL.md")
```

## Step 3 — Black-box run

```python
mgc_run(info_owner="my_workflow", diff_2="my_workflow")
# → {"pid": 12345, "status": "started"}
# AI only gets the launch status, never the source
```

---

# Three critical rules

## Rule 1 — Same-package paths are OK; cross-package calls use the MGC API

Scripts inside the **same folder package** can freely use `import / relative paths / subprocess`** — MGC 1.5.2's `ext08` automatically recognizes and routes them through sealed execution at runtime. **No need to rewrite as API calls.**

Only **cross-folder-package calls** (different `info_owner + diff_2`) require the MGC API:

```python
import os, requests

with open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")) as f:
    MGC_TOKEN = f.read().strip()

def call_remote_script(info_owner, ext02=None):
    return requests.post(
        "http://127.0.0.1:57219/api/mgc/sensitive/get",
        headers={"X-MGC-Token": MGC_TOKEN},
        json={
            "info_type": "script",
            "info_owner": info_owner,
            "diff_1": info_owner,
            "action": "run",
            "ext01": "python",
            "ext02": ext02,
        },
    ).json()
```

## Rule 2 — Author's SKILL.md is plaintext (by design)

The author's SKILL.md must be plaintext — it is the **routing instruction** for the customer: which script to call in which scenario, in what order, with what parameters. Without it, the customer cannot use the package at all.

> This is the public API contract, not implementation detail. **Core logic must go in the scripts** — see the next rule.

## Rule 3 — Put core algorithm in scripts, not in prompts

Both SKILL.md and prompts are **plaintext** — the customer can read them. Therefore:

| ✅ Do this | ❌ Don't do this |
|-----------|------------------|
| Put core algorithm in `run.py` | Put core algorithm in SKILL.md |
| SKILL.md says "when to call run.py, what args to pass" | SKILL.md says "the full business flow is…" (with details) |
| Business rules, thresholds, formulas → in scripts | Business rules written in prompts |

> The prompt is the customer-visible "manual". **The algorithm is what you're selling** — it must be locked inside the scripts.

---

# Recognizable cross-script patterns (MGC 1.5.2 complete table)

> Source: MGC skill_spec §2.4. When you save a folder via `mgc_save_file`, MGC statically parses every script to build the cross-script call graph (`ext08`). At runtime, MGC intercepts these patterns and routes them through sealed execution — **no files on disk, no plaintext, no rewrites**.

| Pattern | Code example | ext08 edge kind | Recognized? |
|---------|-------------|-----------------|-------------|
| `from` import | `from config import DEFAULT_CITY` | `from_import` | Yes |
| `from` import with alias | `from helpers.fetch import get_weather as gw` | `from_import` (asname preserved) | Yes |
| Plain `import` | `import helpers.parse` | `import` | Yes |
| Relative path via `Path` | `Path(__file__).parent / "config.py"` | `path` | Yes |
| Relative path via `open()` | `open("config.json")` against sibling file | `path` | Yes (recognition only in the current version; runtime routing is not yet supported) |
| Subprocess with relative path | `subprocess.run([sys.executable, str(Path(__file__).parent / "config.py"), ...])` | `path` (recognized via the `Path(...)` literal above; runtime also intercepts the subprocess call) | Yes — only when the caller and target were saved into MGC together as one workflow package. |
| Subprocess with literal list | `subprocess.run(['helper.py', '--x'])` (or `from subprocess import run; run([...])`) | `subprocess` (`callee` field records which subprocess function: `run` / `Popen` / `call` / `check_call` / `check_output`) | Yes — same package rule as above. Runtime interception runs the helper as sealed subprocess. |
| Dynamic import | `importlib.import_module(module_name)` | — | No — MGC statically parses only string literals; dynamic names are not recognized. At runtime, Python's standard import will attempt to resolve the name (typically fails with `ModuleNotFoundError`). |
| Absolute path | `open("/Users/alice/scripts/config.py")` | — | No — absolute paths are not portable and cannot be sealed. Use MGC location addressing instead. |
| Cross-subdirectory relative path | `subprocess.run([list, "../y.py"])` or `Path(__file__).parent.parent / "y.py"` when `..` resolves outside the caller's directory | — | No — see Scope below. |
| Function-level call without import | A function defined in another file called only by reference (no `import` / `from-import` / literal `Path` referencing it) | — | No — the parser only inspects string literals reachable via the conventional forms above. |

**Scope (1.5.2):**

- ✅ Cross-script calls are recognized **within the same folder** (`info_owner + diff_2` of the caller and the callee must be identical).
- ❌ **Same folder, different subdirectory** (e.g. `pkg_root/CROSS-FOLDER/x.py → ../y.py`) — not recognized. The parser treats `..` as out-of-scope, so `ext08` will not contain the edge. Place helpers and drivers in one directory.
- ❌ **Function-level calls** that don't appear as `import` / `from-import` / `Path` literals in source — not recognized.

**Key invariants:**

- The `argparse` on each script is independent — the driver's args go to the driver's `ext02`, each helper's args go to the helper's own `ext02`.
- `Path(__file__).parent / "x.py"` resolves correctly on macOS, Linux (POSIX), and Windows (`\` separator) — MGC normalizes via `_normalize_path` in `subprocess_adapter`.
- Subprocess output flows through normally — `capture_output=True, text=True` works because the launched helper is a real Python interpreter with UTF-8 decoding.

**Limits.** The cross-script call only works when both scripts are saved together. To orchestrate scripts across different packages, use the REST API pattern — pass the MGC location (`info_owner`) of the target script.

---

# Error codes and troubleshooting

| Code | Meaning | Resolution |
|------|---------|------------|
| `DIFF2_MISMATCH` | Script used `from-import` but **target script is not in the same folder package** | Put both scripts into the same `mgc_save_file` package; or use MGC API |
| `DEP_MISSING` | A dependency in `ext05` is not installed on the customer's machine | `pip install <missing dep>` (MGC does NOT auto-install) |
| `PLATFORM_INCOMPAT` | The `ext06` platform list doesn't include the current OS | Re-save on a supported platform, or extend platform branches in code |
| `args_not_recognized` | `argparse` parsing failed | Check `add_argument` usage; ensure literal `default=` |
| `dynamic_args_detected` | Default value uses dynamic computation (e.g. `datetime.now()`) | Use literal defaults, or pass via `ext02` explicitly |
| `Invalid PEM format` | `ext04` is not multi-line PEM | Copy from `mgc_get(info_type='__NODE_PUB__')` verbatim, preserving `\n` |

---

# When to use vs. when not to use (boundaries)

| ✅ Good fit | ❌ Not a good fit |
|-----------|------------------|
| Selling or licensing Python small tools | Open-source scripts (use GitHub) |
| Delivering internal small systems to clients | Large SaaS products (use cloud solutions) |
| Cross-node execution of automation workflows | Single-machine personal scripts (no need to seal) |
| "Tool packs" in paid knowledge products | Customer machines with full source environment for re-development |

---

# Comparison with alternatives

| Dimension | GitHub private repo | SaaS encryption service | License server | **MGC Sealed Delivery** |
|-----------|------------------------|-------------------------|-----------------|------------------------|
| Requires cloud | Yes | Yes | Yes | **No** |
| Monthly cost | Medium | High | Medium | **None** |
| Prevents source leak | ❌ Private but visible | ⚠️ Service-dependent | ❌ Server-side visible | ✅ **Completely invisible** |
| Prevents resell | ❌ | ⚠️ Service-dependent | ⚠️ Service-dependent | ✅ **Node-locked, cannot resell** |
| Offline delivery | ❌ | ❌ | ❌ | ✅ **Any channel** |
| Good for small systems | ⚠️ | ❌ Heavy | ⚠️ Heavy | ✅ **Light** |

---

# MCP tools quick reference

| Tool | Purpose | Required params |
|------|---------|-----------------|
| `mgc_save_file` | Store a local folder (auto-recognizes workflow) | path, info_owner |
| `mgc_seal_package` | Seal a package for target node | info_owner, ext04 (PEM), output_dir |
| `mgc_save` | Store a single script (not in a package) | info_type, info_owner, content |
| `mgc_seal` | Seal a single script | info_owner, ext04 (PEM) |
| `mgc_run` | Black-box execution | info_type="script", info_owner, diff_1 |
| `mgc_get` | Retrieve value / retrieve node_pub | info_type, info_owner |
| `mgc_find` | Fuzzy search | info_owner, match_mode |
| `mgc_list` | List all metadata | — |
| `mgc_package` | Plaintext packaging within same trust zone | info_owner |
| `mgc_open_webui` | Open WebUI | — |

---

# Related skills

- **MGC Blackbox (Cross-Device Script Authorization)** — Single-script sealing (lighter weight)
- **MGC Blackbox Meta Skill** — Full reference for all MGC capabilities

---

# Contact

- **Main repo**: https://github.com/zkeviny/MGC-Blackbox
- **Issues**: https://github.com/zkeviny/MGC-Blackbox/issues
- **Contact**: mirgincipher@outlook.com