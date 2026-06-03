# AgentHub 剩余工作全貌

> 更新：2026-05-29（lp 分支：OpencodeAdapter 全链路 + token 透出）
> 优先级：P0=上线必需 / P1=核心功能 / P2=增强 / P3=横向能力

---

## 已完成（5/27 完成）

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

## 已完成（5/28 完成）

- [x] **orchestrator loop 集成测试**（`tests/integration/test_orchestrator_loop.py` 10 用例 + `test_context_compactor.py` 17 用例 + `scripts/preview_compactor.py` 真 LLM 摘要质量预览脚本）
- [x] **trace_id middleware**（`api/middleware/logging.py` TraceIdMiddleware：header 优先 + UUID 兜底，contextvars 自动绑定，stdlib + structlog 共享 trace_id；5 用例集成测试）
- [x] **ConversationCreate agent_ids 校验**（single 必须 1 个 / group 至少 1 个，空传直接 422）
- [x] **统一响应格式 {code, message, data}**（`schemas/response.py` ApiResponse + `middleware/response_envelope.py` 自动包装 + `api/exception_handlers.py` 异常统一包装；SSE / StreamingResponse 不包装；9 用例集成测试）
- [x] **`threads.started_at` 漏写修复**（`start_loop` 进 _agent_loop 前调 mark_running）
- [x] **count_tokens API 404 噪音降级**（模块级降级标志 + `settings.ENABLE_COUNT_TOKENS_API` 强制开关）
- [x] **时区 UTC vs CST 错位修复**（engine connect_args 设 `init_command="SET time_zone='+00:00'"`，MySQL CURRENT_TIMESTAMP 与 Python UTC 对齐）

**5/28 测试统计**：50 passed / 3 skipped（真 LLM 测试需环境变量）

---

## 已完成（5/29 完成 · lp 分支）

> 围绕 OpenCode Adapter 端到端 + token 透出做的一系列工作。所有改动在 `backend/adapters/opencode.py` + 对应单元测试 + 端到端 demo 脚本。

- [x] **OpencodeAdapter 完整实装**（`backend/adapters/opencode.py` ~530 行）
   - CLI 子进程模式（`opencode run --format json`）
   - 完整解析 opencode JSON-stream 协议：`text` → TextBlock，`tool_use` → ToolUseBlock，`step_finish` → token 累加
   - 并落到 AgentHub 块级流式协议（BlockStart / BlockDelta / BlockStop）
- [x] **opencode token 透出**（模块七 P1 项收尾）
   - `step_finish.part.tokens.{input,output}` 多轮累加
   - 通过 `AgentDoneEvent.tokens_input` / `tokens_output` 透出
   - 上游 `thread_service._run_thread` 自动写到 `threads.tokens_total` + `messages.tokens_input/output`
   - 前端已就绪（`stores/chat.ts` 行 83-84 + `types/api.ts` 行 128-129），无需前端改动即可显示
- [x] **opencode 注入 persona 难题攻克**（关键设计经验沉淀）
   - 验证否定：AGENTS.md 注入 / 元层 prompt 标签 / 两步对话 / 自然语言开场白前置 / LLM rewriter—— **opencode alignment 都识破并拒绝**
   - 最终成立方案：**条件性中文开场白** + 主 Agent 派活原文透传
     - `_looks_structured(text)` 检测 markdown ATX header / banner / role-section labels
     - 仅在结构化时加开场白"你是一个子 agent，现在我给你一个任务，任务描述如下"
     - 纯散文 prompt 原样透传，零 LLM 调用开销
- [x] **Windows 工程坑修复**
   - `_flatten_for_cli`：把 prompt 中换行压成空格（绕过 Windows CreateProcess 的 multiline argv 截断）
   - `_resolve_opencode_binary`：解析 `opencode.cmd` shim 找出真正的 `opencode.exe`，绕过 cmd.exe 对 `>` `<` `|` 等元字符的 shell 解析
   - 子进程沙箱 cwd（`tempfile.mkdtemp` 临时空目录）：避免 opencode 加载项目级 AGENTS.md / `.opencode/` 让它误认为"继续项目工作"
- [x] **ORM Message vs Pydantic MessageInHistory 兼容**
   - `_blocks_to_text` + `_msg_field` helper：`thread_service.list_recent` 返回 ORM Message 时（字段是 `.content` 而非 `.blocks`），adapter 仍能正确解析
   - 这是上游 master 的接口缝隙；OpencodeAdapter 防御性兼容，不影响其他 adapter
- [x] **adapter_registry 修复 opencode 类型分支**：原来错误复用 `CodexAdapter`，改为正确路由到 `OpencodeAdapter`
- [x] **端到端 demo 脚本**（`backend/scripts/run_orchestrator_opencode_demo.py`）
   - 镜像 `run_orchestrator_demo.py`（Claude 版）的结构
   - 验证完整调度链：用户消息 → 主 Agent dispatch_to_agent → 子 thread 起 OpencodeAdapter → opencode CLI 真跑 → BlockEvent 流回 → token 累加 → messages 落库 → 主 Agent read_thread_result → respond_to_user
   - 跑 5/29 实测：21 秒端到端完成，子 thread `tokens_total=594`，`messages.tokens_input=4 / tokens_output=590`，主 Agent 完整转交代码给用户
- [x] **OpencodeAdapter 32 个单元测试**（`tests/unit/test_opencode_adapter.py`）
   - text/tool_use 块累加、cancel_event、binary 缺失、空输出、多轮 token 累加、ORM 兼容、`_looks_structured` 三类触发、`_flatten_for_cli` 多行压缩

**5/29 测试统计**：32/32 通过（OpencodeAdapter 单元测试）+ 端到端 demo 跑通（含真实 opencode CLI）

---

## 模块零：测试基础设施 [P0]
> 集成测试已部分搭建（orchestrator loop / context_compactor / trace_id / response_envelope 各自的 fixture），还差跨模块通用基建

- [x] `tests/integration/conftest.py` orchestrator loop fixture（llm_response_queue / temp_tool / clean_hook_manager / clean_orchestrator_state / patch_* 子系统 stub）
- [ ] `tests/conftest.py` 顶层扩展：测试 DB fixture（推荐 in-memory SQLite + `metadata.create_all`）
- [ ] `mock_adapter` fixture（注册到 `adapter_registry`，事先编排事件流）
- [ ] `clean_stream_service` fixture（清 `_sessions` / `_abort_events` / `_pending` / `_locks` / `_listeners`）

---

## 模块一：主链路接通 [P0]

- [x] FastAPI request 入口加 trace_id middleware
- [ ] structlog 业务代码迁移：在 `chat_service.handle_chat` / `orchestrator.start_loop` / `thread_service._run_thread` 入口 `bind_contextvars(trace_id, user_id, conversation_id)`，逐步把 `logger.info("xxx %s", a)` 改成 `logger.info("xxx", a=a)`

---

## 模块二：Orchestrator 工具链 [P0]

- [x] orchestrator loop 集成测试（mock LLM/Adapter，10 用例覆盖八步循环全分支）
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

- [x] `ConversationCreate` agent_ids 长度校验（single 必须 1 个 / group 至少 1 个）
- [ ] `thread_service` D6：从 `message_repo` 加载会话历史塞进子 Adapter `StreamInput.history`
   （注意：跟 `prompt_builder` 第 6 层"塞 20 条进主 Agent system prompt"是**两件事**——这里是给子 LLM 的对话上下文）
- [ ] `api/v1/messages.py`：feedback / 软删 / 重新生成
- [ ] `api/v1/conversations.py`：归属校验 `assert_owned_by` 接通

---

## 模块七：Adapter token / usage 透出 [P1]
> 基础设施完成,只剩各 Adapter 内部填值

- ✅ `AgentDoneEvent` 加字段（已完成）
- ✅ `thread_service._run_thread` 收并写库（已完成）
- [ ] `claude.py` 解析 stream-json `result` 行的 `usage`（input_tokens / output_tokens / cache_*）填到 `AgentDoneEvent`
- [ ] `codex.py` 同上
- [ ] `custom.py` 解析 OpenAI 兼容 API response.usage 填值
- [x] **`opencode.py` 实装**（5/29 完成 · lp 分支）：累加 `step_finish.part.tokens.{input,output}` → AgentDoneEvent，端到端验证 `tokens_total=594` 落到 threads / messages 表

---

## 模块八：WebSocket & 审批流 [P0]
> WS 是审批 / Diff 应用的载体,前端联调依赖

- [x] **全局异常处理器**（`api/exception_handlers.py` HTTPException / RequestValidationError / Exception 统一包装）
- [ ] `api/v1/ws.py`：WebSocket 端点（apply_diff / approval_decision）
- [ ] `approval.py._publish_approval_block` 接 message_service 创建 ApprovalBlock 消息 + WS 通知前端，完成后翻 `_APPROVAL_CHANNEL_READY = True`
- [ ] WS handler 收 `ApprovalDecisionRequest` 后调 `approval.decide(block_id, decision, reason)`

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
> **后端已完全就绪**：`POST /api/v1/chat`、`POST /api/v1/chat/stop`、`GET /api/v1/chat/stream/{conv_id}`、`POST/GET/PATCH /api/v1/conversations` 全部实装。所有响应已统一为 `{code, message, data}`

- [ ] `types/conversation.ts` / `types/message.ts` / `types/artifact.ts` / `types/api.ts` 补全
- [ ] camelCase / snake_case 转换层
- [ ] `api/http.ts`：Axios 实例 + JWT 拦截器 + 响应错误处理（注意：响应已包成 `{code, message, data}`，拦截器拆包）
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

- [x] **trace_id middleware**（contextvars 自动绑 + 响应头 X-Trace-Id 回写）
- [ ] structlog 业务代码迁移（同模块一）
- [ ] `core/audit.py`：audit_log 写库接口
- [ ] `api/middleware/logging.py` 请求日志中间件（已含 trace_id 部分，access log 已有，待与 audit_log 整合）
- [ ] `post_execution.py` `TODO[audit]` 接通 audit_service

---

## 模块十二：部署 & 横向能力 [P2]

- [x] **DB 连接级时区 UTC 化**（engine connect_args，所有时间戳字段对齐）
- [ ] **DB migration 方案**：Alembic 集成 / 或 startup 调 `Base.metadata.create_all(engine)`
- [ ] `.env.example` 模板 + 配置说明文档
- [ ] `core/circuit_breaker.py`：熔断器三态（CLOSED / OPEN / HALF_OPEN）
- [ ] `core/lock.py`：Redis 分布式锁
- [ ] `repositories/stream_buffer_repo.py`：断点恢复
- [x] **OpenCode Adapter**（5/29 完成 · lp 分支）：详见上方 5/29 章节
- [ ] 整体部署一条龙（后端 + 前端 + DB + Redis）

---

## 已知问题清单

| # | 问题 | 影响 | 状态 |
|---|---|---|---|
| 1 | `threads.started_at` 不写 | 监控 / 计费拿不到主 Agent loop 起跑时间 | ✅ 5/28 已修 |
| 2 | `created_at` UTC vs `finished_at` CST 时区不一致 | duration 计算结果异常 | ✅ 5/28 已修（engine UTC） |
| 3 | Kimi `/messages/count_tokens` 返回 404 | 日志噪音 + 浪费 RPM 配额 | ✅ 5/28 已修（降级 + 配置开关） |
| 4 | ClaudeAdapter `-p` 参数长度上限（命令行参数限制） | 长 dispatch_prompt 可能截断 | P2 待处理（建议改 stdin 传 prompt） |
| 5 | `_persist_assistant_message` 只用 mock 单 TextBlock 验证过 | 多 block / ToolUseBlock / ApprovalBlock 反序列化未实测 | ✅ 5/29 OpencodeAdapter 跑出 [tool_use,text] 双 block 真实场景，落库正确 |
| 6 | `_persist_assistant_message` 落库时 `model` 字段为 None | messages.model 快照缺失（agents 表无 model 字段） | P2 待 agents 表加 model 字段 |
| 7 | `thread_service.list_recent` 返回 ORM `Message` 但 `StreamInput.history` 类型注解是 `MessageInHistory` | adapter 调 `msg.blocks` 抛 AttributeError | 🟡 OpencodeAdapter 已防御性兼容（`_msg_field` helper），但其他 adapter（Claude / Codex / Custom）也调 `msg.blocks`——一旦 history 不为空就会炸。建议 thread_service 侧 `MessageInHistory.from_orm` 包装一层 |
| 8 | opencode CLI 在 Windows 通过 `.cmd` shim 运行时，prompt 中 `>` `<` `|` 等被 cmd.exe 误判为 redirection | 错误 `> was unexpected at this time.`，子进程直接挂 | ✅ 5/29 已修（`_resolve_opencode_binary` 找出真 .exe 直调，绕过 cmd shim）|

---

## 优先级路径（上线必需）

```
模块零（测试基础设施补齐）
    ↓
模块三（auth）+ 模块六（messages/conversations API）
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
