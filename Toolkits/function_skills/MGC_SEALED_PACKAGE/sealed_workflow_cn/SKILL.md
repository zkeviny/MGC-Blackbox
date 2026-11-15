---
spec: usk/3.0
id: sealed-workflow-licensing-cn
version: 1.2.0
name: 工作流防盗版授权（加密交付、节点授权）
name_en: Seal and License Workflows or Skill Packages (Anti-Piracy, Node-Authorized Delivery)
description: 针对脚本销售与本地交付场景，把 Python 脚本集合密封为单节点授权的本地包。脚本保持原貌（import / 相对路径 / subprocess 均支持），MGC 1.5.2 自动密封路由；交付包无法读取、改写、二次转售，全链路零云端、零暴露。
author: MirginCipher Team
license: MIT
tags: 脚本销售, 防盗版, 加密交付, 零暴露, 工作流授权, 本地交付, 单节点授权, 密封跨脚本, 工作流自动识别, 小系统交付, 知识产品, mgc, blackbox
platform_compatibility: windows, macos, linux
mcp_tools: mgc_save, mgc_save_file, mgc_get, mgc_run, mgc_find, mgc_list, mgc_seal, mgc_seal_package, mgc_package, mgc_open_webui
requirements:
  mgc_version: ">=1.5.2"
install: pip install mgc-blackbox>=1.5.2
runtime: mgc
port: 57219
files:
  example_dir: example/
changelog:
  - version: 1.2.0
    changes:
      - 升级适配 MGC 1.5.2：纳入 ext08 工作流自动识别与密封跨脚本导入
      - 新增市场场景开篇（脚本销售 / 小系统交付 / 工作流授权 / 知识产品）
      - 新增问题-方案对照表（路径硬编码、配置依赖、依赖库未装、平台不兼容）
      - 新增错误码处理（DIFF2_MISMATCH / DEP_MISSING / PLATFORM_INCOMPAT）
      - 重写关键规则 1：从「禁止路径」改为「同包路径自动密封」
      - tags/keywords 新增：密封跨脚本、工作流自动识别、脚本销售、小系统交付、本地交付、一次一密
  - version: 1.0.0
    changes:
      - 初始版本，基于 MGC 1.5.0 介绍技能包 / 工作流文件夹的密封与授权
---

# 一句话说清楚

**卖脚本最怕发出去就被随手转发？** 把你的 Python 工作流一键密封，客户只能跑、不能读源码、不能改、不能转卖——零云端、零代码改造、5 分钟搞定。

---

# 你遇到过这些情况吗？

| # | 场景 | 痛点 |
|---|------|------|
| 场景 1 | **独立开发者卖工具脚本**：数据处理 / 爬虫 / 报表脚本，想卖几十上百份 | 卖出去一份就等于公开了——买家随手转发到群里，后续全是 0 收入 |
| 场景 2 | **付费社群的"工具包"**：知识星球 / 付费社群里给会员发专属脚本 | 会员退群后脚本照样用，甚至转手卖你的工具；社群价值被稀释 |
| 场景 3 | **乙方 / 顾问交付自动化方案**：给客户做的脚本小系统要交付源码 | 客户拿到源码后随意改、出了问题找你背锅；还可能把你的方案转卖给同行 |
| 场景 4 | **企业内部跨团队脚本授权**：数据团队写的脚本给业务团队用 | 担心业务团队改坏逻辑、泄露敏感配置；又不想每次都走审批流程 |

> **共同点：交付即授权，必须"一次一密、一节点一密"。**

---

# 为什么不用 GitHub 私有仓 / SaaS 加密 / 许可证服务器？

| 你遇到过这种情况吗？ | GitHub 私有仓库 | SaaS 加密服务 | 许可证服务器 | **MGC 密封交付** |
|---|---|---|---|---|
| 客户说"我就给同事用一下"，然后一传十 | ❌ 完全失控 | ⚠️ 取决于服务 | ⚠️ 取决于服务 | ✅ **节点绑定，多一个人都跑不起来** |
| 你需要搭服务器、维护、担心被 DDoS 吗？ | — | — | ❌ 要运维成本 | ✅ **纯本地，零运维** |
| 源码会被第三方看到吗？ | ⚠️ 平台方可见 | ❌ 服务端全可见 | ⚠️ 取决于实现 | ✅ **除了自己，谁都看不到** |
| 离线环境 / 内网客户能用吗？ | ❌ | ❌ | ❌ | ✅ **U 盘 / 邮件 / 内网随便用** |
| 月费 / 抽成成本 | 中（按人头） | 高（按调用量） | 中（按服务器） | ✅ **MGC 本身免费，不订阅不抽成** |

---

# 三大核心卖点

## 卖点 1：零改造 — 你的脚本原封不动

工作流原本怎么写就怎么写：

- `from helpers.fetch import get_weather`
- `import config`
- `Path(__file__).parent / "settings.json"`
- `subprocess.run([sys.executable, "helper.py"])`

**MGC 1.5.2 自动识别这些 import / 相对路径 / subprocess 关系**，运行时通过密封执行路由：

- ✅ 文件**不在客户磁盘落盘**
- ✅ 客户机器**没有任何路径能直接 cat 到源码**
- ✅ **不需要把脚本改造成 API 调用模式**

> 📦 **自带示例**：本技能 `example/` 文件夹里有 4 个脚本（A/B/C/D），覆盖所有可识别模式。先跑通示例，再换你自己的脚本。

## 卖点 2：一次一密 — 每个客户独立密钥

每个客户拿到**独立的 AES 密钥**：

- 密钥用**目标节点的 RSA 公钥**加密（RSA-2048）
- AES-256 加密每个脚本文件
- 客户节点没有私钥 = 拿不到内容
- 客户节点拿到内容后**无法转封**给第三方（密钥已绑定他的节点）

```
作者节点                            客户节点
─────────                           ────────
mgc_save_file(path="./workflow")    
mgc_seal_package(ext04=客户公钥)    
        │
        ▼
   加密包 (.mgc_file)
        │
        └──── 任意方式送达 ──────►   mgc_save_file(path="./received.mgc_file")
                                    mgc_run(...)
```

## 卖点 3：本地交付 — 不连任何云

- 全部加密、解密、运行都在**本地**完成
- MGC 不连任何云、没有任何外部端点
- 加密包可邮件、U 盘、IM、GitHub Releases、私有网盘**任意方式**送达
- 即使加密包被截获，没有对应节点的私钥也无法解密
- 加密包仅在授权节点加密运行，脚本及 print 皆无明文落地，需指定生成结果物

---

# 已验证的真实场景

> MGC 密封交付已经过企业级工作流交付场景实践验证，不是实验室玩具。

- ✅ 乙方团队向客户交付数据自动化工作流，代码全程不落地
- ✅ 独立开发者密封销售工具脚本，单份授权独立管理
- ✅ 企业内部跨团队脚本授权，防止敏感配置和核心逻辑泄露

---

# ⚡ 30 秒快速体验（自己节点上跑通闭环）

先别急着给客户用，在自己机器上跑通密封 → 导入 → 运行的完整闭环：

```bash
# 一键跑通（推荐）
python example/run_demo.py
```

或者手动：

```python
# 1. 把工作流文件夹存入 MGC
mgc_save_file(path="./example", info_owner="demo", diff_2="demo")

# 2. 用自己的 node_pub 密封（模拟给"自己"授权）
my_pub = mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")
mgc_seal_package(info_owner="demo", diff_2="demo", ext04=my_pub)

# 3. 把生成的 .mgc_file 重新导入（模拟客户收到包后导入）
mgc_save_file(path="./demo.mgc_file")

# 4. 黑盒运行 D（同时驱动 B + C）
mgc_run(
    info_type="script", info_owner="demo",
    diff_1="demo", diff_2="demo", diff_3="script_d.py",
)
# → {"pid": 12345, "status": "started"}
```

跑通后桌面应该出现：

- ✅ `~/Desktop/txt1.txt`（B 写入）
- ✅ `~/Desktop/txt2.txt`（C 写入）
- ✅ `~/Desktop/txt2_via_a.txt`（C 调 A 写入）
- ✅ `~/Desktop/combined.txt`（D 汇总写入）

> Linux 无 `~/Desktop` 时自动回退到 `~`。

**跑通了？** 你已经掌握了密封交付的核心流程。接下来只需要把客户的公钥换进去，就能生成专属授权包。

---

# 关于费用

- **MGC Blackbox 本身免费**，免费使用，加密层出于用户安全考虑不提供源码，无月费、无抽成、无使用限制
- **本技能免费**，封装了密封交付的最佳实践和详细指引
- **你卖脚本赚的钱全是你的**，MGC 不抽一分钱

> 为什么免费？我们相信基础安全工具就应该是免费的公共品。

---

# 前置条件

- **Python 3.10+**（macOS 14+ Apple Silicon 不支持 Python 3.12）
- **MGC Blackbox ≥ 1.5.2**（关键：工作流自动识别 + subprocess 字面量列表运行时路由均在 1.5.2 完整支持）
- 安装：`pip install mgc-blackbox`
- 启动：`mgc`（API 在 `http://127.0.0.1:57219`，WebUI 在 `http://127.0.0.1:57218`）

---

# 三步交付（作者侧）

## 步骤 1：把工作流文件夹存入 MGC

```
my_workflow/
├── manifest.json
├── SKILL.md
├── run.py
├── helpers/
│   ├── fetch.py
│   └── parse.py
└── config/
    └── settings.json
```

```python
mgc_save_file(
    path="./my_workflow",
    info_owner="my_workflow",
    diff_2="my_workflow",
)
```

**这一步 MGC 会自动**：
- 解析每个脚本的 `argparse` 写入 `ext02`
- 扫描 import 写入 `ext05`（依赖列表）
- 推断 `ext06`（平台列表）
- 构建 `ext08`（跨脚本调用图）

> 💡 **小建议**：本技能包随附了 `example/` 文件夹，先用它跑通存入 → 密封（用自己的公钥测试） → 导入 → 运行的完整流程，再替换成你自己的工作流。

## 步骤 2：拿到客户的 RSA 公钥

```python
# 客户在他自己的机器上执行（WebUI 或 MCP）
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
# 客户把这段 PEM 公钥发给你（公钥非密，可任意渠道传输）
```

> **WebUI 取法（推荐）**：WebUI → skill 页面 → Settings 下拉 → Node Public Key → 复制多行 PEM。
> **注意**：`ext04` 必须含真实换行符 `\n`，不要单行拼接。

## 步骤 3：一键密封给该客户

```python
mgc_seal_package(
    info_owner="my_workflow",
    diff_2="my_workflow",
    ext04=node_pub,        # 客户的 PEM 公钥
)
# → 生成 .mgc_file 加密包
```

把 `.mgc_file` 通过任意方式发给客户。

---

# 三步接收（客户侧）

## 步骤 1：导入加密包

```python
mgc_save_file(path="./received.mgc_file")
# MGC 把加密包拆解为本地条目
```

## 步骤 2：浏览包内结构

```python
# 列出包内所有条目（仅元信息，无明文）
mgc_find(info_owner="my_workflow", diff_2="my_workflow")

# 读 manifest（明文，了解工作流结构）
mgc_get(info_type="file", info_owner="my_workflow", diff_2="my_workflow")

# 读 SKILL.md（明文，按里面的指引调用对应脚本）
mgc_get(info_type="file", info_owner="my_workflow", diff_2="my_workflow", diff_3="SKILL.md")
```

## 步骤 3：黑盒运行

```python
mgc_run(info_owner="my_workflow", diff_2="my_workflow")
# → {"pid": 12345, "status": "started"}
# AI 只得到启动状态，永远看不到脚本源码
```
**特别注意**出于黑盒执行的需要，MGC 不会返回任何明文及可能暴露认知的信息，因此工作流/脚本的输出结果需要显性指定文件及路径，或写入数据库或 MGC 本身。

---

# 三条关键规则（务必遵守）

## 规则 1（同包路径 OK，跨包用 API）

**同一文件夹包内的脚本可以随意用 `import / 相对路径 / subprocess`** —— MGC 1.5.2 会自动识别并在运行时密封路由，**不需要改成 API 调用**。

**跨文件夹包（不同 `info_owner + diff_2`）的脚本调用**才需要用 MGC API：

```python
import os, requests

with open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")) as f:
    MGC_TOKEN = f.read().strip()

def call_remote_script(info_owner, ext02=None):
    return requests.post(
        "http://127.0.0.1:57219/api/mgc/sensitive/get",
        headers={"X-MGC-Token": MGC_TOKEN},
        json={
            "info_type": "script",
            "info_owner": info_owner,
            "diff_1": info_owner,
            "action": "run",
            "ext01": "python",
            "ext02": ext02,
        },
    ).json()
```

## 规则 2：SKILL.md 是明文

SKILL.md 必须明文 —— 它是客户的**路由说明书**：哪个脚本在什么场景调用、按什么顺序、传什么参数。没有它客户根本无法使用。

> 这是公开 API 契约，不是实现细节。**核心逻辑必须放在脚本里**，下一条规则说明。

## 规则 3：核心算法放脚本，别放提示词

SKILL.md 和提示词都是**明文**，客户能读。**因此**：

| ✅ 应该这样 | ❌ 不要这样 |
|------------|------------|
| 在 `run.py` 里写核心算法 | 把核心算法写在 SKILL.md 里 |
| SKILL.md 只写"何时调用 run.py，传哪些参数" | SKILL.md 写"完整业务流程是这样…（含细节）" |
| 业务规则、阈值、公式 → 都在脚本中 | 业务规则写在 prompt 里 |

> 提示词是客户能看到的"说明书"，**算法是你卖的"产品"** —— 必须把产品锁进脚本里。

---

# 可识别的跨脚本写法（完整对照表）

> 当你用 `mgc_save_file` 保存一个文件夹时，MGC 会对每个脚本做**静态解析**，构建跨脚本调用图。运行时 MGC 拦截这些模式，通过密封执行路由 —— **磁盘无文件、无明文、无需重写代码**。

| 模式 | 代码示例 | 能否识别 |
|------|---------|---------|
| `from` import | `from config import DEFAULT_CITY` | ✅ |
| `from` import 带别名 | `from helpers.fetch import get_weather as gw` | ✅ |
| 普通 `import` | `import helpers.parse` | ✅ |
| `Path` 相对路径 | `Path(__file__).parent / "config.py"` | ✅ |
| `open()` 相对路径 | `open("config.json")` 调用同级文件 | ✅ |
| subprocess + 相对路径 | `subprocess.run([sys.executable, str(Path(__file__).parent / "config.py"), ...])` | ✅ — 仅当调用方和被调用方一起被存进 MGC 作为同一个工作流包 |
| subprocess 字面量列表 | `subprocess.run(['helper.py', '--x'])`（或 `from subprocess import run; run([...])`） | ✅ — 同样要求在同一包内；运行时会以密封子进程方式执行 helper |
| 动态 import | `importlib.import_module(module_name)` | ❌ 只能静态解析字符串字面量；运行时通常会报 `ModuleNotFoundError` |
| 绝对路径 | `open("/Users/alice/scripts/config.py")` | ❌ 绝对路径不可移植，无法密封。改用 MGC location 寻址 |
| 跨子目录相对路径 | `subprocess.run([..., "../y.py"])` 或 `Path(__file__).parent.parent / "y.py"` 当 `..` 跳出调用方所在目录 | ❌ 见下方"作用域" |
| 函数级调用（无 import） | 在另一个文件里定义的函数，仅按引用调用（没有 `import` / `from-import` / 字面量 `Path` 引用） | ❌ 解析器只检查通过上述常规形式可达的字符串字面量 |

**作用域（1.5.2）：**

- ✅ 跨脚本调用 **仅在同一个文件夹包内**被识别（调用方和被调用方的 `info_owner + diff_2` 必须一致）。
- ❌ **同文件夹、不同子目录**（例如 `pkg_root/CROSS-FOLDER/x.py → ../y.py`）—— 暂无法识别（请等待后续版本）。
- ❌ **函数级调用**没有以 `import` / `from-import` / `Path` 字面量出现在源码中 —— 不能识别。

**关键不变量：**

- 每个脚本的 `argparse` 是独立的 —— driver 的参数进 driver 的，每个 helper 的参数进 helper 自己的。
- `Path(__file__).parent / "x.py"` 在 macOS、Linux（POSIX）和 Windows（`\` 分隔符）下都能正确解析。
- subprocess 输出正常流动 —— `capture_output=True, text=True` 可用，因为被启动的 helper 是真实的 Python 解释器，带 UTF-8 解码。

**限制。** 跨脚本调用只能在两个脚本**一起被保存**时生效。要在不同包之间编排脚本，请使用 MGC REST API 模式（参考前面"规则 1"中的 `call_remote_script` 示例），传入目标脚本的 MGC location（`info_owner`）。

---

# 错误码与排查

| 错误码 | 含义 | 处理方式 |
|--------|------|----------|
| `DIFF2_MISMATCH` | 脚本用了 `from-import` 但**目标脚本不在同一文件夹包内** | 把两个脚本放进同一个 `mgc_save_file` 包；或改用 MGC API 调用 |
| `DEP_MISSING` | 依赖未在客户机器安装 | `pip install <缺失的依赖>`（MGC 不会自动装） |
| `PLATFORM_INCOMPAT` | 客户的 OS 不在支持列表 | 在支持的平台重新保存，或扩展代码的平台分支 |
| `args_not_recognized` | `argparse` 解析失败 | 检查 `add_argument` 写法，确保有字面量 `default=` |
| `dynamic_args_detected` | 默认值含动态计算（如 `datetime.now()`） | 改用字面量默认值，或手动传入 |
| `Invalid PEM format` | 公钥不是多行 PEM 格式 | 从 `mgc_get(info_type='__NODE_PUB__')` 原样拷贝，保留 `\n` |

---

# 适用与不适用（边界）

| ✅ 适合用本技能 | ❌ 不适合用本技能 |
|----------------|-------------------|
| 销售 / 授权 Python 小工具脚本 | 开源脚本（用 GitHub 即可） |
| 付费社群 / 知识产品的工具包 | 大型 SaaS 产品（用云方案） |
| 乙方交付企业内部小系统 | 客户机器已有完整源码环境的二次开发 |
| 企业内部跨团队脚本授权 | 单机自用脚本（无需密封） |

---

# MCP 工具速查

| 工具 | 用途 | 必填参数 |
|------|------|----------|
| `mgc_save_file` | 存本地文件夹（自动识别工作流） | path, info_owner |
| `mgc_seal_package` | 加密包给目标节点 | info_owner, ext04（PEM） |
| `mgc_save` | 存单脚本（不入包） | info_type, info_owner, content |
| `mgc_seal` | 单脚本密封 | info_owner, ext04（PEM） |
| `mgc_run` | 黑盒执行 | info_type="script", info_owner, diff_1 |
| `mgc_get` | 取值 / 取 node_pub | info_type, info_owner |
| `mgc_find` | 模糊搜索 | info_owner, match_mode |
| `mgc_list` | 列出全部 metadata | — |
| `mgc_package` | 同信任区内的明文打包 | info_owner |
| `mgc_open_webui` | 打开 WebUI | — |

---

# 相关技能

- **MGC Blackbox（跨设备脚本授权）** —— 单脚本密封（更轻量）
- **MGC Blackbox 元技能** —— MGC 全部能力的完整参考

---

# 联系
- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系邮箱**：mirgincipher@outlook.com