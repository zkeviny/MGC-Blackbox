# example/ — 演示脚本集

> 4 个脚本演示 MGC 1.5.2 `ext08` 自动识别 + 运行时密封路由的所有跨脚本调用模式。
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

## ext08 模式演示矩阵（已在 MGC 1.5.2 实测通过）

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

### 1. 存

```python
mgc_save_file(
    path="./example",
    info_owner="demo_workflow",
    diff_2="example",
)
# 自动构建 ext08 调用图（实测识别 5 条边）
```

### 2. 拿自己的 node_pub

```python
my_pub = mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")
# 返回多行 PEM 公钥
```

### 3. 密封到自己节点

```python
mgc_seal_package(
    info_owner="demo_workflow",
    diff_2="example",
    ext04=str(my_pub),                          # 必填：目标节点 PEM
    output_dir="./_demo_out",                   # 必填：输出目录
)
# → 生成 example_delivery/example.mgc_file + README.md
```

### 4. 导入密封包

```python
mgc_save_file(
    path="./_demo_out/example_delivery/example.mgc_file",
    info_owner="demo_workflow",                 # 必填：与密封时一致
    diff_2="example",
)
# 拆解为 5 个密文 record（含 SKILL.md）
```

### 5. 黑盒运行

```python
mgc_run(
    info_type="script",
    info_owner="demo_workflow",
    diff_2="example",
    diff_3="script_d.py",
)
# → {"status": "started"}
# AI 看不到任何源码
```

### 6. 检查结果

5 秒后查看 `~/Desktop/txt1.txt`、`txt2.txt`、`txt2_via_a.txt`、`combined.txt` 四个文件全部生成 = 全链路贯通。

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
- 跨子目录：`Path(__file__).parent.parent / "y.py"`
- 函数级引用：`import helpers; helpers.some_func()` 不带字面量 Path

这些**不能被 ext08 识别**，详见 SKILL.md §"可识别的跨脚本写法"。