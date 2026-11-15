# 凭据管理工作流（Credential Management）

本文档用于指导数据分析师在 **MGC Blackbox ≥ 1.5.1** 中安全管理数据库密钥、API Token 等敏感凭据，并在脚本中实现 **零暴露调用**。

所有敏感操作必须由用户明确授权后才能进行。

---

# 一、凭据管理概述

MGC Blackbox 提供本地加密存储与零暴露访问能力：

- 密钥永不以明文暴露给 AI
- 密钥仅在用户本地机器解密
- 脚本可以安全调用密钥，但 AI 无法看到内容
- 所有访问必须由用户授权

---

# 二、如何安全存入凭据

凭据存储推荐使用 **MGC WebUI** 或 **mgc_save** 工具。

### 方法 1：通过 WebUI 存储（推荐）

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
info_type: "token"
info_owner: "db_warehouse_prod"   # 自定义名称
content: <你的数据库凭据>         # 明文仅在本地加密
```

### 方法 2：通过 mgc_save 存储

```python
mgc_save(
    info_type="token",
    info_owner="db_warehouse_prod",
    content="postgres://user:password@host:5432/dbname"
)
```

### 安全说明

- 凭据仅在本地加密存储
- AI 无法看到凭据内容
- 所有访问必须由用户授权
- 凭据不会离开用户机器

---

# 三、如何在脚本中零暴露调用凭据（核心）

**MGC 实现机制**：脚本存储在 MGC 中，运行时 MGC 在本地解密脚本并执行。如果脚本需要访问凭据，脚本内部通过本地 API 调用获取凭据。

## 标准示例：脚本内部安全访问凭据

```python
import os, requests, json

# 读取 MGC 访问令牌（固定路径，不要改）
with open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")) as f:
    MGC_TOKEN = f.read().strip()

def get_credential(info_owner="db_warehouse_prod"):
    """从 MGC 获取凭据"""
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

# 使用凭据
def query_monthly_orders():
    credential = get_credential("db_warehouse_prod")
    # ... 使用凭据建立连接并查询
```

**注意**：
- 此调用仅限本地（127.0.0.1），AI 无法看到凭据
- Token 文件路径：`~/.mgc/database/mgc_black_box/.mgc_token`
- 脚本执行由 MGC 管理，凭据在 MGC 内部解密

## 按名称定位凭据（推荐工作流）

访问凭据前，先用 **mgc_find** 按名称模糊搜索定位：

```python
# 按名称模糊搜索凭据
matches = mgc_find(
    info_owner="db_warehouse",  # 部分名称；默认 substring 匹配
    info_type="token",
)
# 返回 metadata 列表——绝不返回凭据明文。
# 定位到精确的 (info_type, info_owner) 后，脚本内部再调 MGC API 解密。
```

**安全特性**：
- `mgc_find` 绝不返回凭据明文——只返回 metadata
- 定位后仍走 MGC API 本地解密
- 所有访问仍需用户授权

---

# 四、如何授权访问凭据（用户必须确认）

当 AI 需要访问凭据时，必须询问用户：

```
凭据名称：db_warehouse_prod
操作：访问凭据
是否需要授权：是

您是否授权访问此凭据？回复"是"继续，回复"否"取消。
```

AI 在未获得用户授权前不得访问任何凭据。

---

# 五、最佳实践

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

# 六、常见问题

| 问题 | 解决方案 |
|------|---------|
| 脚本无法访问凭据 | 检查 info_owner 是否一致 |
| 凭据为空 | 检查 WebUI 是否正确存储 |
| 执行失败 | 检查脚本依赖是否在本地可用 |

---

# 七、总结

本凭据管理文档提供：

- 本地加密存储
- 零暴露调用
- 用户授权机制
- 安全脚本编写规范

这是数据分析师安全工作流的基础能力。
