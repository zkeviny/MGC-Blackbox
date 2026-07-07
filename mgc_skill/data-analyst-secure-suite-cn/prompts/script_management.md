# ⭐ **script_management.md **  
# 数据分析脚本管理（Script Management）

本文档用于指导数据分析师在 **MGC Blackbox** 中安全管理查询脚本、清洗脚本、分析脚本等 **用户自有脚本**，并在本地实现 **零暴露应用**。

所有敏感操作必须由用户明确授权后才能进行。

---

# 📌 一、脚本管理概述

MGC Blackbox 提供脚本的本地加密存储与零暴露应用能力：

- 脚本内容永不暴露给 AI  
- 脚本仅在用户本地机器解密  
- 脚本可安全调用凭据（零暴露）  
- 所有应用必须由用户授权  
- AI 只能看到脚本的执行结果，不可见逻辑  

---

# 📌 二、脚本类型（用户自有）

本技能套件支持管理以下脚本类型：

| 类型 | 说明 |
|------|------|
| 查询脚本 | 用户自有的数据查询逻辑 |
| 清洗脚本 | 用户自有的数据转换逻辑 |
| 分析脚本 | 用户自有的分析逻辑 |
| 交付脚本 | 用户自有的结果处理逻辑 |
| 协作脚本 | 用于跨团队协作的脚本（可密封） |

所有脚本必须由用户提供，本套件不生成脚本。

---

# 📌 三、如何安全存入脚本

脚本存储推荐使用 **MGC WebUI** 或 **mgc_save** 工具。

---

## ✅ 方法 1：通过 WebUI 存储（推荐）

1. 启动 MGC：  
   ```
   mgc
   ```
2. 打开 WebUI：  
   ```
   http://127.0.0.1:57218
   ```
3. 进入 **Save 页面**  
4. 填写字段：

```
info_type: "script"
info_owner: "analysis_monthly_summary"   # 自定义脚本名称
ext01: "python"
content: <你的脚本内容>
```

---

## ✅ 方法 2：通过 mgc_save 存储

```python
mgc_save(
    info_type="script",
    info_owner="analysis_monthly_summary",
    ext01="python",
    content="<你的脚本内容>"
)
```

---

# 📌 四、如何编写脚本以实现“零暴露调用密钥”

**MGC 实现机制**：脚本存储在 MGC 中，当通过 `mgc_get action="run"` 执行脚本时，MGC 在本地解密脚本并执行。如果脚本需要访问凭据，脚本内部通过本地 API 调用获取凭据。

---

## 🔐 标准示例：脚本内部安全访问凭据

脚本内部通过 MGC 本地 API 获取凭据：

```python
import requests
import os
import json

BASE_URL = "http://127.0.0.1:57219"
TOKEN_PATH = os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")

def get_token():
    """读取本地 Token"""
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            return f.read().strip()
    return ""

def get_credential():
    """从 MGC 获取凭据"""
    token = get_token()
    if not token:
        return None

    resp = requests.post(
        f"{BASE_URL}/api/mgc/sensitive/get",
        headers={"X-MGC-Token": token, "Content-Type": "application/json"},
        json={
            "info_type": "credential",
            "info_owner": "db_warehouse_prod"
        }
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

# 使用凭据
def analyze_monthly_sales(input_data):
    credential = get_credential()
    # ... 使用凭据建立连接并分析
```

**注意**：
- 此调用仅限本地（127.0.0.1），AI 无法看到凭据
- Token 文件路径：`~/.mgc/database/mgc_black_box/.mgc_token`

### 🔒 安全特性

- 凭据在本地解密
- AI 无法看到凭据内容
- 脚本内部调用仅限本地
- 调用前必须获得用户授权

---

# 📌 五、如何安全应用脚本（零暴露）

脚本应用必须通过 MGC 完成，AI 不可见脚本内容。

---

## 🔐 标准应用方式（需用户授权）

```python
result = mgc_get(
    info_type="script",
    info_owner="analysis_monthly_summary",
    action="run",
    ext02=input_data   # 如需传入上一步结果
)
```

### 🔒 安全特性

- AI 不可见脚本内容  
- AI 不可见凭据内容  
- 所有执行在本地完成  
- 所有操作必须由用户授权  

---

# 📌 六、脚本协作（密封）

脚本可通过密封方式安全共享给团队成员或外部节点。

---

## 🔐 密封脚本示例

```python
sealed_script = mgc_seal(
    info_type="script",
    info_owner="analysis_monthly_summary",
    ext04=recipient_public_key
)
```

### 🔒 安全特性

- 密封脚本始终加密  
- 接收方可在本地应用脚本  
- 脚本逻辑永不暴露  

---

# 📌 七、授权模板（AI 必须询问）

当 AI 需要应用脚本时，必须询问用户：

```
脚本名称：analysis_monthly_summary
操作：应用脚本（action="run"）
是否需要授权：是

您是否授权此操作？回复“是”继续，回复“否”取消。
```

AI 在未获得用户授权前不得应用任何脚本。

---

# 📌 八、最佳实践

### ✔ 1. 使用描述性脚本名称  
例如：

- `query_monthly_orders`  
- `cleaning_standardize_date`  
- `analysis_monthly_summary`

### ✔ 2. 不在脚本中硬编码密钥  
所有密钥必须通过 MGC 获取。

### ✔ 3. 不在 AI 对话中粘贴脚本内容  
AI 无法保护脚本逻辑。

### ✔ 4. 所有应用必须授权  
AI 不得自动应用脚本。

### ✔ 5. 脚本应输出到本地  
MGC 内部执行不会自动生成文件。

---

# 📌 九、常见问题

| 问题 | 解决方案 |
|------|---------|
| 脚本无法应用 | 检查 info_owner 是否一致 |
| 脚本依赖缺失 | 检查本地环境是否安装依赖 |
| 密封失败 | 检查目标节点是否安装 MGC 1.4.6+ |

---

# 📌 十、总结

本脚本管理文档提供：

- 脚本加密存储  
- 零暴露调用密钥  
- 零暴露应用脚本  
- 用户授权机制  
- 脚本协作与密封  

这是数据分析师安全工作流的核心能力。

---