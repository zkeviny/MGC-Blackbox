---
spec: usk/3.0
id: sealed-chain-cn
version: 1.0.0
skill_type: functional
name: 多 agent 跨设备加密协作（邮件 + 任务密封）
description: 功能性技能。用 MGC 1.6.0 chain mode 组织多个 agent 的跨设备加密协作：按数据域把任务拆成 N 个密封子包，每个执行 agent 只获得授权给自己的脚本；数据与凭证不出域，只流转任务书、脚本和结果摘要。默认邮件分发，任务以密封子包形式传输。包含三种参考角色的任务书模板、凭证调用示例和任务流模板。
author: MirginCipher Team
license: MIT
tags: 多节点协作, chain mode, 任务链密封, 加密交付, 节点授权, 零暴露, a2a, distribution index, 自动化分发, 工作流拆分, 编排, mgc, blackbox, functional
platform_compatibility: windows, macos, linux
mcp_tools: mgc_save, mgc_save_file, mgc_get, mgc_run, mgc_find, mgc_list, mgc_seal, mgc_seal_package, mgc_package, mgc_delete, mgc_open_webui, mgc_skill
requirements:
  mgc_version: ">=1.6.0"
install: pip install mgc-blackbox>=1.6.0
runtime: mgc
port: 57219
changelog:
  - version: 1.0.0
    changes:
      - 初始发布，基于 MGC 1.6.0 chain mode
      - 三种参考角色：编排 agent / 内部执行 agent / 外部执行 agent（按数据域划分）
      - 八阶段协作协议：准备 → 编排 → 存包 → 密封 → 分发 → 执行 → 回传 → 汇总
      - 硬约束：数据与凭证不出域、工作流目录必须平级、targets files 精确匹配 diff_3
      - 默认邮件分发（Subject keyword chain:<task_id>，sha256 写正文），支持 A2A / HTTPS / 共享文件夹
      - distribution_index.json 驱动自动化分发；节点指纹账本核对收件人
      - UNSEAL_FAILED 错误码：导入成功 ≠ 可解封，node_pub 不匹配运行期才报
      - 密封脚本 ext01 可移植性提醒（python vs python3）、--output 父目录需预先存在
      - script-wrapped 加密传输模式：任务书与结果摘要封进脚本随子包密封
      - role_prompts 5 套模板：编排任务书 / 分发指令 / 执行任务书 / 结果回传 / 编排接收回传
      - examples：role_prompts.md、use_credential.py（本地 MGC 凭证调用）、task_flow.md（填空式任务流）
      - targets 规格只含 .py，数据文件与凭证由各执行方存入本地 MGC
      - 多节点硬隔离与单设备软隔离（task_chain_meta_skill）边界明确
      - 覆盖三步交付流程、三节点示例、distribution_index.json、@file 长规格
      - 平级目录硬约束、text 文件 REST API 读取、真实命名与字段说明
---

# 技能定位

**功能性技能**：回答"chain mode 怎么用、多个 agent 怎么分工、数据怎么不出域"。

- **包含**：机制说明、角色模型、协作协议、硬约束、API 用法、模板与示例。
- **不包含**：具体行业/业务场景的拆分方案。场景方案属于后续的场景化技能，不在本技能范围内。

适合：需要把一份工作流按数据域拆给多个 agent、且要求数据与凭证不出本地的跨设备协作。

---

# 一句话

编排 agent 只写任务书和脚本，MGC 按数据域拆出 N 个密封子包，每个执行 agent 只拿到自己的脚本；数据与凭证始终留在各自本地，只回传结果摘要。

---

# 角色模型

三种**参考角色**，不是固定编制。划分依据是**数据域**，不是设备。

| 角色 | 数量 | 持有数据/凭证 | 职责 | 产物 |
|------|------|:---:|------|------|
| 编排 agent | 1 | ❌ | 拆任务、写任务书、生成规格、分发、汇总 | 任务书、targets、汇总报告 |
| 内部执行 agent | 每个内部数据域 1 个 | ✅ 仅本地 | 在本域内执行脚本 | 结果摘要 |
| 外部执行 agent | 每个外部数据域 1 个 | ✅ 仅本地 | 在本域内执行脚本 | 结果摘要 |

划分规则：

1. **编排 agent 只有一个**，且不持有任何业务数据与凭证。
2. **执行 agent 按数据域划分**：一个数据域至少一个，可多可少。
3. 单数据域场景 = 1 编排 + 1 内部执行，外部执行省略。
4. "内部/外部"是数据边界，不是硬件类型；同一台设备也可以是两个数据域。

对应任务书模板见 [examples/role_prompts.md](./examples/role_prompts.md)。

---

# Chain Mode 机制

## 一次调用，N 个密封子包

`mgc_seal_package` 的 `ext04` 传入 target 数组，MGC 按每个 target 的 `files` 产出独立子包：

```json
[
  {"node_pub": "<内部执行方 PEM>", "files": ["analyze.py", "shared_helper.py"]},
  {"node_pub": "<外部执行方 PEM>", "files": ["intel.py", "shared_helper.py"]}
]
```

产出：

```
chain_delivery/<info_owner>__<diff_2>/
├── README.md                         # 主说明：node_pub 映射 + warnings
├── distribution_index.json           # 机器可读：sha256 + 授予文件
├── task_package_01/                  # 只给内部执行方（index 从 1 开始）
│   ├── <info_owner>__<diff_2>__01.mgc_file
│   └── README.md
└── task_package_02/                  # 只给外部执行方
    ├── <info_owner>__<diff_2>__02.mgc_file
    └── README.md
```

每个子包只对各自的 `node_pub` 可解，互相解不开。

## 与 p2p / free mode 对比

| | p2p mode | free mode | **chain mode** |
|---|---|---|---|
| `ext04` | 单个 PEM | 不传 | **target 数组** |
| 子包数 | 1 | 1 | **N** |
| 谁能解 | 只有该 PEM | 任意 1.5.4+ | **各自 PEM** |
| 适合 | 单节点授权 | 公开分发 | **多 agent 协作** |
| distribution_index.json | ❌ | ❌ | ✅ |
| 产出版本 | 1.5.4 | 1.5.4 | **1.6.0** |
| 接收版本 | 1.5.4 | 1.5.4 | 1.5.4 |

---

# 硬约束

## 约束 1：数据与凭证不出域

这是整个协作模式的核心，也是 chain mode 相对普通"发文件夹"的根本差异。

| 内容 | 是否进入密封包 | 说明 |
|------|:---:|------|
| 脚本 `.py` | ✅ | MGC 加密 |
| 任务书 prompt | ⚠️ 见下 | 封装为脚本才加密 |
| 结果摘要 | ⚠️ 见下 | 封装为脚本才加密 |
| 数据 CSV / JSON | ❌ **禁止** | 由执行方存入本地 MGC |
| 凭证 token / key | ❌ **禁止** | 由执行方存入本地 MGC |

正确做法：

```
执行方：数据/凭证 → 存入【本地 MGC】（info_type=text）→ 不向外传输
编排方：只下发 .py 脚本
脚本运行时：通过本地 MGC REST API 读取数据/凭证 → 用完即弃
回传：只回结果摘要
```

凭证读取示例见 [examples/use_credential.py](./examples/use_credential.py)。

## 约束 2：MGC 只加密脚本

chain mode 只加密 `.py` / `.sh` 等可执行脚本；CSV、JSON、TXT、配置文件在子包内**是明文**。

推论：

- 数据/凭证放进包 = 明文外发，**必须避免**。
- 任务书和结果如果要以密文流转，必须**封装成脚本**（见"加密传输模式"）。

## 约束 3：工作流目录必须平级

MGC sealed import hook 只支持平级 import：

```python
from shared_helper import write_json   # ✅
from utils.shared_helper import ...    # ❌ ModuleNotFoundError
```

因此工作流目录不能有 `scripts/`、`utils/`、`data/` 等子目录，所有文件放同一级。

## 约束 4：targets 的 files = 存入时的 diff_3

`files` 必须与 MGC 内记录的 `diff_3` 完全一致。平级目录下就是纯文件名。写规格前先 `mgc_find` 核对。

## 约束 5：密封脚本只返回 pid + status

`mgc_run` 对密封脚本返回 `{"status": "started"}`。结果必须由脚本写到外部（文件 / 本地 MGC / 回传包）。

注意：若通过 `ext02` 传 `--output` 写文件，**先确保父目录存在**——密封脚本不会自动 mkdir，目录缺失时会以 bootstrap code=1 退出。

---

# 协作协议

八阶段，详细填写版见 [examples/task_flow.md](./examples/task_flow.md)。

| 阶段 | 责任角色 | 动作 | 产物 |
|------|---------|------|------|
| 0 准备 | 各执行 agent | 把本地数据/凭证存入本地 MGC | 本地 text 记录 |
| 1 编排 | 编排 agent | 写任务书、准备平级脚本目录 | 任务书 + 脚本 |
| 2 存包 | 编排 agent | `mgc_save_file` 存入脚本目录 | 脚本记录 |
| 3 密封 | 编排 agent | 生成 targets（只含 .py）→ `mgc_seal_package` | N 个子包 + index |
| 4 分发 | 编排 agent | 传输子包（默认邮件） | 送达确认 |
| 5 执行 | 各执行 agent | 导入 → 核对授权清单 → `mgc_run` | 结果摘要 |
| 6 回传 | 各执行 agent | 结果封装 → 回传 | 回传包 |
| 7 汇总 | 编排 agent | 导入回传包 → 运行读取 → 汇总 | 最终交付物 |

其中"核对授权清单"是防越权的关键步骤：执行 agent 导入后先用 `mgc_find` 确认实际文件与任务书一致，不一致则停止。

阶段 7 的接收端动作（编排方视角）：收回传邮件 → 校验 sha256 → `mgc_save_file` 导入回传包 → `mgc_run` 执行回传脚本读取结果摘要（见 [examples/role_prompts.md](./examples/role_prompts.md) 模板 5）。

---

# 编排方操作

## 步骤 1：存入脚本目录

```python
mgc_save_file(
    path="./pipeline",          # 平级目录，只含 .py
    info_owner="<owner>",
    diff_2="pipeline",
)
```

MGC 自动解析 argparse → ext02、扫描 import → ext05、构建跨脚本调用图 → ext08、静态检查 → ext10。

> ⚠️ 密封前用 `mgc_get` 抽查各脚本的 **ext01**：MGC 推断的启动命令可能是 `python` 而非 `python3`，部分 Linux 发行版只有 `python3` 别名，会导致密封包在执行方机器上启动失败。按目标执行方的实际环境确认可移植性。

## 步骤 2：准备 target 规格

方式 A（短规格内联）：

```python
targets = json.dumps([
    {"node_pub": "<内部执行方 PEM>", "files": ["analyze.py", "shared_helper.py"]},
    {"node_pub": "<外部执行方 PEM>", "files": ["intel.py", "shared_helper.py"]},
])
```

方式 B（长规格写文件，推荐）：

```json
[
  {"node_pub": "<内部执行方 PEM>", "files": ["analyze.py", "shared_helper.py"]},
  {"node_pub": "<外部执行方 PEM>", "files": ["intel.py", "shared_helper.py"]}
]
```

```python
mgc_seal_package(
    info_owner="<owner>",
    diff_2="pipeline",
    ext04="@/abs/path/chain_targets.json",
    output_dir="/abs/path/chain_delivery",
)
```

> `node_pub` 由各执行方在自己机器上执行 `mgc_get(info_type='__NODE_PUB__', info_owner='__NODE_PUB__')` 获取，多行 PEM 原样使用，不要单行拼接。

## 步骤 3：分发

维护一份**节点指纹账本**（如 `agent_config.json`）：登记每个执行方的 email + node_pub + node_pub_fingerprint（fingerprint 由 MGC 在密封时生成并写入 `distribution_index.json`，编排方只需登记核对，不必自行计算）。

分发前逐一核对：`distribution_index.json` 中子包的 `node_pub_fingerprint` ↔ 账本中收件人指纹，确认"包发给了正确的节点"。

邮件分发约定（默认方式）：

- **Subject keyword**：统一使用 `chain:<task_id>`，执行方按此 keyword 做收件轮询过滤。
- **sha256 写入正文**：每个附件的 sha256 校验值写在邮件正文（不要只写在文件名里），供接收方在导入前核验。
- `.mgc_file` 必须作为附件传输，不要贴 base64 到正文。

读取 `distribution_index.json`，按 `node_pub_fingerprint` 匹配收件人，把 `task_package_NN/` 发给对应执行方。

---

# 执行方操作

## 步骤 1：导入并核对

收件后先核对正文里的 sha256 与附件实际值一致，再导入：

```python
mgc_save_file(path="./task_package_01/<包名>.mgc_file", info_owner="<包内 owner>", diff_2="pipeline")
mgc_find(info_owner="<包内 owner>", diff_2="pipeline")   # 核对授权清单
```

> 包内记录自带 info_owner / diff_2，导入时传的值只作校验。后续 `mgc_find` / `mgc_run` 用包内的值。
>
> ⚠️ **导入成功 ≠ 可解封**。解封发生在运行期：若子包与本机 node_pub 不匹配（发错节点）或 `.mgc_file` 被改名，`mgc_run` 时才报 `UNSEAL_FAILED`。核对清单后建议先用小参数冒烟跑一次入口脚本。

## 步骤 2：执行

```python
mgc_run(
    info_type="script",
    info_owner="<包内 owner>",
    diff_2="pipeline",
    diff_3="analyze.py",
    ext02='["--owner", "local_data", "--output", "/path/result.json"]',
)
```

## 步骤 3：回传

结果摘要建议封装为 `report.py`（见下节），用编排方 node_pub 做 p2p 密封后回传。

---

# 加密传输模式（script-wrapped）

MGC 只加密脚本，所以任务书和结果若要以密文流转，需要封装为脚本：

| 内容 | 封装方式 | 效果 |
|------|---------|------|
| 任务书 prompt | `task_card.py`，prompt 作为字符串常量 | 被 MGC 加密 |
| 结果摘要 | `report.py`，结果作为字符串常量 | 被 MGC 加密 |

示例 `task_card.py`：

```python
TASK = """
目标：...
约束：...
交付物：...
"""

if __name__ == "__main__":
    print(TASK)
```

这样任务书随脚本一起密封，不会以明文出现在子包里。若不封装，则任务书只能走邮件正文等外部通道，需自行确认内容是否敏感。

---

# 分发方式

| 方式 | 适用 | 备注 |
|------|------|------|
| **邮件附件** | 跨组织、需人工确认与审计 | **默认推荐**：依赖最小、可留痕。Subject 用 `chain:<task_id>`，sha256 写正文 |
| 共享文件夹 | 同组织内网 | 最省事 |
| A2A 消息 | 支持 agent 直连的平台 | 保留 `.mgc_file` 后缀；先验 sha256 |
| HTTPS / 对象存储 | 跨地域自动化 | 每方只发自己的下载链接 |

A2A 四规则：保留 `.mgc_file` 后缀；导入前验 sha256；不要把密钥放进消息体；优先传链接而不是文件本体。

---

# examples 目录

| 文件 | 用途 |
|------|------|
| [role_prompts.md](./examples/role_prompts.md) | 三种角色 + 分发 + 回传的任务书模板，直接复制使用 |
| [use_credential.py](./examples/use_credential.py) | 从本地 MGC 读凭证并使用，不落盘、不打印、只输出摘要 |
| [task_flow.md](./examples/task_flow.md) | 填空式多 agent 任务流模板 |

`use_credential.py` 用法：

```bash
# 本地调试
python3 examples/use_credential.py --local --token-file ./api_token.txt

# 密封态（由执行 agent 在 mgc_run 中调用）
# ext02='["--owner","local_credentials","--name","api_token.txt"]'
```

---

# 前置条件

- **Python 3.10+**（1.6.0 在 macOS Apple Silicon + framework 版 Python 3.11 实测通过；注意密封包 ext01 若为 `python`，执行方环境需有该命令，见编排方步骤 1）
- **MGC Blackbox ≥ 1.6.0**（产出方）；接收方最低 1.5.4
- `pip install mgc-blackbox`
- `mgc` 启动，API `http://127.0.0.1:57219`，WebUI `http://127.0.0.1:57218`

硬限制：每个子包 ≤ 100 个文件且 ≤ 50 MB（`TOO_MANY_FILES` / `PACKAGE_TOO_LARGE`）。

---

# 错误码

| 错误码 | 含义 | 处理 |
|--------|------|------|
| `UNSEAL_FAILED` | 解封失败：`Double-layer unseal failed: Incorrect decryption` | **导入成功、运行期才报**。常见原因：子包发错节点（node_pub 不匹配）、`.mgc_file` 被重命名丢后缀、包元数据被改动。核对 `distribution_index.json` 的 fingerprint 是否本机，向编排方确认包的归属 |
| `TOO_MANY_FILES` | 子包文件超 100 | 减少授予文件或拆多次密封 |
| `PACKAGE_TOO_LARGE` | 子包超 50 MB | 拆大文件后重封 |
| `MISSING_REQUIRED_FIELDS` | `ext04` 不是合法数组 | 检查 JSON；长规格用 `@file` |
| `Invalid PEM format` | node_pub 不是多行 PEM | 原样复制，保留换行 |
| `files not found in storage` | files 与 diff_3 不匹配 | `mgc_find` 核对后修正 |
| `FOLDER_CONTAINS_MGC_FILE` | 把整个目录塞进一个包再导入 | 每个 `.mgc_file` 独立导入 |

---

# MCP 工具速查

| 工具 | 用途 | 必填 |
|------|------|------|
| `mgc_save_file` | 存脚本目录 / 导入子包 | path, info_owner |
| `mgc_seal_package` | chain mode 密封 | info_owner, diff_2, output_dir, ext04 |
| `mgc_find` | 核对 diff_3 / 授权清单 | info_owner |
| `mgc_run` | 执行密封脚本 | info_type="script", info_owner, diff_3 |
| `mgc_get` | 取 node_pub | info_type="__NODE_PUB__" |
| `mgc_seal` | 单包 p2p 回传 | info_owner, output_dir, ext04 |
| `mgc_list` | 列出 metadata | — |
| `mgc_delete` | 删除条目 | info_type, info_owner |
| `mgc_open_webui` | 打开 WebUI | — |

---

# 与 p2p / free mode 的关系

```
mgc_seal_package(ext04=单个 PEM)     → p2p mode（1 个节点）
mgc_seal_package(ext04=不传)          → free mode（任意节点）
mgc_seal_package(ext04=target 数组)   → chain mode（N 个节点）
```

chain mode 是 p2p 的多节点扩展：每个子包内部仍是独立密封。可以混用——例如 chain 分发核心脚本，p2p 密封回传结果。

---

# 安全边界

MGC 保护内容机密性与节点绑定：

- 子包只对匹配私钥的节点可解
- 链路授权（`ext07` / `ext09`）被改动即解封失败
- 密封脚本的运行时行为由脚本作者负责
- **非脚本文件在子包内是明文**——所以数据/凭证不能进包，这是"不出域"要求的由来

---

# 相关技能

- **MGC Blackbox 元技能** —— p2p / free / chain 三种 mode 总览
- **密封工作流 skill** —— p2p / free mode 详细指南
- 场景化技能（后续）—— 针对具体业务的拆分方案，依赖本技能

---

# 联系

- 主仓库：https://github.com/zkeviny/MGC-Blackbox
- 问题反馈：https://github.com/zkeviny/MGC-Blackbox/issues
- 邮箱：mirgincipher@outlook.com
