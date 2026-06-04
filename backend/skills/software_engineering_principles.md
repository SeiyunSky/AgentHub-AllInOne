---
name: software_engineering_principles
description: 软件工程通则 - YAGNI / KISS / 单一职责 / 不过度设计。所有写代码或评审代码的 Agent 都应挂载,作为统一基线。
trigger_keywords: [写代码, 实现, 重构, 审查]
applicable_agents: [claude, custom]
---

# 软件工程通则

无论 Coder / Reviewer / Architect,做技术决定时遵守下面这些原则。**这些不是"风格偏好",是底线**。

## 1. YAGNI (You Aren't Gonna Need It)

只为当前明确需求写代码。不给"未来可能用到"的场景预留扩展点。

具体行为:
- 不为单次使用的逻辑抽象成函数
- 不写没人会调的"通用工具类"
- 不加没必要的配置项("万一用户想改..."→ 等真有用户提出来再说)
- 不为不存在的"插件机制"留 hook

## 2. KISS (Keep It Simple, Stupid)

**两种实现都能满足需求时,选简单的那个**。复杂度要靠需求拉起来,不能凭空叠。

判定:如果一段代码读起来需要"先记住三个概念才能看懂",就是过度复杂。

## 3. 不在系统边界以外做防御

只在以下边界做输入校验和异常处理:
- 用户输入(HTTP 请求 body / query params)
- 外部 API 返回(LLM / 第三方服务)
- 数据库读出来的"可能脏"的数据(老数据迁移过来的)

**内部代码相互信任**。不要在每个内部函数开头都写一堆 `if x is None: raise`。框架已经保证的事不要重复保证。

## 4. 不写"未来可能要解释"的注释

注释只写**为什么**这么做,不写**做了什么**(代码本身能读出来的别复述)。

❌ 反例:
```python
# 把 user_id 加到 query 里
query.user_id = user_id
```

✅ 正例:
```python
# 旧版 schema 没 user_id 字段,先以 owner_id 兜底,迁移后删除这段
query.user_id = user.id or user.owner_id
```

## 5. 改动最小化

修 bug 不顺手重构相邻代码。需求是"加按钮"就只加按钮,不顺手改样式系统。

每一行改动应该能直接对应回**用户提的需求**或**bug 报告**。无关改动单独提 PR。

## 6. 优先用现成的,不重造轮子

当前项目已有的工具 / 函数 / 服务优先复用。新建之前先 grep 一下。

## 7. 命名重于注释

好的命名能省掉 80% 的注释。
- 函数名表达"做什么":`update_user_email` 不是 `process_user`
- 布尔变量明显是 yes/no:`is_admin` / `has_permission` 不是 `admin` / `permission`
- 数字带单位:`timeout_seconds` 不是 `timeout`

## 8. 不为假设性能优化牺牲可读性

需要优化的前提是**已经测出**慢。`O(n^2)` 在 n=10 的场景下完全没问题。

先写清楚,再用 profiler 找瓶颈,有数据再优化。

## 何时违反这些原则是 OK 的

明确写注释说明**为什么**违反:
```python
# 这里的早期 None 校验是有意的:外部 webhook 可能送进 null,
# 内部不防御直接 AttributeError 太隐晦,会被运维误判为代码 bug
if event_payload is None:
    return
```

## 总结

每写一行代码问自己:"这行直接对应了用户什么需求?"
- 答得出来 → 留
- 答不出来 → 删
