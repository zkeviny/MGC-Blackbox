# Best Practice Document

> This document is automatically maintained and updated by the Master Agent, recording best practices, common scripts, user preferences, and other information during collaboration.

---

## Collaboration Flow

### ⚠️ Script Execution Result Handling Principle

**Scripts executed via `mgc_run` (sealed or not) will only return execution results, not the script's stdout.**

#### Handling Methods

**1. One-time tasks**:
- Do not store script in MGC, execute locally
- Directly view script output

**2. Reusable tasks**:
- Store script in MGC
- Script saves results to file (e.g., `~/mgc_outputs/result_xxx.txt`)
- Output file path via stdout (execution result will return)
- Subsequent Agents read the file

#### Task Chain Result Passing Example

```
Sub-task 1: Script saves to ~/mgc_outputs/data_001.txt
  └─ Returns: RESULT_FILE:~/mgc_outputs/data_001.txt

Sub-task 2: Read data_001.txt, after analysis save to analysis_001.txt
  └─ Returns: RESULT_FILE:~/mgc_outputs/analysis_001.txt

Master Agent aggregation: Read final result file, output to user
```

#### Script Output Save Example

```python
import os
from datetime import datetime

def save_result(data):
    output_dir = os.path.expanduser("~/mgc_outputs")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(str(data))

    # Output file path via stdout
    print(f"RESULT_FILE:{filepath}")
```

### Standard Task Chain Flow

```
1. User issues command
   ↓
2. Master Agent understands task goal
   ↓
3. Master Agent views best practices, decomposes task chain
   ↓
4. Identify sensitive operations (require MGC)
   ↓
5. Assign tasks to sub-Agents
   ↓
6. Execute tasks
   ↓
7. Aggregate results
   ↓
8. Ask user feedback
   ↓
9. Update best practice document
```

---

## Script List

> Existing reusable scripts, can be updated after each task

| Script Name | Function Description | Created | Reuse Count | Notes |
|-------------|---------------------|---------|-------------|-------|
| (None yet) | - | - | - | Auto-added after task execution |

---

## Parameter Specifications

### Script Naming Convention

```
{TaskType}_{FunctionDescription}_v{Version}
```

Examples:
- `DataAnalysis_QuerySales_v1`
- `Publish_BlogPush_v1`
- `Marketing_SMSend_v1`

### ext02 Parameter Format

```python
import json
params = {"key": "value"}
ext02 = json.dumps(params)  # Must convert to JSON string
```

---

## User Preferences

> Record user's习惯偏好, update after each task

| Preference Item | Content | Updated |
|----------------|---------|---------|
| (None yet) | - | - |

---

## Common Errors and Fixes

### Error 1: mgc_run returns 422 error

**Cause**: ext02 parameter format error

**Fix**:
```python
import json
ext02 = json.dumps({"to": "user@example.com"})  # Use json.dumps
```

### Error 2: Token file does not exist

**Cause**: MGC not started or token path incorrect

**Fix**:
- Confirm MGC is started
- Token path: `~/.mgc/database/mgc_black_box/.mgc_token`

### Error 3: Script execution failed

**Cause**: Internal script error

**Fix**:
- Check script syntax
- Confirm credential name is correct
- Check MGC logs

---

## Scenario Best Practices

### Scenario 1: Data Analysis

**Flow**:
1. Script Agent writes query script → Store in MGC
2. Executor Agent calls script to get data
3. Analyze data, generate report
4. Publish report

**Notes**:
- Raw data not exposed to Executor Agent
- Analysis results need desensitization

### Scenario 2: Content Publishing

**Flow**:
1. Executor Agent writes content
2. Script Agent writes publish script → Store in MGC
3. Master Agent authorizes execution
4. Executor Agent calls publish script

**Notes**:
- API keys not exposed
- Publishing results need user confirmation

### Scenario 3: Marketing Notifications

**Flow**:
1. Executor Agent filters target users
2. Script Agent writes notification script → Store in MGC
3. Master Agent authorizes execution
4. Executor Agent calls send script

**Notes**:
- Customer data not exposed
- Send frequency needs control

---

## Collaboration Records and User Feedback

> Records after each task completion

| Date | Task | User Feedback | Improvement |
|------|------|--------------|-------------|
| (None yet) | - | - | - |
