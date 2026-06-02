# 📘 **Doc‑as‑Skill #2: Encrypted Cognitive Script Execution**  

## 🎯 Value Scenario  
Your scripts contain:

- business logic  
- decision rules  
- data analysis workflows  
- your personal “cognitive assets”

But AI/agents need to call these scripts.  
The problem:

> If AI can see the script, your cognitive assets are exposed.

MGC solves this by providing:

> **Encrypted script storage + sealed execution + external‑only output**  
> AI can call your script, but can never see it.

> **This document is also a skill — you can give it to your AI and let it follow the steps.**

---

## 🛠 How to Use (AI‑Executable Instructions)

> **Note:**  
> - These examples use MCP tools exactly as implemented (`mgc_save`, `mgc_get`, `mgc_seal`).  
> - REST API / WebUI usage is available in the full skill specification.  
> - Make sure MGC is installed (`pip install mgc-blackbox`) and running (`mgc`).

---

## **Step 1 — Prepare your script (external output only)**

Your script must output results **via external side effects**, not stdout.

Example:

```python
import sys, json
args = sys.argv[1:] if len(sys.argv) > 1 else []
result = {"source": "local", "args_received": args}

with open("D:/MGC/args_output.txt", "w") as f:
    f.write(json.dumps(result))

print("done")
```

---

## **Step 2 — Store your script in MGC (MCP)**

> For executable scripts:  
> - `ext01`: startup command (e.g., `"python"`, `"node"`)  
> - `ext02`: default runtime parameters (optional, string format)

```
mgc_save(
    info_type="script",
    info_owner="my_logic",
    ext01="python",
    ext02="--date 2025-01-01",
    content="<your_script_content>"
)
```

---

## **Step 3 — Run the script (MCP)**

```
mgc_get(
    info_type="script",
    info_owner="my_logic",
    action="run",
    ext02={"date": "2025-01-01"}
)
```

- MGC decrypts  
- Executes the script  
- Does **not** return stdout  
- Produces external output (file, webhook, email, etc.)

---

## **Optional — Seal the script and run the sealed version**

### Get your node’s public key:

```
mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
```

### Seal the script:

```
mgc_seal(
    info_owner="my_logic",
    ext04="<target_node_rsa_public_key>"
)
```

- The script becomes unreadable  
- Even you cannot view it  
- But it remains executable inside MGC  

### Save the sealed script to your MGC:

```
mgc_save(
    info_type="script",
    info_owner="my_sealed_logic",
    ext01="python",
    ext02="--date 2025-01-01",
    ext03="<target_node_rsa_public_key>"
    content="<your_sealed_script_content>"
)
```

### Run the sealed script:

```
mgc_get(
    info_type="script",
    info_owner="my_sealed_logic",
    action="run",
    ext02={"date": "2025-01-01"}
)
```

---

## **Step 4 — Read the external output**

Example:

```python
read_file("D:/MGC/args_output.txt")
```

---

## ⭐ Best Practices

- **If you don't want AI to handle sensitive data directly** — use WebUI for storage, tell AI only the format  
- Do not use `print()` for results  
- Do not return values  
- Always output via files / API calls / emails  
- AI reads only the external output, never from MGC  

---

## 🔒 Security Boundary

- AI / Users cannot see the script unless you authorize it  
- If sealed, even you cannot see it  
- MGC never returns stdout  
- Script logic remains permanently sealed  

---