---
spec: usk/3.0
id: cross_node_script_auth
version: 1.3.0
name: 脚本跨设备加密授权（零暴露）
description: 使用 MGC Blackbox 实现零暴露跨设备脚本授权。脚本用目标节点 RSA 公钥密封，以密文形式交付，仅在授权节点内存中解密执行；也支持免公钥交换的自由模式公开分发。适配 MGC 1.5.4：双层加密、链接授权（link authorization）、胶囊文件交付。
author: MirginCipher Team
license: MIT
tags:
  - 安全
  - 跨设备
  - 加密
  - 零暴露
  - mgc
  - 授权
  - 密封
  - RSA
  - 双层加密
  - 自由模式
  - 链接授权
  - 黑盒执行
platform_compatibility:
  - windows
  - macos
  - linux
mcp_tools:
  - mgc_save
  - mgc_save_file
  - mgc_get
  - mgc_run
  - mgc_find
  - mgc_list
  - mgc_seal
  - mgc_seal_package
  - mgc_package
  - mgc_delete
  - mgc_open_webui
  - mgc_skill
requirements:
  mgc_version: ">=1.5.4"
install: pip install mgc-blackbox>=1.5.4
runtime: mgc
port: 57219
changelog:
  - version: 1.3.0
    changes:
      - 升级至 MGC 1.5.4：密封机制改为双层加密，新增 ext09 模式字段与 ext07 源节点绑定
      - 重写核心概念章节：从单层 RSA 绑定改为「双层加密 + 链接授权」，并新增自由模式对照表
      - 修正密封流程：ext04 自 1.5.4 起改为可选（省略即自由模式），ext04 为空不再报错
      - 修正存储流程：改用 mgc_save_file(path=胶囊文件) 一次导入，自动解析全部 ext 字段
      - 修正安全说明：第 3 条「其它节点均无法解密」在自由模式下不成立，第 6 条「不校验完整性」已过时
      - 新增链接授权章节：ext07 / ext09 篡改即不可还原，含实测验证步骤
      - 修正 mgc_run 参数：diff_1 自 1.5.4 起改为可选，diff_3 最可靠，新增 AMBIGUOUS_SCRIPT 错误码
      - 修正密封包结构：由 4 字段改为 8 字段（新增 ext05 / ext06 / ext07 / ext09），键名去掉下划线
      - 补充 ext05 依赖清单 / ext06 平台清单 / ext10 可运行性徽章说明
      - 修复失效的 Windows 绝对路径链接
      - 措辞规范化：改为「调用方」等中性表述，安全边界按内容机密性与责任归属重新表述
      - mcp_tools 补齐为 12 个，新增 mgc_delete 与 mgc_skill
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

- 用目标节点 RSA 公钥密封脚本，密文交付
- 也支持免公钥交换的**自由模式**，公开分发
- 在授权节点以**黑盒执行**方式运行密封脚本
- 通过**链接授权**校验产物来源

本技能**不含可执行代码**，仅为文档说明。

---

# 本技能实现的功能

阅读本文档后，调用方将了解如何：

- 获取目标节点 RSA 公钥（`__NODE_PUB__`）
- 用 `mgc_seal` 密封脚本（自动提取默认参数），产出可交付的胶囊文件
- 选择授权模式：p2p（绑定特定节点）或自由模式（任何 1.5.4+ 节点可运行）
- 在目标节点用一次调用导入胶囊（自动解析全部字段）
- 用 `mgc_run` 以黑盒方式执行密封脚本
- 校验产物来源完整性（`ext07` / `ext09` 篡改检测）
- 处理依赖一致性（凭据、文件、环境变量）

---

# 前置条件

1. **安装 MGC Blackbox**：`pip install mgc-blackbox>=1.5.4`
2. **启动 MGC 服务**：`mgc`（运行于 http://127.0.0.1:57219，WebUI 在 57218）
3. **MCP 工具可用**：`mgc_save`, `mgc_save_file`, `mgc_get`, `mgc_run`, `mgc_seal`, `mgc_find`, `mgc_list`, `mgc_delete`, `mgc_open_webui`, `mgc_skill`
4. **两个 MGC 节点**：一个用于脚本归属，一个用于授权节点；单节点可自验证流程
5. **Token 文件**：`~/.mgc/database/mgc_black_box/.mgc_token`

> **版本要求**：接收方必须运行 **MGC 1.5.4+**。1.5.4 之前的版本无法解封带链接授权的产物。
> **沙箱模式（1.4.9+）**：若运行在沙箱 Agent（Trae Work / Workbuddy）中，建议将 MGC 装在系统环境；否则 MCP 工具调用可能被沙箱拦截，此种情况请直接调用 FastAPI。

---

# 核心概念

## 为什么要跨设备授权？

```
传统方式：脚本归属节点 → 发送脚本（明文）→ 授权节点
MGC 方式：脚本归属节点 → 密封 → 密文胶囊 → 授权节点
                                    ↓
                        始终加密，从未暴露
```

脚本在以下阶段保持加密：

- 归属节点密封后
- 传输过程
- 授权节点存储期间
- 黑盒执行时解密后立即释放内存

## 1.5.4 的双层加密结构

密封产物由三层构成（1.5.4 起所有密封均走双层路径）：

```
第 1 层：content   = AES-256-CBC(脚本体, 一次性 AES_KEY_4)
第 2 层：AES_KEY_4 = RSA-2048 加密（p2p 用目标节点公钥 / 自由模式用共享默认公钥）
第 3 层：ext03     = AES-256-GCM(第 2 层结果, 密钥 = SHA256(ext07)[:32], AAD = ext09)
```

第 3 层的密钥由 **ext07（归属节点公钥）** 派生、AAD 绑定 **ext09（密封模式）**——这正是链接授权的来源。
第 1 层的 AES_KEY_4 每次密封重新随机生成，不跨产物复用。

## 两种密封模式

`ext04` 是否传入，决定密封模式：

| | p2p 模式（默认） | 自由模式 |
|---|---|---|
| 密封方式 | 传入 `ext04=目标节点多行 PEM` | **省略** `ext04` |
| 产物中的 `ext09` 取值 | `p2p mode` | `free mode` |
| 谁能解封运行 | 仅持有对应私钥的节点 | **任何 MGC 1.5.4+ 节点** |
| 源脚本是否可读 | 不可读 | 不可读（同样只在内存中解密） |
| 是否需要交换公钥 | 需要 | **不需要** |
| 适用场景 | 单客户授权、保密交付 | 公开分发、技能市场、通用安装包 |

自由模式用 MGC 共享的默认公钥包裹内容，因此**任何装有 MGC 1.5.4+ 的机器都能导入并运行**，而源脚本在接收侧仍不会落盘为明文。

> 自由模式适合「给所有人一份可运行的试用件」，**不适用于**需要按客户限制的场景。

## 密封产物结构（1.5.4 实测）

```
{
  "info_type":  "script",
  "info_owner": "my_script",
  "ext01":      "python",                    // 启动命令
  "ext02":      '["--name", "World"]',       // 默认参数（密封时自动解析 argparse）
  "ext03":      "<双层包裹的密文>",           // 密封密钥
  "ext05":      "[]",                        // 第三方依赖清单（自动探测）
  "ext06":      '["windows","macos","linux"]',// 兼容平台清单（静态推断）
  "ext07":      "<归属节点 RSA 公钥>",        // 来源身份，参与密钥派生
  "ext09":      "p2p mode",                 // 密封模式
  "content":    "<AES 加密脚本体>"
}
```

要点：

- 字段键名**不带下划线**（`ext01` 而非 `ext_01`）
- `ext07` 与 `ext09` **必须随产物一起流转**，缺任一项则无法解封
- `ext05` / `ext06` 是运行前的提示信息，MGC **不会**自动安装依赖

---

# 应用场景

## 场景 1：跨组织脚本共享

组织 A 想共享脚本给组织 B，但不暴露脚本内容。

1. 组织 B 安装 MGC 并提供其 `node_pub`
2. 组织 A 用 `node_pub` 密封脚本（p2p 模式）
3. 组织 B 导入胶囊并执行

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

## 场景 4：公开分发（自由模式）

需要把脚本发给不确定的接收方、或上架技能市场时：

1. 归属节点密封，**省略 `ext04`**
2. 产物可放公开渠道
3. 任何装有 MGC 1.5.4+ 的节点导入后即可运行，源脚本始终不落盘

---

# 工作流程

## 步骤 1：获取目标节点公钥

仅 p2p 模式需要。自由模式可跳过本步。

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
> 单行拼接会触发 "Invalid PEM format"，需原样从 `mgc_get` 返回值拷贝。

## 步骤 2：归属节点密封脚本

先存原始脚本，再密封。密封会产出一个**自描述的胶囊文件**。

```python
# 1. 先存储原始脚本（ext01 必填，ext02 可选——MGC 会自动解析 argparse 并填充）
mgc_save(
    info_type="script",
    info_owner="my_script",
    ext01="python",
    content="import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('--name', default='World')\nargs = parser.parse_args()\nprint(f'Hello {args.name}')"
)

# 2. 密封
sealed = mgc_seal(
    info_owner="my_script",        # 必填：要密封的脚本标识
    output_dir="/abs/path/to/out", # 必填：1.5.4 起无桌面兜底，必须显式指定绝对路径
    # p2p 模式传目标节点公钥；自由模式省略这一行
    ext04=node_pub
)

# sealed 中包含：
#   capsule_path  胶囊文件的绝对路径
#   content / ext01..ext09        完整的自描述产物
```

> **`output_dir` 自 1.5.4 起为必填**，没有默认位置。产物落在
> `<output_dir>/<info_owner>_<YYYYMMDD_HHMMSS>/sealed_capsule.json`。

> **自由模式**：把 `ext04` 整行删掉即可，其余参数不变。

> **参数名必须是 `ext04`**：写成 `node_pub` / `target_pub` / `public_key` 等别名会直接报
> `UNKNOWN_PARAM`，避免误以为已做节点绑定、实际产出自由模式产物。

## 步骤 3：传输密封产物

把 `capsule_path` 指向的 `sealed_capsule.json` 整个文件交给接收方——任意渠道（邮件 / U 盘 / IM）均可。

```python
import shutil
shutil.copy(sealed["capsule_path"], "/path/to/send/sealed_capsule.json")
# 或直接把该 JSON 文件内容贴给对方
```

> 产物是密文，但**完整性由链接授权保证**（见「链接授权」章节）。仍建议使用可信渠道。
> 转发时 `ext07` / `ext09` 必须**原样透传**，任何改动都会导致不可还原。

## 步骤 4：授权节点导入产物

**一次调用即可**，MGC 会自动识别胶囊并解析出全部字段：

```python
# 在授权节点上（推荐：路径导入，参数最少，类型自动推断）
mgc_save_file(
    path="/path/to/send/sealed_capsule.json",
    info_owner="partner_script"     # 用你自己的 owner，避免覆盖归属节点上的源记录
)
```

也可直接传 JSON：

```python
mgc_save(
    info_type="script",             # 此工具的 schema 要求，即使胶囊体内已重复该字段
    info_owner="partner_script",
    content=capsule_json_string     # 整个胶囊 JSON 原样传入
)
```

> **不要手工逐字段搬运** `ext01` / `ext02` / `content` / `ext03`——这样会丢掉 `ext07` 与 `ext09`，
> 结果是产物可以存入但**永远无法解封**。

> **owner 的选择**：胶囊内的 `info_owner` 属于归属节点。在同一节点上用同名 owner 存储会**覆盖源记录**；
> 在另一节点上则不影响归属节点。传入你自己的 owner 可同时保留两份。

## 步骤 5：执行密封脚本（黑盒）

```python
# ✅ 1.5.4 推荐：使用 mgc_run
result = mgc_run(
    info_type="script",
    info_owner="partner_script",
    diff_3="partner_script",          # 最可靠的定位字段：脚本的相对路径 / 文件名
    ext02='["--name", "Alice"]'       # 可选：运行时覆盖默认参数（JSON 数组字符串）
)
# 返回示例: {"status": "started"}
# 调用方只拿到启动状态，脚本内容始终未暴露
```

> **`diff_1` 自 1.5.4 起不再必填**。定位脚本时优先用 `diff_3`（最精确），其次 `diff_2`（文件夹名）。
> 若同一 owner 下匹配到多条记录，MGC 返回 `AMBIGUOUS_SCRIPT`，此时先用 `mgc_find` 列出候选再重试。

> **执行输出**：`mgc_run` 只返回启动状态，不返回 stdout。如需详细结果，密封脚本应将结果写入文件并在 stdout 输出文件路径（详见「依赖要求」章节）。

## 步骤 6：（可选）查询已存密封脚本

```python
# 模糊搜索（1.4.10+）
scripts = mgc_find(
    info_owner="partner",
    match_mode="substring",          # substring / prefix / suffix / exact
    limit=50
)
# 返回 metadata 列表，**绝不包含 content 明文**
```

---

# 链接授权

自 1.5.4 起，每个密封产物都携带归属节点的身份（`ext07`）与密封模式（`ext09`）。这两项共同构成**链接授权**。

## 工作机制

解封时，MGC 按以下顺序校验：

1. 用 `ext07` 派生外层密钥 `SHA256(ext07)[:32]`
2. 用 `ext09` 作为 AAD 校验密文完整性
3. 校验不通过 → 报 `UNSEAL_FAILED`

因为密钥派生绑定 `ext07`、完整性校验绑定 `ext09`，**任何对这两项的修改都会让产物不可还原**——包括只改一个空格。

## 实测验证步骤

想在本地确认这项机制确实生效，可以按下面三步走（全程在本机，无需第二个节点）：

```python
# 1. 密封并导入
sealed = mgc_seal(info_owner="my_script", output_dir="/tmp/probe")
mgc_save_file(path=sealed["capsule_path"], info_owner="probe_copy")
```

```python
# 2. 篡改 ext09（加一个尾随空格），写成一个新文件
#    Python 侧操作：对 capsule JSON 的 ext09 追加一个空格，另存为 tampered.json
```

```python
# 3. 导入篡改后的文件并运行
mgc_save_file(path="/tmp/probe/tampered.json", info_owner="probe_tampered")
mgc_run(info_type="script", info_owner="probe_tampered")
```

实测结果：

```
Error: UNSEAL_FAILED
Hint: Double-layer unseal failed: AES-GCM auth tag mismatch:
      source_node_pub (ext07) or mode (ext09) tampered, or wrong key.
```

同样的原理也保护「非目标节点无法解封」：用不匹配的私钥解密时报
`Double-layer unseal failed: Incorrect decryption`。

## 使用建议

- 接收方应核对 `ext07` 与归属节点公钥是否一致（通过可信渠道核对）
- `ext07` / `ext09` 转发时原样透传，不要编辑、不要重新排版
- `ext07` 在产物中是**明文标识**，不是签名；它用于检测篡改与绑定解封密钥，不能替代身份核验

---

# 依赖要求

密封脚本在目标节点执行时，需保证依赖一致：

| 依赖 | 处理方式 |
|------|----------|
| **MGC 凭据** | 目标节点需用相同 `info_type` / `info_owner` 存入凭据；格式一致但内容按节点定制 |
| **外部文件** | 路径应保持一致，建议一并存入 MGC，运行时通过 MGC API 拉取 |
| **环境变量** | 必须在目标节点上设置 |
| **Python 库** | 目标节点需安装相同版本的依赖库；密封时 MGC 会把依赖清单写进 `ext05`，**但不会自动安装** |
| **跨平台差异** | 用 `pathlib.Path` 或 `/` 路径分隔符，避免平台特定 API；兼容平台清单会写进 `ext06` |

> **重要**：依赖不一致是密封脚本执行失败的最常见原因。请在密封前确认源节点与目标节点的 MGC 凭据命名、环境变量、文件路径一致。

---

# 安全说明

1. **零暴露**：脚本在存储和传输时加密，仅在目标节点执行时在内存中解密，明文不落盘
2. **黑盒执行**：密封脚本在 MGC 沙箱中执行，调用方拿不到脚本内容
3. **授权边界随模式而定**：p2p 模式下仅持有对应私钥的节点能解封；**自由模式下任何 MGC 1.5.4+ 节点都能解封**——选自由模式即意味着放弃「限定接收方」这一约束
4. **执行权 ≠ 所有权**：p2p 模式的接收方只能执行，无法把归属节点的产物转封给第三方
5. **无 root 防护**：恶意 root 可在执行瞬间读取内存中解密的内容，请确保目标节点可信后再授权
6. **完整性已可校验**：1.5.4 的链接授权能检测 `ext07` / `ext09` 被篡改（详见「链接授权」章节）；但这是**来源绑定**，不是对脚本运行行为的担保

> **保证范围**：MGC 保护的是**内容机密性**。脚本解封后在节点上以运行它的用户权限执行，它调用哪些命令、读写哪些文件、访问哪些网络端点，MGC 不做限制。这些行为属于脚本作者的职责。导入前请通过可信渠道核对归属节点的公钥。

---

# MCP 工具参考

| 工具 | 用途 | 必填参数 |
|------|------|----------|
| `mgc_save` | 存原始脚本 / 直接传胶囊 JSON | info_type, info_owner, content |
| `mgc_save_file` | 按路径导入胶囊（**推荐**）/ 导入文件夹 / 导入 `.mgc_file` | path, info_owner |
| `mgc_seal` | 密封单脚本，产出胶囊文件 | info_owner, **output_dir**（p2p 另需 ext04） |
| `mgc_run` | 黑盒执行 | info_type="script", info_owner（`diff_3` 最可靠） |
| `mgc_get` | 取 node_pub / 取凭据 / 列全部条目 | info_type, info_owner |
| `mgc_find` | 模糊搜索 | info_owner, match_mode |
| `mgc_list` | 列出全部条目 metadata | — |
| `mgc_delete` | 删除已存记录（含用户确认流程） | info_type, info_owner |
| `mgc_open_webui` | 打开 WebUI | — |
| `mgc_skill` | 阅读 MGC 官方技能文档 | — |

## mgc_seal

**必填：** `info_owner`, `output_dir`　**p2p 模式另需：** `ext04`

```json
{
  "info_owner": "my_script",
  "info_type": "script",
  "diff_1": "optional",
  "diff_2": "optional",
  "diff_3": "optional",
  "output_dir": "/abs/path/to/out",
  "ext04": "<目标节点 node_pub 多行 PEM；自由模式省略>"
}
```

> **PEM 格式要求**：`ext04` 必须是多行 PEM 含真实换行（`\n`）。若返回 "Invalid PEM format"，重新从 `mgc_get(info_type='__NODE_PUB__')` 获取原值。

## mgc_run

**必填：** `info_type="script"`, `info_owner`　**定位字段：** `diff_3`（最可靠）/ `diff_2`（文件夹名）/ `diff_1`（可选）

```json
{
  "info_type": "script",
  "info_owner": "partner_script",
  "diff_3": "partner_script",
  "ext02": "[\"--name\", \"Alice\"]"
}
```

**返回：** `{ "status": "started" }`

---

# 问题排查

| 问题 | 解决方案 |
|------|---------|
| `mgc_seal` 报 "Missing required param: output_dir" | 1.5.4 起 `output_dir` 必填且无桌面兜底，传绝对路径 |
| `mgc_seal` 报 "Unknown param: node_pub"（`UNKNOWN_PARAM`） | 参数名必须是 `ext04`；别名不被接受，避免误产出自由模式产物 |
| `mgc_seal` 返回 "Invalid PEM format" | `ext04` 必须是多行 PEM 含真实换行，从 `mgc_get(info_type='__NODE_PUB__')` 原样拷贝 |
| 导入后运行报 `UNSEAL_FAILED: AES-GCM auth tag mismatch` | `ext07` 或 `ext09` 被改动过；用原始产物重新导入 |
| 导入后运行报 `Double-layer unseal failed: Incorrect decryption` | 当前节点私钥与 `ext04` 不匹配，即不是指定的目标节点 |
| 导入后运行报 "ext09 is non-empty but ext07 is missing" | 手工搬运字段时丢了 `ext07`；改用 `mgc_save_file(path=胶囊文件)` 一次导入 |
| 运行报 `AMBIGUOUS_SCRIPT` | 同一 owner 匹配到多条记录；用 `mgc_find` 列出候选，补 `diff_3` / `diff_2` 重试 |
| `mgc_run` 返回 "args_not_recognized" | 源脚本 `argparse` 未识别；检查 `add_argument` 用法或显式传 `ext02` |
| `mgc_save` 返回 "dynamic_args_detected" warning | 源脚本含动态 default（如 `datetime.now()`、`os.path.expanduser`）；建议改字面量或手动传 `ext02` |
| 目标节点执行找不到凭据 | 凭据命名 `info_type/info_owner` 与源节点不一致；统一命名后再密封 |
| `mgc_run` 返回启动状态但脚本无输出 | 正常行为：`mgc_run` 只返回启动状态；密封脚本应将结果写入文件，stdout 输出路径 |
| 导入后归属节点的源记录消失 | 用了与源相同的 `info_owner` 在同节点导入，覆盖了源记录；改用自己的 owner |
| 目标节点存储失败报重名 | 加 `update_if_exists=true` 覆盖；或先用 `mgc_find` 查重后改名 |
| 提示依赖缺失 | `ext05` 列出的是运行前提示，MGC 不会自动安装，需在目标节点手动装好 |
| WebUI 看不到 node_pub 入口 | 确认 MGC ≥ 1.4.7；skill 页面右上角 Settings 下拉中有"Node Public Key viewer" |
| 沙箱模式下 MCP 工具不可用 | 把 MGC 装在系统环境，或改调 FastAPI 直接调用 |

---

# 相关链接

- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系方式**：mirgincipher@outlook.com
