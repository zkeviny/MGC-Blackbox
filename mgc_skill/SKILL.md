spec: usk/3.0  
id: data-analyst-secure-suite  
version: 1.1.0  
name: 数据分析师安全技能套件  
description: 基于 MGC Blackbox 的数据分析安全工作流套件，提供凭据保护、零暴露脚本应用、脚本密封协作和知识管理。同时包含一个数据分析师 Agent 系统提示词模板。  
author: MirginCipher Team  
license: MIT  
tags: 安全, 数据分析, mgc, 零暴露, 本地沙箱, 凭据管理, 脚本管理, 知识管理, Agent 模板  
platform_compatibility: windows, macos, linux  
changelog:
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

**数据分析师安全技能套件**是一个基于 **MGC Blackbox** 的文档技能套件，用于帮助数据分析师在本地安全地管理：

- 敏感凭据  
- 用户自有脚本  
- 跨团队协作授权  
- 分析框架与知识沉淀  

本套件采用 **混合形态设计**：

- **技能提示词（prompts/）**：提供凭据管理、脚本管理、知识管理三大核心能力  
- **Agent 系统提示词模板（agent_system_prompt.md）**：用于构建遵守严格安全边界的数据分析 Agent  

所有敏感操作均需用户明确授权，本套件不提供任何自动化数据访问能力。

---

# 适用场景

本技能套件适用于：

- 企业内部数据分析  
- 需要保护敏感数据的场景  
- 需要安全共享脚本的团队协作  
- 供应商脚本的安全使用  
- 构建安全数据分析 Agent  
- 构建知识沉淀体系（可搭配 Self-Improving Agent）  

---

# 前置条件

1. 安装 MGC Blackbox：  
   ```
   pip install mgc-blackbox
   ```
2. 启动 MGC 服务：  
   ```
   mgc
   ```
3. MCP 工具可用：mgc_save, mgc_get, mgc_seal, mgc_list, mgc_open_webui  
4. Token 文件：`~/.mgc/database/mgc_black_box/.mgc_token`

---

# 核心能力

## 1. 凭据管理（credential_management.md）

用于安全管理数据库密钥、API Token 等敏感凭据。

### 适用场景
- 需要连接数据库或外部服务  
- 脚本需要安全调用凭据  
- 团队成员需要共享访问权限（非共享数据）  

### 能力说明
- 本地加密存储  
- AI 无法看到凭据内容  
- 脚本可零暴露调用凭据  
- 所有访问必须由用户授权  

### Agent 如何使用
Agent 在用户授权后可读取凭据，但永不看到明文。

---

## 2. 脚本管理（script_management.md）

用于管理用户自有的查询脚本、清洗脚本、分析脚本等。

### 适用场景
- 用户需要应用自己的脚本  
- 脚本需要安全调用凭据  
- 脚本需要跨团队协作（密封）  
- 需要构建完整的数据分析链路（查询 → 清洗 → 分析）  

### 能力说明
- 脚本加密存储  
- AI 不可见脚本内容  
- 脚本可零暴露调用凭据  
- 支持脚本密封协作  
- 所有应用必须由用户授权  

### Agent 如何使用
Agent 在用户授权后通过 MGC 应用脚本，并可在多步骤工作流中逐步请求授权。

---

## 3. 知识管理（knowledge_management.md）

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
- 脚本密封与协作授权  
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
    ├── script_management.md        # 脚本管理
    └── knowledge_management.md     # 知识管理
```

---

# 使用方式

## 方式一：作为技能使用（Skill Mode）

AI 可读取 prompts/ 目录中的三个核心文档：

| 文档 | 使用场景 | 由谁触发 |
|------|----------|----------|
| credential_management.md | 需要存储或访问凭据 | 用户或 Agent |
| script_management.md | 需要存储或应用脚本 | 用户或 Agent |
| knowledge_management.md | 需要存储或读取知识 | 用户或 Agent |

AI 会根据用户请求引用对应文档，并在每个敏感操作前请求授权。

---

## 方式二：作为 Agent 模板（Agent Mode）

将 `agent_system_prompt.md` 作为系统提示词配置给 AI Agent。

Agent 将自动遵守以下安全边界：

- 在每个敏感操作前请求用户授权  
- 仅通过 MGC Blackbox 应用脚本  
- 不得查看脚本内容或凭据  
- 不得自动化执行工作流  
- 不得自动选择脚本名称（info_owner 必须由用户提供）  

Agent 可在用户授权后引用 prompts/ 中的文档作为工作流指导。

---

# MCP 工具参考

| 工具 | 说明 | 授权要求 |
|------|------|---------|
| mgc_save | 存储凭据、脚本、提示词 | 是 |
| mgc_get | 获取或应用脚本 | 是 |
| mgc_seal | 密封脚本用于协作 | 是 |
| mgc_list | 列出存储项 | 可选 |
| mgc_open_webui | 打开 MGC WebUI | 否 |

---

# 安全说明

1. **零暴露**：脚本与凭据在本地执行，AI 仅接收结果  
2. **加密存储**：所有内容加密存储  
3. **无明文泄露**：AI 永不看到脚本或凭据内容  
4. **脚本密封**：跨节点协作保持加密  

---

# 联系方式

- 问题反馈：https://github.com/zkeviny/MGC-Blackbox/issues  
- 邮箱：mirgincipher@outlook.com  

---

> **提醒**：本技能套件用于安全的工作流程管理。所有敏感操作必须获得用户明确授权。所有脚本均为用户自有，所有执行均在本地通过 MGC Blackbox 完成。

---