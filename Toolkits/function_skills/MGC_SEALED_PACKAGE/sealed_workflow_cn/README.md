# 工作流防盗版授权（加密交付、节点授权）

> Seal and License Workflows or Skill Packages · **Version 1.2.0** · 适配 MGC 1.5.2+

**一句话**：把 Python 小系统 / 工作流密封成本地包，一次一密、一次一节点，无需改造代码、无需云端、客户无法转售。

---

## 你是不是在找这样的方案？

- ✅ 我开发了一个 Python 工具，想卖给别人，但**怕被复制传播**
- ✅ 我用脚本拼了个小系统交给客户，但**客户能直接看到所有源码**
- ✅ 我封装了一套自动化工作流给企业，**每个企业需要单独授权**
- ✅ 我想卖一份"工具包"作为付费产品，**但核心方法不能泄露**

如果是，本技能就是为你准备的。

---

## 三大卖点

### 1. 零改造

工作流原本怎么写就怎么写 —— `import / 相对路径 / subprocess` 全部支持。MGC 1.5.2 的 `ext08` 自动识别这些调用关系，运行时通过密封执行接管。

- ✅ 客户的磁盘上**没有任何明文源码**
- ✅ **不需要把脚本改写成 API 调用模式**
- ✅ import、相对路径、subprocess 都照常用

### 2. 一次一密

每个客户拿到**独立的 AES 密钥**，用**目标节点的 RSA 公钥**加密：

- 客户节点没有私钥 = 拿不到内容
- 客户拿到内容后**无法转封**给第三方（密钥已绑定他的节点）

### 3. 本地交付

- 全部加密、解密、运行都在本地完成
- MGC 不连任何云、没有任何外部端点
- 加密包可邮件、U 盘、IM、GitHub Releases **任意方式**送达

---

## 前置条件

- **Python 3.10+**（macOS 14+ Apple Silicon 不支持 Python 3.12）
- **MGC Blackbox ≥ 1.5.2**（`ext08` 工作流自动识别需 1.5.2）
- 安装：`pip install mgc-blackbox`
- 启动：`mgc`（API 在 `http://127.0.0.1:57219`，WebUI 在 `http://127.0.0.1:57218`）

---

## 快速开始（作者侧）

```python
# 步骤 1：把工作流文件夹存入 MGC（MGC 1.5.2 自动构建 ext08 调用图）
mgc_save_file(
    path="./my_workflow",
    info_owner="my_workflow",
    diff_2="my_workflow",
)

# 步骤 2：拿客户的 RSA 公钥（公钥非密，可任意渠道传输）
# 客户在他机器上执行：
#   mgc_get(info_type="__NODE_PUB__", info_owner="__NODE_PUB__")
# 或者 WebUI：skill 页面 → Settings → Node Public Key

# 步骤 3：一键密封给该客户
mgc_seal_package(
    info_owner="my_workflow",
    diff_2="my_workflow",
    ext04=node_pub,           # 客户的 PEM 公钥
)
# → 生成 .mgc_file 加密包
```

把 `.mgc_file` 用邮件、U 盘、IM 任意方式发给客户。

## 快速开始（客户侧）

```python
# 步骤 1：导入加密包
mgc_save_file(path="./received.mgc_file")

# 步骤 2：浏览包内结构（仅元信息 + 明文 SKILL.md）
mgc_find(info_owner="my_workflow", diff_2="my_workflow")
mgc_get(info_type="file", info_owner="my_workflow", diff_2="my_workflow")

# 步骤 3：黑盒运行（AI 永不见源码）
mgc_run(info_owner="my_workflow", diff_2="my_workflow")
# → {"pid": 12345, "status": "started"}
```

---

## 与同类方案对比

| 维度 | GitHub 私有仓库 | SaaS 加密服务 | 许可证服务器 | **MGC 密封交付** |
|------|---------------|-------------|------------|-----------------|
| 需要云 | 是 | 是 | 是 | **否** |
| 月费成本 | 中 | 高 | 中 | **无** |
| 防源码泄露 | ❌ 可见 | ⚠️ 取决于服务 | ❌ 服务端可见 | ✅ **完全不可见** |
| 防止转售 | ❌ | ⚠️ | ⚠️ | ✅ **节点绑定** |
| 可离线交付 | ❌ | ❌ | ❌ | ✅ **任意渠道** |
| 适合小系统 | ⚠️ | ❌ 重 | ⚠️ 重 | ✅ **轻** |

---

## 三条关键规则（务必遵守）

| # | 规则 | 一句话 |
|---|------|--------|
| 1 | 同包路径 OK，跨包用 API | 一个文件夹包内的 import/path 由 MGC 自动接管；不同包之间才需要 API 调用 |
| 2 | 作者 SKILL.md 是明文 | 它是客户的"路由说明书"，必须可读 |
| 3 | 核心算法放脚本，别放提示词 | 提示词客户能看，算法是你的产品，必须锁进脚本 |

---

## 错误排查

| 错误 | 解决 |
|------|------|
| `DIFF2_MISMATCH` | import 的脚本不在同一文件夹包内，把它们一起保存 |
| `DEP_MISSING` | `ext05` 列出的依赖未装：`pip install` |
| `PLATFORM_INCOMPAT` | `ext06` 不包含当前 OS，在支持的平台重新保存 |
| `Invalid PEM format` | `ext04` 必须含真实换行，从 `mgc_get` 原样拷贝 |
| `args_not_recognized` | 检查 `add_argument` 是否有字面量 `default=` |

---

## 支持平台

- Windows（Python 3.10 / 3.11 / 3.12）
- Linux / Ubuntu（Python 3.10 / 3.11 / 3.12）
- macOS 14+ Apple Silicon（Python 3.10 / 3.11；**不支持 3.12**）

---

## 相关链接

- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系邮箱**：mirgincipher@outlook.com

---

## 相关技能（零暴露系列）

- **MGC Blackbox（跨设备脚本授权）** —— 单脚本密封（更轻量）
- **MGC Blackbox 元技能** —— MGC 全部能力的完整参考