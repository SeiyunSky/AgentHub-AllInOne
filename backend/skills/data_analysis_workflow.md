---
name: data_analysis_workflow
description: 数据分析师专用工作流 — 从加载到结论的标准 SOP,搭配 pandas/numpy/matplotlib 用
trigger_keywords: [数据分析, 分析数据, 报表, 指标, 趋势]
applicable_agents: [claude, custom]
---

# 数据分析标准工作流

数据分析师 Agent 接到分析任务时**严格按此流程**。每步必须留下可审查的产出(脚本 + 输出),便于 reviewer_data 验证。

## 阶段 0:确认前置条件

检查主 Agent 在 dispatch_prompt 里是否已提供:
1. 分析目标(要回答什么决策问题)
2. 关键指标定义和计算口径
3. 可用数据源清单

**有任何一项缺失** → 不要硬上,先回报"需要 research_data 调研以下口径:[列出来]"。

## 阶段 1:数据加载与速看

每份新数据先无脑跑这几行,**输出贴报告里**:

```python
import pandas as pd

df = pd.read_csv("data/orders.csv")  # 或 read_excel / read_json / read_sql

print("Shape:", df.shape)
print("\n=== Head ===")
print(df.head())
print("\n=== Dtypes ===")
print(df.dtypes)
print("\n=== Missing ===")
print(df.isna().sum())
print("\n=== Describe ===")
print(df.describe(include='all'))
```

**这一步不能跳**。reviewer_data 第一件事就是检查有没有这些输出。

## 阶段 2:清洗

针对阶段 1 看到的问题逐项处理。**所有处理写在脚本里,不要 notebook 里改完不留痕**。

### 类型修正

```python
df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
# errors='coerce' 让解析失败的变 NaT,后面统一处理
```

### 缺失值

明确策略,**写注释说明为什么这么处理**:

```python
# user_id 缺失的行无法归因,直接丢弃
before = len(df)
df = df.dropna(subset=['user_id'])
print(f"Dropped {before - len(df)} rows due to missing user_id")

# amount 缺失视为 0(订单生成失败的情况)
df['amount'] = df['amount'].fillna(0)
```

### 异常值

看分布(`describe()` / `df['col'].plot.hist()`),决定是真极端还是脏数据:

```python
# 单笔金额 > 100万的视为脏数据(业务上限 50 万)
outliers = df[df['amount'] > 1_000_000]
print(f"Found {len(outliers)} outliers, dropping")
df = df[df['amount'] <= 1_000_000]
```

### 去重

```python
before = len(df)
df = df.drop_duplicates(subset=['order_id'])
print(f"Dropped {before - len(df)} duplicate orders")
```

## 阶段 3:核心分析

按业务问题写代码。常见模式参考:

### 时间序列趋势

```python
daily = (df
    .groupby(df['created_at'].dt.date)
    .agg(
        orders=('order_id', 'count'),
        users=('user_id', 'nunique'),       # 注意: nunique 不是 count
        revenue=('amount', 'sum'),
    )
    .reset_index()
    .rename(columns={'created_at': 'date'})
)
```

### 同环比

```python
daily['revenue_dod_pct'] = daily['revenue'].pct_change() * 100  # 日环比
daily['revenue_wow_pct'] = daily['revenue'].pct_change(periods=7) * 100  # 周环比
```

### 漏斗

```python
funnel = pd.DataFrame({
    'stage': ['访问', '加购', '下单', '支付'],
    'users': [
        df[df['event'] == 'visit'].user_id.nunique(),
        df[df['event'] == 'add_to_cart'].user_id.nunique(),
        df[df['event'] == 'order'].user_id.nunique(),
        df[df['event'] == 'paid'].user_id.nunique(),
    ],
})
funnel['conversion'] = funnel['users'] / funnel['users'].iloc[0] * 100
```

### 留存

```python
# 注:留存定义口径要严格按 research_data 给的来
# 这里假设"次日留存" = 首日有事件的用户次日也有事件
```

## 阶段 4:可视化(推荐)

关键发现配图。matplotlib 出图存沙箱 PNG,**不要 plt.show()**:

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(daily['date'], daily['revenue'], marker='o')
ax.set_title('Daily Revenue Trend')
ax.set_xlabel('Date')
ax.set_ylabel('Revenue (¥)')
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig('output/revenue_trend.png', dpi=120)
plt.close(fig)
```

## 阶段 5:结论与报告

按 `data_storytelling` skill 的格式输出。

## 文件组织

```
sandbox/{conv_id}/
├── data/                # 源数据(read-only,不改)
│   └── orders.csv
├── scripts/
│   └── analysis.py      # 分析脚本(reviewer_data 审这个)
├── output/              # 产出
│   ├── revenue_trend.png
│   ├── daily_summary.csv  # 计算出的中间数据
│   └── report.md          # 最终报告
└── README.md            # 任务说明(可选)
```

## 反模式(不要这么做)

- ❌ 跳阶段 1 直接分析(reviewer 拒收)
- ❌ 在 chat 里贴 raw 数据当分析(应该写脚本然后跑出来)
- ❌ 给"明显结论"不附数字("销量上涨明显" → 涨多少?基线多少?)
- ❌ 多个数据源 join 时不验证 join key 唯一性
- ❌ 改业务口径自己创新发明(必须按 research_data 来)
