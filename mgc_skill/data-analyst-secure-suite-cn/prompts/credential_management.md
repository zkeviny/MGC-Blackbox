# 数据库密钥管理工作流（Credential Management）

本文档用于指导数据分析师在 **MGC Blackbox** 中安全管理数据库密钥、API Token 等敏感凭据，并在脚本中实现 **零暴露调用**。

所有敏感操作必须由用户明确授权后才能进行。

---

# 📌 一、密钥管理概述

MGC Blackbox 提供本地加密存储与零暴露访问能力：

- 密钥永不以明文暴露给 AI  
- 密钥仅在用户本地机器解密  
- 脚本可以安全调用密钥，但 AI 无法看到内容  
- 所有访问必须由用户授权  

---

# 📌 二、如何安全存入密钥（凭据）

密钥存储推荐使用 **MGC WebUI** 或 **mgc_save** 工具。

### ✅ 方法 1：通过 WebUI 存储（推荐）

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
info_type: "credential"
info_owner: "db_warehouse_prod"   # 自定义名称
content: <你的数据库凭据>         # 明文仅在本地加密
```

### ✅ 方法 2：通过 mgc_save 存储

```python
mgc_save(
    info_type="credential",
    info_owner="db_warehouse_prod",
    content="postgres://user:password@host:5432/dbname"
)
```

### 🔒 安全说明

- 密钥仅在本地加密存储  
- AI 无法看到密钥内容  
- 所有访问必须由用户授权  
- 密钥不会离开用户机器  

---

# 📌 三、如何在脚本中零暴露调用密钥（核心）

**MGC 实现机制**：脚本存储在 MGC 中，当通过 `mgc_get action="run"` 执行脚本时，MGC 在本地解密脚本并执行。如果脚本需要访问凭据，脚本内部通过本地 API 调用获取凭据。

---

## ✅ 标准示例：脚本内部安全访问凭据

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
        print("Token not found!")
        return None

    resp = requests.post(
        f"{BASE_URL}/api/mgc/sensitive/get",
        headers={"X-MGC-Token": token, "Content-Type": "application/json"},
        json={
            "info_type": "credential",
            "info_owner": "db_warehouse_prod"  # 凭据名称
        }
    )

    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 200:
            data_field = data.get("data")
            # data_field 可能是字符串或字典
            if isinstance(data_field, str):
                return json.loads(data_field)
            elif isinstance(data_field, dict):
                content = data_field.get("content")
                if content:
                    return json.loads(content)
    return None

# 使用凭据
def query_monthly_orders():
    credential = get_credential()
    # ... 使用凭据建立连接并查询
```

**注意**：
- 此调用仅限本地（127.0.0.1），AI 无法看到凭据
- Token 文件路径：`~/.mgc/database/mgc_black_box/.mgc_token`
- 脚本执行由 MGC 管理，凭据在 MGC 内部解密

### 🔒 安全特性

- 凭据在本地解密  
- AI 无法看到凭据内容  
- 脚本内部调用仅限本地  
- 调用前必须获得用户授权

---

# 📌 四、如何授权访问密钥（用户必须确认）

当 AI 需要访问密钥时，必须询问用户：

```
凭据名称：db_warehouse_prod
操作：访问凭据
是否需要授权：是

您是否授权访问此凭据？回复“是”继续，回复“否”取消。
```

AI 在未获得用户授权前不得访问任何凭据。

---

# 📌 五、最佳实践

### ✔ 1. 使用描述性 info_owner  
例如：

- `db_warehouse_prod`  
- `api_salesforce_token`  
- `redis_cache_credential`

### ✔ 2. 不在脚本中硬编码密钥  
所有密钥必须通过 MGC 获取。

### ✔ 3. 不在 AI 对话中粘贴密钥  
AI 无法保护明文密钥。

### ✔ 4. 所有访问必须授权  
AI 不得自动访问凭据。

---

# 📌 六、常见问题

| 问题 | 解决方案 |
|------|---------|
| 脚本无法访问凭据 | 检查 info_owner 是否一致 |
| 凭据为空 | 检查 WebUI 是否正确存储 |
| 执行失败 | 检查脚本依赖是否在本地可用 |

---

# 📌 七、总结

本密钥管理文档提供：

- 本地加密存储  
- 零暴露调用  
- 用户授权机制  
- 安全脚本编写规范  

这是数据分析师安全工作流的基础能力。

---