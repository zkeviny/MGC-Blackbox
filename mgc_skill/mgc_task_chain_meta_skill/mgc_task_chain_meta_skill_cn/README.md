# 多Agent安全协作(单设备)
**Multi-Agent Safe-Cooperation (Single Device)**

基于 MGC 的单设备多 Agent 任务链协作方法论，实现敏感资源零暴露的安全协作。

---

## 什么是 MGC 安全协作

在单设备上部署多个 Agent 协作完成任务时，传统方式存在以下问题：

- 所有 Agent 共享环境，密钥易泄露
- 脚本内容暴露给所有 Agent
- 缺乏任务协作方法

MGC 安全协作通过以下方式解决：

1. **敏感资源托管**：密钥、脚本、数据存入 MGC，Agent 无接触执行
2. **任务链编排**：指导主 Agent 拆解任务并分配给子 Agent
3. **执行零暴露**：执行 Agent 只调用 mgc_run，由mgc黑盒执行，不接触密钥

---

## 角色分工

| 角色 | 职责 | 工具 |
|------|------|------|
| 用户 | 存入密钥/脚本，下达目标 | WebUI / mgc_open_webui |
| 主 Agent | 任务拆解，编排调度 | mgc_list, mgc_run |
| 脚本角色 | 编写脚本，存入 MGC | mgc_save, mgc_get, mgc_list |
| 执行 Agent | 完成非敏感任务 | mgc_run, mgc_list |

> 注：敏感操作（mgc_get 获取明文）需要用户授权后执行

---

## 快速开始

### 1. 安装 MGC

```bash
pip install mgc-blackbox
```

### 2. 启动 MGC

```bash
mgc
```

- WebUI: http://127.0.0.1:57218
- API: http://127.0.0.1:57219

### 3. 配置 MCP（让 AI 能调用 MGC）

在 AI 客户端（如 TRAE）的 MCP 配置中添加：

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

### 4. 存入敏感资源

通过 WebUI 存入：
- API 密钥
- 数据库凭证
- 业务脚本

### 5. 配置 Agent 提示词

加载 `prompts/` 目录下的提示词模板：
- `master_agent.md` → 主 Agent
- `script_agent.md` → 脚本角色
- `executor_agent.md` → 执行 Agent

### 6. 开始协作

用户下达任务后，主 Agent 自动拆解任务链并协调子 Agent 完成。

---

## 协作流程图

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

## 提示词模板说明

### 主 Agent (master_agent.md)

- 任务拆解方法
- MGC 调用时机
- 子任务分配规则

### 脚本角色 (script_agent.md)

- mgc_save 使用方法
- 脚本命名规范
- 脚本位置汇报格式

### 执行 Agent (executor_agent.md)

- mgc_run 调用方法
- 禁止行为清单
- 结果处理规范

---

## 常见问题

**Q: 子 Agent 能否绕过 MGC？**
A: 提示词约束无法完全禁止，需确保子 Agent 无法访问本地脚本文件，或使用mgc_seal密封脚本，密封后的脚本只能在mgc内部运行，无法解密和查看明文。

**Q: 如何隔离不同任务的脚本？**
A: 通过 info_owner 命名区分，如 `任务A_查询脚本`、`任务B_发布脚本`。

**Q: 主 Agent 如何知道有哪些脚本？**
A: 使用 mgc_list 查看，或由脚本角色汇报，历史高复用脚本建议更新到“cooperation_best_practice.md”方便管理查看，节省token。

**Q: 如何让 AI 打开 WebUI？**
A: 使用 `mgc_open_webui()` 工具，AI 会自动打开浏览器访问 MGC WebUI。

---

## MGC 工具说明

| 工具 | 用途 |
|------|------|
| mgc_save | 存入脚本 |
| mgc_run | 执行脚本 |
| mgc_list | 查看脚本列表 |
| mgc_seal | 密封脚本（可执行） |
| mgc_open_webui | 打开 WebUI |

---

## 相关资源

- [MGC 核心仓库](https://github.com/zkeviny/MGC-Blackbox)
- [MGC 安装指南](#)
- 问题反馈: mirgincipher@outlook.com
