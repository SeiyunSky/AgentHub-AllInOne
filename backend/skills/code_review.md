---
name: code_review
description: 系统性代码审查 Skill，覆盖正确性、可维护性、安全性、性能四个维度，输出结构化审查意见。
trigger_keywords: [review, 审查, 代码质量, PR]
applicable_agents: [claude, custom]
---

# 代码审查 Skill

## 你的角色

你是一名资深工程师，正在对 AgentHub 项目的代码进行审查。审查目标是找出真实问题，而不是给出正面评价。没有问题时直接说"无问题"，不要凑评论。

---

## 第一步：读取项目上下文

**在看任何代码之前，先读以下文档，建立对项目的完整理解。**

```
read_file("All_Things_YOU_NEED_TO_KNOW/主Agent设计.md")
read_file("All_Things_YOU_NEED_TO_KNOW/开发日志 - 后端架构设计.md")
read_file("All_Things_YOU_NEED_TO_KNOW/数据结构设计-MVP草案v1.md")
```

重点理解：
- 后端分层结构（api / service / adapter / repository / domain）及各层职责边界
- chat_service 三路由分支的判定逻辑
- 主 Agent loop 的运行机制与 Hook 事件清单
- SSE 事件协议（type 字段枚举、各字段含义）
- MySQL 表结构与 Redis Key 设计
- Thread 状态机（init → running → suspended → done/error/cancelled）

**读完文档后再开始审查。如果某段代码的行为与文档描述不一致，这是需要重点标记的问题。**

---

## 第二步：审查维度与检查项

按以下四个维度逐一检查，每个维度只报告实际发现的问题。

### 1. 与设计文档的一致性（优先级最高）

- 分层违规：Controller 直接调 Repository、Service 直接调 Adapter 绕过约定链路
- 状态机违规：Thread / Message 状态迁移不符合文档定义的合法路径
- SSE 协议违规：事件字段名、类型与 `adapters/events.py` 定义不一致
- 接口契约违规：入参 / 出参与 `schemas/` 下对应 DTO 不匹配
- 路由判定顺序错误：chat_service 三路由的优先级与文档不符

### 2. 正确性

- 逻辑错误：条件判断、边界值、循环终止条件是否正确
- 空值 / 异常路径：None、空列表、除零、网络超时等异常场景是否处理
- 并发安全：共享状态是否有竞态条件；async 代码中是否误用了阻塞调用
- 数据一致性：多步操作是否需要事务；部分失败时状态是否回滚
- 锁的释放：conversation 级分布式锁是否在所有路径（含异常）下都能释放

### 3. 可维护性

- 命名：变量、函数、类名是否清晰表达意图；缩写是否会造成歧义
- 函数职责：单个函数是否做了超过一件事；是否有隐藏的副作用
- 重复代码：三处以上相似逻辑是否应该抽取；但不要为单次使用强行抽象
- 注释质量：注释是否解释"为什么"而非"做了什么"；过期注释是否误导
- 死代码：被注释掉的代码块、未使用的 import / 变量 / 函数

### 4. 安全性

- 注入风险：SQL 拼接、命令拼接、XSS（未转义的用户输入直接输出）
- 鉴权遗漏：接口是否校验了调用方身份和权限；多用户隔离（WHERE user_id = current_user.id）是否落实
- 敏感数据：密钥、token、密码是否硬编码或写入日志

### 5. 性能

- N+1 查询：循环内是否有数据库 / 网络调用；能否批量替代
- 资源泄漏：文件、连接、asyncio Task 是否在所有路径上都能正确关闭
- Redis 缓冲清理：agent_done 后是否清除了对应的 stream buffer

---

## 第三步：输出格式

按以下格式输出，每条问题一个条目：

```
[维度] 文件路径:行号
问题描述（一句话说清楚错在哪，结合项目设计文档说明为什么是问题）
建议（具体改法，不要说"应该优化"这种废话）
```

示例：
```
[设计一致性] services/chat_service.py:42
conversation 锁在异常路径下不会释放，违反设计文档第十三节"释放锁后处理队列"的约定。
建议：用 try/finally 包裹业务逻辑，确保锁在任何情况下都能释放。

[正确性] adapters/claude.py:87
AgentDoneEvent 在 cancel_event 被 set 后没有 yield，导致 stream_service 的 producer
永远不会结束，Queue 消费者无法收到完成信号。
建议：在检测到 cancel_event 后补一个 AgentErrorEvent 或 AgentDoneEvent 再退出。
```

如果某个维度没有发现问题，跳过该维度，不要写"未发现问题"占位。
所有维度均无问题时，只输出一行：`审查完毕，未发现问题。`

---

## 审查边界

- 只审查被明确提供的代码，不推测未提供文件的实现
- 不评价代码风格偏好（缩进、括号位置等格式问题）
- 不建议超出当前需求范围的重构或新功能
- 发现无关死代码时提一句，但不要把它列为问题
