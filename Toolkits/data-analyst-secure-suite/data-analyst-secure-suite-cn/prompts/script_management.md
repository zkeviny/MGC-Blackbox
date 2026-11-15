# 数据分析工作流管理（Script & Workflow Management）

本文档用于指导数据分析师在 **MGC Blackbox ≥ 1.5.2** 中安全管理查询脚本、清洗脚本、分析脚本等 **用户自有脚本**，并在本地实现 **零暴露应用**。

所有敏感操作必须由用户明确授权后才能进行。

---

# 一、工作流管理概述

MGC Blackbox 1.5.2+ 提供脚本与工作流的本地加密存储、自动识别与零暴露应用能力：

- 脚本内容永不暴露给 AI
- 脚本仅在用户本地机器解密
- 脚本可安全调用凭据（零暴露）
- 所有应用必须由用户授权
- AI 只能看到脚本的执行结果，不可见逻辑
- **工作流文件夹可自动识别 import / 相对路径 / subprocess 调用关系**（1.5.1+）

---

# 二、两种管理模式

| 模式 | 适用场景 | 存储工具 | 运行工具 |
|------|---------|---------|---------|
| **工作流模式（推荐）** | 查询→清洗→分析多脚本串联 | `mgc_save_file` | `mgc_run`（指定入口脚本） |
| **单脚本模式** | 单个独立脚本 | `mgc_save` | `mgc_run` |

> **建议**：如果你的分析链有 2 个以上脚本，用工作流模式。MGC 会自动识别脚本间的 import/from-import/相对路径/subprocess 调用关系，运行时密封路由，不需要手动传参串联。

---

# 三、工作流模式（推荐，1.5.2+）

## 3.1 工作流文件夹结构

一个典型的数据分析工作流：

```
my_analysis/
├── manifest.json
├── run.py              # 入口脚本：调用 helpers 中的模块
├── helpers/
│   ├── query.py        # 查询模块
│   ├── clean.py        # 清洗模块
│   └── analyze.py      # 分析模块
└── config/
    └── settings.json   # 配置文件
```

`run.py` 可以直接 import 同包内的模块：

```python
# run.py
from helpers.query import query_data
from helpers.clean import clean_data
from helpers.analyze import analyze_data

def main():
    raw = query_data()
    cleaned = clean_data(raw)
    result = analyze_data(cleaned)
    # 结果写入文件或 MGC，不返回明文
    with open("output/report.xlsx", "wb") as f:
        f.write(result)

if __name__ == "__main__":
    main()
```

## 3.2 存入工作流

```python
mgc_save_file(
    path="./my_analysis",
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)
```

**这一步 MGC 会自动**：
- 解析每个脚本的 `argparse` 写入 `ext02`（参数列表）
- 扫描 import 写入 `ext05`（依赖列表）
- 推断 `ext06`（平台列表）
- 构建 `ext08`（跨脚本调用图）— 识别 `import / from-import / Path 相对路径 / subprocess` 关系

> **注意**：MGC 会**用路径最后一段目录名作为 `diff_2`**（如 `path="./my_analysis"` 实际写入 `diff_2="my_analysis"`）。存完后请用 `mgc_find` 确认实际 `diff_2`，密封时再传入。

## 3.3 运行工作流

```python
mgc_run(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)
# → {"pid": 12345, "status": "started"}
```

MGC 会自动：
- 解密所有脚本到内存（不在磁盘落盘）
- 拦截 import / subprocess 调用，通过密封执行路由
- 返回运行状态，不返回脚本内容

## 3.4 按名称定位工作流

```python
# 模糊搜索工作流
matches = mgc_find(
    info_owner="monthly",      # 部分名称；默认 substring 匹配
    match_mode="substring",
)
# 返回 metadata 列表（info_type、info_owner、ext01..ext03）—— 绝不返回明文。
# 定位到精确的 info_owner 后，传给 mgc_run。
```

## 3.5 工作流密封协作（1.5.2+）

将整个工作流一次性密封给另一个节点（团队成员、客户）：

```python
# 1. 对方先获取自己的 node_pub
# 对方执行：mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")

# 2. 你用对方的公钥密封整个工作流
mgc_seal_package(
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
    ext04=recipient_node_pub,          # 对方的 PEM 公钥
    output_dir="./delivery",            # 1.5.2+ 必填：密封包输出目录
)
# → 生成 .mgc_file 加密包
```

对方收到 `.mgc_file` 后：

```python
# 对方导入密封包（info_owner / diff_2 必须与密封时一致）
mgc_save_file(
    path="./received.mgc_file",
    info_owner="monthly_sales_analysis",
    diff_2="monthly_sales_analysis",
)

# 对方黑盒运行
mgc_run(info_owner="monthly_sales_analysis", diff_2="monthly_sales_analysis")
```

**安全特性**：
- 整个工作流一次密封，不需要逐个脚本密封
- AES 密钥绑定目标节点 RSA 公钥，对方无法转封给第三方
- 对方只能运行，不能读取源码

> **注意**：`ext04` 必须含真实换行符 `\n`，不要单行拼接 PEM。

---

# 四、单脚本模式（简单场景）

当只需要管理单个独立脚本（无跨脚本调用）时，可使用 `mgc_save`。

## 4.1 存入单脚本

```python
mgc_save(
    info_type="script",
    info_owner="quick_query",
    ext01="python",
    content="<你的脚本内容>"
)
```

## 4.2 运行单脚本

```python
mgc_run(
    info_type="script",
    info_owner="quick_query",
    diff_1="quick_query",
)
```

## 4.3 密封单脚本

```python
sealed = mgc_seal(
    info_owner="quick_query",
    ext04=recipient_node_pub,
)
```

---

# 五、脚本内部如何零暴露调用凭据

**MGC 实现机制**：脚本存储在 MGC 中，运行时 MGC 在本地解密脚本并执行。如果脚本需要访问凭据，脚本内部通过本地 API 调用获取凭据。

## 标准示例：脚本内部安全访问凭据

```python
import os, requests, json

# 读取 MGC 访问令牌（固定路径，不要改）
with open(os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")) as f:
    MGC_TOKEN = f.read().strip()

def get_credential(info_owner="db_warehouse_prod"):
    """从 MGC 获取凭据"""
    resp = requests.post(
        "http://127.0.0.1:57219/api/mgc/sensitive/get",
        headers={"X-MGC-Token": MGC_TOKEN},
        json={
            "info_type": "token",
            "info_owner": info_owner,
        },
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 200:
            data_field = data.get("data")
            if isinstance(data_field, str):
                return json.loads(data_field)
            elif isinstance(data_field, dict):
                content = data_field.get("content")
                if content:
                    return json.loads(content)
    return None

# 使用凭据
def query_monthly_orders():
    credential = get_credential("db_warehouse_prod")
    # ... 使用凭据建立连接并查询
```

**注意**：
- 此调用仅限本地（127.0.0.1），AI 无法看到凭据
- Token 文件路径：`~/.mgc/database/mgc_black_box/.mgc_token`

---

# 六、可识别的跨脚本写法（工作流模式必备）

当使用 `mgc_save_file` 保存工作流文件夹时，MGC 会自动识别以下模式：

| 模式 | 代码示例 | 能否识别 |
|------|---------|---------|
| `from` import | `from config import DEFAULT_CITY` | ✅ |
| `from` import 带别名 | `from helpers.fetch import get_weather as gw` | ✅ |
| 普通 `import` | `import helpers.parse` | ✅ |
| `Path` 相对路径 | `Path(__file__).parent / "config.py"` | ✅ |
| `open()` 相对路径 | `open("config.json")` 调用同级文件 | ✅ |
| subprocess + 相对路径 | `subprocess.run([sys.executable, str(Path(__file__).parent / "config.py"), ...])` | ✅ — 仅当在同一包内 |
| subprocess + 字面量列表（1.5.2+） | `subprocess.run([sys.executable, "helper.py", "--arg"])` | ✅ — 1.5.2 起运行时路由支持 |
| 动态 import | `importlib.import_module(module_name)` | ❌ 只能静态解析 |
| 绝对路径 | `open("/Users/alice/config.py")` | ❌ 不可移植 |

**作用域**：跨脚本调用仅在同一个文件夹包内被识别。请把 helpers 和 driver 放在同一个目录。

---

# 七、授权模板（AI 必须询问）

当 AI 需要应用脚本或工作流时，必须询问用户：

```
工作流名称：monthly_sales_analysis
操作：运行工作流
是否需要授权：是

您是否授权此操作？回复"是"继续，回复"否"取消。
```

AI 在未获得用户授权前不得应用任何脚本或工作流。

---

# 八、最佳实践

### ✔ 1. 优先使用工作流模式
多脚本分析链用 `mgc_save_file` 存入，MGC 自动识别 import 关系，不需要手动传参串联。

### ✔ 2. 入口脚本只写编排逻辑
`run.py` 只负责调用 helpers 中的模块，核心算法放在各自的模块里。

### ✔ 3. 结果写入文件或 MGC
出于黑盒执行的需要，MGC 不会返回任何明文。工作流的输出结果需要显性指定文件路径，或写入数据库或 MGC 本身。

### ✔ 4. 使用描述性 info_owner
例如：`monthly_sales_analysis`、`customer_churn_prediction`、`daily_report_gen`

### ✔ 5. 不在脚本中硬编码密钥
所有密钥必须通过 MGC 获取。

### ✔ 6. 所有应用必须授权
AI 不得自动应用脚本或工作流。

---

# 九、常见问题

| 问题 | 解决方案 |
|------|---------|
| 工作流运行失败 | 检查 `ext05` 中的依赖是否在本地安装 |
| import 找不到模块 | 确保所有脚本在同一个 `mgc_save_file` 包内 |
| 密封失败 | 检查 `ext04` 是否为多行 PEM 公钥（保留 `\n`） |
| 平台不兼容 | 检查 `ext06` 是否包含当前 OS |
| 凭据获取失败 | 检查 `info_owner` 是否一致 |

---

# 十、总结

本工作流管理文档提供：

- 工作流文件夹加密存储与自动识别
- 零暴露调用凭据
- 零暴露运行工作流
- 用户授权机制
- 工作流密封与协作授权

这是数据分析师安全工作流的核心能力。
