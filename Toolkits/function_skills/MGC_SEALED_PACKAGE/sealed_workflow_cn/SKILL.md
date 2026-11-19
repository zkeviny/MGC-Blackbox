---
spec: usk/3.0
id: sealed-workflow-licensing-cn
version: 1.3.0
name: 工作流防盗版授权（加密交付、节点授权）
name_en: Seal and License Workflows or Skill Packages (Anti-Piracy, Node-Authorized Delivery)
description: 针对脚本销售与本地交付场景，把 Python 脚本集合密封为本地包。脚本保持原貌（import / 相对路径 / subprocess 均支持），MGC 1.5.4 自动密封路由；双层加密 + 链路授权绑定来源节点，支持单节点授权与自由模式公开分发，全链路零云端。
author: MirginCipher Team
license: MIT
tags: 脚本销售, 防盗版, 加密交付, 零暴露, 工作流授权, 本地交付, 单节点授权, 自由模式分发, 链路授权, 密封跨脚本, 工作流自动识别, 小系统交付, 知识产品, mgc, blackbox
platform_compatibility: windows, macos, linux
mcp_tools: mgc_save, mgc_save_file, mgc_get, mgc_run, mgc_find, mgc_list, mgc_seal, mgc_seal_package, mgc_package, mgc_delete, mgc_open_webui, mgc_skill
requirements:
  mgc_version: ">=1.5.4"
install: pip install mgc-blackbox>=1.5.4
runtime: mgc
port: 57219
files:
  example_dir: example/
changelog:
  - version: 1.3.0
    changes:
      - 升级适配 MGC 1.5.4：密封机制改为双层加密（ext09 模式字段 + ext07 来源绑定）
      - 重写卖点 2：从单层 RSA 绑定改写为双层加密 + 链路授权，并说明自由模式（省略 ext04）
      - 新增自由模式公开分发场景（技能市场 / 公开演示）
      - 全部密封示例补 output_dir（1.5.4 起为必填，无桌面回退），并写清产物目录结构
      - 修正跨脚本可识别范围：同包跨子目录引用 1.5.4 起支持；新增计算式绝对路径 subprocess
      - 新增 ext10 运行兼容性徽章与致命路径检查说明
      - 新增错误码 AMBIGUOUS_SCRIPT / NO_SCRIPT_TO_SEAL / MULTIPLE_MATCHES
      - 更正 mgc_run 参数：diff_1 可选，diff_3 为定位单个脚本最可靠方式
      - 新增单脚本胶囊导出与双路导入说明（含同 info_owner 覆盖源记录的警告）
      - 移除失效的 run_demo.py 引用，改为完整的手动闭环步骤
      - 新增「试一次：用 example/ 做一次自由模式密封」实测走查（无需第二节点与公钥交换）
      - 更正导入身份语义：包内记录自带 info_owner，导入时传入值仅作必填校验；同节点同 owner 会覆盖源记录
      - 规范化措辞：去 AI 化表述，安全边界改写为来源绑定与责任归属
      - tags/keywords 新增：自由模式分发、链路授权、公开分发
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

**卖脚本最怕发出去就被随手转发？** 把你的 Python 工作流密封成带来源绑定的本地包 —— 授权节点能跑、源码全程加密、但无法修改你的来源公钥，改了就废、也转不出去。零云端、零代码改造。

---

# 你遇到过这些情况吗？

| # | 场景 | 痛点 |
|---|------|------|
| 场景 1 | **独立开发者卖工具脚本**：数据处理 / 爬虫 / 报表脚本，想卖几十上百份 | 卖出去一份就等于公开了——买家随手转发到群里，后续全是 0 收入 |
| 场景 2 | **付费社群的"工具包"**：知识星球 / 付费社群里给会员发专属脚本 | 会员退群后脚本照样用，甚至转手卖你的工具；社群价值被稀释 |
| 场景 3 | **乙方 / 顾问交付自动化方案**：给客户做的脚本小系统要交付源码 | 客户拿到源码后随意改、出了问题找你背锅；还可能把你的方案转卖给同行 |
| 场景 4 | **企业内部跨团队脚本授权**：数据团队写的脚本给业务团队用 | 担心业务团队改坏逻辑、泄露敏感配置；又不想每次都走审批流程 |
| 场景 5 | **公开分发 / 技能市场上架**：希望任意 MGC 节点都能安装运行 | 需要一个不指定具体节点的通用安装包，同时保证源码不随包流出 |

> **共同点：交付即授权 —— 每个授权对象一次一密，包内还锁住来源。**

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

**MGC 1.5.4 自动识别这些 import / 相对路径 / subprocess 关系**，运行时通过密封执行路由：

- ✅ 文件**不在客户磁盘落盘**
- ✅ 客户机器**没有任何路径能直接 cat 到源码**
- ✅ **不需要把脚本改造成 API 调用模式**
- ✅ 1.5.4 起**同包内跨子目录**的引用也能识别（`from helpers.fetch import ...`、`Path(__file__).resolve().parent.parent / "y.py"`）

> 📦 **自带示例**：本技能 `example/` 文件夹里有 4 个脚本（A/B/C/D），覆盖所有可识别模式。先跑通示例，再换你自己的脚本。

## 卖点 2：一次一密 — 每个客户独立密钥

**MGC 1.5.4 起密封是双层加密**：来源公钥也加入加解密

带来的直接结果：

- p2p 模式下，目标节点没有匹配的私钥 → 拿不到内容
- **改动 `ext07` 或 `ext09`（哪怕只改一个空格）→ 整个包不可还原**（链路授权，p2p 与自由模式同样生效）
- p2p 接收方不持有可用于再转封的来源密钥 → 无法把原包原样交给第三方

```
作者节点                            客户节点
─────────                           ────────
mgc_save_file(path="./workflow")    
mgc_seal_package(ext04=客户公钥,    
                 output_dir=...)     
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

# 自由模式：面向公开分发的新选项

MGC 1.5.4 新增**自由模式（free mode）** —— 密封时**省略 `ext04`**：

| | p2p 模式（默认） | 自由模式 |
|---|---|---|
| 怎么密封 | 传 `ext04=目标节点 PEM` | **不传** `ext04` |
| 谁能解封运行 | 只有持有对应私钥的那个节点 | **任意 MGC 1.5.4+ 节点** |
| 源码可见吗 | 不可见 | 不可见（同样只在内解密） |
| 适合场景 | 单客户授权、私有交付 | **技能市场上架、公开演示、通用安装包** |

自由模式用 MGC 的共享默认公钥包装，因此**任何装了 MGC 1.5.4+ 的机器都能装上并运行**，而源码在接收端始终不解密落地。

> ⚠️ 自由模式包可被任意节点运行 —— 适合"给所有人一份可运行的试用版"，**不适合**需要按客户单独限制的场景。

## 试一次：用 example/ 做一次自由模式密封

本技能自带的 `example/` 就是一份现成的工作流（4 个脚本 + README），可以直接拿来跑通自由模式全链路。**无需第二个节点、无需公钥交换**。

```python
# 1 · 存入 MGC（工作流文件夹）
mgc_save_file(path="./example", info_owner="demo_free", diff_2="example")
# → 5 条记录（4 脚本 + README），自动生成 ext08 调用图

# 2 · 自由模式密封 —— 注意：不传 ext04
mgc_seal_package(
    info_owner="demo_free",
    diff_2="example",
    output_dir="./_demo_out",   # 1.5.4 起必填
)
# → _demo_out/example_delivery/{ example.mgc_file, README.md }

# 3 · 导入刚生成的包
mgc_save_file(
    path="./_demo_out/example_delivery/example.mgc_file",
    info_owner="demo_free",
    diff_2="example",
)
# → 5 条密文记录（ext03 已填充，ext09="free mode"）

# 4 · 运行 driver（同时驱动 B + C）
mgc_run(
    info_type="script",
    info_owner="demo_free",
    diff_2="example",
    diff_3="script_d.py",
)
# → {"status": "started"}
```

**验证结果**（桌面出现 4 个文件即全链路贯通）：

| 文件 | 写入方 | 内容 |
|------|--------|------|
| `~/Desktop/txt1.txt` | B | 从 A import 到的问候语 |
| `~/Desktop/txt2.txt` | C | C 自身摘要 |
| `~/Desktop/txt2_via_a.txt` | C 调 A | A 子进程写入的问候语 |
| `~/Desktop/combined.txt` | D | B 与 C 的汇总 |

> Linux 无 `~/Desktop` 时自动回退到 `~`。

**再验证"源码读不到"** —— 导入后取脚本内容：

```python
mgc_get(info_type="script", info_owner="demo_free", diff_2="example", diff_3="config_a.py")
# → 返回一长串 Base64 密文，看不到任何 Python 源码
```

此时 `mgc_run` 依然能正常跑 —— **能跑，但读不到源码**，这就是自由模式的核心特征。

> ⚠️ **两条实测确认的注意事项**
> 1. **第 3 步的 `info_owner` 沿用密封时的值**（本例 `demo_free`）。包内记录自带 `info_owner`，导入时传的值不生效 —— 即使传别的名字，查询仍要用包内的 `demo_free`。
> 2. **同节点 + 同 `info_owner` 会覆盖源记录**。想同时保留明文与密文两套，请用不同 `info_owner` 存盘，或改用另一台机器导入。

---

# 已验证的真实场景

> MGC 密封交付已经过企业级工作流交付场景实践验证，不是实验室玩具。

- ✅ 乙方团队向客户交付数据自动化工作流，代码全程不落地
- ✅ 独立开发者密封销售工具脚本，单份授权独立管理
- ✅ 企业内部跨团队脚本授权，防止敏感配置和核心逻辑泄露
- ✅ 自由模式包分发到公开渠道，接收端导入即用

---

# ⚡ 30 秒快速体验（自己节点上跑通闭环）

先别急着给客户用，在自己机器上跑通密封 → 导入 → 运行的完整闭环。

> 💡 **想跳过公钥交换？** 直接看上面「试一次：用 example/ 做一次自由模式密封」—— 自由模式不需要 `ext04`，一步到位。

```python
# 1. 把工作流文件夹存入 MGC
mgc_save_file(path="./example", info_owner="demo", diff_2="demo")

# 2. 用自己的 node_pub 密封（模拟给"自己"授权）
my_pub = mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")
mgc_seal_package(
    info_owner="demo",
    diff_2="demo",
    ext04=my_pub,
    output_dir="./_demo_out",      # 1.5.4 起必填
)

# 3. 把生成的 .mgc_file 重新导入（模拟客户收到包后导入）
mgc_save_file(
    path="./_demo_out/demo_delivery/demo.mgc_file",
    info_owner="demo",             # 必填；实际落库身份取包内的值
    diff_2="demo",
)

# 4. 黑盒运行 D（同时驱动 B + C）
mgc_run(
    info_type="script", info_owner="demo",
    diff_2="demo", diff_3="script_d.py",
)
# → {"pid": 12345, "status": "started"}
```

> 💡 `diff_1` 在 1.5.4 起是可选的；`diff_3`（脚本在包内的相对路径）是定位单个脚本最可靠的方式。

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

# 问题-方案对照表

| # | 用户痛点 | MGC 1.5.4 方案 |
|---|---------|----------------|
| P1 | 客户能直接 `cat` 我的 `.py` 文件 | 全量 AES-256 加密，**磁盘无明文** |
| P2 | 客户把脚本转发给同事 | AES 密钥由接收方节点 RSA 包装 —— **换台节点就解不开** |
| P3 | 多脚本用 `import`，客户机器路径又不一样 | `ext08` 自动识别 `import / Path / subprocess`，**运行时密封路由**，不依赖路径 |
| P4 | 客户改了我的代码就不付费了 | 链路授权 —— **`ext07` / `ext09` 一改即不可还原** |
| P5 | 我得写"使用手册"，客户还装不上依赖 | `ext05` 自动推断依赖列表、`ext06` 推断平台、`ext10` 标记运行兼容性 |
| P6 | 每个客户都要重新封一次，太麻烦 | `mgc_seal_package` 一次调用完成文件夹级密封 + 节点绑定 |
| P7 | 我想在技能市场发一个通用包 | **自由模式** —— 不传 `ext04`，任意 MGC 1.5.4+ 节点可运行 |

---

# 前置条件

- **Python 3.10+**（macOS 14+ Apple Silicon 不支持 Python 3.12）
- **MGC Blackbox ≥ 1.5.4**（关键：双层加密 + 链路授权 + 自由模式 + 同包跨子目录识别均为 1.5.4 能力）
- 安装：`pip install mgc-blackbox`
- 启动：`mgc`（API 在 `http://127.0.0.1:57219`，WebUI 在 `http://127.0.0.1:57218`）

> ⚠️ 1.5.4 起 `mgc_seal` / `mgc_seal_package` / `mgc_package` **必须传 `output_dir`**（绝对路径），没有桌面回退 —— 桌面位置各平台不一致，MGC 不再替你猜。

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
- 静态检查运行兼容性写入 `ext10`（`supported` / `unsupported` 徽章）

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

> 💡 **自由模式不需要这一步** —— 省略 `ext04` 即可产出任意 1.5.4+ 节点可运行的包。

## 步骤 3：一键密封给该客户

```python
mgc_seal_package(
    info_owner="my_workflow",
    diff_2="my_workflow",
    ext04=node_pub,          # 客户的 PEM 公钥；自由模式则省略此行
    output_dir="./delivery", # 1.5.4 起必填
)
```

**产物目录结构**：

```
delivery/
└── my_workflow_delivery/
    ├── my_workflow.mgc_file   # zip：密封脚本 + MGCFILE.json 清单
    └── README.md               # usk/3.0 yaml + 导入指引
```

把 `my_workflow_delivery/` 整个目录通过任意方式发给客户。

> 🔒 **自密封警告**：如果 `ext04` 填的是**你自己**的 node_pub，MGC 会提示"本机密封" —— 存回 MGC 时明文记录会被密文覆盖，且不可逆。演示用请单独准备一个测试节点。

---

# 三步接收（客户侧）

## 步骤 1：导入加密包

```python
mgc_save_file(
    path="./my_workflow_delivery/my_workflow.mgc_file",
    info_owner="my_workflow",
    diff_2="my_workflow",
)
# MGC 把加密包拆解为本地条目
```

> 💡 **包内记录自带 `info_owner`** —— 导入时传的 `info_owner` 只是必填校验，不改变落库身份。后续 `mgc_get` / `mgc_run` 要用**包内的那个 `info_owner`**（本例即 `my_workflow`）。
> ⚠️ **同节点 + 同 `info_owner` 会覆盖源记录** —— 在作者自己的机器上回灌同一个包，明文会被密文替换（不可逆）。要在同一台机器上同时保留明文与密文，请让包从另一个 `info_owner` 存盘，或换一台机器导入。

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
# 调用方只得到启动状态，脚本源码始终加密
```

**特别注意**出于黑盒执行的需要，MGC 不会返回任何明文及可能暴露认知的信息，因此工作流/脚本的输出结果需要显性指定文件及路径，或写入数据库或 MGC 本身。

> 💡 定位单个脚本时用 `diff_3`（脚本在包内的相对路径）最可靠：`mgc_run(info_owner=..., diff_2=..., diff_3="script/main.py")`。

---

# 单脚本交付：胶囊导出与双路导入

只需要交付**一个脚本**时，用 `mgc_seal` 更轻量。

## 导出胶囊

```python
mgc_seal(
    info_owner="my_script",
    ext04=node_pub,           # 自由模式则省略
    output_dir="./delivery",  # 1.5.4 起必填
)
# → delivery/my_script_20260929_120000/sealed_capsule.json
```

`sealed_capsule.json` 是**自描述**的 JSON —— 里含 `info_type` / `info_owner` / `diff_*` / `ext03` / `ext07` / `ext09` / 密文内容，接收端导入时不需要手动挑字段。

## 导入（两条路，任选其一）

| 路径 | 怎么导入 | 需要 `info_type` 吗 |
|------|---------|------------------|
| **A · 交接文件（推荐）** | `mgc_save_file(path='<capsule.json>', info_owner='<你的 owner>')` | **不需要** —— 从胶囊自动推断 |
| **B · 传 JSON 内容** | `mgc_save(content=<整段胶囊 JSON>, info_type='script', info_owner='<你的 owner>')` | **需要** —— 必须显式写 `info_type="script"` |

> ⚠️ 走路径 B 时**不要**再单独传 `ext03` / `ext07` / `ext09` —— 传整段 JSON 时 MGC 会自动提取全部 ext 字段。
> 💡 **胶囊自带 `info_owner`** —— 路径 A 导入时传的 `info_owner` 只作必填校验，实际落库身份取胶囊内的值；路径 B 则以你传入的 `info_owner` 为准（传空则回落胶囊内的值）。
> ⚠️ **同节点 + 同 `info_owner` 会覆盖源记录** —— 与源相同的 `info_owner` 在目标节点会替换掉原来的明文记录（不可逆）。要保留两套，请用不同的 `info_owner`。

---

# 三条关键规则（务必遵守）

## 规则 1（同包路径 OK，跨包用 API）

**同一文件夹包内的脚本可以随意用 `import / 相对路径 / subprocess`** —— MGC 1.5.4 会自动识别并在运行时密封路由，**不需要改成 API 调用**（含 1.5.4 起支持的同包跨子目录引用）。

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
| **同包跨子目录 import** | `from helpers.fetch import get_weather`（`helpers/` 是子目录） | ✅ **1.5.4 新增** |
| **同包跨子目录 `Path` 引用** | `Path(__file__).resolve().parent.parent / "y.py"` | ✅ **1.5.4 新增** |
| **subprocess 计算式绝对路径** | `subprocess.run([sys.executable, str(base_dir / "y.py")])` | ✅ **1.5.4 新增** — 目标脚本名须在包内唯一 |
| 动态 import | `importlib.import_module(module_name)` | ❌ 只能静态解析字符串字面量；运行时通常会报 `ModuleNotFoundError` |
| 绝对路径 | `open("/Users/alice/scripts/config.py")` | ❌ 绝对路径不可移植，无法密封。改用 MGC location 寻址 |
| subprocess 字面量里的 `..` | `subprocess.run([..., "../y.py"])`（`..` 跳出调用方目录） | ❌ 改用计算式绝对路径 `Path(__file__).resolve().parent.parent / "y.py"` |
| 函数级调用（无 import） | 在另一个文件里定义的函数，仅按引用调用（没有 `import` / `from-import` / 字面量 `Path` 引用） | ❌ 解析器只检查通过上述常规形式可达的字符串字面量 |

**作用域（1.5.4）：**

- ✅ 跨脚本调用 **在同一文件夹包内**被识别（调用方和被调用方的 `info_owner + diff_2` 必须一致）。
- ✅ **1.5.4 起同包内跨子目录的引用可被识别** —— 包括 `from helpers.x import y` 和 `Path(__file__).resolve().parent.parent / "y.py"`。
- ✅ **1.5.4 起跨不同保存文件夹的字面量调用也能识别**（要求被调脚本文件名全局唯一）。⚠️ 此时调用方需在**被调方存盘后重新保存**，以重建依赖图。
- ❌ **函数级调用**没有以 `import` / `from-import` / `Path` 字面量出现在源码中 —— 不能识别。

**关键不变量：**

- 每个脚本的 `argparse` 是独立的 —— driver 的参数进 driver 的，每个 helper 的参数进 helper 自己的。
- `Path(__file__).parent / "x.py"` 在 macOS、Linux（POSIX）和 Windows（`\` 分隔符）下都能正确解析。
- subprocess 输出正常流动 —— `capture_output=True, text=True` 可用，因为被启动的 helper 是真实的 Python 解释器，带 UTF-8 解码。

**运行兼容性徽章（`ext10`）：**

每个脚本在存入时会被静态检查能否在 MGC 内运行，结果以 `mgc_run` 徽章（`supported` / `unsupported`）显示在列表与详情视图。

- `unsupported` 的含义：脚本里有**致命路径检查**（例如 `if not Path(...).exists(): sys.exit(1)`），会在 MGC 拦截路由生效**之前**就退出。
- 改法：把路径检查改成"路径不存在时给出提示并走降级分支"，而不是直接 `sys.exit(1)`。

**限制。** 跨脚本调用只能在两个脚本**一起被保存**时生效。要在不同包之间编排脚本，请使用 MGC REST API 模式（参考前面"规则 1"中的 `call_remote_script` 示例），传入目标脚本的 MGC location（`info_owner`）。

---

# 错误码与排查

| 错误码 | 含义 | 处理方式 |
|--------|------|----------|
| `MISSING_REQUIRED_FIELDS` | `mgc_seal` / `mgc_seal_package` 缺少必填参数 | 1.5.4 起 `output_dir` **必填**；p2p 模式还需 `ext04`（自由模式省略 `ext04`） |
| `DIFF2_MISMATCH` | 脚本用了 `from-import` 但**目标脚本不在同一文件夹包内** | 把两个脚本放进同一个 `mgc_save_file` 包；或改用 MGC API 调用 |
| `DEP_MISSING` | 依赖未在客户机器安装 | `pip install <缺失的依赖>`（MGC 不会自动装） |
| `PLATFORM_INCOMPAT` | 客户的 OS 不在支持列表 | 在支持的平台重新保存，或扩展代码的平台分支 |
| `AMBIGUOUS_SCRIPT` | `mgc_run` 的 `diff_3` 匹配到多个脚本 | 改用更完整的 `diff_3`（含子目录，如 `script/main.py`） |
| `NO_SCRIPT_TO_SEAL` | 密封时没找到可密封的脚本 | 确认脚本已存入 MGC，且 `info_owner` / `diff_2` 与存入时一致 |
| `MULTIPLE_MATCHES` | 查询条件命中多条记录 | 补全 `diff_2` / `diff_3` 缩小范围 |
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
| **技能市场 / 公开分发通用安装包**（自由模式） | **需要按客户单独限制的场景**（自由模式任何节点都能跑） |

---

# 与其他方案对比

| 维度 | GitHub 私有仓库 | SaaS 加密服务 | 许可证服务器 | **MGC 密封交付** |
|------|----------------|---------------|-------------|-----------------|
| 需要上云 | 是 | 是 | 是 | **否** |
| 月费 | 中 | 高 | 中 | **无** |
| 防止源码泄露 | ❌ 私有但可见 | ⚠️ 取决于服务 | ❌ 服务端可见 | ✅ **完全不可见** |
| 防止转卖 | ❌ | ⚠️ 取决于服务 | ⚠️ 取决于服务 | ✅ **节点绑定，无法转卖** |
| 离线交付 | ❌ | ❌ | ❌ | ✅ **任意方式** |
| 适合小系统 | ⚠️ | ❌ 沉重 | ⚠️ 沉重 | ✅ **轻量** |

---

# 安全边界

MGC 保护的是**内容机密性**，不是运行时行为：

- 数据静态加密，密封源码仅在执行节点内存中解密，不落盘
- 密封后脚本的运行时行为由**脚本作者本人负责** —— MGC 无法担保作者的可信度
- 导入前请通过可信渠道核对来源节点的公钥；链路授权可发现来源标识被篡改

---

# MCP 工具速查

| 工具 | 用途 | 必填参数 |
|------|------|----------|
| `mgc_save_file` | 存本地文件夹（自动识别工作流）/ 导入 `.mgc_file` / 导入胶囊 | path, info_owner |
| `mgc_seal_package` | 加密包给目标节点 | info_owner, diff_2, **output_dir**（p2p 另需 ext04） |
| `mgc_save` | 存单脚本（不入包）/ 传胶囊 JSON | info_type, info_owner, content |
| `mgc_seal` | 单脚本密封（导出胶囊） | info_owner, **output_dir**（p2p 另需 ext04） |
| `mgc_run` | 黑盒执行 | info_type="script", info_owner（`diff_3` 定位单个脚本最可靠） |
| `mgc_get` | 取值 / 取 node_pub | info_type, info_owner |
| `mgc_find` | 模糊搜索 | info_owner, match_mode |
| `mgc_list` | 列出全部 metadata | — |
| `mgc_package` | 同信任区内的明文打包 | info_owner, **output_dir** |
| `mgc_delete` | 删除已存条目（有确认流程） | info_type, info_owner |
| `mgc_open_webui` | 打开 WebUI | — |
| `mgc_skill` | 读取 MGC 技能文档 | — |

---

# 相关技能

- **MGC Blackbox（跨设备脚本授权）** —— 单脚本密封（更轻量）
- **MGC Blackbox 元技能** —— MGC 全部能力的完整参考

---

# 联系
- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系邮箱**：mirgincipher@outlook.com