# 脚本跨设备加密授权（零暴露）

基于 MGC Blackbox 1.4.10 实现**零暴露跨设备脚本授权**的文档技能。

## 本技能是什么

脚本跨设备加密授权教授如何：

- 使用目标节点 RSA 公钥密封脚本
- 将加密脚本安全传输给授权节点
- 授权节点以**黑盒执行**（`mgc_run`）方式运行，脚本源永不上传
- 构建跨设备信任链

## 前置条件

- Python 3.10+
- 安装：`pip install mgc-blackbox`（建议 1.4.10+）
- 启动 MGC：`mgc`（API 端口 57219，WebUI 端口 57218）
- 两个 MGC 节点（一个归属，一个授权；单节点可自验证）

## 快速开始

### 1. 获取目标节点公钥

```python
# MCP/API 懒生成
node_pub = mgc_get(
    info_type="__NODE_PUB__",
    info_owner="__NODE_PUB__"
)
```

或 WebUI：skill 页面 → Settings → **Node Public Key** → 复制多行 PEM。

> `node_pub` 必须是**多行 PEM** 含真实换行（`\n`），不能单行拼接。

### 2. 密封脚本（源节点）

```python
# 先存原始脚本
mgc_save(
    info_type="script",
    info_owner="my_script",
    ext01="python",
    content="print('Confidential script')"
)

# 用目标节点公钥密封
sealed = mgc_seal(
    info_owner="my_script",
    ext04=node_pub
)
# sealed = { content, ext_01, ext_02, ext_03 }
# ext_02 由 MGC 1.4.10 自动从脚本 argparse 解析打包
```

### 3. 传输密封包

通过邮件 / U 盘 / IM 等任意可信渠道发送 `sealed` 字典（4 个字段必须齐全）。

### 4. 目标节点存储并执行

```python
# 在目标节点
mgc_save(
    info_type="script",
    info_owner="partner_script",
    ext01=sealed["ext_01"],
    ext02=sealed["ext_02"],          # 默认参数（来自源节点 argparse）
    content=sealed["content"],       # AES 加密体
    ext03=sealed["ext_03"],          # RSA 加密的 AES key
    update_if_exists=True
)

# 黑盒执行（1.4.7+ 推荐）
result = mgc_run(
    info_owner="partner_script",
    diff_1="partner_script",
    ext02='["--name", "Alice"]'      # 可选：运行时覆盖默认参数
)
# 返回: {"pid": 12345, "status": "started"}
```

## 应用场景

| 场景 | 说明 |
|------|------|
| 跨组织共享 | 共享脚本但不暴露逻辑 |
| 可信合作伙伴自动化 | 安全地向合作伙伴提供自动化 |
| 委托任务执行 | 中央服务器向边缘设备委托任务 |

## MCP 工具

| 工具 | 说明 | 必填参数 |
|------|------|----------|
| `mgc_save` | 存储原始 / 密封脚本 | info_type, info_owner, content |
| `mgc_run` | 黑盒执行脚本（1.4.7+） | info_type=script, info_owner, diff_1（schema 必填区分字段，单条任意非空字符串） |
| `mgc_seal` | 用目标节点公钥密封脚本 | info_owner, ext04（多行 PEM） |
| `mgc_list` | 列出条目 metadata | — |
| `mgc_find` | 模糊搜索（1.4.10 新增） | info_owner, match_mode |
| `mgc_open_webui` | 打开 WebUI | — |
| `mgc_get` | 取 node_pub / 取凭据 | info_type, info_owner |

## 适配 MGC 1.4.10

- ✅ `mgc_run` 黑盒执行（替代旧的 `mgc_get(action=run)`）
- ✅ `ext02` 自动解析 argparse（密封包自动包含默认参数）
- ✅ `mgc_find` 模糊搜索（`match_mode` 自动加 `%` 通配符）
- ✅ `update_if_exists` 覆盖同名脚本
- ✅ WebUI Settings → Node Public Key 直接查看多行 PEM
- ✅ 1.4.9 沙箱模式兼容

## 支持平台

- Windows
- macOS
- Linux

## 相关链接

- **主仓库**：https://github.com/zkeviny/MGC-Blackbox
- **问题反馈**：https://github.com/zkeviny/MGC-Blackbox/issues
- **联系方式**：mirgincipher@outlook.com
