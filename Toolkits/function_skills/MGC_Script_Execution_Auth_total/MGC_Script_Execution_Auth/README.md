# Cross‑Device Encrypted Script Authorization (Zero‑Exposure)

A documentation skill for **zero‑exposure cross‑device script authorization** built on MGC Blackbox 1.4.10.

## What This Skill Is

Cross‑Device Encrypted Script Authorization teaches how to:

- Seal scripts using the target node's RSA public key
- Transfer encrypted scripts to authorized nodes
- Run sealed scripts on the authorized node via **blackbox execution** (`mgc_run`) — the source never uploads plaintext
- Build cross‑device trust chains

## Prerequisites

- Python 3.10+
- Install: `pip install mgc-blackbox>=1.4.9` (1.4.10+ recommended)
- Start MGC: `mgc` (API port 57219, WebUI port 57218)
- Two MGC nodes (one owner, one authorized; a single node can self-verify)

## Quick Start

### 1. Get Target Node Public Key

```python
# MCP/API lazy generation
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
```

Or via WebUI: skill page → Settings → **Node Public Key** → copy the multi-line PEM.

> `node_pub` must be a **multi-line PEM** with real newlines (`\n`); do not concatenate into a single line.

### 2. Seal Script (Owner Node)

```python
# Store original script first
mgc_save(
    info_type="script",
    info_owner="my_script",
    ext01="python",
    content="print('Confidential script')"
)

# Seal with target node's public key
sealed = mgc_seal(
    info_owner="my_script",
    ext04=node_pub
)
# sealed = { content, ext_01, ext_02, ext_03 }
# ext_02 is auto-parsed from the script's argparse by MGC 1.4.10
```

### 3. Transfer the Capsule

Send the `sealed` dict via email / USB / IM — any trusted channel. All four fields must travel together.

### 4. Target Node Stores and Executes

```python
# On the target node
mgc_save(
    info_type="script",
    info_owner="partner_script",
    ext01=sealed["ext_01"],
    ext02=sealed["ext_02"],          # default args from source's argparse
    content=sealed["content"],       # AES-encrypted body
    ext03=sealed["ext_03"],          # RSA-encrypted AES key
    update_if_exists=True
)

# Blackbox execution (1.4.7+ recommended)
result = mgc_run(
    info_owner="partner_script",
    diff_1="partner_script",
    ext02='["--name", "Alice"]'      # optional: runtime override of default args
)
# Returns: {"pid": 12345, "status": "started"}
```

## Use Cases

| Use Case | Description |
|----------|-------------|
| Cross‑Organization Sharing | Share scripts without exposing logic |
| Trusted Partner Automation | Provide automation to partners securely |
| Delegated Task Execution | Central server delegates to edge devices |

## MCP Tools

| Tool | Description | Required Parameters |
|------|-------------|---------------------|
| `mgc_save` | Store original or sealed script | info_type, info_owner, content |
| `mgc_run` | Blackbox script execution (1.4.7+) | info_type=script, info_owner, diff_1 (schema-required differentiation field; any non-empty string for a single entry) |
| `mgc_seal` | Seal script with target node public key | info_owner, ext04 (multi-line PEM) |
| `mgc_list` | List entry metadata | — |
| `mgc_find` | Fuzzy search (1.4.10 new) | info_owner, match_mode |
| `mgc_open_webui` | Open WebUI | — |
| `mgc_get` | Fetch node_pub / fetch credential | info_type, info_owner |

## MGC 1.4.10 Adaptation

- ✅ `mgc_run` blackbox execution (replaces legacy `mgc_get(action=run)`)
- ✅ `ext02` auto-parsing of argparse (default args are bundled into the capsule)
- ✅ `mgc_find` fuzzy search (`match_mode` auto-applies `%` wildcards)
- ✅ `update_if_exists` to overwrite same-name scripts
- ✅ WebUI Settings → Node Public Key directly exposes the multi-line PEM
- ✅ 1.4.9 sandbox mode compatible

## Supported Platforms

- Windows
- macOS
- Linux

## Links

- **Main Repository**: https://github.com/zkeviny/MGC-Blackbox
- **Issues**: https://github.com/zkeviny/MGC-Blackbox/issues
- **Contact**: mirgincipher@outlook.com
