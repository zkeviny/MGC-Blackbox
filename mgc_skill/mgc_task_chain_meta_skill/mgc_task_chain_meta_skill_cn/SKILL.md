---
spec: usk/3.0
id: mgc_task_chain_meta_skill_cn
version: 1.0.0
name: 多Agent安全协作(单设备)
description: 基于 MGC 的单设备多 Agent 任务链协作方法论，通过主 Agent 调度、脚本角色编写、执行 Agent 执行，实现敏感资源零暴露的安全协作。
author: MirginCipher Team
license: MIT
tags: mgc, 多Agent, 任务链, 安全协作, 零暴露, 本地沙箱
platform_compatibility: windows, macos, linux
changelog:
  - version: 1.0.0
    changes:
      - 初始版本
      - 提供主 Agent、脚本角色、执行 Agent 三套提示词模板
      - 包含完整协作流程说明
---

# 多Agent安全协作(单设备)

---

## 一句话定位

基于 MGC 的单设备多 Agent 任务链协作方法论，通过主 Agent 调度、脚本角色编写、 执行 Agent 执行，实现敏感资源零暴露的安全协作。

---

## 解决的问题

| 痛点 | 解决方案 |
|------|---------|
| 多 Agent 共用环境，密钥易泄露 | 密钥存入 MGC，Agent 无接触执行 |
| 脚本内容暴露给所有 Agent | 脚本存入 MGC，执行时零暴露 |
| 缺乏任务协作方法 | 主 Agent 任务链编排模板 |
| 子 Agent 越权访问敏感资源 | 执行 Agent 提示词约束 |

---

## 核心概念

### MGC 在协作中的角色

MGC 是 **本地敏感资源托管与执行层**：

1. **用户** 通过 WebUI（浏览器或 mgc_open_webui）存入密钥和脚本
2. **脚本角色** 编写脚本并通过 mgc_save 存入 MGC
3. **主 Agent** 编排任务链，指定调用时机；在子 Agent 失败或用户授权时可直接执行
4. **执行 Agent** 只调用 mgc_run，不接触密钥和脚本

### 四种角色

| 角色 | 职责 | 能力 |
|------|------|------|
| 用户 | 存入密钥/脚本，下达目标 | WebUI / mgc_open_webui |
| 主 Agent | 任务拆解，编排调度，在授权/子Agent失败时执行 | mgc_list, mgc_run |
| 脚本角色 | 编写脚本，存入 MGC | mgc_save, mgc_get, mgc_list |
| 执行 Agent | 完成非敏感任务 | mgc_run, mgc_list |

> 注：敏感操作（mgc_get 获取明文）需要用户授权后执行

---

## 协作流程

```
用户 ──存入密钥/脚本(WebUI)──> MGC
                │
                ▼
用户 ──下达目标──> 主 Agent
                │
                ├──拆解任务链
                │
                ▼
        ┌───────┴───────┐
        ▼               ▼
   脚本角色          执行 Agent
   (编写脚本)        (完成任务)
        │               │
        ▼               ▼
   mgc_save         mgc_run
        │               │
        └───────┬───────┘
                ▼
           MGC 执行
        (返回结果)
```

---

## 快速开始

### 前置条件

1. 安装 MGC v1.4.7+
2. 配置 MCP（在 AI 客户端添加以下配置）：
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
3. 通过 WebUI 或 mgc_open_webui 存入敏感资源：
   - API 密钥
   - 数据库凭证
   - 业务脚本

### 步骤 2：配置主 Agent

在主 Agent 系统提示词中加载 `prompts/master_agent.md`

### 步骤 3：配置脚本角色

加载 `prompts/script_agent.md`

### 步骤 4：配置执行 Agent

加载 `prompts/executor_agent.md`

### 步骤 5：开始协作

用户下达任务后，主 Agent 自动拆解任务链并协调子 Agent 完成。

---

## 提示词模板

### prompts/master_agent.md

主 Agent 提示词模板，包含：
- 任务拆解方法
- MGC 调用时机
- 子任务分配规则

### prompts/script_agent.md

脚本角色提示词模板，包含：
- mgc_save 使用方法
- 脚本命名规范
- 脚本位置汇报格式

### prompts/executor_agent.md

执行 Agent 提示词模板，包含：
- mgc_run 调用方法
- 禁止行为清单
- 结果处理规范

### prompts/cooperation_best_practice.md

最佳实践文档，由主 Agent 自动维护：
- 协作流程
- 可复用脚本列表
- 参数规范
- 用户偏好
- 常见错误与修复
- 场景最佳实践
- 协作记录及用户反馈

---

## MGC 工具使用

### mgc_save（脚本角色使用）

```python
# 存入脚本
mgc_save(
    info_type="script",
    info_owner="数据查询脚本",
    ext01="python",
    content="""# 脚本内容..."""
)
```

### mgc_run（执行 Agent 使用）

> ⚠️ 注意：部分 MCP 客户端可能存在 ext02 JSON 对象序列化的兼容性问题，建议使用 JSON 字符串格式。

```python
# 执行脚本
mgc_run(
    info_type="script",      # 必填，指定类型为脚本
    info_owner="数据查询脚本",  # 必填，脚本名称
    diff_1="v1",             # 必填，版本号或分支标识
    ext02='{"param1": "value1"}'  # 可选，JSON 字符串格式的执行参数
)
```

### mgc_list（所有 Agent 可用）

> 注：mgc_list 仅查看信息列表，不获取明文，所有 Agent 都可使用。

```python
# 查看可用脚本
mgc_list(info_type="script")
```

### mgc_open_webui（用户使用）

> 用于让 AI 打开 MGC WebUI，方便用户存入敏感资源。

```python
# 打开 WebUI
mgc_open_webui()
```

---

## 安全边界

### 此技能提供

- 协作方法论框架
- 提示词模板
- MGC 工具调用规范

### 此技能不提供

- MGC 权限强制管控（依赖提示词约束）
- 自动密钥管理
- Agent 身份鉴权

### ⚠️ 重要提醒

1. 所有敏感资源必须用户通过 MGC WebUI 存入
2. 执行 Agent 只能调用 mgc_run，禁止读取脚本内容
3. 主 Agent 需明确告知子 Agent 调用时机和脚本位置
4. 敏感操作结果返回后，主 Agent 负责更新任务状态，协调子Agent协作

---

## 常见问题

| 问题 | 解答 |
|------|------|
| 存入MGC的信息是否会同步云端？ | MGC是一个本地工具，不具备主动联网能力 |
| MGC的主要能力？ | 安装MGC后查看 ~/.mgc/skills/mgc_skill.md |
| 子 Agent 能否绕过 MGC？ | 提示词约束无法完全禁止，需确保子 Agent 无法访问本地脚本文件 |
| 如何隔离不同任务的脚本？ | 通过 info_owner 命名区分，如 `任务A_查询脚本`、`任务B_发布脚本` |
| 主 Agent 如何知道有哪些脚本？ | 使用 mgc_list 查看，或由脚本角色汇报 |

---

## 相关资源

- **MGC 核心仓库**: https://github.com/zkeviny/MGC-Blackbox
- **MGC 安装**: `pip install mgc-blackbox`
- **WebUI**: http://127.0.0.1:57218
- **API**: http://127.0.0.1:57219
- **MGC接口鉴权token**：~/.mgc/database/mgc_black_box/.mgc_token
- **问题反馈**: mirgincipher@outlook.com

---

## 更新日志

### v1.0.0

- 初始版本
- 提供主 Agent、脚本角色、执行 Agent 三套提示词模板
- 包含完整协作流程说明
