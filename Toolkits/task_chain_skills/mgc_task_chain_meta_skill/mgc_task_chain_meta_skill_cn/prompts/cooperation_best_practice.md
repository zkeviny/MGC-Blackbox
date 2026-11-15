# 最佳实践文档

> 此文档由主 Agent 自动维护和更新，记录协作过程中的最佳实践、常用脚本、用户偏好等信息。

---

## 协作流程

### ⚠️ 脚本执行结果处理原则

**通过 `mgc_run` 执行的脚本（无论是否密封），MGC 只会返回执行结果，不会返回脚本的标准输出（stdout）。**

#### 处理方式

**1. 一次性任务**：
- 脚本不存入 MGC，本地直接执行
- 直接查看脚本输出

**2. 多次复用任务**：
- 脚本存入 MGC
- 脚本将结果保存到文件（如 `~/mgc_outputs/result_xxx.txt`）
- 通过 stdout 输出文件路径（执行结果会返回）
- 后续 Agent 读取该文件

#### 任务链结果传递示例

```
子任务1：脚本保存到 ~/mgc_outputs/data_001.txt
  └─ 返回：RESULT_FILE:~/mgc_outputs/data_001.txt

子任务2：读取 data_001.txt，分析后保存到 analysis_001.txt
  └─ 返回：RESULT_FILE:~/mgc_outputs/analysis_001.txt

主 Agent 汇总：读取最终结果文件，输出给用户
```

#### 脚本输出保存示例

```python
import os
from datetime import datetime

def save_result(data):
    output_dir = os.path.expanduser("~/mgc_outputs")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(str(data))

    # 通过 stdout 输出文件路径
    print(f"RESULT_FILE:{filepath}")
```

### 标准任务链流程

```
1. 用户下达任务
   ↓
2. 主 Agent 理解任务目标
   ↓
3. 主 Agent 查看最佳实践，并拆解任务链
   ↓
4. 识别敏感操作（需要 MGC）
   ↓
5. 分配任务给子 Agent
   ↓
6. 执行任务
   ↓
7. 汇总结果
   ↓
8. 询问用户反馈
   ↓
9. 更新最佳实践文档
```

---

## 脚本列表

> 已有的可复用脚本，每次任务后可更新。建议用 `mgc_find` 模糊检索。

| 脚本名称 | 功能描述 | 创建时间 | 复用次数 | 备注 |
|----------|---------|---------|---------|------|
| （暂无） | - | - | - | 任务执行后自动添加 |

### 检索方式（1.4.10 推荐）

```python
# 模糊查找 — 自动加 LIKE 通配符
scripts = mgc_find(info_owner="查询", match_mode="substring", limit=50)
# match_mode: substring (%x%) / prefix (x%) / suffix (%x) / exact (x)
```

---

## 参数规范

### 脚本命名规范

```
{任务类型}_{功能描述}_v{版本}
```

示例：
- `数据分析_查询销售_v1`
- `发布_博客推送_v1`
- `营销_短信发送_v1`

### ⚠️ ext02 参数格式（1.4.10 契约）

**必须是 JSON 数组字符串**，对应脚本 `argparse` 的 argv list：

```python
import json

# ✅ 正确：JSON 数组字符串
params = ["--start", "2026-08-08", "--verbose"]
ext02 = json.dumps(params)
# ext02 = '["--start", "2026-08-08", "--verbose"]'

# ❌ 错误：dict 风格 JSON 对象（1.4.10 起会触发 422）
# ext02 = json.dumps({"start": "2026-08-08"})  # 不要这样写
```

### argparse default 规范（1.4.10）

```python
import argparse
parser = argparse.ArgumentParser()

# ✅ 字面量 default — MGC 自动解析到 ext02
parser.add_argument('--start', default='2026-08-08')
parser.add_argument('--count', default=10, type=int)
parser.add_argument('--verbose', action='store_true')

# ❌ 动态 default — 触发 dynamic_args_detected warning
# parser.add_argument('--start', default=datetime.now().strftime('%Y-%m-%d'))
# parser.add_argument('--home', default=os.path.expanduser('~'))
# parser.add_argument('--items', default=os.listdir('.'))
```

---

## 用户偏好

> 记录用户的习惯偏好，每次任务后更新

| 偏好项 | 内容 | 更新时间 |
|--------|------|---------|
| （暂无） | - | - | 任务执行后自动添加 |

---

## 常见错误与修复

### 错误 1：mgc_run 返回 422 错误

**原因**：`ext02` 参数格式错误（dict 风格而非 JSON 数组）

**修复**：
```python
import json
# ✅ 正确：JSON 数组
ext02 = json.dumps(["--to", "user@example.com"])
# ❌ 错误：JSON 对象
# ext02 = json.dumps({"to": "user@example.com"})
```

### 错误 2：dynamic_args_detected warning

**原因**：脚本 `argparse` default 用了动态表达式（`datetime.now()`、`os.path.expanduser()` 等）

**修复**：
- 改用字面量 default
- 或在调用 `mgc_run` 时手动传 `ext02`

### 错误 3：脚本执行失败

**原因**：脚本内部错误

**修复**：
- 检查脚本语法
- 确认凭据名称正确
- 查看 MGC 日志

### 错误 4：脚本解析参数时报错退出

**原因**：`parse_args()` 遇到未知参数

**修复**：
```python
# ✅ 改用 parse_known_args
args, unknown = parser.parse_known_args()
```

### 错误 5：mgc_get 返回明文风险

**原因**：`mgc_get` 会获取明文，破坏零暴露

**修复**：
- 执行 Agent 一律使用 `mgc_run`
- 凭据获取限制在脚本内部通过 HTTP API 拉取

---

## 场景最佳实践

### 场景 1：数据分析

**流程**：
1. 脚本角色编写查询脚本（argparse default 用字面量）→ 存入 MGC
2. 主 Agent 调度 `mgc_find` 查找脚本 → 分配给执行 Agent
3. 执行 Agent 调用脚本获取数据
4. 脚本将结果写入文件
5. 执行 Agent 读取文件，分析后生成报告
6. 发布报告

**注意事项**：
- 原始数据不暴露给执行 Agent
- 分析结果需脱敏处理

### 场景 2：内容发布

**流程**：
1. 执行 Agent 撰写内容
2. 脚本角色编写发布脚本 → 存入 MGC
3. 主 Agent 授权执行发布
4. 执行 Agent 调用发布脚本

**注意事项**：
- API 密钥不暴露
- 发布结果需用户确认

### 场景 3：营销通知

**流程**：
1. 执行 Agent 筛选目标用户
2. 脚本角色编写通知脚本 → 存入 MGC
3. 主 Agent 授权执行发送
4. 执行 Agent 调用发送脚本

**注意事项**：
- 客户数据不暴露
- 发送频率需控制

---

## MGC 1.4.10 工具速查

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `mgc_save` | 存入敏感信息或脚本 | info_type, info_owner, content |
| `mgc_run` | 黑盒执行脚本（1.4.7+） | info_owner, diff_1（schema 必填区分字段，单条任意非空字符串）, ext02(JSON 数组字符串) |
| `mgc_list` | 列出条目 metadata（精确） | info_type |
| `mgc_find` | 模糊搜索（1.4.10 新增） | info_owner, match_mode, limit |
| `mgc_open_webui` | 打开 WebUI | — |

---

## 协作记录及用户反馈

> 每次任务完成后的记录

| 日期 | 任务 | 用户反馈 | 改进点 |
|------|------|---------|-------|
| （暂无） | - | - | 任务执行后自动添加 |
