# 数据结构设计 - MVP

## MVP 功能清单

1. 登录/登出
2. 单聊（Claude）
3. 群聊并行流（Claude + Codex）
4. @个体特化
5. Diff卡片 + 一键应用
6. HTML产物预览
7. 对话式创建Agent
8. 审批Action
9. 消息点赞/点踩、删除、复制、重新生成
10. 会话重命名、置顶、归档
11. 流式中止

---

## 一、MySQL 表设计

### 1. users — 用户

| 字段 | 类型 | 说明 |
|---|---|---|
| id | VARCHAR(36) PRIMARY KEY | UUID |
| username | VARCHAR(50) UNIQUE NOT NULL | 登录名 |
| password_hash | VARCHAR(255) NOT NULL | bcrypt 哈希 |
| email | VARCHAR(100) UNIQUE NULL | 邮箱，找回密码/通知用 |
| display_name | VARCHAR(100) NULL | 昵称，前端显示用（与登录名解耦） |
| last_login_at | TIMESTAMP NULL | 上次登录时间，安全审计 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**判断**：刷新后要保留登录态 → 入库

---

### 2. agents — Agent 配置

| 字段 | 类型 | 说明 |
|---|---|---|
| id | VARCHAR(36) PRIMARY KEY | UUID |
| user_id | VARCHAR(36) NOT NULL | 创建者；值为 'GUGA' 表示系统内置 Agent |
| name | VARCHAR(100) NOT NULL | 联系人列表展示名 |
| description | VARCHAR(500) NULL | Agent 简介，联系人卡片副标题 |
| type | ENUM('claude','codex','custom') | 路由到对应 Adapter |
| system_prompt | TEXT | Agent 人格定义 |
| capabilities | JSON | `{"supports_diff":true,"supports_approval":true}` |
| tags | JSON | `["python","code-review"]` 联系人标签 |
| is_public | TINYINT(1) DEFAULT 0 | 公开/私有，公开的所有人可见 |
| is_active | TINYINT(1) DEFAULT 1 | 启用/停用，停用后联系人不可见、不可发消息 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

INDEX(user_id, is_active)
INDEX(is_public, is_active)

**判断**：
- 对话式创建Agent后，刷新还要在 → 入库
- Agent 挂载了哪些 Skill 走 `agent_skills` 关联表，不放 JSON 字段
- 不存 `avatar_url`，前端用首字母色块
- 联系人列表查询：`WHERE is_active=1 AND (user_id=:me OR is_public=1)`

---

### 3. skills — Skill 元数据

| 字段 | 类型 | 说明 |
|---|---|---|
| id | VARCHAR(36) PRIMARY KEY | UUID |
| name | VARCHAR(100) NOT NULL | 英文唯一标识，对应 .md 文件名 |
| display_name | VARCHAR(100) NULL | 中文展示名，前端列表显示 |
| description | VARCHAR(500) | frontmatter description，progressive disclosure 时塞进系统prompt |
| category | VARCHAR(50) NULL | 分类（代码/安全/领域知识等），市场筛选用 |
| file_path | VARCHAR(255) NOT NULL | 指向 `skills/{name}.md` |
| author_id | VARCHAR(36) NOT NULL | 创建者用户 ID；值为 'GUGA' 表示系统内置 |
| is_public | TINYINT(1) DEFAULT 0 | 公开/私有，公开的所有人可挂载 |
| is_active | TINYINT(1) DEFAULT 1 | 启用/停用，停用后不再注入 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

UNIQUE KEY (author_id, name)  -- 同一作者下 name 唯一，不同作者可重名
INDEX (is_public, is_active)

**判断**：
- Skill 内容（正文）→ Markdown 文件，git 版本化，不入库
- Skill 元数据（谁创建的、是否公开、文件路径）→ 入库，因为要做权限控制 + 列表查询
- 系统启动时扫描 `skills/*.md` 自动同步元数据到表
- PK 改用 UUID，避免不同用户创建同名 Skill 冲突

---

### 4. agent_skills — Agent 挂载 Skill 关联表

| 字段 | 类型 | 说明 |
|---|---|---|
| agent_id | VARCHAR(36) | |
| skill_id | VARCHAR(36) | FK → skills.id |
| created_at | TIMESTAMP | |

PRIMARY KEY (agent_id, skill_id)
INDEX (skill_id)  -- 反向查支持："哪些Agent挂了某Skill"

---

### 5. conversations — 会话

| 字段 | 类型 | 说明 |
|---|---|---|
| id | VARCHAR(36) PRIMARY KEY | UUID |
| user_id | VARCHAR(36) NOT NULL | 多用户隔离 |
| title | VARCHAR(200) | 会话标题 |
| mode | ENUM('single','group') | chat_service 路由分支用 |
| is_pinned | TINYINT(1) DEFAULT 0 | 置顶 |
| is_archived | TINYINT(1) DEFAULT 0 | 归档 |
| last_message_preview | VARCHAR(200) NULL | 最后一条消息摘要，会话列表展示用 |
| last_message_at | TIMESTAMP NULL | 最后一条消息时间，比 updated_at 更精确（updated_at 改 title 也会动） |
| message_count | INT DEFAULT 0 | 消息总数，列表展示"23条" |
| unread_count | INT DEFAULT 0 | 未读数，前端badge展示 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

INDEX(user_id, last_message_at DESC)

---

### 6. conversation_agents — 会话参与的 Agent（多对多）

| 字段 | 类型 | 说明 |
|---|---|---|
| conversation_id | VARCHAR(36) | |
| agent_id | VARCHAR(36) | |
| joined_at | TIMESTAMP | 加入时间，群成员列表按加入顺序展示 |
| is_active | TINYINT(1) DEFAULT 1 | 是否还在群里（踢出后置0，历史消息不丢） |

PRIMARY KEY (conversation_id, agent_id)

**判断**：群聊里有哪些Agent，刷新要保留 → 入库；is_active 软删除保留历史。

---

### 7. messages — 消息

| 字段 | 类型 | 说明 |
|---|---|---|
| id | VARCHAR(36) PRIMARY KEY | messageId |
| conversation_id | VARCHAR(36) NOT NULL | |
| thread_id | VARCHAR(36) NULL | 关联 threads 表，反查执行状态 |
| parent_id | VARCHAR(36) NULL | 树形结构（重新生成/分支） |
| user_id | VARCHAR(36) NULL | 用户消息时填 |
| agent_id | VARCHAR(36) NULL | Agent 消息时填，NULL=用户消息 |
| role | ENUM('user','assistant') | |
| content | JSON NOT NULL | ContentBlock 数组的 JSON 序列化（见 domain/message.py） |
| status | ENUM('streaming','done','error') | streaming态进Redis，done落MySQL |
| error_message | VARCHAR(500) NULL | status=error 时的错误信息 |
| model | VARCHAR(50) NULL | 实际用的模型，hover 气泡显示，审计/调试用 |
| sender | VARCHAR(100) NULL | Agent 显示名快照，避免每次 join agents 表 |
| tokens_input | INT NULL | 输入 token 数，计费/审计/context管理 |
| tokens_output | INT NULL | 输出 token 数 |
| latency_ms | INT NULL | Agent 响应耗时（毫秒），性能监控/调试 |
| feedback | ENUM('up','down') NULL | 用户对Agent消息的点赞/点踩，NULL=未评价 |
| selected_range | JSON NULL | 用户选中的代码段 `{file,start,end,code}`，对话式局部修改用 |
| is_deleted | TINYINT(1) DEFAULT 0 | 软删除 |
| created_at | TIMESTAMP | |

INDEX(conversation_id, created_at)
INDEX(thread_id)

**判断**：
- 内容模型用 ContentBlock 数组（domain/message.py），一条消息可同时含 thinking / tool_use / code / text / approval / deployment / image / artifacts 等多个块
- 块级别字段（如 ApprovalBlock.status / CodeBlock.applied_commit_hash）由块自身承载，不再有外层 content_type / approval_status / applied_commit_hash 字段
- 流式增量通过 SSE 块级事件协议（block_start / block_delta / block_stop）推送，最终态落库为完整 blocks 数组
- MVP 不存 attachments / files

---

### 8. threads — Thread 执行状态

| 字段 | 类型 | 说明 |
|---|---|---|
| id | VARCHAR(36) PRIMARY KEY | |
| conversation_id | VARCHAR(36) NOT NULL | |
| message_id | VARCHAR(36) NOT NULL | 触发本Thread的用户消息 |
| agent_id | VARCHAR(36) NOT NULL | |
| status | ENUM('init','running','suspended','done','error','cancelled') | |
| checkpoint | JSON NULL | 冷存储（热缓存在Redis） |
| started_at | TIMESTAMP NULL | 进入 running 的时间，统计耗时 |
| finished_at | TIMESTAMP NULL | 进入 done/error 的时间 |
| error_message | VARCHAR(500) NULL | status=error 时的错误信息 |
| tokens_total | INT DEFAULT 0 | 累计 token 消耗（输入+输出） |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

INDEX(conversation_id, agent_id, updated_at DESC)  -- resume_or_create 查询用

**判断**：
- @个体特化要 `resume_or_create`，必须能查到历史Thread → 入库
- checkpoint 冷热双写：Redis 是热缓存，MySQL 是冷存储防丢

---

### 9. audit_logs — 审计日志

| 字段 | 类型 | 说明 |
|---|---|---|
| id | VARCHAR(36) PRIMARY KEY | UUID |
| user_id | VARCHAR(36) NULL | 谁触发的，系统操作时为NULL |
| action | VARCHAR(50) NOT NULL | 行为标识，如 `login` / `agent.create` / `diff.apply` / `approval.confirm` |
| target_type | VARCHAR(50) NULL | 目标资源类型，如 `agent` / `conversation` / `message` |
| target_id | VARCHAR(36) NULL | 目标资源 ID |
| detail | JSON NULL | 细节（输入参数、变更前后值等） |
| ip | VARCHAR(45) NULL | 客户端IP（IPv6最长45） |
| user_agent | VARCHAR(255) NULL | 浏览器UA |
| trace_id | VARCHAR(36) NULL | 关联运行日志的 trace_id |
| created_at | TIMESTAMP | |

INDEX(user_id, created_at DESC)
INDEX(action, created_at DESC)
INDEX(target_type, target_id)

**判断**：
- 关键业务行为不可变记录，只增不改
- 写入时机：hook 系统统一触发（pre_execution / approval）+ 关键 service（auth/agent CRUD）
- 关键 action 列表：login / logout / agent.create / agent.update / agent.delete / diff.apply / approval.confirm / approval.reject / chat.start / skill.create

---

### 日志体系总览（三类日志的边界）

| 类型 | 存储 | 触发点 | 用途 |
|---|---|---|---|
| 应用运行日志 | 文件（`logs/app-{date}.log`，结构化JSON） | 各 service 通过 logger 输出 | 排错/监控 |
| 审计日志 | MySQL `audit_logs` 表 | hooks 统一触发 + 关键 service | 合规/追溯 |
| Agent 执行追踪 | 复用 `messages.tokens_input/output/latency_ms` + `threads.tokens_total/started_at/finished_at` | post_execution hook 写入 | 性能分析 |

**关键约定**：
- 每个 HTTP 请求生成 `trace_id`，贯穿运行日志 + 审计日志
- 运行日志不入库（量大，文件就行）
- Agent 工具调用细节先写文件日志，MVP 不单独建 `agent_traces` 表

---

### 不入库的内容

`skills/*.md` 和 `prompts/*.md` **正文**是文件，git 版本化，不入 MySQL。

**Skill 文件结构**（参考 CC s05_skill_loading.py）：
```markdown
---
name: code_review
description: 代码审查Skill，适用Python/Go代码
---
（完整Skill内容，被load_skill工具按需加载）
```

**Skill 元数据如何同步**：
- 系统启动时 `skill_service.py` 扫描 `skills/` 目录，解析 frontmatter
- 与 `skills` 表对账：新增的入库，已删除的清理
- 用户创建 Skill：前端表单 → 写文件到 `skills/user_{user_id}/{name}.md` → 同时入 `skills` 表

---

## 二、Redis 设计

> **MVP 阶段策略**：所有 Redis Key 设计**保留接口位置**，但**实现先用内存**（单进程 dict / asyncio.Lock / set）。Phase 3 上线前切换到真实 Redis，业务代码不动。
>
> 下面的 Key 设计是**目标态规范**，本期实现时各 service 调用统一的抽象层（如 `cache_service.get/set` / `lock_service.acquire`），抽象层底层选 InMemory 或 Redis。

### 1. 流式 token 缓冲（Resumable SSE）

| 项 | 说明 |
|---|---|
| Key | `stream:msg:{message_id}` |
| 结构 | List |
| 值 | 每个元素是 JSON 序列化的 SSE 事件，例如 `{"type":"token","content":"你"}` |
| 操作 | `RPUSH` 追加事件；`LRANGE` 断点续传 |
| TTL | 1 小时 |
| 清理 | `agent_done` 后立即 `DEL` |
| 用途 | 客户端 SSE 断线重连，带 `last_event_id` 续传 |

### 2. Thread Checkpoint 热缓存

| 项 | 说明 |
|---|---|
| Key | `checkpoint:thread:{thread_id}` |
| 结构 | String（JSON 序列化） |
| 值 | `{"messages_history":[...],"tool_calls_done":[...],"current_step":"...","pending_action":"...","version":N}` |
| 操作 | 状态变更：写 Redis（热）+ 异步写 MySQL（冷）；resume：先读 Redis，miss 走 MySQL |
| TTL | 24 小时 |
| 清理 | Thread `done`/`error` 后 `DEL`，MySQL 冷存储保留 |
| 用途 | Thread 暂停（等审批/中断）后恢复执行 |

### 3. 分布式锁（防并发重入）

| 项 | 说明 |
|---|---|
| Key | `lock:conversation:{conversation_id}` |
| 结构 | String |
| 值 | 持锁者标识（thread_id + 时间戳） |
| 获取 | `SET key {owner} NX EX 30` |
| 释放 | Lua 脚本：value == owner 才 `DEL`（防误删） |
| TTL | 30 秒（防死锁兜底） |
| 用途 | 同一 conversation 不允许两个 chat 请求并发跑；同一 thread 不允许并发 resume |

### 4. JWT 黑名单

| 项 | 说明 |
|---|---|
| Key | `jwt:blacklist:{jti}` |
| 结构 | String |
| 值 | `1`（占位） |
| TTL | = token 剩余有效期 |
| 写入 | 登出时 `SET key 1 EX {remaining_ttl}` |
| 校验 | 每个请求中间件 `EXISTS jwt:blacklist:{jti}` |

### 5. SSE 活跃连接注册（中止流式用）

| 项 | 说明 |
|---|---|
| Key | `sse:active:{conversation_id}` |
| 结构 | Set |
| 值 | 当前活跃的 SSE 连接 ID（thread_id 或 message_id） |
| 操作 | 建立连接 `SADD`；关闭 `SREM`；用户点停止 `SMEMBERS` 拿到所有活跃连接发停止信号 |
| TTL | 无（手动维护） |

### 6. 用户限流

| 项 | 说明 |
|---|---|
| Key | `ratelimit:user:{user_id}:{minute_bucket}` |
| 结构 | String（计数器） |
| 操作 | `INCR` + `EXPIRE 60` |
| 判定 | 当前分钟 > 60 次 → 拒绝 |
| TTL | 1 分钟自动过期 |

### 7. 熔断器状态

| 项 | 说明 |
|---|---|
| Key | `circuit:agent:{agent_id}` |
| 结构 | Hash |
| 字段 | `state`(CLOSED/OPEN/HALF_OPEN) / `failure_count` / `last_failure_at` / `opened_at` |
| 操作 | 调用前 HGETALL 判断状态；调用结果 HINCRBY/HSET |
| TTL | 无（手动维护，OPEN→HALF_OPEN 由 reset_timeout 推进） |
| 用途 | core/circuit_breaker.py 三态状态机持久化，多进程共享 |

### 8. Agent 草稿态（对话式创建）

| 项 | 说明 |
|---|---|
| Key | `agent_draft:user:{user_id}:{session_id}` |
| 结构 | String（JSON 序列化） |
| 值 | `{"name":"...","system_prompt":"...","tags":[],"suggested_tools":[]}` 草稿 Agent |
| TTL | 1 小时 |
| 写入 | `agent_builder_service` 第一轮 LLM 生成草稿后写入 |
| 清理 | 用户确认后写 MySQL 同时 DEL；超时自动过期 |

### 9. WebSocket 连接注册

| 项 | 说明 |
|---|---|
| Key | `ws:user:{user_id}` |
| 结构 | Set |
| 值 | 进程ID 或 Pub/Sub channel 名（多进程部署时定位连接所在进程） |
| 操作 | 连接建立 SADD；断开 SREM；推送时 SMEMBERS 拿到目标进程 → Redis Pub/Sub 转发 |
| TTL | 无（手动维护） |
| 用途 | 异步推审批确认/diff_applied 等 WS 事件，跨进程定位连接 |

---

## 三、SSE 事件协议（前后端契约）

消息内容用块级流式协议：`block_start`（创建块）→ `block_delta`（增量更新）→ `block_stop`（块结束）。
块类型见 `domain/message.py:ContentBlock`：text / thinking / tool_use / code / approval / deployment / image / artifacts。

```
// 消息级
{"type":"agent_start","agent_id":"claude","agent_name":"Claude","thread_id":"t_1","message_id":"msg_1"}
{"type":"agent_done","agent_id":"claude","thread_id":"t_1","message_id":"msg_1"}
{"type":"agent_error","agent_id":"claude","thread_id":"t_1","message_id":"msg_1","error":"timeout"}

// 块级（block 字段是 ContentBlock 子类）
{"type":"block_start","agent_id":"claude","thread_id":"t_1","message_id":"msg_1",
 "block":{"type":"text","block_id":"b_1","content":""}}
{"type":"block_delta","agent_id":"claude","thread_id":"t_1","message_id":"msg_1",
 "block_id":"b_1","delta":{"content":"你好"}}
{"type":"block_stop","agent_id":"claude","thread_id":"t_1","message_id":"msg_1","block_id":"b_1"}

// 整轮 / 队列信号（独立类型，不属于 AgentEvent）
{"type":"round_done"}
{"type":"queue_drained"}
```

**约定**：
- 一条消息可包含多个块，按 block_start 顺序追加；不同块的 delta 可交错
- block_delta 的 delta 字段语义由具体块类型决定（如 TextBlock 的 content 累加，ToolUseBlock 的 status 覆盖）
- block_stop 可选携带 final_fields 补全最终字段

---

## 四、REST API 接口

### 鉴权
- `POST /api/v1/auth/login` `{username, password}` → `{token, user:{id,username}}`
- `POST /api/v1/auth/logout` → `{success:true}`

### 会话
- `GET /api/v1/conversations` → `[{id,title,mode,is_pinned,is_archived,last_message_preview,updated_at}]`
- `POST /api/v1/conversations` `{title,mode,agent_ids:[]}` → `Conversation`
- `PATCH /api/v1/conversations/{id}` `{title?,is_pinned?,is_archived?}` → `Conversation`（重命名/置顶/归档）
- `GET /api/v1/conversations/{id}/messages?before=&limit=` → `[Message]`

### 消息
- `PATCH /api/v1/messages/{id}/feedback` `{feedback:"up"|"down"|null}` → `{success:true}`
- `DELETE /api/v1/messages/{id}` → 软删除

### Agent
- `GET /api/v1/agents` → `[Agent]`（联系人列表）
- `POST /api/v1/agents` `{name,type,system_prompt,tags,skill_names:[]}` → `Agent`
- `POST /api/v1/agents/build` `{description}` → 对话式创建，返回草稿 `Agent`
- `PATCH /api/v1/agents/{id}/skills` `{skill_names:[]}` → 修改挂载的 Skill

### Skill
- `GET /api/v1/skills` → `[Skill]`（当前用户可见：自己的 + 公开的）
- `POST /api/v1/skills` `{name,description,content,is_public}` → `Skill`（写文件+入库）
- `GET /api/v1/skills/{name}` → `Skill`（含正文，用于编辑器展示）
- `GET /api/v1/skills/{name}/agents` → `[Agent]`（反向查：哪些 Agent 挂了它）

### 聊天
- `POST /api/v1/chat`（SSE）`{conversation_id, content, mention_ids:[], selected_range?}`
- `POST /api/v1/chat/stop` `{conversation_id}` → 中止当前流（前端关闭SSE+后端清Redis）

### 产物
- `POST /api/v1/artifacts/diff/apply` `{message_id}` → 触发应用，结果走 WebSocket

### WebSocket
- `WS /api/v1/ws` 推 `approval_request` 确认结果 / `diff_applied`

---

## 五、关键设计决策

1. **Skill 元数据入库 + 内容走文件**：表存权限/列表/反向查能力，文件存正文。Agent ↔ Skill 用 `agent_skills` 关联表，正反向查都快。

2. **messages.content 存什么**：JSON 数组，元素是 ContentBlock 子类（domain/message.py 定义）。一条消息可同时含多个块（thinking / tool_use / code / text / approval / deployment / image / artifacts），有序渲染。块级别字段（如 ApprovalBlock.status / CodeBlock.applied_commit_hash）由块自身承载。

3. **threads.checkpoint 冷热双写**：Redis 是热路径，MySQL 是兜底。Redis 挂了能从 MySQL 恢复但慢一点。

4. **多用户隔离**：所有业务表都带 `user_id`，Service 层强制 `WHERE user_id = current_user.id`。

5. **last_message_preview / sender 冗余字段**：写新消息时同步更新，省一次 join 或 LIMIT 1 查询。sender 还能保留"消息历史不可变"语义（Agent 改名后历史消息仍显示当时的名字）。
