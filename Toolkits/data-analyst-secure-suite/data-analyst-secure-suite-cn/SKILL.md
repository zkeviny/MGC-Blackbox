---
spec: usk/3.0  
id: data-analyst-secure-suite  
version: 1.5.0  
name: 数据分析师安全技能套件  
description: 基于 MGC Blackbox 1.6.0+ 的数据分析安全工作流套件，提供凭据保护、零暴露脚本与工作流应用、工作流/技能包密封授权协作和知识管理。支持 1.5.4 双层加密与链路授权、free 模式，以及 1.6.0 新增的 chain mode 多节点密封分发（一次密封产出多个独立子包 + distribution_index.json），包含数据分析师 Agent 系统提示词模板。  
author: MirginCipher Team
license: MIT
tags: 安全, 数据分析, mgc, 零暴露, 本地沙箱, 凭据管理, 工作流管理, 密封授权协作, 知识管理, Agent 模板, 模糊搜索, 工作流自动识别, 密封跨脚本
platform_compatibility: windows, macos, linux  
requires:
  mgc_blackbox: ">=1.6.0"
changelog:
  - version: 1.5.0
    changes:
      - 升级适配 MGC 1.6.0：新增 chain mode 多节点密封分发，一次密封产出 N 个独立子包
      - collaboration_management.md 新增 3.3 节：target 数组、distribution_index.json、子包结构与接收方核对流程
      - 补充 chain mode 硬约束：只支持平级目录、files 必须与 diff_3 一致、files 只放脚本（数据与凭证不出域）、运行期 UNSEAL_FAILED 的成因
      - 同步英文版 1.4.0 基线：双层加密与 ext07 / ext09 链路授权、free 模式、mgc_delete 与 mgc_skill 工具
      - MCP 工具列表补齐至 12 个，与英文版对齐
      - 全文版本声明统一为 MGC Blackbox 1.6.0+
  - version: 1.3.0
    changes:
      - 升级适配 MGC 1.5.2+：新增 mgc_save_file（工作流文件夹存储）、mgc_seal_package（工作流密封）、mgc_package（明文打包）
      - 脚本管理重构：从单脚本管理升级为工作流管理模式，支持 import/subprocess 自动识别
      - 凭据管理：info_type 从 "credential" 统一为 "token"，与 skill_spec 对齐
      - 新增 prompts/collaboration_management.md：工作流/技能包密封授权协作专项文档
      - Agent 模板：工作流示例从 5 步手动串联升级为 find → save_file → run 模式
      - 新增工作流密封协作章节（mgc_seal_package 一键密封整个工作流）
      - 新增可识别跨脚本写法对照表（from-import / import / Path / subprocess）
      - MCP 工具列表扩展至 10 个（新增 mgc_save_file、mgc_seal_package、mgc_package）
  - version: 1.2.0
    changes:
      - 同步 MGC Blackbox 1.4.10：在 MCP 工具列表中添加 mgc_find（模糊搜索）和 mgc_run（推荐代替 mgc_get action=run）。
      - 脚本管理：将示例中的 mgc_get(action='run') 替换为独立的 mgc_run 工具。
      - 脚本管理：新增 mgc_find 模糊搜索工作流。
      - 脚本密封：明确 ext04 必须是多行 PEM 公钥。
      - 凭据管理：新增 mgc_find 模糊搜索工作流。
      - 知识管理：新增 mgc_find 模糊搜索工作流。
      - Agent 系统提示词：记录 find -> get/run 工作流模式。
  - version: 1.1.1
    changes:
      - 根据评测报告优化文档结构
      - 新增"反模式与陷阱"章节
      - 新增"完整使用案例"章节
      - 统一引用 prompts 文件名
  - version: 1.1.0
    changes:
      - 整合 prompts 结构为凭据管理、脚本管理、知识管理三大核心模块
      - 新增 agent_system_prompt.md 作为数据分析 Agent 系统提示词模板
      - 增强文档结构，明确各模块的适用场景与调用方式
  - version: 1.0.0
    changes:
      - 初始版本
---

# 概述

**数据分析师安全技能套件**是一个基于 **MGC Blackbox 1.6.0+** 的文档技能套件，用于帮助数据分析师在本地安全地管理：

- 敏感凭据  
- 用户自有脚本与工作流  
- 工作流/技能包密封授权协作  
- 分析框架与知识沉淀  

本套件采用 **混合形态设计**：

- **技能提示词（prompts/）**：提供凭据管理、工作流管理、密封授权协作、知识管理四大核心能力  
- **Agent 系统提示词模板（agent_system_prompt.md）**：用于构建遵守严格安全边界的数据分析 Agent  

所有敏感操作均需用户明确授权，本套件不提供任何自动化数据访问能力。

---

# 适用场景

本技能套件适用于：

- 企业内部数据分析  
- 需要保护敏感数据的场景  
- 需要安全共享脚本/工作流的团队协作  
- 供应商脚本的安全使用  
- 构建安全数据分析 Agent  
- 构建知识沉淀体系（可搭配 Self-Improving Agent）  

---

# 前置条件

1. 安装 MGC Blackbox（>=1.6.0）：  
   ```
   pip install mgc-blackbox>=1.6.0
   ```
2. 启动 MGC 服务：  
   ```
   mgc
   ```
3. MCP 工具可用：mgc_save, mgc_save_file, mgc_get, mgc_run, mgc_seal, mgc_seal_package, mgc_package, mgc_list, mgc_find, mgc_open_webui  
4. Token 文件：`~/.mgc/database/mgc_black_box/.mgc_token`

---

# 核心能力

## 1. 凭据管理（credential_management.md）

用于安全管理数据库密钥、API Token 等敏感凭据。

### 适用场景
- 需要连接数据库或外部服务  
- 脚本需要安全调用凭据  
- 团队成员共享数据库/服务的**访问权限**（不共享数据本身）
- 团队内/外部共享**数据分析方法与脚本**（通过工作流密封授权）

### 能力说明
- 本地加密存储  
- AI 无法看到凭据内容  
- 脚本可零暴露调用凭据  
- 所有访问必须由用户授权  

### Agent 如何使用
Agent 在用户授权后可读取凭据，但永不看到明文。

---

## 2. 工作流管理（script_management.md）

用于管理用户自有的查询脚本、清洗脚本、分析脚本等，支持单脚本和工作流文件夹两种模式。

### 适用场景
- 用户需要应用自己的脚本或工作流  
- 脚本需要安全调用凭据  
- 多脚本工作流需要自动识别 import/subprocess 调用关系（1.5.1+）  
- 工作流需要跨团队协作（密封）  
- 需要构建完整的数据分析链路（查询 → 清洗 → 分析）  

### 能力说明
- 单脚本加密存储（mgc_save）  
- 工作流文件夹加密存储，自动识别 import/subprocess（mgc_save_file，1.5.1+）  
- AI 不可见脚本内容  
- 脚本可零暴露调用凭据  
- 支持单脚本密封（mgc_seal）和工作流密封（mgc_seal_package）  
- 所有应用必须由用户授权  

### Agent 如何使用
Agent 在用户授权后通过 MGC 运行脚本或工作流。工作流模式下，MGC 自动识别 import 链，无需手动传参串联。

---

## 3. 密封授权协作（collaboration_management.md）

用于将工作流和技能包密封授权给其他节点，实现"可用不可读、可运行不可转卖"的跨团队/跨组织协作。

### 适用场景
- 数据团队把分析工作流密封给业务团队（只允许运行，不允许看源码）
- 乙方分析师把分析方案密封交付给客户
- 跨部门共享分析方法论但保护核心逻辑
- 给多个客户分别独立授权

### 能力说明
- 工作流密封（mgc_seal_package）：整个工作流一次性密封，AES-256加密
- 技能包密封：密封带 SKILL.md 的完整技能包，对方 AI 可读说明但不可见源码
- 节点绑定：AES 密钥绑定目标节点 RSA 公钥，无法转封给第三方
- 一次一密：每个客户独立密封，互不影响
- 无云端：全部加密/解密/运行在本地完成
- 多节点分发（`chain mode`，1.6.0+）：`mgc_seal_package` 的 `ext04` 传 target 数组，一次密封产出每个目标节点各自独立的子包，并生成 `distribution_index.json` 供分发与校验
- chain mode 下 targets 的 `files` 只放脚本；数据与凭证留在各节点本地 MGC，由脚本运行时通过 REST API 读取

### Agent 如何使用
Agent 在用户授权后执行密封操作。密封包由用户手动传输，Agent 不参与传输过程。

---

## 4. 知识管理（knowledge_management.md）

用于管理分析框架、提示词模板、方法论、业务规则等知识资产。

### 适用场景
- 构建标准化分析框架  
- 复用提示词模板  
- 团队共享分析方法  
- 构建知识沉淀体系  
- 搭配 Self-Improving Agent 自动沉淀知识  

### 能力说明
- 知识内容加密存储  
- AI 可在用户授权后读取知识  
- 支持知识密封协作  
- 可用于构建分析报告结构  

### Agent 如何使用
Agent 在用户授权后可读取知识，并用于指导分析结构或生成提示词。

---

# 安全边界

## 本技能套件提供

- 本地凭据加密存储
- 用户自有脚本的零暴露应用
- 工作流自动识别与密封路由（1.5.2+，含 subprocess 字面量列表运行时路由）
- 工作流/技能包密封授权协作（1.5.2+；1.6.0+ 支持 chain mode 多节点分发）
- 产物完整性校验：链路授权 + `distribution_index.json` 的 sha256
- 知识加密管理  

## 本技能套件不提供

- 自动化数据访问  
- 自动化清洗或分析  
- 自动化传输  
- 脚本生成或修改  

所有脚本必须由用户提供并符合组织政策。

---

# 文件结构

```
data-analyst-secure-suite/
├── SKILL.md                    # 主文档（本文件）
├── README.md                   # 详细使用说明
├── manifest.json               # 技能元数据
├── agent_system_prompt.md      # Agent 系统提示词模板
└── prompts/
    ├── credential_management.md    # 凭据管理
    ├── script_management.md        # 工作流与脚本管理
    ├── collaboration_management.md # 密封授权协作
    └── knowledge_management.md     # 知识管理
```

---

# 使用方式

## 方式一：作为技能使用（Skill Mode）

AI 可读取 prompts/ 目录中的四个核心文档：

| 文档 | 使用场景 | 由谁触发 |
|------|----------|----------|
| credential_management.md | 需要存储或访问凭据 | 用户或 Agent |
| script_management.md | 需要存储或运行脚本/工作流 | 用户或 Agent |
| collaboration_management.md | 需要密封工作流/技能包给其他节点 | 用户或 Agent |
| knowledge_management.md | 需要存储或读取知识 | 用户或 Agent |

AI 会根据用户请求引用对应文档，并在每个敏感操作前请求授权。

---

## 方式二：作为 Agent 模板（Agent Mode）

将 `agent_system_prompt.md` 作为系统提示词配置给 AI Agent。

Agent 将自动遵守以下安全边界：

- 在每个敏感操作前请求用户授权  
- 仅通过 MGC Blackbox 应用脚本或工作流  
- 不得查看脚本内容或凭据  
- 不得自动化执行工作流  
- 不得自动选择脚本名称（info_owner 必须由用户提供）  

Agent 可在用户授权后引用 prompts/ 中的文档作为工作流指导。

---

# MCP 工具参考

| 工具 | 说明 | 授权要求 |
|------|------|---------|
| mgc_save | 存储凭据、单脚本、提示词 | 是 |
| mgc_save_file | 存储工作流文件夹（自动识别 import/subprocess）| 是 |
| mgc_get | 获取值 / 取 node_pub | 是 |
| mgc_run | 运行脚本或工作流（黑盒执行）| 是 |
| mgc_seal | 密封单个脚本用于协作 | 是 |
| mgc_seal_package | 密封工作流文件夹；`ext04` 传 target 数组即为 chain mode 多节点分发 | 是 |
| mgc_package | 同信任区内的明文打包 | 是 |
| mgc_delete | 删除存储项 | 是 |
| mgc_list | 列出存储项（精确匹配）| 可选 |
| mgc_find | 按名称模糊搜索条目 | 可选 |
| mgc_skill | 读取技能说明 | 否 |
| mgc_open_webui | 打开 MGC WebUI | 否 |

---

# 安全说明

1. **零暴露**：脚本与凭据在本地执行，AI 仅接收运行状态  
2. **加密存储**：所有内容加密存储  
3. **无明文泄露**：AI 永不看到脚本或凭据内容  
4. **工作流自动识别**：import/from-import/相对路径/subprocess 调用链自动路由，磁盘无文件落盘（1.5.2+）
5. **工作流/技能包密封**：整个工作流或技能包一次性密封给目标节点，节点绑定，不可转售（1.5.2+）
6. **多节点 chain mode**：一次密封产出多个独立子包，每个子包只对目标节点可解；`distribution_index.json` 记录 `granted_files` 与 `sha256`，运行期解封失败报 `UNSEAL_FAILED`（1.6.0+）
7. **加密边界**：MGC 只加密脚本文件；CSV / JSON / 配置文件在密封包内为明文。因此 `files` 只放脚本，数据与凭证留在本地 MGC

---

# 联系方式

- 问题反馈：https://github.com/zkeviny/MGC-Blackbox/issues  
- 邮箱：mirgincipher@outlook.com  

---

> **提醒**：本技能套件用于安全的工作流程管理。所有敏感操作必须获得用户明确授权。所有脚本均为用户自有，所有执行均在本地通过 MGC Blackbox 完成。

---
