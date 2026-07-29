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

> 已有的可复用脚本，每次任务后可更新

| 脚本名称 | 功能描述 | 创建时间 | 复用次数 | 备注 |
|----------|---------|---------|---------|------|
| （暂无） | - | - | - | 任务执行后自动添加 |

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

### ext02 参数格式

```python
import json
params = {"key": "value"}
ext02 = json.dumps(params)  # 必须转为 JSON 字符串
```

---

## 用户偏好

> 记录用户的习惯偏好，每次任务后更新

| 偏好项 | 内容 | 更新时间 |
|--------|------|---------|
| （暂无） | - | - |

---

## 常见错误与修复

### 错误 1：mgc_run 返回 422 错误

**原因**：ext02 参数格式错误

**修复**：
```python
import json
ext02 = json.dumps({"to": "user@example.com"})  # 使用 json.dumps
```

### 错误 2：Token 文件不存在

**原因**：MGC 未启动或 Token 路径错误

**修复**：
- 确认 MGC 已启动
- Token 路径：`~/.mgc/database/mgc_black_box/.mgc_token`

### 错误 3：脚本执行失败

**原因**：脚本内部错误

**修复**：
- 检查脚本语法
- 确认凭据名称正确
- 查看 MGC 日志

---

## 场景最佳实践

### 场景 1：数据分析

**流程**：
1. 脚本角色编写查询脚本 → 存入 MGC
2. 执行 Agent 调用脚本获取数据
3. 分析数据，生成报告
4. 发布报告

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

## 协作记录及用户反馈

> 每次任务完成后的记录

| 日期 | 任务 | 用户反馈 | 改进点 |
|------|------|---------|-------|
| （暂无） | - | - | - |
