---
spec: usk/3.0
id: mgc_task_chain_meta_skill_cn
version: 1.1.0
name: 多Agent安全协作(单设备)
description: 基于 MGC 的单设备多 Agent 任务链协作方法论，通过主 Agent 调度、脚本角色编写、执行 Agent 执行，实现敏感资源零暴露的安全协作。适配 MGC 1.4.10。
author: MirginCipher Team
license: MIT
tags: mgc, 多Agent, 任务链, 安全协作, 零暴露, 本地沙箱, mgc_find
platform_compatibility: windows, macos, linux
changelog:
  - version: 1.1.0
    changes:
      - 升级至适配 MGC 1.4.10
      - 修正 mgc_run ext02 签名：必须为 JSON 数组字符串
      - 新增 mgc_find 模糊搜索工具
      - 补充 ext02 自动解析（1.4.10）
      - 补充 mgc_run 只返回 pid+status 的提示
      - 补充 1.4.9 沙箱模式注意事项
      - 更新 MGC 主技能文档入口为 WebUI 'MGC Skills' 按钮
  - version: 1.0.0
    changes:
      - 初始版本，提供三套提示词模板
---

# 多Agent安全协作(单设备)

---

## 一句话定位

基于 MGC 的单设备多 Agent 任务链协作方法论，通过主 Agent 调度、脚本角色编写、执行 Agent 执行，实现敏感资源零暴露的安全协作。

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

MGC 是 **本地敏感资源托管与执行层**（[skill_spec.md](file:///D:/MirginCipher/mgc/docs/skill_spec.md) §1）：

1. **用户** 通过 WebUI（浏览器或 `mgc_open_webui`）存入密钥和脚本
2. **脚本角色** 编写脚本并通过 `mgc_save` 存入 MGC（MGC 1.4.10 会自动从 `argparse` 解析默认参数到 `ext02`）
3. **主 Agent** 编排任务链，指定调用时机；在子 Agent 失败或用户授权时可直接执行
4. **执行 Agent** 只调用 `mgc_run`，不接触密钥和脚本

### 四种角色

| 角色 | 职责 | 能力 |
|------|------|------|
| 用户 | 存入密钥/脚本，下达目标 | WebUI / `mgc_open_webui` |
| 主 Agent | 任务拆解，编排调度，在授权/子Agent失败时执行 | `mgc_list`, `mgc_find`, `mgc_run` |
| 脚本角色 | 编写脚本，存入 MGC | `mgc_save`, `mgc_list`, `mgc_find` |
| 执行 Agent | 完成非敏感任务 | `mgc_run`, `mgc_list`, `mgc_find` |

> 注：`mgc_get` 获取明文属于敏感操作，需用户授权后执行；脚本角色通常不需要。

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
        (返回 pid+status)
```

---

## 快速开始

### 前置条件

1. 安装 MGC v1.4.9+（建议 1.4.10）：`pip install mgc-blackbox`
2. 启动 MGC：`mgc`（API 端口 57219，WebUI 端口 57218）
3. 配置 MCP（在 AI 客户端添加）：
   ```json
   {
     "mcpServers": {
       "mgc-blackbox": {
         "command": "mgc",
         "args": ["--mcp"],
         "env": { "PYTHONIOENCODING": "utf-8" }
       }
     }
   }
   ```
4. 通过 WebUI 或 `mgc_open_webui` 存入敏感资源：API 密钥、数据库凭证、业务脚本
5. 加载提示词模板到对应 Agent

> **沙箱模式（1.4.9+）**：若运行在沙箱 Agent（Trae Work / Workbuddy）中，建议把 MGC 装在系统环境；否则 MCP 调用可能受限，此种情况请使用 FastAPI 直接调用。

### 步骤 1：配置主 Agent

加载 `prompts/master_agent.md`

### 步骤 2：配置脚本角色

加载 `prompts/script_agent.md`

### 步骤 3：配置执行 Agent

加载 `prompts/executor_agent.md`

### 步骤 4：开始协作

用户下达任务后，主 Agent 自动拆解任务链并协调子 Agent 完成。

---

## 提示词模板

| 文件 | 用途 |
|------|------|
| [prompts/master_agent.md](file:///D:/MirginCipher/Toolkits/task_chain_skills/mgc_task_chain_meta_skill/mgc_task_chain_meta_skill_cn/prompts/master_agent.md) | 主 Agent：任务拆解、调度、`mgc_find` 查找可用脚本 |
| [prompts/script_agent.md](file:///D:/MirginCipher/Toolkits/task_chain_skills/mgc_task_chain_meta_skill/mgc_task_chain_meta_skill_cn/prompts/script_agent.md) | 脚本角色：`mgc_save` 存脚本、`mgc_find` 查重名 |
| [prompts/executor_agent.md](file:///D:/MirginCipher/Toolkits/task_chain_skills/mgc_task_chain_meta_skill/mgc_task_chain_meta_skill_cn/prompts/executor_agent.md) | 执行 Agent：`mgc_run` 执行脚本 |
| [prompts/cooperation_best_practice.md](file:///D:/MirginCipher/Toolkits/task_chain_skills/mgc_task_chain_meta_skill/mgc_task_chain_meta_skill_cn/prompts/cooperation_best_practice.md) | 最佳实践文档，由主 Agent 自动维护 |

---

## MGC 工具使用

### mgc_save（脚本角色使用）

```python
# 存入脚本（ext01 必填；ext02 可选——MGC 1.4.10 会自动从 argparse 解析默认参数）
mgc_save(
    info_type="script",
    info_owner="数据查询脚本",
    ext01="python",
    content="""import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--query', default='default')
args = parser.parse_args()
print(args.query)"""
)
```

### mgc_find（1.4.10 新增，模糊搜索）

> 用于按 info_owner / diff 字段模糊查找可用脚本，**不返回 content 明文**。

```python
# 查找 owner 包含"查询"的脚本
scripts = mgc_find(info_owner="查询", match_mode="substring", limit=50)
# match_mode: substring (%x%) / prefix (x%) / suffix (%x) / exact (x)
```

### mgc_run（执行 Agent 使用，1.4.7+ 黑盒执行）

> ⚠️ **重要（1.4.10 契约）**：`ext02` 必须是 **JSON 数组字符串**，对应脚本 `argparse` 的 argv list。dict 风格 `{"k":"v"}` 不再适用，会触发 422。
>
> **自动解析**：脚本角色存好脚本后 MGC 会自动从 `argparse` 提取默认参数到 `ext02`，执行时省略 `ext02` 即可使用默认值。

```python
import json

# 推荐：用 json.dumps 构造 JSON 数组字符串
params = ["--query", "2026-08-08"]
result = mgc_run(
    info_type="script",              # 必填，类型为 script
    info_owner="数据查询脚本",        # 必填，脚本名称
    diff_1="v1",                     # schema 必填的区分字段；多条同 owner 时消歧，单条时任意非空字符串均可
    ext02=json.dumps(params)         # 可选，JSON 数组字符串：'["--query", "2026-08-08"]'
)
# 返回：{"pid": 12345, "status": "started"}
# 注意：mgc_run 不返回 stdout；如需执行结果，脚本应将结果写入文件并 stdout 输出路径
```

### mgc_list（所有 Agent 可用，精确匹配）

> 注：`mgc_list` 仅查看信息列表，不获取明文。1.4.10 起推荐用 `mgc_find` 进行模糊查找。

```python
# 查看可用脚本
scripts = mgc_list(info_type="script")
```

### mgc_open_webui（用户使用）

> 用于让 AI 打开 MGC WebUI，方便用户存入敏感资源。

```python
mgc_open_webui()
```

---

## ext02 自动解析（1.4.10 重要变更）

MGC 1.4.10 起，存脚本时会**自动解析 `argparse` 字面量 default**，组装成 JSON 数组字符串写入 `ext02`：

```python
# 脚本角色 mgc_save 后，MGC 自动填充 ext02：
# '["--start", "2026-08-08", "--verbose"]'

# 执行 Agent 调用时省略 ext02 即可使用默认值
mgc_run(info_owner="my_script", diff_1="my_script")  # diff_1: any non-empty string works

# 或运行时覆盖
mgc_run(
    info_owner="my_script",
    diff_1="my_script",
    ext02='["--start", "2026-12-25"]'
)
```

**不支持动态 default**（如 `datetime.now()`、`os.path.expanduser("~")`、`f-string`），MGC 会返回 `dynamic_args_detected` warning，提示手动设置 `ext02`。脚本角色应使用字面量 default。

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
2. 执行 Agent 只能调用 `mgc_run`，禁止读取脚本内容
3. 主 Agent 需明确告知子 Agent 调用时机和脚本位置
4. 敏感操作结果返回后，主 Agent 负责更新任务状态，协调子 Agent 协作
5. `ext02` 必须是 JSON 数组字符串（如 `["--flag","value"]`），不要用 dict 风格

---

## 常见问题

| 问题 | 解答 |
|------|------|
| 存入 MGC 的信息是否会同步云端？ | MGC 是本地工具，不具备主动联网能力 |
| MGC 的主要能力？ | 安装 MGC 后，在 WebUI 点击右上角 **MGC Skills** 按钮（1.4.7+）查看主技能文档 |
| 子 Agent 能否绕过 MGC？ | 提示词约束无法完全禁止，需确保子 Agent 无法访问本地脚本文件 |
| 如何隔离不同任务的脚本？ | 通过 `info_owner` 命名区分，如 `任务A_查询脚本`、`任务B_发布脚本` |
| 主 Agent 如何知道有哪些脚本？ | 使用 `mgc_find`（模糊）或 `mgc_list`（精确）查看，或由脚本角色汇报 |
| `mgc_run` 收到 422 怎么办？ | `ext02` 必须为 JSON 数组字符串，用 `json.dumps(["--flag","value"])` 转换 |
| `dynamic_args_detected` warning 如何处理？ | 脚本 default 不能用 `datetime.now()` 等动态表达式，需用字面量或手动传 `ext02` |
| 沙箱模式下 MCP 不可用怎么办？ | 把 MGC 装在系统环境，或改调 FastAPI 直接调用 `/api/mgc/sensitive/run` |

---

## 相关资源

- **MGC 核心仓库**：https://github.com/zkeviny/MGC-Blackbox
- **MGC 安装**：`pip install mgc-blackbox>=1.4.9`
- **WebUI**：http://127.0.0.1:57218
- **API**：http://127.0.0.1:57219
- **MGC 接口鉴权 token**：`~/.mgc/database/mgc_black_box/.mgc_token`
- **问题反馈**：mirgincipher@outlook.com

---

## 更新日志

### v1.1.0

- 升级至适配 MGC 1.4.10
- 修正 `mgc_run` `ext02` 签名：必须为 JSON 数组字符串
- 新增 `mgc_find` 模糊搜索工具
- 补充 `ext02` 自动解析（1.4.10）
- 补充 `mgc_run` 只返回 pid+status 不返回 stdout 的提示
- 补充 1.4.9 沙箱模式注意事项
- 更新 MGC 主技能文档入口为 WebUI "MGC Skills" 按钮

### v1.0.0

- 初始版本
- 提供主 Agent、脚本角色、执行 Agent 三套提示词模板
- 包含完整协作流程说明
