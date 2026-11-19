# 工作流与技能包密封授权协作（Collaboration Management）

本文档用于指导数据分析师在 **MGC Blackbox ≥ 1.6.0** 中安全地将工作流和技能包密封授权给其他节点，实现"可用不可读、可运行不可转卖"的跨团队/跨组织协作。

所有敏感操作必须由用户明确授权后才能进行。

---

# 一、为什么需要密封授权协作

数据分析工作流中常见的协作痛点：

| 场景 | 痛点 | MGC 解决方案 |
|------|------|-------------|
| 数据团队把分析工作流给业务团队 | 不想让业务团队看到源码、改逻辑 | 工作流密封后对方只能运行，不能读取 |
| 乙方分析师交付分析方案给客户 | 客户拿到源码后转卖给同行 | AES 密钥绑定客户节点，无法转封 |
| 跨部门共享分析方法论 | 担心核心算法泄露 | 整个工作流一次性密封，核心算法锁在脚本里 |
| 给多个客户分别交付 | 每个客户需要独立授权 | 一次一密，每个客户独立密钥 |

> **核心原则**：交付即授权，密封后对方只能运行，不能读取、不能修改、不能转卖。

---

# 二、工作流密封 vs 技能包密封

MGC 支持两种密封协作模式：

| 维度 | 工作流密封 | 技能包密封 |
|------|-----------|-----------|
| **密封对象** | 分析脚本文件夹（run.py + helpers/） | 带有 SKILL.md 的完整技能包 |
| **密封工具** | `mgc_seal_package` | `mgc_seal_package` |
| **对方使用方式** | `mgc_run` 直接运行入口脚本 | AI 读取 SKILL.md 指引，按指引调用对应脚本 |
| **适用场景** | 给业务团队一个"一键运行"的分析工具 | 给客户一个"AI 可理解使用说明"的完整方案 |
| **SKILL.md 是否包含** | 不必须 | 必须（是对方 AI 的使用说明书） |
| **对方 AI 可见性** | 只看到运行状态 | 可读 SKILL.md（明文），但不可见脚本源码 |

> **选择建议**：
> - 如果对方只需要"跑一下你的分析"，用**工作流密封**
> - 如果对方需要 AI 按你的方案自主调用不同脚本，用**技能包密封**

---

# 三、完整授权协作链路

## 3.1 端到端流程

```
作者节点                                         接收节点（客户/团队）
─────────                                        ────────────────

1. 存入工作流/技能包
   mgc_save_file(path="./my_workflow")
   → MGC 自动识别 import/subprocess 关系

2. 对方获取自己的公钥                             mgc_get(info_type="__NODE_PUB__",
   （公钥非密，可任意渠道传输）                       info_owner="__NODE_PUB__")
                                                 → PEM 公钥发给作者

3. 用对方公钥密封
   mgc_seal_package(
       info_owner="my_workflow",
       diff_2="my_workflow",
       ext04=对方PEM公钥,
       output_dir="./delivery",          # 1.5.2+ 必填
   )
   → 生成 .mgc_file 加密包

4. 任意方式送达                                     5. 导入密封包
   （邮件/U盘/IM/网盘）                              mgc_save_file(
                                                      path="./received.mgc_file",
                                                      info_owner="my_workflow",
                                                      diff_2="my_workflow",
                                                   )

                                                   6. 运行
                                                      mgc_run(info_owner="my_workflow",
                                                              diff_2="my_workflow")
                                                      → 密封执行，磁盘无明文
```

## 3.2 安全特性

- **AES-256 加密**：每个脚本文件独立加密
- **RSA-2048 密钥交换**：AES 密钥用对方节点公钥加密，只有对方能解
- **节点绑定**：密钥绑定目标节点，对方无法转封给第三方
- **无云端**：全部加密/解密/运行在本地完成，MGC 不连任何云
- **任意渠道传输**：加密包可邮件、U盘、IM、网盘送达，被截获也无法解密

---

## 3.3 多节点 chain mode（1.6.0 新增）

当一个工作流需要交付给**多个节点**（把分析任务拆给两台机器或两个团队）时，p2p 模式需要逐个节点交换公钥并逐个密封；chain mode 一次密封即可产出每个目标节点各自独立的子包。

| | p2p 模式 | free 模式 | chain 模式（1.6.0+） |
|---|---|---|---|
| `ext04` | 单个 PEM | 不传 | **target 数组** |
| 产出的子包数 | 1 | 1 | **N（每目标一个）** |
| 谁能解封运行 | 该 PEM 对应节点 | 任意 1.5.4+ 节点 | **各目标节点自己** |
| 公钥交换 | 逐个 | 无需 | 先收集全部 `node_pub` |
| distribution_index.json | ❌ | ❌ | ✅ |
| 适用 | 商业交付、客户隔离 | 公开分发、通用工具 | **多节点协作、任务拆分** |

targets 规格（只放脚本；数据与凭证留在各节点本地）：

```json
[
  {"node_pub": "<节点 A 的 PEM>", "files": ["run_query.py", "shared_helper.py"]},
  {"node_pub": "<节点 B 的 PEM>", "files": ["run_analyze.py", "shared_helper.py"]}
]
```

```python
mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04="@/abs/path/chain_targets.json",   # 或 json.dumps(targets)
    output_dir="./delivery",
)
```

产物结构：

```text
./delivery/monthly_sales_analysis__monthly_sales_analysis/
├── distribution_index.json      # package_index / dir_name / package_file_name / granted_files / sha256
├── task_package_01/             # 仅节点 A
│   └── ...__01.mgc_file
└── task_package_02/             # 仅节点 B
    └── ...__02.mgc_file
```

各接收方只导入自己的 `.mgc_file`，运行前用 `granted_files` 核对授权清单。`distribution_index.json` 记录每个子包的 `sha256`，发送前与接收后都可校验完整性。

chain mode 硬约束：

- **只支持平级目录**：密封态跨脚本 import 在同一层解析。原有 `helpers/query.py` 结构需先扁平化为 `query.py`（并改成 `from query import ...`）再密封。
- **`files` 必须与 `diff_3` 完全一致**：`mgc_save_file` 后用 `mgc_find` 确认。
- **`files` 只放脚本**：CSV / JSON / 配置文件在包内是明文。数据与凭证留在各节点本地 MGC，由脚本运行时读取。
- **运行期报 `UNSEAL_FAILED`**：说明子包发错了节点，或 `.mgc_file` 被改名。

---

# 四、工作流密封实操

## 4.1 准备工作流文件夹

```
my_analysis/
├── manifest.json
├── run.py              # 入口脚本
├── helpers/
│   ├── query.py        # 查询模块
│   ├── clean.py        # 清洗模块
│   └── analyze.py      # 分析模块
└── config/
    └── settings.json
```

## 4.2 存入 MGC

```python
mgc_save_file(
    path="./my_analysis",
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)
# MGC 自动识别 import / subprocess 调用关系
```

## 4.3 密封给目标节点

```python
# 目标节点的公钥（由对方通过 mgc_get 获取后发给你）
recipient_pub = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"""

mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04=recipient_pub,
)
# → 生成 .mgc_file 加密包
```

> **注意**：`ext04` 必须含真实换行符 `\n`，不要单行拼接 PEM。

## 4.4 对方接收并运行

```python
# 对方导入密封包
mgc_save_file(path="./received.mgc_file")

# 对方运行（黑盒执行，磁盘无明文）
mgc_run(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)
# → {"pid": 12345, "status": "started"}
```

---

# 五、技能包密封实操

技能包与工作流的区别：包含 SKILL.md 作为对方 AI 的使用说明书。

## 5.1 准备技能包文件夹

```
my_skill_package/
├── manifest.json
├── SKILL.md             # ← 技能包必须有，是对方 AI 的使用说明（明文）
├── run_query.py          # 查询脚本
├── run_clean.py          # 清洗脚本
├── run_analyze.py        # 分析脚本
└── helpers/
    ├── db_connect.py
    └── stats.py
```

## 5.2 SKILL.md 的作用

SKILL.md 是**明文**的——对方 AI 需要读它来知道：
- 有哪些脚本可用
- 什么场景调用哪个脚本
- 传什么参数
- 按什么顺序

> **关键规则**：SKILL.md 写"怎么用"，核心算法写在脚本里。对方 AI 能读 SKILL.md 但不能读脚本源码。

## 5.3 存入并密封

```python
# 存入技能包
mgc_save_file(
    path="./my_skill_package",
    info_owner="sales_analysis_suite",
    diff_2="sales_analysis_suite",
)

# 密封给目标节点
mgc_seal_package(
    info_owner="sales_analysis_suite",
    diff_2="sales_analysis_suite",
    ext04=recipient_pub,
)
# → 生成 .mgc_file 加密包
```

## 5.4 对方接收并使用

```python
# 对方导入
mgc_save_file(path="./received.mgc_file")

# 对方 AI 读取 SKILL.md（明文，了解怎么用）
mgc_get(
    info_type="file",
    info_owner="sales_analysis_suite",
    diff_2="sales_analysis_suite",
    diff_3="SKILL.md",
)

# 对方 AI 按 SKILL.md 指引运行对应脚本
mgc_run(
    info_owner="sales_analysis_suite",
    diff_2="sales_analysis_suite",
)
```

---

# 六、给多个客户分别授权

每个客户需要独立密封——一份密钥只绑定一个节点：

```python
# 给客户 A 密封
mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04=client_a_pub,
)
# → 生成给客户A的 .mgc_file

# 给客户 B 密封（同一个工作流，不同密钥）
mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04=client_b_pub,
)
# → 生成给客户B的 .mgc_file
```

**安全特性**：
- 客户 A 拿到的包在客户 B 的机器上无法运行（密钥不匹配）
- 客户 A 无法将自己的包转封给客户 C（AES 密钥已绑定 A 的节点）
- 每个客户的密封包独立，互不影响

---

# 七、授权模板（AI 必须询问）

### 密封工作流前：

```
工作流名称：monthly_sales_analysis
目标节点公钥：{node_pub前16位}...
操作：密封工作流
是否需要授权：是

您是否授权密封此工作流？回复"是"继续，回复"否"取消。
```

### 密封技能包前：

```
技能包名称：sales_analysis_suite
目标节点公钥：{node_pub前16位}...
操作：密封技能包
是否需要授权：是

您是否授权密封此技能包？回复"是"继续，回复"否"取消。
```

---

# 八、最佳实践

### ✔ 1. 核心算法放脚本，别放 SKILL.md
SKILL.md 是明文，对方能读。算法是你卖的"产品"，必须锁进脚本里。

### ✔ 2. SKILL.md 只写路由说明
写清楚"什么场景调用哪个脚本、传什么参数"，不写业务逻辑细节。

### ✔ 3. 每个客户独立密封
不要试图用一个密封包给多个客户——每个客户的密钥绑定各自的节点。

### ✔ 4. 结果输出到指定文件
密封包运行后，MGC 不会返回明文。工作流的输出结果需要显性指定文件路径，或写入数据库或 MGC 本身。

### ✔ 5. 传输方式不受限制
加密包可邮件、U盘、IM、网盘任意方式送达。即使被截获，没有对应节点的私钥也无法解密。

---

# 九、常见问题

| 问题 | 解决方案 |
|------|---------|
| 密封失败 | 检查 ext04 是否为多行 PEM 公钥（保留 `\n`） |
| 对方运行报错 | 检查 ext05 中的依赖对方是否已安装 |
| 对方 import 失败 | 确保所有脚本在同一个 mgc_save_file 包内 |
| 平台不兼容 | 检查 ext06 是否包含对方的 OS |
| 客户说"换个机器就不能用了" | 这是设计如此——节点绑定，防止转卖 |

---

# 十、总结

本密封授权协作文档提供：

- 工作流密封（mgc_seal_package）与技能包密封
- 端到端授权协作链路（node_pub → seal → import → run）
- 多客户独立授权（一次一密、一节点一密）
- "可用不可读、可运行不可转卖"的 IP 保护

这是数据分析师安全协作工作流的核心能力。
