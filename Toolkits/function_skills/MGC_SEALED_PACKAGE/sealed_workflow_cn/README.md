# 工作流防盗版授权（加密交付、节点授权）

> **Version 1.3.0** · 面向脚本销售与小系统交付 —— 把 Python 工作流密封成带来源绑定的本地包，授权节点直接运行，源码全程加密。全链路零云端、零代码改造。

---

## 这个技能解决什么

| 你的处境 | 传统做法的坑 | 本技能的做法 |
|---------|-------------|------------|
| 我卖脚本，客户拿到就能转发 | 发出去一份 = 公开一份 | 每个客户一次一密，包绑定到指定节点 |
| 我交付小系统源码，客户看完就改 | 改坏了找我背锅，还可能转卖同行 | 交付的是密封包，源码不落地 |
| 我要在技能市场发个通用工具包 | 公开源码 = 放弃所有权 | 自由模式包：任意节点可装可跑，源码不流出 |
| 团队之间要共享脚本但怕泄露 | 走审批流程效率低 | 密封包 + 链路授权，来源可追溯、篡改即失效 |

---

## 核心特性

### 双层加密 + 链路授权（MGC 1.5.4）

密封时内容先经 AES-256-GCM 加密，AES 密钥用目标节点 RSA-2048 公钥包装，包装结果再以**授权方 source_node_pub** 派生的密钥包一层（AAD = 密封模式）。

- `ext03` —— 双层包装后的密文
- `ext07` —— 授权方 node_pub（明文标识，参与加密）
- `ext09` —— 密封模式（`p2p mode` / `free mode`）

**改动 `ext07` 或 `ext09`（哪怕一个空格）→ 整个包不可还原。** 来源身份即完整性锚点。

### 两种密封模式

| | p2p 模式 | 自由模式 |
|---|---|---|
| 怎么密封 | 传 `ext04=目标节点 PEM` | **省略 `ext04`** |
| 谁能解封运行 | 只有持有对应私钥的那个节点 | **任意 MGC 1.5.4+ 节点** |
| 源码 | 不落盘、不外泄 | 同样不落盘、不外泄 |
| 适合 | 单客户授权、私有交付 | 技能市场上架、公开演示 |

### 零改造密封

脚本保持原貌，MGC 在存入时自动识别跨脚本关系：

- `from helpers.fetch import get_weather` ✅
- `import config` ✅
- `Path(__file__).parent / "settings.json"` ✅
- `subprocess.run([sys.executable, "helper.py"])` ✅
- **同包跨子目录** `Path(__file__).resolve().parent.parent / "y.py"` ✅（1.5.4 新增）
- **subprocess 计算式绝对路径** `subprocess.run([sys.executable, str(base_dir / "y.py")])` ✅（1.5.4 新增）

运行时通过密封执行路由 —— **磁盘无文件、无明文、无需重写代码**。

---

## 快速上手

### 1 · 存（作者侧）

```python
mgc_save_file(path="./my_workflow", info_owner="my_workflow", diff_2="my_workflow")
```

### 2 · 拿目标节点的公钥

```python
node_pub = mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")
```

### 3 · 密封

```python
mgc_seal_package(
    info_owner="my_workflow",
    diff_2="my_workflow",
    ext04=node_pub,           # 自由模式则省略此行
    output_dir="./delivery",  # 1.5.4 起必填
)
# → delivery/my_workflow_delivery/{ my_workflow.mgc_file, README.md }
```

### 4 · 导入（接收侧）

```python
mgc_save_file(
    path="./my_workflow_delivery/my_workflow.mgc_file",
    info_owner="my_workflow",
    diff_2="my_workflow",
)
```

### 5 · 运行

```python
mgc_run(info_type="script", info_owner="my_workflow", diff_2="my_workflow")
# → {"pid": 12345, "status": "started"}
```

> 💡 `diff_1` 在 1.5.4 起可选；定位单个脚本用 `diff_3`（包内相对路径）最可靠。

---

## 环境要求

- **Python 3.10+**（macOS 14+ Apple Silicon 不支持 Python 3.12）
- **MGC Blackbox ≥ 1.5.4**
- `pip install mgc-blackbox>=1.5.4` → 运行 `mgc`（API `127.0.0.1:57219` / WebUI `127.0.0.1:57218`）

> ⚠️ 1.5.4 起 `mgc_seal` / `mgc_seal_package` / `mgc_package` **必须传 `output_dir`**（绝对路径），无桌面回退。

---

## 示例

`example/` 提供 4 个零依赖脚本，覆盖全部可识别调用模式：

```
example/
├── config_a.py     # 配置脚本
├── script_b.py     # 从 A import 取值
├── script_c.py     # subprocess 调用 A
└── script_d.py     # driver，同时驱动 B + C
```

### 试一次：用 example/ 做自由模式密封

无需第二个节点、无需公钥交换，四步跑通全链路：

```python
# 1 · 存入 MGC
mgc_save_file(path="./example", info_owner="demo_free", diff_2="example")

# 2 · 自由模式密封（不传 ext04）
mgc_seal_package(
    info_owner="demo_free",
    diff_2="example",
    output_dir="./_demo_out",
)

# 3 · 导入刚生成的包
mgc_save_file(
    path="./_demo_out/example_delivery/example.mgc_file",
    info_owner="demo_free",
    diff_2="example",
)

# 4 · 运行 driver
mgc_run(info_type="script", info_owner="demo_free", diff_2="example", diff_3="script_d.py")
```

桌面出现 `txt1.txt` / `txt2.txt` / `txt2_via_a.txt` / `combined.txt` 四个文件即全链路贯通。此时用 `mgc_get` 取脚本内容只会得到一长串 Base64 密文 —— **能跑，但读不到源码**。

> ⚠️ 包内记录自带 `info_owner`，导入时传的值只作必填校验；后续查询要用包内的 `info_owner`。同节点 + 同 `info_owner` 会覆盖源记录。

完整流程见 [example/README.md](example/README.md)。

---

## 安全边界

MGC 保护的是**内容机密性**，不是运行时行为：

- 数据静态加密，密封源码仅在执行节点内存中解密，不落盘
- 密封后脚本的运行时行为由**脚本作者本人负责** —— MGC 无法担保作者的可信度
- 导入前请通过可信渠道核对来源节点的公钥；链路授权可发现来源标识被篡改

---

## 相关技能

- **MGC Blackbox 元技能** —— MGC 全部能力的完整参考
- **MGC Blackbox 跨设备脚本授权** —— 单脚本密封（更轻量）

---

## 联系

- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系邮箱**：mirgincipher@outlook.com
