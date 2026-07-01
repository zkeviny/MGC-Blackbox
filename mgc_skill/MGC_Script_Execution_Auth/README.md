# Cross‑Device Encrypted Script Authorization (Zero‑Exposure)

A documentation skill for **zero‑exposure cross‑device script authorization** using MGC Blackbox.

## What This Skill Is

Cross‑Device Encrypted Script Authorization teaches how to:
- Seal scripts using target node's public key
- Transfer encrypted scripts to authorized nodes
- Execute sealed scripts with zero plaintext exposure
- Build cross‑device trust chains

## Prerequisites

- Python 3.10+
- Install: `pip install mgc-blackbox` (recommended 1.4.6+)
- Start MGC: `mgc` (runs at http://127.0.0.1:57219)
- Two MGC nodes required

## Quick Start

### 1. Get Target Node Public Key

```python
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
```

### 2. Seal Script

```python
sealed = mgc_seal(
    info_type="script",
    info_owner="my_script",
    ext04=node_pub
)
```

### 3. Transfer to Target Node

Transfer the sealed content to the authorized node.

### 4. Store and Execute

```python
# On target node
mgc_save(
    info_type="script",
    info_owner="sealed_script",
    ext01="python",
    content=sealed
)

# Execute
result = mgc_get(
    info_type="script",
    info_owner="sealed_script",
    action="run"
)
```

## Use Cases

| Use Case | Description |
|----------|-------------|
| Cross‑Organization Sharing | Share scripts without exposing logic |
| Trusted Partner Automation | Provide automation to partners securely |
| Delegated Task Execution | Central server delegates to edge devices |

## MCP Tools

| Tool | Description |
|------|-------------|
| mgc_get | Get node_pub, execute sealed scripts |
| mgc_seal | Seal scripts with target node key |
| mgc_save | Store original or sealed scripts |
| mgc_list | List stored scripts |
| mgc_open_webui | Open WebUI |

## Supported Platforms

- Windows
- macOS
- Linux

## Links

- **Main Repo**: https://github.com/zkeviny/MGC-Blackbox
- **Issues**: https://github.com/zkeviny/MGC-Blackbox/issues
- **Contact**: mirgincipher@outlook.com