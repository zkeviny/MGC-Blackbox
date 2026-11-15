# Seal and License Workflows or Skill Packages

> **Anti-Piracy, Node-Authorized Delivery** · For small systems and workflows delivered locally.

Ship your Python scripts and small systems to customers as **sealed packages** — they can run, but cannot read the source, modify it, or resell it. Everything stays local: no cloud, no server, no internet required.

## Why this skill

| If you are … | Pain | This skill solves it by |
|--------------|------|----------------------|
| Selling a data-processing / report / scraper script | Buyer can copy and resell it | One AES key per buyer; the key is bound to their node — they can't re-seal |
| Delivering a small internal system to a client | Client can modify code or hand it to a third party | Source is encrypted; any tampering invalidates execution |
| Selling an automation workflow to enterprises | Each enterprise needs its own license | `mgc_seal_package` ties each package to one node's RSA public key |
| Selling a paid "tool pack" with knowledge product | Need to let users run it without exposing core methods | Core logic lives in scripts (sealed); instructions live in SKILL.md (plaintext by design) |

## The three promises

1. **No read** — Source is AES-256 encrypted; nothing on the customer's disk is plaintext.
2. **No modify** — Any tampering invalidates the AES signature.
3. **No resell** — AES key is sealed by the customer's RSA-2048 public key; only their node can decrypt, and they cannot re-seal for anyone else.

## How it works (one-screen mental model)

```
Author node                              Customer node
───────────                              ────────────
mgc_save_file(path="./workflow")         
mgc_seal_package(ext04=customer_pub)     
        │
        ▼
   sealed capsule (.mgc_file)
        │
        └──── any channel ─────►       mgc_save_file(path="./received.mgc_file")
                                     mgc_run(...)
```

100% local. No cloud, no external endpoint. The capsule can travel via email, USB, IM, GitHub Releases, or any private channel.

## Prerequisites

- **Python 3.10+** (macOS 14+ Apple Silicon does NOT support Python 3.12)
- **MGC Blackbox ≥ 1.5.2** (the auto-recognized workflow + sealed cross-script import require 1.5.2)
- Install: `pip install mgc-blackbox`
- Run: `mgc` (API at `http://127.0.0.1:57219`, WebUI at `http://127.0.0.1:57218`)

## Three steps to deliver (author side)

### Step 1 — Store the workflow folder into MGC

```python
mgc_save_file(
    path="./my_workflow",
    info_owner="my_workflow",
    diff_2="my_workflow",
)
```

MGC automatically:
- Parses each script's `argparse` and writes `ext02`
- Scans imports and writes `ext05` (dependency list)
- Infers `ext06` (platform list)
- Builds `ext08` (cross-script call graph)

### Step 2 — Get the customer's RSA public key

```python
# Customer runs this on their own machine (WebUI or MCP):
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__",
)
# They send you the multi-line PEM (public key is not secret; any channel works)
```

> **WebUI path (1.4.7+ recommended)**: WebUI → Skill page → Settings dropdown → Node Public Key → copy multi-line PEM.
>
> ⚠️ `ext04` must contain real `\n` newlines; do not concatenate into a single line.

### Step 3 — Seal for that customer

```python
mgc_seal_package(
    info_owner="my_workflow",
    diff_2="my_workflow",
    ext04=node_pub,         # customer's PEM
    output_dir="./delivery",  # MGC 1.5.2 requires explicit output_dir
)
# → generates .mgc_file
```

Send the `.mgc_file` to the customer through any channel.

## Three steps to receive (customer side)

### Step 1 — Import the capsule

```python
mgc_save_file(path="./received.mgc_file", info_owner="my_workflow", diff_2="my_workflow")
# MGC decrypts the capsule into local records
```

### Step 2 — Browse the structure

```python
# List package entries (metadata only, no plaintext)
mgc_find(info_owner="my_workflow", diff_2="my_workflow")

# Read manifest (plaintext — describes the package layout)
mgc_get(info_type="file", info_owner="my_workflow", diff_2="my_workflow")

# Read SKILL.md (plaintext — your routing instructions)
mgc_get(info_type="file", info_owner="my_workflow", diff_2="my_workflow", diff_3="SKILL.md")
```

### Step 3 — Run black-box

```python
mgc_run(info_owner="my_workflow", diff_2="my_workflow", diff_3="script_d.py")
# → {"pid": 12345, "status": "started"}
# AI only sees the launch status — never the source
```

## Three critical rules

### Rule 1 — Same-package paths are OK; cross-package calls use the MGC API

Scripts inside the **same folder package** can freely use `import / relative paths / subprocess` — MGC 1.5.2's `ext08` auto-recognizes and routes them through sealed execution at runtime. **No need to rewrite as API calls.**

Cross-package calls (different `info_owner + diff_2`) require the MGC REST API. See SKILL.md for details.

### Rule 2 — Author's SKILL.md is plaintext (by design)

The author's SKILL.md must be plaintext — it is the **routing instruction** for the customer: which script to call in which scenario, in what order, with what parameters. Without it, the customer cannot use the package at all.

> This is the public API contract, not implementation detail. Core logic goes in the scripts (see Rule 3).

### Rule 3 — Put the algorithm in scripts, not in prompts

Both SKILL.md and prompts are **plaintext** — the customer can read them. So:

| ✅ Do this | ❌ Don't do this |
|-----------|------------------|
| Put core algorithm in `run.py` | Put core algorithm in SKILL.md |
| SKILL.md says "when to call run.py, what args to pass" | SKILL.md says "the full business flow is…" |
| Business thresholds, formulas → in scripts | Business thresholds written in prompts |

> The prompt is the customer-visible manual. **The algorithm is what you're selling** — must live inside the sealed scripts.

## Compatible cross-script patterns (MGC 1.5.2)

The full list of patterns that MGC's `ext08` auto-recognizes. See SKILL.md §"Recognizable cross-script patterns" for the complete table.

Supported patterns include:

| Pattern | Example |
|---------|---------|
| `from` import | `from config import DEFAULT_CITY` |
| `from` import with alias | `from helpers.fetch import get_weather as gw` |
| Plain `import` | `import helpers.parse` |
| Relative path via `Path` | `Path(__file__).parent / "config.py"` |
| Subprocess with relative path | `subprocess.run([sys.executable, str(Path(__file__).parent / "config.py"), ...])` |
| Subprocess with literal list | `subprocess.run(['helper.py', '--x'])` |
| **Subprocess with `[sys.executable, "x.py"]`** (1.5.2+) | `subprocess.run([sys.executable, "x.py", "--arg"])` |

Unsupported patterns (will fall back to standard Python import, typically `ModuleNotFoundError`):

- Dynamic import: `importlib.import_module(x)`
- Absolute paths: `open("/Users/alice/scripts/config.py")`
- Cross-subdirectory relative paths
- Function-level calls without `import` / `from-import` / `Path` literal

## Error codes

| Code | Meaning | Resolution |
|------|---------|------------|
| `DIFF2_MISMATCH` | `from-import` referenced a script outside the caller's package | Save both scripts into the same `mgc_save_file` package, or use MGC API for cross-package calls |
| `DEP_MISSING` | A dependency in `ext05` is not installed on the target | `pip install <missing dep>` (MGC does NOT auto-install) |
| `PLATFORM_INCOMPAT` | The `ext06` platform list doesn't include the current OS | Re-save on a supported platform, or extend the platform branches in code |
| `args_not_recognized` | `argparse` parsing failed | Check `add_argument` usage; ensure literal `default=` |
| `dynamic_args_detected` | Default value uses dynamic computation (e.g. `datetime.now()`) | Use literal defaults, or pass via `ext02` explicitly |
| `Invalid PEM format` | `ext04` is not multi-line PEM | Copy from `mgc_get(info_type='__NODE_PUB__')` verbatim, preserving `\n` |

## When to use vs. when not to use

| ✅ Good fit | ❌ Not a good fit |
|-----------|------------------|
| Selling or licensing Python small tools | Open-source scripts (just use GitHub) |
| Delivering internal small systems to clients | Large SaaS products (use cloud solutions) |
| Cross-node execution of automation workflows | Single-machine personal scripts (no need to seal) |
| Paid "tool packs" within knowledge products | Customer machines with full source environment for re-development |

## Comparison with alternatives

| Dimension | GitHub private repo | SaaS encryption service | License server | **MGC Sealed Delivery** |
|-----------|------------------------|-------------------------|-----------------|------------------------|
| Requires cloud | Yes | Yes | Yes | **No** |
| Monthly cost | Medium | High | Medium | **None** |
| Prevents source leak | ❌ Private but visible | ⚠️ Service-dependent | ❌ Server-side visible | ✅ **Completely invisible** |
| Prevents resell | ❌ | ⚠️ Service-dependent | ⚠️ Service-dependent | ✅ **Node-locked, cannot resell** |
| Offline delivery | ❌ | ❌ | ❌ | ✅ **Any channel** |
| Good for small systems | ⚠️ | ❌ Heavy | ⚠️ Heavy | ✅ **Light** |

## Try it locally

The skill ships with `example/` — 4 scripts that demonstrate all 5 auto-recognized patterns (import + from-import + subprocess literal list). End-to-end test produces 4 files on your Desktop.

See `example/README.md` for the full walkthrough.

## Related skills

- **MGC Blackbox (Cross-Device Script Authorization)** — Single-script sealing (lighter weight)
- **MGC Blackbox Meta Skill** — Full reference for all MGC capabilities

## Links

- **Main repo**: https://github.com/zkeviny/MGC-Blackbox
- **Issues**: https://github.com/zkeviny/MGC-Blackbox/issues
- **Contact**: mirgincipher@outlook.com