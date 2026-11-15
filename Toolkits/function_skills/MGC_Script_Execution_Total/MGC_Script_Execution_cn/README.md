# 脚本安全运行（零暴露执行沙箱）

使用 MGC Blackbox 实现**脚本零暴露运行**的文档技能。

> **此技能仅在用户明确授权时执行脚本，不会自动执行任何脚本。**

## 本技能是什么

安全脚本运行器教授如何：
- 在 MGC Blackbox 中加密存储脚本
- 本地执行脚本（AI 仅获结果）
- 使用三种执行模式：MCP、API、WebUI
- 从脚本调用 MGC 内部凭据
- 密封脚本实现跨节点委托

## 前置条件

- Python 3.10+
- 安装：`pip install mgc-blackbox`
- 启动 MGC：`mgc`（运行于 http://127.0.0.1:57219）

## 快速开始

### 1. 存储脚本

```python
# 通过 MCP 工具
mgc_save(
    info_type="script",
    info_owner="my_script",
    ext01="python",
    content="print('Hello from zero-exposure!')"
)
```

### 2. 通过 MCP 执行（AI）

```python
result = mgc_get(
    info_type="script",
    info_owner="my_script",
    action="run"
)
# AI 仅获执行结果
```

### 3. 通过 WebUI 执行（人工）

1. 打开：http://127.0.0.1:57218
2. 找到脚本
3. 点击 "Run"

## 三种执行模式

| 模式 | 接口 | 适用场景 |
|------|------|----------|
| MCP | mgc_get | AI 代理 |
| REST API | /api/mgc/sensitive/get | 系统脚本 |
| WebUI | http://127.0.0.1:57218 | 人工操作 |

## ⚠️ 安全警告

> **请仔细阅读以下警告**

1. **不要执行不可信脚本**：仅执行来源可信的脚本
2. **AI 无法审查脚本内容**：AI 执行脚本时无法审查代码安全性
3. **脚本可能访问本地凭据**：脚本可调用 MGC 凭据，务必确认脚本用途
4. **用户必须人工确认脚本来源**：执行前必须确认脚本提供者和用途
5. **用户必须承担执行风险**：执行结果由用户自行负责
6. **必须人工批准每一次执行**：AI 不会自动执行，必须用户明确授权

## 权限边界

- 脚本只能访问本地环境
- 不会访问远程资源（除非脚本本身包含远程调用）
- 不会自动执行
- 不会自动调用凭据
- 所有敏感操作必须由用户触发

## 脚本来源审查清单

> **执行脚本前，用户必须确认以下事项：**

- [ ] 确认脚本来源可信
- [ ] 确认脚本用途明确
- [ ] 确认脚本不会访问敏感数据（除非需要）
- [ ] 确认脚本不会执行危险命令（如格式化磁盘等）
- [ ] 用户必须人工批准执行

## MCP 工具

| 工具 | 说明 |
|------|------|
| mgc_save | 加密存储脚本 |
| mgc_get | 获取或执行脚本 |
| mgc_seal | 密封脚本用于委托 |
| mgc_list | 列出存储的脚本 |
| mgc_open_webui | 打开 WebUI |

## 支持平台

- Windows
- macOS
- Linux

## 相关链接

- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系方式**：mirgincipher@outlook.com