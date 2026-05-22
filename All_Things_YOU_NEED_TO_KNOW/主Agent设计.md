# 主Agent 设计 - 工作中

> 队伍：咕嘎一辈子队
> 修改者：Adam Zhang
> 修改日期：2026-05-22
>
> 本文档是主Agent（Orchestrator）的设计稿。

---

## 一、整体架构图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       Client (Vue 3 前端)                                 │
│  会话列表  │  聊天流（多 Agent 并行气泡）  │  产物预览 / Diff / 审批       │
└────────────────────────────▲─────────────────────────────────────────────┘
                             │ SSE / WebSocket / REST
                             │
┌────────────────────────────┼─────────────────────────────────────────────┐
│   AgentHub Backend         │                                              │
│                            │                                              │
│  ┌─────────────────────────┴──────────────────────────────────┐  ┌─────┐ │
│  │  api/  Controller (JWT、SSE 端点、WebSocket)                │◀─┤     │ │
│  └─────────────────────────┬──────────────────────────────────┘  │ H   │ │
│                            │                                     │ o   │ │
│  ┌─────────────────────────▼──────────────────────────────────┐  │ o   │ │
│  │  chat_service  三路由分发                                    │◀─┤ k   │ │
│  │  单聊直通 / @个体特化 / 群聊→主Agent                          │  │     │ │
│  └─────────────────────────┬──────────────────────────────────┘  │ 抽  │ │
│                            │                                     │ 象  │ │
│  ┌─────────────────────────▼──────────────────────────────────┐  │ 层  │ │
│  │  主Agent (orchestrator_service)                             │◀─┤     │ │
│  │  System Prompt 六层管道 / Agent Loop / Tools / Memory /      │  │ 贯  │ │
│  │  Error Recovery 三路                                         │  │ 穿  │ │
│  └─────────────────────────┬──────────────────────────────────┘  │ 所  │ │
│                            │                                     │ 有  │ │
│  ┌─────────────────────────▼──────────────────────────────────┐  │ 层  │ │
│  │  thread_service  Thread 生命周期 + 任务图调度                │◀─┤     │ │
│  │  init → running → suspended → done/error                    │  │ 在  │ │
│  │  blocked_by 解锁 → 并行启动                                  │  │ 关  │ │
│  └─────────────────────────┬──────────────────────────────────┘  │ 键  │ │
│                            │                                     │ 时  │ │
│  ┌─────────────────────────▼──────────────────────────────────┐  │ 刻  │ │
│  │  adapters/  Claude / Codex / OpenCode / Custom              │◀─┤ fire│ │
│  └─────────────────────────┬──────────────────────────────────┘  │ 事  │ │
│                            │                                     │ 件  │ │
│  ┌─────────────────────────▼──────────────────────────────────┐  │     │ │
│  │  stream_service  asyncio.TaskGroup + Queue 合并多路 SSE      │◀─┤     │ │
│  └─────────────────────────────────────────────────────────────┘  └─────┘ │
└──────────────────────────────────────────────────────────────────────────┘

事件清单：SESSION_START / PRE_ORCHESTRATE / POST_ORCHESTRATE /
        PRE_DISPATCH / POST_DISPATCH / PRE_TOOL_USE / POST_TOOL_USE /
        APPROVAL_REQUESTED / APPROVAL_DECIDED /
        PRE_THREAD_START / POST_THREAD_END

监听者：AuditLogger（写 audit_logs）/ RateLimiter / PermissionGate / ...
```

---

## 二、主流程图（用户单次发消息）

```
用户发消息
   │
   ▼
[chat_service 三路由分发]
   ├ selected_range 不为空 → 局部修改流程（特化 prompt）
   ├ mode=single          → 单聊：直通 Adapter
   ├ group + 单 mention   → @个体特化：thread_service.resume_or_create
   └ group 全员 / 无mention → 走主Agent
                                │
                                ▼
                       [主Agent loop 启动]
                                │
                       SESSION_START hook
                       读长期记忆（read_file MEMORY.md → 按相关性挑 top-K）
                                │
                                ▼
                  [构建 System Prompt 六层管道]
                                │
                                ▼
                       loop 一轮 = 调 LLM
                                │
              ┌─────────────────┴────────────────┐
              ▼                                  ▼
       stop_reason=end_turn            stop_reason=tool_use
              │                                  │
       respond_to_user                    PRE_TOOL_USE hook
       loop 结束                                 │
              │                                  ▼
              │                       工具分支：
              │                        - dispatch_to_agent → 创建子 Thread → PRE_DISPATCH hook
              │                        - read_thread_status / read_thread_result
              │                        - create_task_plan / update / read
              │                        - create_file / read_file / edit_file
              │                                  │
              │                          POST_TOOL_USE hook
              │                          拼工具结果到 context → 下一轮 loop
              │
              │         (期间任意时刻：子 Thread done/error)
              │            │
              │     POST_DISPATCH hook
              │     事件驱动注入 user 消息「Thread t_xxx done, 摘要：...」
              │     唤醒主Agent loop 跑下一轮
              │
              ▼
       POST_ORCHESTRATE hook
              │
              ▼
       round_done 推前端
```

---

## 三、章节索引

| # | 章节 | 状态 |
|---|---|---|
| 四 | 主Agent 是什么 | 已定 |
| 五 | Tools 工具集 | 已定 |
| 六 | Memory 双层管理 | 已定 |
| 七 | Hook 抽象 | 已定 |
| 八 | System Prompt 六层管道 | 已定 |
| 九 | 主Agent 自挂的 Skill | 已定 |
| 十 | Error Recovery | 已定 |
| 十一 | 任务图调度算法 | 已定 |
| 十二 | 主Agent loop 实现思路 | 已定 |
| 十三 | chat_service 三路由分发 | 已定 |
| 十四 | stream_service 并行流合并 | 已定 |
| 十五 | 接口契约 | 已定 |

---

## 四、主Agent 是什么

**主Agent ≠ 路由器**。它是一个完整的 Agent，有自己的：

| 维度 | 说明 |
|---|---|
| Skill | 主Agent 自己挂的 Skill |
| Tools | 调度类、任务链管理、用户交互、文件（19 个内置） |
| Memory | 短期（Thread.checkpoint）+ 长期（文件方案） |
| System Prompt | 六层管道 |
| 错误恢复 | max_tokens / prompt_too_long / API 错误三路恢复 |
| Context 压缩 | 大输出持久化 + 摘要 |
| 任务图调度 | 依赖图 + 并行/串行混合 |

它和子 Agent 的本质区别：

- 子 Agent 的工具是 `bash / read_file / write_file / edit_file ...`（操作代码 / 文件）
- 主 Agent 的工具是 `dispatch_to_agent / read_thread_result / 文件 ...`（操作其他 Agent 与全局状态）

---

## 五、Tools 工具集

### 1. 设计原则

- **下派优先**：能让子 Agent 做的事都不放在主Agent
- **没有 bash**：主Agent 不直接执行命令
- **异步调度**：`dispatch_to_agent` 派完立即返回 thread_id，子 Thread 完成时通过事件回注主Agent context
- **可观测**：所有调度结果都能用 thread_id 反查
- **细粒度任务图**：依赖关系显式声明，调度器按图启动
- **记忆即文件**：长期记忆是普通文件目录，主Agent 用通用文件工具操作

### 2. 工具列表（19 个内置）

#### A. 任务调度（4 个）

| 工具 | 用途 |
|---|---|
| `dispatch_to_agent(agent_id, prompt, role_hint, blocked_by=[])` | 异步派任务给某个 Agent，可声明依赖；返回 thread_id |
| `read_thread_status(thread_id)` | 查 Thread 当前状态（init/running/suspended/done/error） |
| `read_thread_result(thread_id)` | 读取 Thread 完整结果（含中间产物） |
| `cancel_thread(thread_id)` | 主动中止某个子 Thread |

#### B. 任务链管理（5 个）

| 工具 | 用途 |
|---|---|
| `create_task_plan(tasks)` | 创建结构化任务计划（含依赖图）落地到 `threads` 表 |
| `update_task_status(task_id, status)` | 更新任务状态 |
| `read_task_plan()` | 读取当前轮次的完整任务图 |
| `add_task(...)` | 运行中动态追加任务 |
| `remove_task(...)` | 运行中移除尚未启动的任务 |

> 任务计划本身落地到 MySQL `threads` 表 + `blocked_by` JSON 字段，不是文件。

#### C. 用户交互（3 个）

| 工具 | 用途 |
|---|---|
| `respond_to_user(message)` | 直接给用户回话（不走子 Agent） |
| `request_user_clarification(question)` | 主动问用户澄清问题（暂停整轮等待） |
| `present_task_plan_for_review(plan)` | 向用户展示拟执行的任务计划，等用户批准 |

#### D. 上下文检索（3 个）

| 工具 | 用途 |
|---|---|
| `read_conversation_history(limit=N)` | 读取当前会话最近 N 条消息 |
| `list_available_agents()` | 列出当前会话挂载的所有 Agent + 能力 |
| `get_agent_capabilities(agent_id)` | 查某个 Agent 的详细能力（capabilities / tags / skills） |

#### E. 文件（4 个）

| 工具 | 用途 |
|---|---|
| `create_file(path, content)` | 创建新文件（任务说明 / 阶段总结 / 计划文档 / 新记忆） |
| `read_file(path)` | 读取文件（子 Agent 产出 / 记忆文件） |
| `edit_file(path, old_text, new_text)` | 精确替换文件中一段文字（编辑 MEMORY.md / 记忆文件） |
| `list_directory(path)` | 列目录（探索记忆目录 / 浏览子 Agent 产出） |

> 不给 `write_file`（全文覆盖），防止误毁。

---

## 六、Memory 双层管理

### 1. 设计原则

- **记忆即文件**：记忆是普通 markdown 文件，不入 MySQL
- **作用域**：用户 + 会话双重隔离 `runtime/memory/{user_id}/{conversation_id}/`
- **主Agent 自主操作**：用通用文件工具读写，不做专用记忆 API
- **MEMORY.md 索引**：主Agent 进入对话时先 read_file 读索引，按需再读具体记忆
- **frontmatter 元数据**：每条记忆 markdown 文件头有 frontmatter（type / name / description / created_at / updated_at）

### 2. 双层结构

| 层 | 范围 | 存哪 | 何时读 | 何时写 |
|---|---|---|---|---|
| **短期** | 一个 Thread 内 | `threads.checkpoint` JSON 字段 | Thread resume 时 | 每次 loop 一轮结束 |
| **长期** | 跨 Thread / 跨会话内的 user+conv | `runtime/memory/{user_id}/{conv_id}/*.md` | 主Agent 进入 loop 前 | 主Agent 检测到值得记的事 |

### 3. 长期记忆目录结构

```
runtime/memory/{user_id}/{conversation_id}/
├── MEMORY.md                   ← 索引（一行一条，主Agent 第一步读）
├── user_role.md                ← user 类型
├── feedback_no_emoji.md        ← feedback 类型
├── project_agenthub.md         ← project 类型
└── reference_design_doc.md     ← reference 类型
```

### 4. 记忆类型（4 类）

| 类型 | 内容 | 何时写 |
|---|---|---|
| **user** | 用户身份 / 技术栈 / 口味 / 工作方式 | 用户首次表态、推断出关键身份信息 |
| **feedback** | 用户对主Agent 的纠正、确认 | 用户说"别这样"/"对，就这样"时立即写 |
| **project** | 当前会话相关的项目背景 | 用户描述项目 / 拆任务时识别出关键约束 |
| **reference** | 外部链接、参考资源 | 用户提供链接 / 引用了外部资料 |

### 5. 单条记忆文件格式

```markdown
---
name: feedback_no_emoji
description: 用户明确要求所有输出禁用 emoji
type: feedback
created_at: 2026-05-22T10:30:00
updated_at: 2026-05-22T10:30:00
---

用户在 2026-05-22 明确说："不要 emoji，看着就脑残"。
此后所有主Agent 与子 Agent 输出都禁止用 emoji，
包括聊天回复、产物文档、commit 消息。
```

### 6. MEMORY.md 索引格式

```markdown
- [feedback_no_emoji](feedback_no_emoji.md) — 用户禁用 emoji
- [project_agenthub](project_agenthub.md) — 4 人团队，20 天 IM 多 Agent 协作平台
- [reference_design_doc](reference_design_doc.md) — 用户提供的设计参考文档链接
```

### 7. 主Agent 读取记忆流程

```
主Agent loop 启动
  ↓
read_file MEMORY.md  → 拿索引
  ↓
按当前任务相关性，挑出 top-K（默认 5）
  ↓
read_file 逐个读详细内容
  ↓
塞到 system prompt 的"长期记忆"层
```

### 8. 主Agent 写入记忆流程

```
主Agent 检测到值得记的事
  ↓
create_file 写新记忆文件（frontmatter + 正文）
  ↓
edit_file 把新一行追加到 MEMORY.md
  ↓
hook 触发 → 写 audit_logs
```

### 9. 短期记忆压缩策略（三层）

| 层 | 触发 | 行为 |
|---|---|---|
| 大工具输出持久化 | dispatch 子 Thread 完成 | 完整结果不放 messages_history，只留摘要 + thread_id |
| micro_compact | 每轮结束检查 | 保留最近 N（默认 3）次工具结果，老的折叠为占位 |
| 全局摘要 | token 超阈值（默认 30K） | LLM 摘要 → 用摘要 + 最近 5 条替换全部 messages_history |

### 10. Token 预算

| 项 | 阈值 | 行为 |
|---|---|---|
| 长期记忆 | 单条 5K（软上限） | 主Agent prompt 提示警告 |
| 短期记忆 | 50K | 触发压缩 |

---

## 七、Hook 抽象

### 1. 设计原则

- Hook 是切面机制，业务 service 在关键时刻 fire 事件
- 审计 / 限流 / Skill 注入 / 权限检查这些横切关注点用 Hook 实现，不散落在业务代码里
- Hook 的返回值能影响主流程（继续 / 阻断 / 注入消息 / 改写工具入参）

### 2. 实现形态（同步 + 异步并存）

按 hook 的性质分两种实现形态，**不是二选一**：

| 形态 | 适用 hook | 是否阻塞主流程 |
|---|---|---|
| **同步 Python 函数** | 限流 / 权限检查 / 审批 / Skill 注入 / 任何要 block / inject / replace_input 的 hook | 阻塞 |
| **异步线程池** | 审计日志 / 任何只观察不影响主流程的 hook | 不阻塞，发后即忘 |

调用约定：

- 同步 hook：`await hook_manager.fire(event, ctx)` 阻塞拿 HookResult，按 decision 决策
- 异步 hook：`hook_manager.emit(event, ctx)` 投到 worker 队列，立即返回，主流程不等

每个事件可同时注册多个 hook，混合形态。例如 `PRE_TOOL_USE`：
- 同步：权限检查（决定是否 block）
- 异步：审计日志（写 audit_logs，主流程不等）

### 3. Hook 事件枚举（11 个）

| 事件 | 触发时机 |
|---|---|
| `SESSION_START` | 用户发消息进入 chat_service 时 |
| `PRE_ORCHESTRATE` | 主Agent loop 启动前 |
| `POST_ORCHESTRATE` | 主Agent loop 结束后 |
| `PRE_DISPATCH` | 派子 Thread 前（每次 dispatch_to_agent 工具调用） |
| `POST_DISPATCH` | 子 Thread 完成事件回注前 |
| `PRE_TOOL_USE` | 主Agent 调用任何工具前 |
| `POST_TOOL_USE` | 主Agent 调用任何工具后 |
| `APPROVAL_REQUESTED` | 子 Thread 触发审批 |
| `APPROVAL_DECIDED` | 用户决策审批 |
| `PRE_THREAD_START` | 子 Thread 启动前（Adapter 层 fire） |
| `POST_THREAD_END` | 子 Thread 结束（Adapter 层 fire） |

### 4. Hook 返回值协议（同步 hook 用 / 4 种决策）

异步 hook 没有返回值。下面 4 种决策只对同步 hook 有效：

| 决策 | 含义 |
|---|---|
| `continue` | 正常往下走 |
| `block` | 中断流程，业务层抛异常 |
| `inject` | 注入一段消息到主Agent context |
| `replace_input` | 改写工具的 input（hook 拦截改参数） |

### 5. HookContext 字段（统一 payload）

| 字段 | 类型 |
|---|---|
| event | HookEvent |
| trace_id | str |
| user_id | str |
| conversation_id | str |
| thread_id | Optional[str] |
| message_id | Optional[str] |
| agent_id | Optional[str] |
| tool_name | Optional[str] |
| tool_input | Optional[dict] |
| tool_output | Optional[Any] |
| extra | dict |

### 6. 主Agent 与 Hook 的关系

- 主Agent loop 在每次工具调用前后 fire `PRE_TOOL_USE` / `POST_TOOL_USE`，这是审计日志的核心来源
- 主Agent loop 内的 dispatch 工具会 fire `PRE_DISPATCH`，子 Thread 完成回注前 fire `POST_DISPATCH`
- 会话级事件（`SESSION_START` / `PRE_ORCHESTRATE` / `POST_ORCHESTRATE`）由外层 chat_service / orchestrator_service 包装时 fire
- 子 Thread 的执行事件（`PRE_THREAD_START` / `POST_THREAD_END`）由 Adapter 层 fire

---

## 八、System Prompt 六层管道

### 1. 设计原则

- system prompt 不是单一字符串，而是分层组装管道
- 静态层 + 动态层之间放 `DYNAMIC_BOUNDARY` 标记，方便 LLM 前缀缓存
- 每层都可独立调整，不互相耦合

### 2. 六层结构

| 层 | 内容 | 静态 / 动态 |
|---|---|---|
| 1. 核心指令 | "你是 AgentHub 主Agent，负责调度多个子 Agent..." | 静态 |
| 2. 工具列表 | 19 个内置工具的 schema | 静态 |
| 3. Skill 元数据 | 主Agent 自挂的 Skill description（progressive disclosure） | 静态 |
| 4. CLAUDE.md 链 | 用户全局 CLAUDE.md + 项目级 CLAUDE.md 内容 | 静态 |
| --- | DYNAMIC_BOUNDARY | --- |
| 5. 长期记忆 | 按当前任务相关性筛出的 top-K 条记忆正文 | 动态 |
| 6. 动态上下文 | 当前会话历史 + 可用 Agent 列表 + 当前任务图状态 | 动态 |

### 3. CLAUDE.md 加载优先级

1. 用户全局：`~/.claude/CLAUDE.md`
2. 项目根：`{project_root}/CLAUDE.md`
3. 子目录：`{cwd}/CLAUDE.md`（如有）

合并方式：依次拼接，不去重（用户偏好优先级最高，写在最前）

---

## 九、主Agent 自挂的 Skill

### 1. 设计原则

- 主Agent 的 Skill 用于教它"怎么做调度"，不是教子 Agent 干活
- Skill 走 progressive disclosure：system prompt 只放 description 列表，主Agent 调 `load_skill` 工具按需加载完整正文
- Skill 文件存 `backend/skills/orchestrator/*.md`，与子 Agent 的 Skill 分目录

### 2. 候选 Skill 列表

| Skill | 描述 |
|---|---|
| `task-decomposition` | 教主Agent 怎么把用户大需求拆成可执行的子任务 |
| `agent-routing` | 教主Agent 怎么根据任务特性选合适的子 Agent |
| `dependency-analysis` | 教主Agent 怎么识别任务间依赖关系（哪些必须串行） |
| `result-aggregation` | 教主Agent 怎么聚合多个子 Agent 的产出 |
| `failure-recovery` | 教主Agent 怎么在子 Agent 失败时降级 / 切换 |
| `memory-curation` | 教主Agent 什么值得记 / 什么不值得记 |

### 3. Skill 文件结构

每个 Skill 一个 markdown 文件，frontmatter + 正文：

```markdown
---
name: task-decomposition
description: 把用户需求拆解成可独立执行的子任务，识别依赖关系
applicable_to: orchestrator
---

# 任务拆解原则
（完整正文）
```

### 4. 加载机制

- 启动时扫描 `backend/skills/orchestrator/*.md`，构建 SkillRegistry
- system prompt 第 3 层只放 description 列表
- 主Agent 决定需要某 Skill 时调 `load_skill(name)` 工具读完整正文

---

## 十、Error Recovery

### 1. 设计原则

- LLM 调用失败有 3 类原因，每类一套恢复策略
- 单次重试不够则降级到下一策略
- 所有恢复都写 audit_logs，方便事后分析

### 2. 三路恢复

| 错误类型 | 触发条件 | 恢复策略 |
|---|---|---|
| **max_tokens** | LLM 返回 stop_reason=max_tokens | 注入"请继续"用户消息让其续写，最多 3 次 |
| **prompt_too_long** | API 返回上下文过长错误 | 调 LLM 摘要历史 → 替换 messages_history → 重试 |
| **API 错误** | 网络 / 5xx / rate limit | 指数退避：base × 2^attempt + 随机抖动，最多 5 次 |

### 3. 子 Agent 失败的处理

- 单 Agent failed → 该 Thread 标记 error，主Agent context 注入"Thread t_xxx 失败：原因"
- 主Agent 自己决定下一步（重派 / 切换 Agent / 跳过 / 报告用户）
- 不影响其他并行 Agent 继续执行

### 4. 主Agent 自身失败

- 主Agent loop 异常 → 写 audit_logs（含完整 stack trace）
- 推 SSE 事件 `agent_error` 给前端
- 释放 conversation 锁
- 前端显示错误提示，用户可点"重试"重新发起

---

## 十一、任务图调度算法

### 1. 设计原则

- 任务以 DAG 形式存储，节点 = Thread，边 = blocked_by
- 调度器只启动"无未完成依赖"的节点
- 每次节点完成事件触发解锁扫描

### 2. 数据模型

`threads` 表关键字段：

| 字段 | 含义 |
|---|---|
| id | Thread ID |
| status | init / running / suspended / done / error |
| blocked_by | JSON 数组，存依赖的 thread_id |

### 3. 调度流程

```
主Agent dispatch_to_agent 多次后
  → thread_service 把所有 Thread 落库（status=init）

调度循环（独立协程）：
  扫所有 init Thread
  对每个 init Thread：
    所有 blocked_by 都 done → 启动（init → running，调对应 Adapter）
  等任意 Thread 状态变化（done / error / suspended）
  重新扫
  直到没有 init / running / suspended Thread
```

### 4. 解锁判定

任意 Thread 进入 done/error 时：

1. 找出所有 blocked_by 包含该 thread_id 的其他 Thread
2. 检查它们的所有 blocked_by 是否都已 done
3. 全 done 则解锁，进入可启动队列

### 5. 死锁检测

- 创建任务计划时校验 DAG 无环
- 有环则拒绝创建，报错给主Agent

### 6. 失败传播策略

| 策略 | 行为 |
|---|---|
| **传播** | A failed → 所有依赖 A 的下游全部标 cancelled |
| **不传播** | A failed → 下游 Thread 改成依赖 A 的"错误结果"继续跑 |

MVP 默认 **传播**，主Agent 可按需手动 add_task 补救。

---

## 十二、主Agent loop 实现思路

### 1. 一轮的步骤

1. 检查并消费唤醒事件（pop pending events 队列，转成 user 消息追加到 context）
2. 构建 System Prompt，调 LLM
3. 异常 → 进入 Error Recovery 三路 → 重试或降级
4. `stop_reason=end_turn` → 标 Thread done，结束
5. `stop_reason=tool_use` → 顺序处理 tool block：fire `PRE_TOOL_USE` → 执行工具 → fire `POST_TOOL_USE` → 拼 tool_result 回 context
6. 持久化 checkpoint（threads.checkpoint）
7. 检查 token 是否超 50K，超则触发短期记忆压缩
8. 回到第 1 步

### 2. 唤醒机制

- 子 Thread done/error 时写入 `pending_events:{parent_thread_id}` 队列
- 主Agent loop 每轮开头先 pop 该队列，把事件格式化为 user 消息追加
- 主Agent 处于 suspended 时（无未完成 dispatch），队列写入触发唤醒

### 3. 主Agent 自身也是 Thread

- 一个会话的主Agent 也对应 `threads` 表里一行（agent_id="orchestrator"）
- 它的 checkpoint 也是 messages_history
- 它和子 Thread 通过 parent 关系绑定（threads 表保留 parent_thread_id 字段）

---

## 十三、chat_service 三路由分发

### 1. 路由判定优先级

按以下顺序判定，命中即走对应分支：

| 优先级 | 条件 | 分支 |
|---|---|---|
| 1 | `selected_range` 不为空 | 局部修改流程 |
| 2 | `mode == single` | 单聊流程（直通 Adapter） |
| 3 | `mode == group` 且 mention 数 = 1 | @个体特化流程（resume_or_create） |
| 4 | 其他 | 群聊全员流程（走主Agent） |

### 2. 单聊流程（直通）

- 直接走 `thread_service.create_thread` + 对应 Adapter
- 不进主Agent loop（单聊没有调度需求）

### 3. @个体特化流程

- `thread_service.resume_or_create(agent_id, conversation_id)` 找历史 Thread
- 复用上下文继续跑该 Agent
- 不打扰其他 Agent

### 4. 群聊全员流程

- 进入主Agent loop（创建 orchestrator Thread）
- 主Agent 自己决定派给哪些子 Agent

### 5. 局部修改流程

- prompt_service 加载 `prompts/local_edit.md` 模板
- 渲染：file / start / end / selected_code / user_intent
- 走单聊 / 群聊主流程（取决于 mode）

---

## 十四、stream_service 并行流合并

### 1. 设计原则

- 所有子 Thread 流式事件汇总到一个 SSE 连接推前端
- 用 `asyncio.Queue` 作为多生产者单消费者通道
- 每个事件自带 `agentId / messageId`，前端按字段路由到对应气泡

### 2. 合并机制

- 每个子 Thread 是一个 producer：从 Adapter 拿事件流，逐条 put 进 Queue，结束时 put AgentDoneEvent
- 单一 consumer：从 Queue 取事件，逐条 yield 成 SSE 推前端
- 所有 producer 都 done 后，consumer 推 RoundDoneEvent，关闭 SSE

### 3. SSE 事件协议

参见《数据结构设计-MVP草案v1.md》第三节，所有事件含 `agentId / messageId`。

### 4. 中止流式

- 用户点"停止" → 后端收到 → 标记 conversation 的 abort 标志
- 各 producer 检查 abort 标志主动退出
- 清 Redis 缓冲

---

## 十五、接口契约

### 1. chat_service 输入输出

| 字段 | 类型 | 说明 |
|---|---|---|
| conversation_id | str | |
| content | str | |
| mention_ids | list[str] | |
| selected_range | Optional[SelectedRange] | 局部修改时携带 |

输出：SSE 事件流（协议见数据结构文档）

### 2. orchestrator_service 输入

| 字段 | 类型 |
|---|---|
| conversation_id | str |
| user_message_id | str |
| available_agents | list[Agent] |
| history_window | int |

输出：通过工具调用驱动 thread_service / stream_service，没有直接返回值。

### 3. thread_service 关键方法

| 方法 | 说明 |
|---|---|
| `create_thread(agent_id, conversation_id, message_id, blocked_by=[])` | 创建 Thread，返回 Thread |
| `resume_or_create(agent_id, conversation_id)` | @个体特化用，找最近 Thread 或新建 |
| `update_status(thread_id, status)` | 状态机迁移 |
| `save_checkpoint(thread_id, checkpoint)` | 持久化短期记忆 |
| `mark_done(thread_id, result)` | 标记 done 并写入结果 |
| `mark_error(thread_id, error)` | 标记 error 并写入错误信息 |

### 4. stream_service 关键方法

| 方法 | 说明 |
|---|---|
| `stream_round(conversation_id, threads)` | 启动多 producer + 单 consumer，yield SSE 事件流 |
| `abort(conversation_id)` | 中止该 conversation 的当前流式 |

### 5. Hook fire 接口

| 方法 | 说明 |
|---|---|
| `hook_manager.fire(event, ctx)` | 返回 HookResult，业务按 decision 决定继续 / 阻断 / 注入 / 改入参 |
