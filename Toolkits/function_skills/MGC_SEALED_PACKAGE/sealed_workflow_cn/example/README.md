# example/ — 演示脚本集

> 4 个脚本演示 MGC 1.5.4 `ext08` 自动识别 + 运行时密封路由的所有跨脚本调用模式。
> 仅用 Python 标准库，跨 macOS / Linux / Windows。

## 文件结构

```
example/
├── config_a.py        # A · 配置脚本（import 与 subprocess 都能调）
├── script_b.py        # B · 从 A import 取值 → 桌面 txt1.txt
├── script_c.py        # C · subprocess 调用 A → 桌面 txt2.txt
├── script_d.py        # D · 同时 import B + subprocess C → 桌面 combined.txt
└── README.md          # 本文件
```

## ext08 模式演示矩阵（已在 MGC 1.5.2 实测通过，1.5.4 沿用）

| 调用关系 | 代码写法 | ext08 边类型 | 识别 |
|---------|---------|-------------|------|
| B → A | `from config_a import get_greeting, DEFAULT_USER` | `from_import` | ✅ |
| B → A | `import config_a` | `import` | ✅ |
| C → A | `subprocess.run([sys.executable, "config_a.py", ...])` | `subprocess` | ✅ |
| D → B | `import script_b; script_b.run(...)` | `import` | ✅ |
| D → C | `subprocess.run([sys.executable, "script_c.py", ...])` | `subprocess` | ✅ |

> 1.5.2 之前，`subprocess.run([sys.executable, "x.py"])` 字面量列表运行时路由**不被支持**；1.5.2 起完整支持。

## 输出文件（黑盒执行时不靠 print，需显式落盘）

| 文件 | 由谁写 | 内容 |
|------|--------|------|
| `~/Desktop/txt1.txt` | B | 从 A import 的问候语 + DEFAULT_USER |
| `~/Desktop/txt2.txt` | C | C 自身摘要（通过 subprocess 调用 A） |
| `~/Desktop/txt2_via_a.txt` | C 调 A | A 子进程写入的问候语 |
| `~/Desktop/combined.txt` | D | B 与 C 的产出汇总 |

> Linux 无 `~/Desktop` 时自动回退到 `~`。

## 推荐体验流程（用 MGC MCP 工具）

### 方式 A · 自由模式（推荐先试这个）

无需第二个节点、无需公钥交换 —— 密封时**不传 `ext04`** 即可。

```python
# 1. 存
mgc_save_file(
    path="./example",
    info_owner="demo_workflow",
    diff_2="example",
)
# 自动构建 ext08 调用图（实测识别 5 条边）

# 2. 自由模式密封 —— 注意不传 ext04
mgc_seal_package(
    info_owner="demo_workflow",
    diff_2="example",
    output_dir="./_demo_out",                   # 1.5.4 起必填
)
# → 生成 _demo_out/example_delivery/example.mgc_file + README.md
#   产物 ext09 = "free mode"

# 3. 导入刚生成的包
mgc_save_file(
    path="./_demo_out/example_delivery/example.mgc_file",
    info_owner="demo_workflow",                 # 必填；实际落库身份取包内的值
    diff_2="example",
)
# 拆解为 5 个密文 record（含 README.md）

# 4. 运行
mgc_run(
    info_type="script",
    info_owner="demo_workflow",
    diff_2="example",
    diff_3="script_d.py",
)
# → {"status": "started"}
```

### 方式 B · p2p 模式（指定节点）

```python
# 1. 存（同上）

# 2. 拿目标节点的 node_pub
my_pub = mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")
# 返回多行 PEM 公钥

# 3. 密封到该节点
mgc_seal_package(
    info_owner="demo_workflow",
    diff_2="example",
    ext04=str(my_pub),                          # p2p 模式必填
    output_dir="./_demo_out",                   # 1.5.4 起必填
)

# 4. 导入 + 5. 运行（同方式 A）
```

### 检查结果

5 秒后查看 `~/Desktop/txt1.txt`、`txt2.txt`、`txt2_via_a.txt`、`combined.txt` 四个文件全部生成 = 全链路贯通。

再验证"源码读不到"：

```python
mgc_get(info_type="script", info_owner="demo_workflow", diff_2="example", diff_3="config_a.py")
# → 一长串 Base64 密文，看不到 Python 源码；但 mgc_run 仍能正常执行
```

> ⚠️ **两条实测确认的注意事项**
> 1. **包内记录自带 `info_owner`** —— 导入时传的 `info_owner` 只作必填校验，实际落库身份取包内的值，后续查询要用它。
> 2. **同节点 + 同 `info_owner` 会覆盖源记录** —— 在自己机器上回灌同一个包，明文会被密文替换（不可逆）。想两套都留着，请用不同 `info_owner` 存盘。

> ⚠️ 已知警告：MGC 会把同包内的 `script_b` 误报为外部依赖 `DEP_MISSING`，可忽略——脚本本身运行正常。

## 设计原则

1. **零非标准库依赖**：仅 `os` / `sys` / `subprocess` / `argparse` / `pathlib` / `time`
2. **跨平台**：`Path.home() / "Desktop"`，Linux 不存在则回退到 `~`
3. **黑盒执行友好**：所有结果物显式写到桌面文件，不依赖 `print` 被上层捕获
4. **argparse 完整**：每个脚本都有字面量 `default=`，方便 ext02 自动识别
5. **UTF-8 全程**：避免 Windows 中文乱码

## 不演示的反例（看 SKILL.md 即可）

- 动态模块名：`importlib.import_module(x)`
- 绝对路径：`open("/Users/.../config.py")`
- subprocess 字面量里的 `..`：`subprocess.run([..., "../y.py"])` —— 1.5.4 起应改用计算式绝对路径 `Path(__file__).resolve().parent.parent / "y.py"`
- 函数级引用：`import helpers; helpers.some_func()` 不带字面量 Path

> 💡 **1.5.4 起同包跨子目录引用已可识别**（如 `from helpers.fetch import get_weather`、`Path(__file__).resolve().parent.parent / "y.py"`）。本示例为了保持"同级目录"的最简形态，仍用同级调用；跨子目录写法见 SKILL.md §"可识别的跨脚本写法"。

详见 SKILL.md §"可识别的跨脚本写法"。