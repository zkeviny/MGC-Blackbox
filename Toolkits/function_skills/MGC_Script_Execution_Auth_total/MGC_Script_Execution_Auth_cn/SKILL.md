---
spec: usk/3.0
id: cross_node_script_auth
version: 1.1.0
name: 脚本跨设备加密授权（零暴露）
description: 使用 MGC Blackbox 密封功能实现零暴露跨设备脚本授权。脚本使用目标节点 RSA 公钥加密，以密文形式传输，仅在授权节点执行时解密。适配 MGC 1.4.10，使用 mgc_run 黑盒执行、ext02 自动解析等最新能力。
author: MirginCipher Team
license: MIT
tags: 安全, 跨设备, 加密, 零暴露, mgc, 授权, 密封, RSA, 黑盒执行
platform_compatibility: windows, macos, linux
changelog:
  - version: 1.1.0
    changes:
      - 升级至适配 MGC 1.4.10
      - 执行密封脚本改用 mgc_run（1.4.7+）替代 mgc_get(action=run)
      - 补充 ext02 自动解析（1.4.10）：密封时 argparse 默认参数会打包到 ext_02
      - 修正 mgc_seal 必填参数：info_type 改为可选，ext04 必须为多行 PEM
      - 新增 mgc_find 模糊搜索工具
      - WebUI 获取 node_pub 流程更新：Settings → Node Public Key 可直接查看
      - 新增 update_if_exists 覆盖同名脚本
      - 新增 1.4.9 沙箱模式简要提示
  - version: 1.0.1
    changes:
      - 明确 node_pub 懒生成机制的差异（MCP/API vs WebUI）
  - version: 1.0.0
    changes:
      - 初始版本，跨设备加密脚本授权
---

# 概述

脚本跨设备加密授权是一个文档技能，教授如何**跨设备授权脚本执行而不暴露明文**。

本技能实现：
- 使用目标节点 RSA 公钥密封脚本
- 将加密脚本安全传输给授权节点
- 在授权节点以**黑盒执行**方式运行密封脚本
- 构建跨设备信任链

本技能**不包含可执行代码**，自动审批安全。

---

# 本技能实现的功能

阅读本文档后，AI 代理将了解如何：

- 获取目标节点 RSA 公钥（`__NODE_PUB__`）
- 使用 `mgc_seal` 密封脚本（包含自动提取的默认参数）
- 安全传输密封包到目标节点
- 在目标节点存储密封脚本（同时存入 `ext03` RSA 包裹的 AES key 与 `ext02` 默认参数）
- 使用 `mgc_run`（1.4.7+）以黑盒方式执行密封脚本
- 处理依赖一致性（凭据、文件、环境变量）

---

# 前置条件

1. **安装 MGC Blackbox**：`pip install mgc-blackbox`（建议 1.4.10+）
2. **启动 MGC 服务**：`mgc`（运行于 http://127.0.0.1:57219，WebUI 在 57218）
3. **MCP 工具可用**：`mgc_save`, `mgc_run`, `mgc_seal`, `mgc_list`, `mgc_find`, `mgc_open_webui`
4. **两个 MGC 节点**：一个用于脚本归属，一个用于授权节点；单节点可自验证流程
5. **Token 文件**：`~/.mgc/database/mgc_black_box/.mgc_token`

> **沙箱模式（1.4.9+）**：若运行在沙箱 Agent（Trae Work / Workbuddy）中，建议将 MGC 装在系统环境；否则 MCP 工具调用可能被沙箱拦截。本技能的密封流程仍可工作，但mcp操作可能受限，此种情况请使用fastapi。

---

# 核心概念

## 为什么要跨设备授权？

```
传统方式：脚本归属节点 → 发送脚本（明文）→ 授权节点
MGC 方式：脚本归属节点 → 用 node_pub 密封 → 密文 → 授权节点
                                    ↓
                        始终加密，从未暴露
```

脚本在以下阶段保持加密：
- 源节点密封后
- 网络传输过程
- 授权节点存储期间
- 黑盒执行时解密后立即释放内存

密封包结构（MGC 1.4.10）：
```
{
  "content":  "AES-256 加密的脚本体",
  "ext_01":   "原始启动命令（如 python）",
  "ext_02":   "原始脚本的默认参数（JSON 数组，1.4.10 自动解析并打包）",
  "ext_03":   "RSA 加密的 AES key（仅目标节点可解密）"
}
```

---

# 应用场景

## 场景 1：跨组织脚本共享

组织 A 想共享脚本给组织 B，但不暴露脚本内容。

1. 组织 B 安装 MGC 并提供其 `node_pub`
2. 组织 A 用 `node_pub` 密封脚本
3. 组织 B 存储密封脚本并执行

## 场景 2：可信合作伙伴自动化

公司想向合作伙伴提供自动化脚本，但不暴露脚本逻辑。

1. 合作伙伴安装 MGC 并提供 `node_pub`
2. 公司用合作伙伴的 `node_pub` 密封脚本
3. 合作伙伴本地以黑盒方式执行

## 场景 3：委托任务执行

中央服务器向边缘设备委托任务，但不暴露任务逻辑。

1. 边缘设备向中央服务器提供 `node_pub`
2. 中央服务器密封任务脚本
3. 边缘设备执行密封任务

---

# 工作流程

## 步骤 1：获取目标节点公钥

目标节点（即运行密封脚本的节点）必须提供其 RSA 公钥。

**方式 A：通过 MCP/API 触发懒生成**
```python
# 通过 MCP 获取节点公钥（首次调用时自动生成 keypair）
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
```

**方式 B：WebUI 查看（1.4.7+）**
打开 WebUI → skill 页面 → Settings 下拉 → **Node Public Key** → 复制多行 PEM。
Safari 浏览器下会下载 `.pem` 文件。

> **关键要求**：`node_pub` **必须**是**多行 PEM**，每行真实换行：
> ```
> -----BEGIN PUBLIC KEY-----
> MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
> ...（base64 多行）...
> -----END PUBLIC KEY-----
> ```
> 单行拼接会触发 MGC 提示"Invalid PEM format"，需原样从 mgc_get 返回值拷贝。

## 步骤 2：脚本归属节点密封脚本

脚本归属节点使用目标节点公钥密封脚本。

```python
# 1. 先存储原始脚本（ext01 必填，ext02 可选——MGC 会自动解析 argparse 并填充）
mgc_save(
    info_type="script",
    info_owner="my_script",
    ext01="python",
    content="import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('--name', default='World')\nargs = parser.parse_args()\nprint(f'Hello {args.name}')"
)

# 2. 用目标节点公钥密封脚本
sealed = mgc_seal(
    info_owner="my_script",        # 必填：要密封的脚本标识
    # info_type 可选，默认 "script"
    ext04=node_pub                 # 必填：目标节点的多行 PEM 公钥
)

# sealed 现在是 dict：
# {
#   "content": "<AES 加密脚本体>",
#   "ext_01":  "python",
#   "ext_02":  '["--name", "World"]',   # 1.4.10 自动解析并打包
#   "ext_03":  "<RSA 加密的 AES key>"
# }
```

## 步骤 3：传输密封脚本

将密封包完整传给授权节点。**所有四个字段**（content / ext_01 / ext_02 / ext_03）必须一起传，否则目标节点无法执行。

```python
import json
payload = json.dumps(sealed, ensure_ascii=False)
# 通过邮件 / U 盘 / 即时通讯等任意渠道发送 payload
```

> **注意**：密封包是密文，但请使用可信传输渠道；MGC 不阻止篡改，仅保证机密性。

## 步骤 4：授权节点存储密封脚本

授权节点收到密封包后，将其存入本地 MGC。**必须同时存入 content + ext01 + ext02 + ext03**：

```python
# 在目标节点（授权节点）上
mgc_save(
    info_type="script",
    info_owner="partner_script",     # 脚本标识，建议与源一致
    ext01=sealed["ext_01"],          # 启动命令，如 "python"
    ext02=sealed["ext_02"],          # 默认参数（来自源节点的 argparse 解析）
    content=sealed["content"],       # AES 加密脚本体
    ext03=sealed["ext_03"],          # RSA 加密的 AES key（仅本节点可解）
    update_if_exists=True            # 1.4.10 新增：允许覆盖同名脚本
)
```

> **为什么 ext02 必填**：`ext02` 是密封时从源脚本 `argparse` 自动提取的默认参数列表。目标节点执行时若不写入 `ext02`，`mgc_run` 启动会用空 args，argparse 仍可解析（因脚本内 default 兜底），但若源脚本有动态 default（如 `os.path.expanduser("~")`），会被识别为 `dynamic_args_detected`，此时建议显式传入 `ext02`。

## 步骤 5：执行密封脚本（黑盒）

授权节点使用 `mgc_run`（1.4.10+ 推荐）以黑盒方式执行密封脚本：

```python
# ✅ 1.4.10 推荐：使用 mgc_run
result = mgc_run(
    info_owner="partner_script",
    diff_1="partner_script",          # schema 必填的区分字段；多条同 owner 时消歧，单条时任意非空字符串均可
    ext02='["--name", "Alice"]'       # 可选：运行时覆盖默认参数（JSON 数组字符串）
)
# 返回示例: {"pid": 12345, "status": "started"}
# 脚本从未暴露，AI 仅得到启动状态
```

> **历史兼容**：`mgc_get(info_type="script", info_owner="...", action="run")` 仍可用，但 1.4.10 起 `mgc_run` 是首选，意图更明确。
> **执行输出**：`mgc_run` 只返回 `pid + status`，不返回 stdout。如需详细结果，密封脚本应将结果写入文件并在 stdout 输出文件路径（详见「依赖要求」章节）。

## 步骤 6：（可选）查询/查找已存密封脚本

1.4.10 新增 `mgc_find` 支持模糊搜索：

```python
# 列出所有脚本条目（精确匹配 info_owner 包含 "partner" 的）
scripts = mgc_find(
    info_owner="partner",
    match_mode="substring",          # substring / prefix / suffix / exact
    limit=50
)
# 返回 metadata 列表，**绝不包含 content 明文**
```

---

# 依赖要求

密封脚本在目标节点执行时，需保证依赖一致：

| 依赖 | 处理方式 |
|------|----------|
| **MGC 凭据** | 目标节点需用相同 `info_type` / `info_owner` 存入凭据；格式一致但内容按节点定制 |
| **外部文件** | 路径应保持一致，建议一并存入 MGC，运行时通过 MGC API 拉取 |
| **环境变量** | 必须在目标节点上设置 |
| **Python 库** | 目标节点需安装相同版本的依赖库（建议用 `requirements.txt` 一并打包） |
| **跨平台差异** | 用 `pathlib.Path` 或 `/` 路径分隔符，避免平台特定 API（[skill_spec.md §2 Scenario C](file:///D:/MirginCipher/mgc/docs/skill_spec.md) 提及） |

> **重要**：依赖不一致是密封脚本执行失败的最常见原因。请在密封前确认源节点与目标节点的 MGC 凭据命名、环境变量、文件路径一致。

---

# 安全说明

1. **零暴露**：脚本在存储和传输时加密，仅在目标节点执行时内存中解密
2. **黑盒执行**：密封脚本在 MGC 沙箱中执行，AI 不可见脚本内容
3. **单向密封**：一旦密封，仅在目标节点（拥有对应 `node_priv`）运行时可解密，其它节点（含源节点）均无法解密
4. **执行权 ≠ 所有权**：目标节点只能执行，不能转密封给第三方（因 AES key 仅绑定目标节点 RSA 公钥）
5. **无 root 防护**：恶意 root 可在执行瞬间读取内存解密内容，请确保目标节点可信后再授权
6. **传输安全**：MGC 不验证密封包完整性，请通过可信渠道传输，避免中间人篡改

---

# MCP 工具参考

## mgc_get

**获取节点公钥：**
```json
{
  "info_type": "__NODE_PUB__",
  "info_owner": "__NODE_PUB__"
}
```

## mgc_run（1.4.7+，推荐用于执行）

**必填：** `info_type="script"`, `info_owner`, `diff_1`（schema 必填的区分字段；多条同 owner 时消歧，单条时任意非空字符串均可）

**执行密封脚本：**
```json
{
  "info_type": "script",
  "info_owner": "partner_script",
  "diff_1": "partner_script",
  "ext02": "[\"--name\", \"Alice\"]"
}
```

**返回：** `{ "pid": <int>, "status": "started" }`

## mgc_seal

**必填：** `info_owner`, `ext04`

**参数：**
```json
{
  "info_owner": "my_script",
  "info_type": "script",
  "diff_1": "optional",
  "diff_2": "optional",
  "diff_3": "optional",
  "ext04": "<target_node_pub_multi_line_PEM>"
}
```

**返回（dict）：**
```json
{
  "content":  "<AES encrypted body>",
  "ext_01":   "python",
  "ext_02":   "[\"--name\", \"World\"]",
  "ext_03":   "<RSA encrypted AES key>"
}
```

> **PEM 格式要求**：`ext04` 必须是多行 PEM 含真实换行（`\n`）。若返回 "Invalid PEM format" 提示，重新从 `mgc_get(info_type='__NODE_PUB__')` 获取原值。

## mgc_save

**存储原始脚本：**
```json
{
  "info_type": "script",
  "info_owner": "my_script",
  "ext01": "python",
  "ext02": "[\"--name\", \"World\"]",
  "content": "script plaintext"
}
```

**存储密封脚本（目标节点）：**
```json
{
  "info_type": "script",
  "info_owner": "partner_script",
  "ext01": "python",
  "ext02": "[\"--name\", \"World\"]",
  "content": "<sealed content>",
  "ext03": "<sealed AES key>",
  "update_if_exists": true
}
```

> **1.4.10 新增** `update_if_exists`：当 `info_type + info_owner + diff_1/2/3` 重复时设为 `true` 可覆盖，否则返回错误。

## mgc_list / mgc_find（1.4.10 新增）

```python
# mgc_list：精确匹配，meta-only
scripts = mgc_list()  # 列出所有条目 metadata（不含 content）

# mgc_find：模糊搜索，match_mode 自动加 LIKE 通配符
scripts = mgc_find(info_owner="partner", match_mode="substring", limit=50)
# match_mode: substring (%x%) / prefix (x%) / suffix (%x) / exact (x)
```

---

# 问题排查

| 问题 | 解决方案 |
|------|---------|
| `mgc_seal` 返回 "Invalid PEM format" | `ext04` 必须是多行 PEM 含真实换行，从 `mgc_get(info_type='__NODE_PUB__')` 原样拷贝 |
| `mgc_run` 返回 "args_not_recognized" | 源脚本 `argparse` 未识别；检查 `add_argument` 用法或显式传 `ext02` |
| `mgc_save` 返回 "dynamic_args_detected" warning | 源脚本含动态 default（如 `datetime.now()`、`os.path.expanduser`）；建议改字面量或手动传 `ext02` |
| 目标节点执行找不到凭据 | 凭据命名 `info_type/info_owner` 与源节点不一致；统一命名后再密封 |
| `mgc_run` 返回 `pid + started` 但脚本无输出 | 正常行为：`mgc_run` 只返回启动状态；密封脚本应将结果写入文件，stdout 输出路径 |
| 目标节点存储失败报重名 | 加 `update_if_exists=true` 覆盖；或先用 `mgc_find` 查重后改名 |
| WebUI 看不到 node_pub 入口 | 确认 MGC ≥ 1.4.7；skill 页面右上角 Settings 下拉中有"Node Public Key viewer" |
| 沙箱模式下 MCP 工具不可用 | 把 MGC 装在系统环境，或改调 FastAPI 直接调用 `/api/mgc/sensitive/run` |

---

# 相关链接

- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系方式**：mirgincipher@outlook.com
