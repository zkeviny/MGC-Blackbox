---
spec: usk/3.0
id: secure_script_runner
version: 1.1.1
name: 脚本安全授权运行（零暴露执行沙箱）
description: 使用 MGC Blackbox 实现脚本零暴露运行。脚本加密存储，黑盒执行，AI 零暴露。支持 MCP (mgc_run) / API / WebUI 执行、内部凭据调用、脚本密封。含 MGC 1.4.9 临时绕行规范。此技能仅在用户明确授权时执行脚本，不会自动执行任何脚本。
author: MirginCipher Team
license: MIT
tags: 安全, 脚本, 零暴露, mgc, 沙箱, 执行, 黑盒执行
platform_compatibility: windows, macos, linux
changelog:
  - version: 1.1.1
    changes:
      - 新增 MGC 1.4.9 临时绕行方案章节（parse_known_args / _strip_quotes / 输出走文件）
      - 补充 ext02 参数格式建议（正斜杠路径、T 替代空格）
      - 提供完整脚本模板
      - 标注已知问题将在后续版本修复
  - version: 1.1.0
    changes:
      - 核心流程升级：使用 mgc_run 黑盒执行脚本（不再暴露脚本给AI）
      - 移除 mgc_get(action="run") 的推荐用法
      - 增加 ext02 参数传递规范
      - 适配 MGC 1.4.9 沙箱模式
  - version: 1.0.1
    changes:
      - 安全修复更新：添加强安全警告、权限边界、脚本来源审查流程
      - 删除危险的安全声明
      - 添加授权要求说明
  - version: 1.0.0
    changes:
      - 初始版本，零暴露脚本执行
---

# 概述

安全脚本运行器是一个文档技能，教授如何使用 MGC Blackbox 实现**脚本零明文暴露**运行。

本技能实现：
- 脚本加密存储于本地 MGC
- **黑盒执行脚本**（AI 仅获结果，无标准输出）
- 多种执行模式：MCP (`mgc_run`, 推荐)、API、WebUI
- 脚本可调用 MGC 内部凭据
- 脚本密封实现跨节点加密授权运行

本技能**仅提供文档说明**，但涉及脚本执行，必须由用户人工批准。

---

# 本技能实现的功能

阅读本文档后，AI 代理将了解如何：

- 在 MGC Blackbox 中安全存储脚本
- 通过 MCP（AI）、API（脚本）或 WebUI（人工）执行脚本
- 使用节点公钥密封脚本
- 构建零暴露工作流

---

# 前置条件

1. **安装 MGC Blackbox**：`pip install mgc-blackbox>=1.4.9`
2. **启动 MGC 服务**：`mgc`（WebUI: http://127.0.0.1:57218, API: http://127.0.0.1:57219）
3. **MCP 工具可用**：`mgc_save`, `mgc_run`, `mgc_list`, `mgc_seal`, `mgc_open_webui`
4. **Token 文件**：`~/.mgc/database/mgc_black_box/.mgc_token`

> **重要提示**：AI 代理请使用 **MCP 工具**。`mgc_run` 是执行脚本的首选，可实现真正的零暴露。

> **沙箱模式 (Trae Work / Workbuddy)**：MGC 1.4.9 引入了沙箱模式。在此模式下，`mgc_run` 执行的脚本在隔离环境中运行，进一步增强安全性。AI 可调用 `mgc_open_webui` 引导用户查看状态。

---

# 零暴露执行

## 核心概念

```
脚本（明文）→ MGC 加密 → 加密存储
                          ↓
              本地执行（MGC）
                          ↓
              AI 仅获执行结果
```

AI 执行但**永不见脚本明文**。

---

## 三种执行模式

| 模式 | 接口 | 适用场景 |
|------|------|----------|
| **MCP (推荐)** | `mgc_run` | AI 代理 (黑盒执行, 零暴露) |
| **REST API** | `/api/mgc/sensitive/run` | 系统脚本 |
| **WebUI** | http://127.0.0.1:57218 | 人工操作 |

> **注意**: `mgc_get(action="run")` 仍可用，但推荐使用 `mgc_run`，因为它明确标记为执行操作，且不暴露执行过程。

---

# 存储脚本

## 步骤 1：准备脚本

存储带执行元数据的脚本：

```python
# 通过 MCP 工具
mgc_save(
    info_type="script",
    info_owner="my_script",
    ext01="python",           # 启动命令 (如 python, python3)
    ext02="",                 # 默认运行时参数 (可选)
    content="print('Hello from zero-exposure!')"
)
```

### 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| info_type | 是 | 必须为 "script" |
| info_owner | 是 | 唯一脚本标识符 |
| ext01 | 是 | 启动命令（python、node 等） |
| ext02 | 否 | 默认运行时参数 |
| content | 是 | 脚本明文（存储时加密） |

---

# 执行脚本

## 模式 1：通过 MCP（AI）- 推荐

使用 `mgc_run` 工具执行：

```python
# 基本执行
result = mgc_run(
    info_owner="my_script"
)

# 带参数执行 (通过 ext02)
import json
params = {"arg1": "value1", "arg2": "value2"}
result = mgc_run(
    info_owner="my_script",
    ext02=json.dumps(params)  # 必须是 JSON 字符串
)
# AI 仅获执行结果
```

> **ext02 参数规范**：
> - `ext02` 用于向脚本传递运行时参数。
> - **必须**使用 `json.dumps()` 将参数对象转换为 JSON 字符串。
> - 否则可能导致 MCP 序列化错误 (HTTP 422)。
> - 脚本内部可以从环境变量或标准输入读取这些参数。

## 模式 2：通过 REST API（脚本）

```bash
# 执行脚本
curl -X POST http://127.0.0.1:57219/api/mgc/sensitive/run \
  -H "Content-Type: application/json" \
  -H "X-MGC-Token: $(cat ~/.mgc/database/mgc_black_box/.mgc_token)" \
  -d '{
    "info_type": "script",
    "info_owner": "my_script",
    "ext02": "{\"arg1\": \"value1\"}"
  }'
```

## 模式 3：通过 WebUI（人工）

1. 打开 WebUI：http://127.0.0.1:57218
2. 进入 Skill 页面
3. 找到脚本
4. 点击 "Run" 按钮

---

# ⚠️ MGC 1.4.9 临时绕行方案（脚本执行规范）

> **重要提示**：MGC 1.4.9 版本在脚本执行时存在已知工程缺陷，可能导致脚本静默失败或无输出。请严格遵循以下脚本编写规范，MGC 团队将在后续版本中彻底修复。

## 脚本编写三条强制规范

### 规范 1：使用 `parse_known_args` 替代 `parse_args`

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--output_dir')
parser.add_argument('--content')
parser.add_argument('--filename')

# ❌ 错误：parse_args() 遇未知参数报错退出
# args = parser.parse_args()

# ✅ 正确：parse_known_args() 忽略额外参数
args, unknown = parser.parse_known_args()
```

### 规范 2：手动去除 MGC 注入的引号

```python
def _strip_quotes(v):
    """去除 MGC 通过 ext02 传递时附加的引号"""
    if isinstance(v, str) and len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v

# 对所有可能含路径或内容的字段调用
args.output_dir = _strip_quotes(args.output_dir)
args.content = _strip_quotes(args.content)
```

### 规范 3：输出走文件，不要大量 print

```python
# ❌ 错误：print() 输出超过 4KB 会导致 PIPE 阻塞
# print(f"处理完成，结果: {result}")

# ✅ 正确：将结果写入文件
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(f"处理完成\n")
    f.write(f"结果: {result}\n")
```

## ext02 参数格式建议

| 规则 | 推荐做法 | 避免做法 |
|------|----------|----------|
| **路径分隔符** | ✅ 正斜杠 `/` (`D:/path`) | ❌ 反斜杠 `\` (`D:\path`) |
| **含空格参数** | ✅ 用 `T` 替代空格 (`2026-07-28T00:00:00`) | ❌ 直接使用空格 |
| **参数结构** | ✅ `--key "value"` 明确指定 | ❌ 位置参数 |

## 完整脚本模板

```python
import argparse
import os
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description='MGC 脚本模板')
    parser.add_argument('--content', default='默认内容')
    parser.add_argument('--output_dir', default=os.path.expanduser("~/Desktop"))
    parser.add_argument('--filename', default=None)

    # 规范 1: 使用 parse_known_args
    args, unknown = parser.parse_known_args()

    # 规范 2: 去除引号
    def _strip_quotes(v):
        if isinstance(v, str) and len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            return v[1:-1]
        return v
    args.content = _strip_quotes(args.content)
    args.output_dir = _strip_quotes(args.output_dir)
    args.filename = _strip_quotes(args.filename)

    # 业务逻辑
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    filename = args.filename or f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    output_file = os.path.join(args.output_dir, filename)

    # 规范 3: 输出走文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"content={args.content}\n")
        f.write(f"output_dir={args.output_dir}\n")

    # 返回执行结果 (简洁)
    print(f"SUCCESS:{output_file}")

if __name__ == "__main__":
    main()
```

> **备注**：以上规范为 MGC 1.4.9 的临时绕行方案，MGC 团队将在后续版本修复 `ext02` 参数解析、`stdout` 阻塞等问题，届时可简化脚本编写。

---

# 调用 MGC 凭据

脚本可使用内部 API 调用 MGC 凭据：

```python
# 示例：从脚本调用 MGC 凭据
import urllib.request
import json

def get_mgc_credential(info_type, info_owner):
    data = json.dumps({
        "info_type": info_type,
        "info_owner": info_owner
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://127.0.0.1:57219/api/mgc/sensitive/get",
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-MGC-Token": open("/path/to/token").read()
        },
        method="POST"
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())["data"]
```

> **注意**：凭据本地获取，脚本本地执行，AI 不接触明文密钥和脚本即可执行。

---

# 脚本密封（高级）

实现跨节点委托时，可使用节点公钥密封脚本：

## 步骤 1：获取节点公钥

```python
# 通过 MCP 工具
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
```

## 步骤 2：密封脚本

```python
# 通过 MCP 工具
sealed = mgc_seal(
    info_type="script",
    info_owner="my_script",
    ext04=node_pub  # 目标节点公钥（也可为当前节点本身公钥）
)
```

## 步骤 3：存储密封脚本

```python
# 存储密封版本
mgc_save(
    info_type="script",
    info_owner="my_script_sealed",
    ext01="python",
    content=sealed
)
```

密封脚本已加密，仅目标节点可执行。

---

# MCP 工具参考

## mgc_save (存储脚本)

**参数：**
```json
{
  "info_type": "script",
  "info_owner": "唯一标识符",
  "ext01": "启动命令 (python, node 等)",
  "ext02": "默认运行时参数 (可选)",
  "content": "脚本明文"
}
```

## mgc_run (执行脚本 - 推荐)

**参数：**
```json
{
  "info_owner": "脚本标识符",
  "ext02": "运行时参数 (JSON 字符串, 可选)"
}
```

**返回：** 脚本执行结果

## mgc_list (列出脚本)

**参数：**
```json
{
  "info_type": "script"
}
```

**返回：** 脚本列表 (不含明文)

## mgc_seal (密封脚本)

**参数：**
```json
{
  "info_type": "script",
  "info_owner": "脚本标识符",
  "ext04": "目标节点 RSA 公钥"
}
```

**返回：** 密封脚本（用目标节点密钥加密）

## mgc_open_webui (打开WebUI)

**用途：** 在浏览器中打开 MGC WebUI，方便用户查看或手动操作。

---

# 安全说明

1. **零暴露**：脚本本地执行，AI 仅获结果（除非用户主动暴露）
2. **加密存储**：所有脚本存储时加密
3. **无明文泄露**：AI 默认不会看到脚本内容
4. **脚本密封**：跨节点脚本保持加密

---

# ⚠️ 安全警告

> **请仔细阅读以下警告**

1. **不要执行不可信脚本**：仅执行来源可信的脚本
2. **AI 无法审查脚本内容**：AI 执行脚本时无法审查代码安全性
3. **脚本可能访问本地凭据**：脚本可调用 MGC 凭据，务必确认脚本用途
4. **用户必须人工确认脚本来源**：执行前必须确认脚本提供者和用途
5. **用户必须承担执行风险**：执行结果由用户自行负责
6. **必须人工批准每一次执行**：AI 不会自动执行，必须用户明确授权

---

# 权限边界

1. 脚本只能访问本地环境
2. 不会访问远程资源（除非脚本本身包含远程调用）
3. 不会自动执行
4. 不会自动调用凭据
5. 所有敏感操作必须由用户触发

---

# 脚本来源审查清单

> **执行脚本前，用户必须确认以下事项：**

- [ ] 确认脚本来源可信
- [ ] 确认脚本用途明确
- [ ] 确认脚本不会访问敏感数据（除非需要）
- [ ] 确认脚本不会执行危险命令（如格式化磁盘等）
- [ ] 用户必须人工批准执行

---

# 相关链接

- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系方式**：mirgincipher@outlook.com