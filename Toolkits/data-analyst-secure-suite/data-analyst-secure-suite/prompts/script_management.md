# Script & Workflow Management

This document guides data analysts on how to securely manage query scripts, cleaning scripts, analysis scripts, and other **user-owned scripts** in **MGC Blackbox ≥ 1.5.2**, and implement **zero-exposure application** locally.

All sensitive operations must be explicitly authorized by the user before proceeding.

---

# 1. Overview

MGC Blackbox 1.5.2+ provides local encrypted storage, automatic cross-script recognition, and zero-exposure application:

- Script content never exposed to AI
- Scripts decrypted only on the user's local machine
- Scripts can safely call credentials (zero-exposure)
- All applications must be authorized by the user
- AI can only see execution results, never script logic
- **Workflow folders are automatically scanned for `import` / relative-path / `subprocess` call relationships** (1.5.1+)

---

# 2. Two Management Modes

| Mode | Scenario | Storage Tool | Run Tool |
|------|---------|-------------|---------|
| **Workflow Mode (recommended)** | Multi-script pipelines (query → clean → analyze) | `mgc_save_file` | `mgc_run` (specify entry script) |
| **Single-Script Mode** | Single independent script | `mgc_save` | `mgc_run` |

> **Recommendation**: If your analysis chain has 2+ scripts, use Workflow Mode. MGC will automatically recognize `import` / `from-import` / relative-path / `subprocess` relationships between scripts and route execution under sealing — no manual parameter passing needed.

---

# 3. Workflow Mode (Recommended, 1.5.2+)

## 3.1 Workflow Folder Structure

A typical data analysis workflow:

```
my_analysis/
├── manifest.json
├── run.py              # Entry script: invokes modules under helpers
├── helpers/
│   ├── query.py        # Query module
│   ├── clean.py        # Cleaning module
│   └── analyze.py      # Analysis module
└── config/
    └── settings.json   # Configuration file
```

`run.py` can directly `import` modules from the same package:

```python
# run.py
from helpers.query import query_data
from helpers.clean import clean_data
from helpers.analyze import analyze_data

def main():
    raw = query_data()
    cleaned = clean_data(raw)
    result = analyze_data(cleaned)
    # Write result to file or MGC; never return it
    with open("output/report.xlsx", "wb") as f:
        f.write(result)

if __name__ == "__main__":
    main()
```

## 3.2 Save the Workflow

```python
mgc_save_file(
    path="./my_analysis",
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)
```

**MGC will automatically**:
- Parse each script's `argparse` and write it to `ext02` (parameter list)
- Scan imports and write them to `ext05` (dependency list)
- Infer `ext06` (platform list)
- Build `ext08` (cross-script call graph) — recognizing `import` / `from-import` / `Path` relative-path / `subprocess` relationships

> **Note**: MGC will **use the last segment of the path as `diff_2`** (e.g. `path="./my_analysis"` actually writes `diff_2="my_analysis"`). After saving, please use `mgc_find` to confirm the actual `diff_2` before passing it to sealing.

## 3.3 Run the Workflow

```python
mgc_run(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)
# → {"pid": 12345, "status": "started"}
```

MGC will automatically:
- Decrypt all scripts into memory (never written to disk)
- Intercept `import` / `subprocess` calls and route through sealed execution
- Return run status, never script content

## 3.4 Locate Workflow by Name

```python
# Fuzzy search for a workflow
matches = mgc_find(
    info_owner="monthly",      # partial name; substring match by default
    match_mode="substring",
)
# Returns metadata list (info_type, info_owner, ext01..ext03) — never plain text.
# After locating the exact info_owner, pass it to mgc_run.
```

## 3.5 Workflow Sealed Collaboration (1.5.2+)

Seal the entire workflow to another node (team member / client) in one shot:

```python
# 1. The recipient first fetches their own node_pub
# Recipient runs: mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")

# 2. You seal the entire workflow with the recipient's public key
mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04=recipient_node_pub,          # Recipient's PEM public key
    output_dir="./delivery",            # REQUIRED in 1.5.2+: output directory for sealed package
)
# → Generates .mgc_file encrypted package
```

After the recipient receives the `.mgc_file`:

```python
# Recipient imports the sealed package (info_owner / diff_2 must match sealing-time values)
mgc_save_file(
    path="./received.mgc_file",
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)

# Recipient runs in blackbox mode
mgc_run(info_owner="monthly_sales_analysis", diff_2="monthly_sales_analysis")
```

**Security features**:
- Whole workflow sealed in one shot, no need to seal each script individually
- AES key bound to recipient's RSA public key, recipient cannot re-seal to a third party
- Recipient can only run, never read source

> **Note**: `ext04` MUST contain real newline characters `\n`. Do NOT pass PEM as a single concatenated line.

---

# 4. Single-Script Mode (Simple Scenarios)

When you only need to manage a single independent script (no cross-script calls), use `mgc_save`.

## 4.1 Save a Single Script

```python
mgc_save(
    info_type="script",
    info_owner="quick_query",
    ext01="python",
    content="<your script content>"
)
```

## 4.2 Run a Single Script

```python
mgc_run(
    info_type="script",
    info_owner="quick_query",
    diff_1="quick_query",
)
```

## 4.3 Seal a Single Script

```python
sealed = mgc_seal(
    info_owner="quick_query",
    ext04=recipient_node_pub,
)
```

---

# 5. How Scripts Zero-Exposure Call Credentials Internally

**MGC implementation**: Scripts are stored in MGC; at runtime MGC decrypts and executes the script locally. If the script needs to access credentials, it calls a local API to fetch them internally.

## Standard Example: Script Safely Accesses Credentials Internally

```python
import os, requests, json

# Read MGC access token (fixed path, do not change)
with open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")) as f:
    MGC_TOKEN = f.read().strip()

def get_credential(info_owner="db_warehouse_prod"):
    """Fetch credential from MGC"""
    resp = requests.post(
        "http://127.0.0.1:57219/api/mgc/sensitive/get",
        headers={"X-MGC-Token": MGC_TOKEN},
        json={
            "info_type": "token",
            "info_owner": info_owner,
        },
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 200:
            data_field = data.get("data")
            if isinstance(data_field, str):
                return json.loads(data_field)
            elif isinstance(data_field, dict):
                content = data_field.get("content")
                if content:
                    return json.loads(content)
    return None

# Using credential
def query_monthly_orders():
    credential = get_credential("db_warehouse_prod")
    # ... use credential to connect and query
```

**Notes**:
- This call is local-only (127.0.0.1), AI cannot see credentials
- Token file path: `~/.mgc/database/mgc_black_box/.mgc_token`

---

# 6. Recognizable Cross-Script Patterns (Required for Workflow Mode)

When saving a workflow folder with `mgc_save_file`, MGC automatically recognizes the following patterns:

| Pattern | Code Example | Recognizable? |
|---------|--------------|--------------|
| `from` import | `from config import DEFAULT_CITY` | ✅ |
| `from` import with alias | `from helpers.fetch import get_weather as gw` | ✅ |
| Plain `import` | `import helpers.parse` | ✅ |
| `Path` relative path | `Path(__file__).parent / "config.py"` | ✅ |
| `open()` relative path | `open("config.json")` referencing a sibling file | ✅ |
| `subprocess` + relative path | `subprocess.run([sys.executable, str(Path(__file__).parent / "config.py"), ...])` | ✅ — only within the same package |
| `subprocess` + literal list (1.5.2+) | `subprocess.run([sys.executable, "helper.py", "--arg"])` | ✅ — runtime routing support since 1.5.2 |
| Dynamic import | `importlib.import_module(module_name)` | ❌ only static parsing supported |
| Absolute path | `open("/Users/alice/config.py")` | ❌ not portable |

**Scope**: Cross-script calls are only recognized within the same folder package. Please keep helpers and driver in the same directory.

---

# 7. Authorization Template (AI Must Ask)

When AI needs to apply scripts or workflows, it must ask the user:

```
Workflow Name: monthly_sales_analysis
Operation: Run Workflow
Authorization Required: YES

Do you authorize this operation? Reply "yes" to proceed, or "no" to cancel.
```

AI must not apply any script or workflow without user authorization.

---

# 8. Best Practices

### ✔ 1. Prefer Workflow Mode
For multi-script analysis chains, save with `mgc_save_file` — MGC auto-recognizes import relationships, no manual parameter passing needed.

### ✔ 2. Entry Script Only Handles Orchestration
`run.py` should only call modules under `helpers`; put core algorithms in their own modules.

### ✔ 3. Write Results to File or MGC
For blackbox execution, MGC will not return any plaintext. Workflow output must explicitly target a file path, or be written to a database or MGC itself.

### ✔ 4. Use Descriptive `info_owner`
For example: `monthly_sales_analysis`, `customer_churn_prediction`, `daily_report_gen`

### ✔ 5. Never Hardcode Secrets in Scripts
All secrets must be obtained through MGC.

### ✔ 6. All Applications Require Authorization
AI must not automatically apply scripts or workflows.

---

# 9. FAQ

| Issue | Solution |
|-------|----------|
| Workflow run fails | Check whether dependencies in `ext05` are installed locally |
| Import cannot find module | Ensure all scripts are within the same `mgc_save_file` package |
| Sealing failed | Check whether `ext04` is a multi-line PEM public key (preserving `\n`) |
| Platform incompatible | Check whether `ext06` contains the current OS |
| Credential fetch failed | Check whether `info_owner` matches |

---

# 10. Summary

This workflow management document provides:

- Encrypted workflow folder storage and automatic recognition
- Zero-exposure credential calls
- Zero-exposure workflow execution
- User authorization mechanism
- Workflow sealing and collaboration authorization

This is the core capability of secure data analyst workflows.