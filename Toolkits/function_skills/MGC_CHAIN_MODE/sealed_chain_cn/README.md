# 多 agent 跨设备加密协作 — 邮件 + 任务密封（功能性技能）

> **v1.0.0** · MGC 1.6.0 · 功能性技能
> 按数据域把任务拆成 N 个密封子包：每个执行 agent 只拿到自己的脚本，数据与凭证不出本地，只流转任务书、脚本和结果摘要。默认邮件分发。

## 这个技能解决什么

多个 agent 跨设备协作时，常见两个问题：

1. **文件隔离**：不想让每个 agent 都拿到全部脚本。
2. **数据出域**：业务数据和凭证不应该离开本地。

chain mode 的做法：编排 agent 只下发脚本，每个执行 agent 得到一个只含自己授权脚本的密封子包；数据与凭证由执行方存入**本地 MGC**，脚本运行时按需读取。

## 角色

| 角色 | 数量 | 持有数据/凭证 |
|------|------|:---:|
| 编排 agent | 1 | ❌ |
| 内部执行 agent | 每个内部数据域 1 个 | ✅ 仅本地 |
| 外部执行 agent | 每个外部数据域 1 个 | ✅ 仅本地 |

角色按**数据域**划分，不是按设备。单数据域场景可以只有"1 编排 + 1 内部执行"。

## 快速流程

```text
0 准备   各执行 agent 把数据/凭证存入本地 MGC
1 编排   编排 agent 写任务书 + 准备平级脚本目录
2 存包   mgc_save_file(path="./pipeline")
3 密封   mgc_seal_package(ext04=targets)  → N 个子包 + distribution_index.json
4 分发   默认邮件发送 task_package_NN/
5 执行   执行 agent 导入 → 核对授权清单 → mgc_run
6 回传   结果摘要 → 封装回传
7 汇总   编排 agent 解密汇总
```

## 硬约束

- **数据/凭证不进包**：MGC 只加密脚本，CSV/JSON/config 在包内是明文。
- **脚本目录必须平级**：sealed import hook 不支持子目录。
- **`files` = 存入时的 `diff_3`**：写规格前先 `mgc_find` 核对。
- **密封脚本只返回 status**：结果由脚本写到外部；`--output` 的父目录要先建好（脚本不自动 mkdir）。
- **导入成功 ≠ 可解封**：node_pub 不匹配时运行期才报 `UNSEAL_FAILED`，核对清单后先冒烟试跑。

## examples

| 文件 | 用途 |
|------|------|
| `examples/role_prompts.md` | 三种角色 + 分发 + 回传的任务书模板 |
| `examples/use_credential.py` | 从本地 MGC 读凭证并使用（不落盘、不打印） |
| `examples/task_flow.md` | 填空式多 agent 任务流模板 |

## 前置条件

- MGC Blackbox ≥ 1.6.0（接收方 ≥ 1.5.4）
- Python 3.10+
- `pip install mgc-blackbox` → `mgc` 启动（API `http://127.0.0.1:57219`）

## 详细文档

完整机制、协议、错误码见 [SKILL.md](./SKILL.md)。

## Links

- GitHub: https://github.com/zkeviny/MGC-Blackbox
- Issues: https://github.com/zkeviny/MGC-Blackbox/issues
- Contact: mirgincipher@outlook.com
