# 脚本跨设备加密授权（零暴露）

基于 MGC Blackbox 1.5.4 实现**零暴露跨设备脚本授权**的文档技能。

## 本技能是什么

脚本跨设备加密授权教授如何：

- 用目标节点 RSA 公钥密封脚本，以密文胶囊交付
- 也支持免公钥交换的**自由模式**，公开分发
- 在授权节点以**黑盒执行**（`mgc_run`）方式运行，脚本源永不上传
- 通过**链接授权**校验产物来源完整性
- 构建跨设备信任链

## 前置条件

- Python 3.10+
- 安装：`pip install mgc-blackbox>=1.5.4`
- 启动 MGC：`mgc`（API 端口 57219，WebUI 端口 57218）
- 两个 MGC 节点（一个归属，一个授权；单节点可自验证）

> 接收方必须运行 **MGC 1.5.4+**，旧版本无法解封带链接授权的产物。

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

## 快速开始

### 1. 获取目标节点公钥（仅 p2p 模式需要）

```python
# MCP/API 懒生成
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
```

或 WebUI：skill 页面 → Settings → **Node Public Key** → 复制多行 PEM。

> `node_pub` 必须是**多行 PEM** 含真实换行（`\n`），不能单行拼接。

### 2. 密封脚本（归属节点）

```python
# 先存原始脚本
mgc_save(
    info_type="script",
    info_owner="my_script",
    ext01="python",
    content="print('Confidential script')"
)

# 密封，产出胶囊文件
sealed = mgc_seal(
    info_owner="my_script",
    output_dir="/abs/path/to/out",   # 1.5.4 起必填，无桌面兜底
    ext04=node_pub,                 # 自由模式：删掉这一行
)
# → /abs/path/to/out/my_script_<时间戳>/sealed_capsule.json
# 胶囊含 content / ext01..ext09，其中 ext07=源节点公钥、ext09=密封模式
```

### 3. 传输密封产物

把 `sealed_capsule.json` 整个文件交给接收方——邮件 / U 盘 / IM 任意渠道均可。

### 4. 授权节点导入并执行

```python
# 在授权节点上：一次调用导入，MGC 自动解析全部字段
mgc_save_file(
    path="/path/to/send/sealed_capsule.json",
    info_owner="partner_script"     # 用自己的 owner，避免覆盖归属节点的源记录
)

# 黑盒执行
result = mgc_run(
    info_type="script",
    info_owner="partner_script",
    diff_3="partner_script",        # 最可靠的定位字段
    ext02='["--name", "Alice"]'     # 可选：运行时覆盖默认参数
)
# 返回: {"status": "started"}
```

> **不要手工逐字段搬运** `ext01`/`ext02`/`content`/`ext03`——会丢掉 `ext07` 与 `ext09`，产物将永远无法解封。

## 链接授权

1.5.4 起每个密封产物都携带归属节点身份（`ext07`）与密封模式（`ext09`）。解封时用 `ext07` 派生外层密钥、用 `ext09` 作为 AAD 校验完整性，因此**对这两项的任何修改都会让产物不可还原**——包括只改一个空格。

实测对照：

| 场景 | 结果 |
|---|---|
| 篡改 `ext09` 加一个空格 | `UNSEAL_FAILED: AES-GCM auth tag mismatch` |
| 用不匹配的私钥解密 | `Double-layer unseal failed: Incorrect decryption` |
| 正常导入并执行 | `{"status": "started"}` |

> `ext07` 是明文标识而非签名，用于检测篡改与绑定解封密钥，不能替代身份核验。接收方仍应通过可信渠道核对归属节点公钥。

## 应用场景

| 场景 | 说明 |
|------|------|
| 跨组织共享 | 共享脚本但不暴露逻辑 |
| 可信合作伙伴自动化 | 安全地向合作伙伴提供自动化 |
| 委托任务执行 | 中央服务器向边缘设备委托任务 |
| 公开分发 | 自由模式，无需交换公钥，任意 1.5.4+ 节点可运行 |

## MCP 工具

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `mgc_save` | 存原始脚本 / 直接传胶囊 JSON | info_type, info_owner, content |
| `mgc_save_file` | 按路径导入胶囊（**推荐**）/ 导入文件夹 / 导入 `.mgc_file` | path, info_owner |
| `mgc_seal` | 密封单脚本，产出胶囊文件 | info_owner, **output_dir**（p2p 另需 ext04） |
| `mgc_run` | 黑盒执行脚本 | info_type=script, info_owner（`diff_3` 最可靠） |
| `mgc_get` | 取 node_pub / 取凭据 / 列全部条目 | info_type, info_owner |
| `mgc_find` | 模糊搜索 | info_owner, match_mode |
| `mgc_list` | 列出条目 metadata | — |
| `mgc_delete` | 删除已存记录（含用户确认流程） | info_type, info_owner |
| `mgc_open_webui` | 打开 WebUI | — |
| `mgc_skill` | 阅读 MGC 官方技能文档 | — |

## 适配 MGC 1.5.4

- ✅ 密封改为**双层加密**：`ext03` 外层用 `SHA256(ext07)[:32]` 派生密钥、`ext09` 作 AAD
- ✅ **链接授权**：`ext07` / `ext09` 任一被改即不可还原
- ✅ **自由模式**：省略 `ext04` 即可公开分发，无需交换公钥
- ✅ `output_dir` 成为密封必填项，产出**自描述胶囊文件**
- ✅ `mgc_save_file(path=胶囊)` 一次导入，自动解析全部 ext 字段
- ✅ `mgc_run` 不再要求 `diff_1`，`diff_3` 最可靠，新增 `AMBIGUOUS_SCRIPT` 错误码
- ✅ `ext05` 依赖清单 / `ext06` 平台清单随产物流转
- ✅ 新增 `mgc_delete`、`mgc_skill` 工具

## 安全边界

MGC 保护的是**内容机密性**，不担保运行时行为：密封脚本解封后以运行它的用户权限执行，它调用哪些命令、读写哪些文件、访问哪些网络端点，MGC 不做限制——这属于脚本作者的职责。导入前请通过可信渠道核对归属节点的公钥。

## 支持平台

- Windows
- macOS
- Linux

## 相关链接

- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系方式**：mirgincipher@outlook.com
