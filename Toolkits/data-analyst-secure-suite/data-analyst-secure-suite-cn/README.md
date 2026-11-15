# 数据分析师安全技能套件

# 数据分析师安全技能套件  

> **版本**：1.3.0 · **依赖**：MGC Blackbox ≥ 1.5.2

基于 **MGC Blackbox** 的数据分析安全工作流套件，提供 **技能提示词 + Agent 系统提示词模板** 的混合形态，帮助数据分析师在本地安全地管理脚本、工作流、凭据、密封授权协作与知识沉淀。

---

## 本技能套件是什么

本技能套件用于帮助数据分析师在本地安全地完成数据分析相关工作流，包括：

- **数据库凭据安全管理**（零暴露）
- **用户自有脚本与工作流的安全应用**（查询 / 清洗 / 分析）
- **工作流自动识别**（import / from-import / 相对路径 / subprocess 调用链自动路由，1.5.2+）
- **工作流/技能包密封授权协作**（一次一密、节点绑定、不可转卖，1.5.2+）
- **分析方法与提示词的知识管理**（本地加密存储）
- **可选的数据分析 Agent 模板**（自动遵守安全边界）

所有敏感操作均需用户明确授权，本套件不提供任何自动化数据访问能力。

---

## 前置条件

- Python 3.10+
- 安装 MGC Blackbox：  
  ```
  pip install mgc-blackbox>=1.5.2
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

## 目标用户

- 处理敏感业务数据的数据分析师  
- 需要安全脚本协作的团队  
- 需要保护本地数据资产的组织  
- 需要构建安全数据分析 Agent 的用户  

---

## 工作流概述（安全链路）

```
┌──────────────────────────────────────────────────────────┐
│                数据分析安全工作流                         │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  凭据管理 → 数据查询（工作流包） → 数据清洗（同包自动路由）│
│                                                          │
│  → 数据分析 → 结果输出（文件/DB/MGC） → 知识沉淀         │
│                                                          │
│  可选：整个工作流密封给另一个节点（团队/客户）            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

所有脚本均为用户自有脚本，所有应用均在本地通过 MGC 完成，AI 不可见脚本与凭据。

---

## 核心组件说明

### 1. 凭据管理

用户通过 MGC 存储数据库凭据，实现零暴露调用。

**存储凭据：**
```
info_type: "token"
info_owner: "db_connection_name"
content: 加密凭据（用户自有）
```

**在脚本中调用凭据：** 详见 `prompts/credential_management.md`

AI 不可见凭据内容。

---

### 2. 工作流管理

用户将查询、清洗、分析脚本作为工作流文件夹存入 MGC，1.5.2+ 自动识别 import/from-import/相对路径/subprocess 调用关系，运行时密封路由。

**存储工作流：**
```python
mgc_save_file(
    path="./my_analysis",
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)
```

**运行工作流：**
```python
mgc_run(info_owner="monthly_sales_analysis", diff_2="monthly_sales_analysis")
```

也支持单脚本模式（`mgc_save` + `mgc_run`），详见 `prompts/script_management.md`。

---

### 3. 密封授权协作

将工作流或技能包密封授权给其他节点，实现"可用不可读、可运行不可转卖"的跨团队/跨组织协作。

**密封工作流：**
```python
mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04=对方公钥,
)
# → 生成 .mgc_file 加密包
```

**对方接收并运行：**
```python
mgc_save_file(path="./received.mgc_file")
mgc_run(info_owner="monthly_sales_analysis", diff_2="monthly_sales_analysis")
```

支持工作流密封和技能包密封两种模式，详见 `prompts/collaboration_management.md`。

---

### 4. 知识管理

用户将分析框架、提示词模板、方法论存入 MGC。

**存储知识：**
```python
mgc_save(
    info_type="prompt",
    info_owner="framework_monthly_sales",
    content="分析框架内容"
)
```

详见 `prompts/knowledge_management.md`

---

## 安全边界（必须遵守）

### 本技能套件提供：

- 本地凭据加密存储  
- 用户自有脚本的零暴露应用  
- 工作流自动识别与密封路由（import/from-import/相对路径/subprocess，1.5.2+）
- 工作流/技能包密封授权协作（一次一密、节点绑定，1.5.2+）
- 分析方法的知识管理

### 本技能套件不提供：

- 自动化数据访问  
- 自动化清洗或分析  
- 自动化传输  
- 跨组织数据传输  
- 脚本生成或修改  

所有脚本必须由用户提供并符合组织政策。

---

## 反模式与陷阱

### 常见错误做法

| 错误做法 | 风险 | 正确做法 |
|---------|------|---------|
| 在 AI 对话中粘贴凭据内容 | 凭据暴露 | 使用 MGC 存储，脚本内部调用 |
| 让 AI 自动选择脚本名 | 脚本误用风险 | 必须由用户提供 info_owner |
| 未授权就调用凭据 | 违规访问 | 每次访问前请求用户授权 |
| 将脚本内容发给 AI | 脚本暴露 | 通过 MGC 应用，AI 只看结果 |
| 期望套件自动处理数据 | 违反设计原则 | 用户自有脚本，手动触发每一步 |
| 多脚本手动串联传参 | 繁琐易错 | 用 mgc_save_file 存为工作流包，自动识别 import |

---

## 完整使用案例

### 场景：月度销售数据分析

**步骤 1：准备阶段**

用户将凭据和工作流存入 MGC：
- 凭据：`db_sales_prod`（info_type: token）
- 工作流文件夹：`monthly_sales_analysis`（包含 query.py + clean.py + analyze.py）

**步骤 2：工作流程**

```
用户：帮我分析上月销售数据

Agent：
[1] 请求授权：是否运行工作流 monthly_sales_analysis？
用户：yes

[2] MGC 自动识别 import 链，密封路由执行整个工作流
    query → clean → analyze（全自动串联，无需手动传参）

[3] 结果写入指定文件，返回运行状态
```

只需一次授权，MGC 自动串联整个工作流，Agent 无法看到脚本内容或凭据。

---

## MCP 工具参考

| 工具 | 说明 |
|------|------|
| mgc_save | 存储凭据、单脚本、提示词 |
| mgc_save_file | 存储工作流文件夹（自动识别 import/subprocess）|
| mgc_get | 获取值 / 取 node_pub |
| mgc_run | 运行脚本或工作流（黑盒执行）|
| mgc_seal | 密封单个脚本用于协作 |
| mgc_seal_package | 密封整个工作流文件夹 |
| mgc_package | 同信任区内的明文打包 |
| mgc_list | 列出存储项（精确匹配）|
| mgc_find | 按名称模糊搜索条目 |
| mgc_open_webui | 打开 MGC WebUI |

---

## 提示词模板（技能套件部分）

位于 `prompts/` 目录：

- `credential_management.md` — 凭据管理工作流
- `script_management.md` — 工作流与脚本管理
- `collaboration_management.md` — 密封授权协作工作流
- `knowledge_management.md` — 知识管理工作流

---

## Agent 模板（混合形态增强）

本技能套件包含一个可选的 **数据分析师 Agent 系统提示词模板**：

### agent_system_prompt.md

用于构建一个安全的数据分析 Agent，Agent 将：

- 在每个敏感操作前请求用户授权  
- 在用户授权后通过 MGC 应用脚本或工作流  
- 不得查看脚本内容  
- 不得访问凭据  
- 不得自动化执行工作流  
- 不得自动选择脚本名称（info_owner 必须由用户提供）  

### 如何使用 Agent 模板

1. 在创建 Agent 时，将 `agent_system_prompt.md` 作为系统提示词  
2. 配置 MCP 工具：mgc_save / mgc_save_file / mgc_get / mgc_run / mgc_seal / mgc_seal_package / mgc_list / mgc_find / mgc_open_webui  
3. Agent 可参考 `prompts/` 目录中的提示词执行工作流节点  

Agent 是可选增强，不是必需组件。

---

## 问题排查

| 问题 | 解决方案 |
|------|---------|
| 工作流运行失败 | 检查 ext05 中的依赖是否安装 |
| import 找不到模块 | 确保所有脚本在同一个 mgc_save_file 包内 |
| 密封失败 | 检查 ext04 是否为多行 PEM 公钥 |
| 凭据获取失败 | 检查 info_owner 是否一致 |

---

## 联系方式

- Issues：https://github.com/zkeviny/MGC-Blackbox/issues  
- 邮箱：mirgincipher@outlook.com  

---

## 许可证

MIT License

---

## 完整说明

本技能套件用于安全的工作流程管理。  
所有敏感操作均需用户授权。  
本套件不提供任何自动化数据访问能力，所有脚本必须由用户提供并符合组织政策。

---
