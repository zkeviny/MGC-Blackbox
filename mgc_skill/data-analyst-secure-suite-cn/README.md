# ⭐ 数据分析师安全技能套件

# 数据分析师安全技能套件  
基于 **MGC Blackbox** 的数据分析安全工作流套件，提供 **技能提示词 + Agent 系统提示词模板** 的混合形态，帮助数据分析师在本地安全地管理脚本、凭据、协作授权与知识沉淀。

---

## 📌 本技能套件是什么

本技能套件用于帮助数据分析师在本地安全地完成数据分析相关工作流，包括：

- **数据库凭据安全管理**（零暴露）
- **用户自有脚本的安全应用**（查询 / 清洗 / 分析）
- **脚本密封与协作授权**（跨团队安全协作）
- **分析方法与提示词的知识管理**（本地加密存储）
- **可选的数据分析 Agent 模板**（自动遵守安全边界）

所有敏感操作均需用户明确授权，本套件不提供任何自动化数据访问能力。

---

## 📌 前置条件

- Python 3.10+
- 安装 MGC Blackbox：  
  ```
  pip install mgc-blackbox
  ```
- 启动 MGC：  
  ```
  mgc
  ```
  - WebUI：`http://127.0.0.1:57218`（可视化界面）
  - API：`http://127.0.0.1:57219`（API 接口）
  - Token Required: Header "X-MGC-Token"
  - Token File: `~/.mgc/database/mgc_black_box/.mgc_token`

---

## 📌 目标用户

- 处理敏感业务数据的数据分析师  
- 需要安全脚本协作的团队  
- 需要保护本地数据资产的组织  
- 需要构建安全数据分析 Agent 的用户  

---

## 📌 工作流概述（安全链路）

```
┌──────────────────────────────────────────────┐
│                数据分析安全工作流            │
├──────────────────────────────────────────────┤
│                                              │
│  凭据管理 → 数据查询脚本（用户自有） → 数据清洗 │
│                                              │
│  → 数据分析 → 安全交付 → 知识沉淀              │
│                                              │
└──────────────────────────────────────────────┘
```

所有脚本均为用户自有脚本，所有应用均在本地通过 MGC 完成，AI 不可见脚本与凭据。

---

## 📌 核心组件说明

### 1. 凭据管理（零暴露）

用户可通过 MGC WebUI 存储数据库凭据：

```
info_type: "credential"
info_owner: "db_connection_name"
content: 加密凭据（用户自有）
```

AI 不可见凭据内容。

---

### 2. 数据查询脚本（用户自有）

用户将自己的查询脚本存入 MGC：

```
info_type: "script"
info_owner: "query_monthly_orders"
ext01: "python"
content: 用户自有脚本
```

应用脚本（需用户授权）：

```python
result = mgc_get(
    info_type="script",
    info_owner="query_monthly_orders",
    action="run"
)
```

---

### 3. 数据清洗脚本（用户自有）

清洗脚本同样由用户提供：

```python
result = mgc_get(
    info_type="script",
    info_owner="cleaning_standardize_date",
    action="run",
    ext02=input_data
)
```

---

### 4. 数据分析脚本（用户自有）

分析脚本可在本地使用用户存储于MGC的凭据（AI 不可见）：

```python
result = mgc_get(
    info_type="script",
    info_owner="analysis_monthly_summary",
    action="run"
)
```

---

### 5. 安全交付

支持三种交付方式：

- 本地导出  
- 密封结果（用于协作）  
- 基于各自凭据的访问（团队内部共享）  

所有传输均需用户手动完成，本套件不提供自动传输能力。

---

### 6. 知识管理（分析框架 / 提示词 / 方法论）

用户可将分析框架存入 MGC：

```python
mgc_save(
    info_type="prompt",
    info_owner="framework_monthly_sales",
    content="分析框架内容"
)
```

AI 可在用户授权后读取框架用于分析。

---

## 📌 安全边界（必须遵守）

### 本技能套件提供：

- 本地凭据加密存储  
- 用户自有脚本的零暴露应用  
- 脚本密封与协作授权  
- 分析方法的知识管理  

### 本技能套件不提供：

- ❌ 自动化数据访问  
- ❌ 自动化清洗或分析  
- ❌ 自动化传输  
- ❌ 跨组织数据传输  
- ❌ 脚本生成或修改  

所有脚本必须由用户提供并符合组织政策。

---

## 📌 MCP 工具参考

| 工具 | 说明 |
|------|------|
| mgc_save | 存储凭据、脚本、提示词 |
| mgc_get | 在用户授权后应用脚本 |
| mgc_seal | 密封脚本用于协作 |
| mgc_list | 列出存储项 |
| mgc_open_webui | 打开 MGC WebUI |

---

## 📌 提示词模板（技能套件部分）

位于 `prompts/` 目录：

- `credential_management.md` — 凭据管理工作流  
- `script_management.md` — 脚本管理工作流  
- `knowledge_management.md` — 知识管理工作流  

---

## 📌 Agent 模板（混合形态增强）

本技能套件包含一个可选的 **数据分析师 Agent 系统提示词模板**：

### 📄 agent_system_prompt.md

用于构建一个安全的数据分析 Agent，Agent 将：

- 在每个敏感操作前请求用户授权  
- 在用户授权后通过 MGC 应用脚本  
- 不得查看脚本内容  
- 不得访问凭据  
- 不得自动化执行工作流  
- 不得自动选择脚本名称（info_owner 必须由用户提供）  

### 如何使用 Agent 模板

1. 在创建 Agent 时，将 `agent_system_prompt.md` 作为系统提示词  
2. 配置 MCP 工具：mgc_save / mgc_get / mgc_seal / mgc_list / mgc_open_webui  
3. Agent 可参考 `prompts/` 目录中的提示词执行工作流节点  

Agent 是可选增强，不是必需组件。

---

## 📌 问题排查

| 问题 | 解决方案 |
|------|---------|
| 脚本应用失败 | 检查凭据是否正确存储 |
| 密封失败 | 确保目标节点安装 MGC 1.4.6+ |
| 工作流中断 | 检查是否缺少用户授权 |

---

## 📌 联系方式

- Issues：https://github.com/zkeviny/MGC-Blackbox/issues  
- 邮箱：mirgincipher@outlook.com  

---

## 📌 许可证

MIT License

---

# ⭐ 完整说明

本技能套件用于安全的工作流程管理。  
所有敏感操作均需用户授权。  
本套件不提供任何自动化数据访问能力，所有脚本必须由用户提供并符合组织政策。

---