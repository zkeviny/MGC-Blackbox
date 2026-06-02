# 📘 **Doc‑as‑Skill #3: Cross‑Node Execution Grant (Encrypted Capability Sharing)**

## 🎯 Value Scenario  
You distilled your core workflow into a skill:

- a prompt (plain text)  
- a logic script (or more)  
- maybe a multi‑step task chain  

Your AI agent can use it to automate your work.  
But when someone (a friend, a colleague, your boss) asks for your skill:

> If you give them the folder, you lose ownership of your cognitive asset forever.

MGC enables:

> **Execution‑right transfer without revealing the script**  
> You can give others the ability to run your skill, without giving them your logic.

---

## 🛠 How to Use (AI‑Executable Instructions)

> **Note:** These examples use MCP tools.  
> For REST API or WebUI, see the full skill specification.

---

## **Example logic script (logic.py)**

```python
import sys, json
args = sys.argv[1:] if len(sys.argv) > 1 else []
result = {"source": "local", "args_received": args}

with open("D:/MGC/args_output.txt", "w") as f:
    f.write(json.dumps(result))

print("done")
```

---

## **Step 1 — Split your skill**

```
skill/
   prompt.txt        ← visible to AI
   logic.py          ← must be encrypted
```

---

## **Step 2 — Obtain the other party’s node_pub**

They run:

```
mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
```

You receive:

```
<their_node_pub>
```

---

## **Step 3 — Seal your script using their node_pub**

```
mgc_seal(
    info_type="script",
    info_owner="my_skill_logic",
    ext04="<their_node_pub>"
)
```

This produces a sealed_script_json:

```
{
  "content": "<sealed_script_content>",
  "ext01": "python",
  "ext02": "--date 2025-01-01",
  "ext03": "<target_node_rsa_public_key>"
}
```

---

## **Step 4 — Package and send**

```
skill/
   prompt.txt
   sealed_script_json
```

---

## **Step 5 — They store the sealed script into their MGC**

```
mgc_save(
    info_type="script",
    info_owner="Mary_logic",
    ext01="python",
    ext02="--date 2025-01-01",
    ext03="<target_node_rsa_public_key>",
    content="<sealed_script_content>"
)
```

---

## **Step 6 — Their MGC can now run your skill**

```
mgc_get(
    info_type="script",
    info_owner="Mary_logic",
    action="run"
)
```

---

## ⭐ Best Practices

- Prompt = plain text  
- Script = encrypted  
- Execution rights transferable  
- Ownership never transferred  

---

## 🔒 Security Boundary

- They cannot read your script  
- They cannot decrypt your script  
- They can only execute it  
- Your cognitive asset remains yours  

---