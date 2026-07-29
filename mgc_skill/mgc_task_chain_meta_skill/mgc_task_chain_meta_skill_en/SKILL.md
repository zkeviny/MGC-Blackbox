# Multi-Agent Safe-Cooperation (Single Device)

---

## One-Line Description

A single-device multi-Agent task chain collaboration methodology based on MGC. Through Master Agent orchestration, Script Agent scripting, and Executor Agent execution, achieves zero-exposure security collaboration for sensitive resources.

---

## Problem Solved

| Pain Point | Solution |
|------------|----------|
| Multiple Agents sharing environment, keys easily leaked | Store keys in MGC, agents execute without exposure |
| Script content exposed to all Agents | Store scripts in MGC, zero exposure during execution |
| Lack of task collaboration methodology | Master Agent task chain orchestration template |
| Sub-Agent unauthorized access to sensitive resources | Executor Agent prompt constraints |

---

## Core Concepts

### MGC's Role in Collaboration

MGC is the **local sensitive resource hosting and execution layer**:

1. **User** stores keys and scripts via WebUI (browser or mgc_open_webui)
2. **Script Agent** writes scripts and stores them in MGC via mgc_save
3. **Master Agent** orchestrates task chain, specifies call timing; can execute directly when sub-Agents fail or with user authorization
4. **Executor Agent** only calls mgc_run, never touches keys or scripts

### Four Roles

| Role | Responsibility | Capabilities |
|------|----------------|--------------|
| User | Store keys/scripts, issue commands | WebUI / mgc_open_webui |
| Master Agent | Task decomposition, orchestration, execute on authorization/sub-Agent failure | mgc_list, mgc_run |
| Script Agent | Write scripts, store in MGC | mgc_save, mgc_get, mgc_list |
| Executor Agent | Complete non-sensitive tasks | mgc_run, mgc_list |

> Note: Sensitive operations (mgc_get to retrieve plaintext) require user authorization.

---

## Collaboration Flow

```
User ──Store Keys/Scripts (WebUI)──> MGC
                │
                ▼
User ──Issue Command──> Master Agent
                │
                ├──Decompose Task Chain
                │
                ▼
        ┌───────┴───────┐
        ▼               ▼
   Script Agent      Executor Agent
   (Write Scripts)  (Execute Tasks)
        │               │
        ▼               ▼
   mgc_save         mgc_run
        │               │
        └───────┬───────┘
                ▼
           MGC Execution
        (Return Results)
```

---

## Quick Start

### Prerequisites

1. Install MGC v1.4.7+
2. Configure MCP (add to AI client):
   ```json
   {
     "mcpServers": {
       "mgc-blackbox": {
         "command": "mgc",
         "args": ["--mcp"]
       }
     }
   }
   ```
3. Store sensitive resources via WebUI or mgc_open_webui:
   - API Keys
   - Database Credentials
   - Business Scripts

### Step 1: Configure Master Agent

Load `prompts/master_agent.md` into the Master Agent's system prompt.

### Step 2: Configure Script Agent

Load `prompts/script_agent.md`.

### Step 3: Configure Executor Agent

Load `prompts/executor_agent.md`.

### Step 4: Start Collaboration

After user issues a command, the Master Agent automatically decomposes the task chain and coordinates sub-Agents to complete.

---

## Prompt Templates

### prompts/master_agent.md

Master Agent prompt template, includes:
- Task decomposition methods
- MGC call timing
- Sub-task allocation rules

### prompts/script_agent.md

Script Agent prompt template, includes:
- mgc_save usage
- Script naming conventions
- Script location reporting format

### prompts/executor_agent.md

Executor Agent prompt template, includes:
- mgc_run usage
- Prohibited behaviors
- Result handling specifications

### prompts/cooperation_best_practice.md

Best practice document, automatically maintained by Master Agent:
- Collaboration flow
- Reusable script list
- Parameter specifications
- User preferences
- Common errors and fixes
- Scenario best practices
- Collaboration records and user feedback

---

## MGC Tool Usage

### mgc_save (Used by Script Agent)

```python
# Store script
mgc_save(
    info_type="script",
    info_owner="Data Query Script",
    ext01="python",
    content="""# Script content..."""
)
```

### mgc_run (Used by Executor Agent)

> ⚠️ Note: Some MCP clients may have ext02 JSON object serialization compatibility issues; recommended to use JSON string format.

```python
# Execute script
mgc_run(
    info_type="script",      # Required, specify type as script
    info_owner="Data Query Script",  # Required, script name
    diff_1="v1",             # Required, version or branch identifier
    ext02='{"param1": "value1"}'  # Optional, JSON string format for execution parameters
)
```

### mgc_list (Available to All Agents)

> Note: mgc_list only views information lists, does not retrieve plaintext; all Agents can use it.

```python
# View available scripts
mgc_list(info_type="script")
```

### mgc_open_webui (Used by User)

> Used to have AI open MGC WebUI for users to store sensitive resources.

```python
# Open WebUI
mgc_open_webui()
```

---

## Security Boundaries

### What This Skill Provides

- Collaboration methodology framework
- Prompt templates
- MGC tool usage specifications

### What This Skill Does NOT Provide

- MGC permission enforcement (relies on prompt constraints)
- Automatic key management
- Agent identity authentication

### ⚠️ Important Reminders

1. All sensitive resources must be stored by users via MGC WebUI
2. Executor Agent can only call mgc_run, cannot read script content
3. Master Agent must clearly inform sub-Agents of call timing and script location
4. After sensitive operation results return, Master Agent is responsible for updating task status and coordinating sub-Agent collaboration

---

## FAQ

| Question | Answer |
|----------|--------|
| Will information stored in MGC sync to cloud? | MGC is a local tool without active network capability |
| What are MGC's main capabilities? | After installing MGC, view ~/.mgc/skills/mgc_skill.md |
| Can sub-Agents bypass MGC? | Prompt constraints cannot completely prevent; ensure sub-Agents cannot access local script files |
| How to isolate scripts for different tasks? | Use info_owner naming to distinguish, e.g., `TaskA_QueryScript`, `TaskB_PublishScript` |
| How does Master Agent know what scripts are available? | Use mgc_list to view, or report by Script Agent |

---

## Related Resources

- **MGC Core Repository**: https://github.com/zkeviny/MGC-Blackbox
- **MGC Installation**: `pip install mgc-blackbox`
- **WebUI**: http://127.0.0.1:57218
- **API**: http://127.0.0.1:57219
- **MGC API Auth Token**: ~/.mgc/database/mgc_black_box/.mgc_token
- **Feedback**: mirgincipher@outlook.com

---

## Changelog

### v1.0.0

- Initial release
- Provides Master Agent, Script Agent, Executor Agent prompt templates
- Includes complete collaboration flow documentation
