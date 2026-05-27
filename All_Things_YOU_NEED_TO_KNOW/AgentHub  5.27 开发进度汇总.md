# AgentHub 剩余工作全貌

> 更新：2026-05-27（Adam Zhang）
> 优先级：P0=上线必需 / P1=核心功能 / P2=增强 / P3=横向能力

---

## 已完成（5/27 完成的任务，留作上下文）

- [x] `main.py` 接通 `seed_from_db`
- [x] `_drain_pending_messages` 接 SessionLocal
- [x] `pre_execution.py` 实装（黑名单 + 路径穿越拦截）
- [x] `post_execution.py` 实装（异步审计日志）
- [x] `approval.py` 实装（审批闭环 + 通道守卫，等 ws 接通后翻 `_APPROVAL_CHANNEL_READY=True`）
- [x] `main.py` 接通 hook 注册（PRE_TOOL_USE 链：PreExecutionHook → ApprovalHook；POST_TOOL_USE：PostExecutionHook）
- [x] `tool_registry` $ref inline 展开 + schema 校验 + 4KB 截断
- [x] `error_recovery` 三路（max_tokens / prompt_too_long / API 退避）已完整实装并接入 service.py
- [x] `context_compactor` 三层（micro_compact / global_summarize / 阈值递进）已实装
- [x] `prompt_builder` 第 6 层动态上下文（最近 20 条历史 + 可用 Agent + 任务图）
- [x] `AgentDoneEvent` 加 `tokens_input` / `tokens_output` 字段
- [x] `thread_service._run_thread` 收 `AgentDoneEvent` → 写 `threads.tokens_total` + `messages.tokens_*`
- [x] `thread_service` 子 Thread 流式产出落 messages 表（block_states 累积 + `_persist_assistant_message`）
- [x] `thread_service._extract_summary` 同时收 `BlockStartEvent` 和 `BlockDeltaEvent`（修复"摘要回注空字符串"）
- [x] `core/logging.py` structlog 配置层（stdlib 桥接，foreign_pre_chain，contextvars 支持）
- [x] `ClaudeAdapter._flatten_for_cli` Windows CLI 多行 prompt 兼容修复
- [x] orchestrator demo 端到端跑通（用户 → 主 Agent → 派子 Thread → 子 Thread 落库 → 摘要回注 → 主 Agent 总结回复）

---

## 模块零：测试基础设施 [P0]
> 没这个 #15 集成测试做不动，模块二/三/四的 API 测试也没法写

- [ ] `tests/conftest.py` 扩展：测试 DB fixture（推荐 in-memory SQLite + `metadata.create_all`）
- [ ] `tests/conftest.py` `mock_anthropic_response` fixture（按 stop_reason / content / tool_calls / usage 构造）
- [ ] `tests/conftest.py` `mock_adapter` fixture（注册到 `adapter_registry`，事先编排事件流）
- [ ] `tests/conftest.py` `clean_hook_manager` fixture（每个测试自动 `hook_manager.clear()`，防模块级单例污染）
- [ ] `tests/conftest.py` `clean_stream_service` fixture（清 `_sessions` / `_abort_events` / `_pending` / `_locks` / `_listeners`）

---

## 模块一：主链路接通 [P0]

- [ ] structlog 业务代码迁移：在 `chat_service.handle_chat` / `orchestrator.start_loop` / `thread_service._run_thread` 入口 `bind_contextvars(trace_id, user_id, conversation_id)`，逐步把 `logger.info("xxx %s", a)` 改成 `logger.info("xxx", a=a)`
- [ ] FastAPI request 入口加 trace_id middleware（每个请求 bind 一次，结束 clear），不然 contextvars 链路不会自动带

---

## 模块二：Orchestrator 工具链 [P0]

- [ ] orchestrator loop 集成测试（依赖模块零）—— mock LLM/Adapter，跑完整闭环
- 🟡 `prompt_builder` 第 3 层 Skill 元数据（**注释固化设计意图，实装代码仍返回 `""`**，待模块五 `skill_service` 实装后回填）

---

## 模块三：Auth 全栈 [P0]
> 上线必需

- [ ] `user_repo.py`：users 表 CRUD
- [ ] `auth_service.py`：JWT 签发 / 校验
- [ ] `api/v1/auth.py`：`/login` `/logout` `/refresh`
- [ ] `api/middleware/auth.py`：JWT 校验中间件
- [ ] `core/redis.py`：Redis 连接池
- [ ] JWT 黑名单（Redis）
- [ ] auth 端点 pytest 集成测试

---

## 模块四：Agent 管理全栈 [P1]

- [ ] `api/v1/agents.py`：CRUD 端点（列表 / 创建 / 编辑 / 删除 / 启停）
- [ ] `agent_builder_service.py`：LLM 辅助草稿生成 + 审核 + Redis 草稿态
- [ ] **agents 表 seed `agent_id='orchestrator'` 行**（主 Agent 自身要在 agents 表才能挂 Skill / prompt_builder 第 3 层才能查它的 skill）
- [ ] 3 个角色 Agent seed（research / coder / reviewer）+ 调研 Agent 挂 MCP
- [ ] 前端 `AgentBuilderDialog.vue` + `useAgentBuilder.ts`：对话式创建弹窗
- [ ] 前端 `AgentConfigForm.vue`：system prompt / 工具 / Skill 挂载配置
- [ ] agents API pytest 集成测试

---

## 模块五：Skill 子系统 [P1]

- [ ] `skill_repo.py`：挂载关系
- [ ] `skill_service.py`：
   - 扫 `backend/skills/*.md` 同步元数据到 skills 表（系统内置 author=GUGA）
   - `list_for_orchestrator(user_id)` 接口供 `prompt_builder._layer_3` 调用
   - 用户上传的 Skill 双源：DB 写元数据 + 写入文件，本地删了能从 DB 重新生成
- [ ] `api/v1/skills.py`：CRUD 端点
- [ ] 前端 Skill 编辑器：LLM 辅助 description + 全流程
- [ ] `thread_service` D6：按 `agent_id` 加载挂载 Skill 注入到子 Adapter `StreamInput.skills`
- [ ] 实装后翻 `prompt_builder._layer_3_skill_metadata` 的占位代码
- [ ] skills API pytest 集成测试

---

## 模块六：消息操作 & 会话补全 [P0]

- [ ] `thread_service` D6：从 `message_repo` 加载会话历史塞进子 Adapter `StreamInput.history`
   （注意：跟 `prompt_builder` 第 6 层"塞 20 条进主 Agent system prompt"是**两件事**——这里是给子 LLM 的对话上下文）
- [ ] `api/v1/messages.py`：feedback / 软删 / 重新生成
- [ ] `api/v1/conversations.py`：归属校验 `assert_owned_by` 接通

---

## 模块七：Adapter token / usage 透出 [P1]
> 基础设施今天完成,只剩各 Adapter 内部填值

- ✅ `AgentDoneEvent` 加字段（已完成）
- ✅ `thread_service._run_thread` 收并写库（已完成）
- [ ] `claude.py` 解析 stream-json `result` 行的 `usage`（input_tokens / output_tokens / cache_*）填到 `AgentDoneEvent`
- [ ] `codex.py` 同上
- [ ] `custom.py` 解析 OpenAI 兼容 API response.usage 填值
- [ ] `opencode.py` 实装

---

## 模块八：WebSocket & 审批流 [P0]
> WS 是审批 / Diff 应用的载体,前端联调依赖

- [ ] `api/v1/ws.py`：WebSocket 端点（apply_diff / approval_decision）
- [ ] `approval.py._publish_approval_block` 接 message_service 创建 ApprovalBlock 消息 + WS 通知前端，完成后翻 `_APPROVAL_CHANNEL_READY = True`
- [ ] WS handler 收 `ApprovalDecisionRequest` 后调 `approval.decide(block_id, decision, reason)`
- [ ] `api/middleware/error_handler.py`：全局异常处理（含 hook / Adapter / orchestrator loop 异常的统一传播路径）

---

## 模块九：Artifacts 全栈 [P1]

- [ ] `diff_service.py`：文件变更 → Git diff → 构造 diff 消息
- [ ] `diff_apply_service.py`：用户确认 → 写入文件 → Git commit
- [ ] `preview_service.py`：HTML / 代码产物 → 预览 URL
- [ ] `deploy_service.py`：触发部署
- [ ] `git_repo.py`：commit / branch / diff / 冲突检测
- [ ] `api/v1/artifacts.py`：一键应用 Diff / 部署端点
- [ ] post_execution hook 内部 `TODO[diff]` / `TODO[preview]` 接通：识别工具产物 → 调对应 service

---

## 模块十：前端联调 [P0]

- [ ] `types/conversation.ts` / `types/message.ts` / `types/artifact.ts` / `types/api.ts` 补全
- [ ] camelCase / snake_case 转换层
- [ ] `api/http.ts`：Axios 实例 + JWT 拦截器 + 响应错误处理
- [ ] `api/chat.ts`：发消息
- [ ] `api/sse.ts`：SSE 连接管理（支持 POST + Authorization header）
- [ ] `api/conversations.ts`：会话 CRUD
- [ ] `api/agents.ts`：接真后端（当前 mock）
- [ ] `api/ws.ts`：WebSocket 封装（重连 / 心跳 / 消息分发）
- [ ] `api/messages.ts` / `api/skills.ts` / `api/artifacts.ts` / `api/auth.ts`
- [ ] `stores/chat.ts`：消息状态机（streamingIds / agentBubbles）
- [ ] `stores/conversations.ts`：会话列表 / 当前会话 / 未读数 / 置顶
- [ ] `composables/useChat.ts`：发消息主流程
- [ ] `composables/useSSE.ts`：SSE 连接生命周期
- [ ] `composables/useWebSocket.ts`：WebSocket 连接管理
- [ ] `composables/useDiff.ts`：DiffCard 交互
- [ ] `composables/useApproval.ts`：审批弹窗流程
- [ ] `composables/useArtifactPreview.ts`：iframe 生命周期管理
- [ ] `composables/useInfiniteScroll.ts`：消息历史分页加载
- [ ] SSE EventSource 鉴权（polyfill 或 query param）
- [ ] 打字机效果（BlockDelta 排队 setInterval 渲染）

---

## 模块十一：可观测性 [P1]

- [ ] `core/audit.py`：audit_log 写库接口
- [ ] `api/middleware/logging.py`：请求日志中间件
- [ ] `post_execution.py` `TODO[audit]` 接通 audit_service

---

## 模块十二：部署 & 横向能力 [P2]

- [ ] **DB migration 方案**：Alembic 集成 / 或 startup 调 `Base.metadata.create_all(engine)`
- [ ] `.env.example` 模板 + 配置说明文档
- [ ] `core/circuit_breaker.py`：熔断器三态（CLOSED / OPEN / HALF_OPEN）
- [ ] `core/lock.py`：Redis 分布式锁
- [ ] `repositories/stream_buffer_repo.py`：断点恢复
- [ ] OpenCode Adapter
- [ ] 整体部署一条龙（后端 + 前端 + DB + Redis）

---

## 已知问题清单（5/27 跑 demo 时发现，非阻塞但要处理）

| # | 问题 | 影响 | 优先级 |
|---|---|---|---|
| 1 | `threads.started_at` 不写（`thread_repo.mark_status(RUNNING)` 路径漏字段） | 监控 / 计费拿不到主 Agent loop 实际起跑时间 | P1 |
| 2 | `threads.created_at` UTC vs `finished_at` CST 时区不一致 | duration 计算结果异常 | P1 |
| 3 | Kimi Anthropic 端点不支持 `/messages/count_tokens` 返回 404 | `context_compactor.estimate_tokens` 已兜底但日志噪音爆 | P2 |
| 4 | ClaudeAdapter 用 `-p` 参数传 prompt，单条参数有长度上限 | 长 dispatch_prompt 可能截断（今天换行已修，长度限制未处理） | P2 |
| 5 | `_persist_assistant_message` 只用 mock 单 TextBlock 验证过，多 block / ToolUseBlock / ApprovalBlock 反序列化未实测 | 边角场景可能 silently 跳过 | P2 |
| 6 | Adapter 流式产出 `_persist_assistant_message` 落库时 `model` 字段为 `None`（agents 表无 model 字段） | messages.model 快照缺失 | P2 |

---

## 优先级路径（上线必需）

```
模块零（测试基础设施）
    ↓
模块三（auth）+ 模块六（messages/conversations API）+ 模块二集成测试
    ↓
模块八（ws + approval 接通）
    ↓
模块十（前端联调）
    ↓
模块十二（部署 + DB migration + .env.example）
    ↓
🚀 上线
```

**功能扩展**（不阻塞上线，可并行/后置）：
- 模块四（Agent 管理全栈）
- 模块五（Skill 子系统）
- 模块七（Adapter usage 透出）
- 模块九（Artifacts 全栈）
- 模块十一（可观测性深化）

---

队伍：咕嘎一辈子队
