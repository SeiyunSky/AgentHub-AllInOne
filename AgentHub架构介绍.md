# AgentHub 核心架构完整介绍

> 本文档面向视频录制，覆盖项目全部核心设计内容，包括架构范式、Orchestrator 实现、Prompt 工程内部机制、工具系统、Hook 体系、SSE 协议和前端状态机。

---

## 一、项目定位与整体架构范式

AgentHub 是一个**多 Agent 协作 IM 平台**，不是普通的 AI 对话工具。核心差异在于：普通 AI 对话是单 LLM 回答问题，AgentHub 是一个**主 Agent 编排、多个专职子 Agent 并行执行**的分布式任务系统。

### 架构全貌

```
用户发消息
    ↓
ChatService（消息分流器）
    ├── 单聊模式 → 直接转发给指定子 Agent Adapter
    ├── 群聊模式 → 进入 OrchestratorService 主 Agent Loop
    └── Broadcast 模式 → 推给全部 Agent，各自 70% 概率回复

                    群聊模式核心链路：

            OrchestratorService（主 Agent）
                Anthropic Claude API
                    ↓ 22 个工具
           ┌────────────────────────────────┐
           ↓                               ↓
    dispatch_to_agent              dispatch_to_agent
           ↓                               ↓
      Coder Agent                   Reviewer Agent
    (ClaudeAdapter/CLI)           (CustomAdapter/HTTP)
    只输出文本，零工具               只输出文本，零工具
```

**架构核心哲学**：子 Agent 没有任何工具权限，不能写文件、不能部署应用、不能调其他 Agent。**所有真实操作 100% 由 Orchestrator 执行**。这是整个系统最核心的设计决策。

### 五种对话模式

| 模式 | 触发条件 | 流程描述 |
|------|---------|---------|
| 单聊 | `conversation.mode = "single"` | 用户 → ThreadService → 子 Agent Adapter → 流式返回 |
| 群聊 | `conversation.mode = "group"` | 用户 → Orchestrator 八步 Loop → 派活给子 Agent |
| Broadcast | `conversation.mode = "broadcast"` | 消息广播给所有 Agent，各自独立回复 |
| @个体 | `@coder` 前缀 | Orchestrator 静默调度，不自行回复，等结果后汇总 |
| local_edit | 代码选区 + apply | DiffApplyService 直接修改沙箱文件 |

---

## 二、OrchestratorService 八步循环

这是整个项目最核心的代码，位于 `backend/services/orchestrator/service.py` 的 `_agent_loop` 方法。

### 2.1 生命周期管理（`start_loop`）

主 Agent 的完整生命周期：

```
start_loop 入口
    ↓
创建 asyncio.Event wake_event（等待子 Thread 完成时挂起用）
注册子 Thread 完成事件监听器（子 Thread 完成 → wake_event.set()）
    ↓
fire PRE_ORCHESTRATE hook（保留扩展点）
    ↓
mark_running(thread_id)  写 DB：Thread 状态 init → running
推 agent_start SSE 事件  前端立即出现"Orchestrator 正在思考"气泡
    ↓
await _agent_loop(...)   主循环（可能跑几十轮）
    ↓
finally 块（无论成功/异常/取消都执行）：
  fire POST_ORCHESTRATE hook
  unregister 子 Thread 事件监听器
  mark_done / mark_error（写 DB）
  update_tokens（统计 token 消耗）
  on_round_done → 推 round_done SSE + drain pending 消息
```

**Session 策略**：主 Agent Loop 跑几十秒到几分钟，不能持有跨 `await` 的长 SQLAlchemy Session（会导致事务泄漏和连接池耗尽）。所有数据库操作都用 `with db_session() as s` 短事务，用完立刻关闭。

### 2.2 八步循环正文（`_agent_loop`）

```python
while True:
    # 步 0：abort 检查
    if stream_service.is_aborted(conversation_id):
        raise asyncio.CancelledError()  # 用户点了 Stop
    
    # 步 1：消费 pending_events
    # 子 Thread 完成后 ThreadService 写入事件队列
    # 这里取出来，转成 user 消息注入 messages
    for summary in ThreadService.pop_pending_events(thread_id):
        messages.append({"role": "user", "content": f"[子 Thread 事件] {summary}"})
    
    # 步 2：构建 system prompt（六层管道，见第三节）
    dynamic_prompt = await prompt_builder.build_dynamic(ctx)
    system_prompt = static_prompt + DYNAMIC_BOUNDARY + dynamic_prompt
    
    # 步 3：调用 Anthropic API
    try:
        response = await llm_client.chat_completion(
            system=system_prompt,
            messages=messages,
            tools=tools,  # 22 个工具 schema
        )
    except Exception as exc:
        # 异常分类路由：
        # "fatal" → 直接抛出（认证失败、非法请求）
        # "prompt_too_long" → global_summarize 压缩历史后重试
        # "api_error" → 指数退避重试
    
    # 步 3.5：max_tokens 处理（stop_reason 路径，不走 except）
    if response.stop_reason == "max_tokens":
        # 把已截断的 text 部分保留，丢弃不完整的 tool_use
        # 注入续写提示消息，continue 回到步 1
    
    # 步 4：end_turn 收敛判断
    if is_terminal_stop_reason(response):
        if self._has_unfinished_children(conversation_id, thread_id):
            # 还有子 Thread 没回报
            # 挂起等待，asyncio.Event，最多等 30 分钟
            await asyncio.wait_for(wake_event.wait(), timeout=1800)
            wake_event.clear()
            continue  # 被唤醒后回步 1 消费新事件
        else:
            # 所有子 Thread 完成，主 Agent 也说完了
            break  # 正常退出 loop
    
    # 步 5：tool_use 派发
    if has_tool_calls(response):
        # 步 5-pre：批量文件审批
        # 同一轮有 ≥2 个 create_file/edit_file → 合并成一个审批弹窗
        
        # PRE_TOOL_USE hook 链（串行）
        # → PreExecutionHook（黑名单+路径校验）
        # → ApprovalHook（高危工具阻塞等待用户审批）
        
        # 执行工具（内置工具或 MCP 工具）
        tool_result = await dispatch_tool_call(effective_call, ctx=tool_ctx)
        
        # 推 BlockStart + BlockStop SSE（前端 workflow 可视化）
        # POST_TOOL_USE hook（异步审计）
        
        # 拼 tool_result 回 messages
        messages.append({"role": "user", "content": tool_result_blocks})
        
        # 步 6：context compactor
        messages = await context_compactor.maybe_compact(messages)
        continue  # 回步 1，让 LLM 看到工具结果
```

### 2.3 唤醒机制详解

这是 Loop 里最精妙的设计：

```
子 Thread 完成（任意终态）
    ↓
ThreadService._on_thread_terminal()
    ↓
向队列写入完成摘要（pending_events[orchestrator_thread_id].append(summary)）
    ↓
调用注册的监听器 _on_child_thread_event()
    ↓
wake_event.set()
    ↓
_agent_loop 步 4 从 await wake_event.wait() 恢复
    ↓
wake_event.clear()（为下次等待复位）
continue 回步 1，消费新 pending_events
```

为什么只在 `end_turn` 时挂起，`tool_use` 时不挂起？因为 `tool_use` 表示 LLM 正在主动做事（调工具），不需要等待。`end_turn` 表示 LLM 认为"我没事干了"，这时如果还有子 Thread 在跑，就挂起等结果回来。

---

## 三、Prompt 工程：六层管道

这是理解 Orchestrator 智能的关键，位于 `backend/services/orchestrator/prompt_builder.py`。

### 3.1 整体结构

System Prompt 被切分为**静态层**和**动态层**两大块，中间用 `--- DYNAMIC ---` 分隔：

```
Static（loop 开始时算一次，缓存到局部变量）
  Layer 1: 核心指令（orchestrator.md 全文，进程级缓存）
  Layer 2: 工具列表（空！工具走 tools= 参数，不重复）
  Layer 3: Skill 元数据索引（只列名称，详情让 LLM 用工具按需加载）
  Layer 4: AGENTHUB.md 链（项目根 + 部署 cwd，后者覆盖前者）

--- DYNAMIC BOUNDARY ---

Dynamic（每轮重新计算）
  Layer 5: 长期记忆索引（MEMORY.md 摘要，让 LLM 用 read_file 按需加载）
  Layer 6: 动态上下文
    ├─ 最近 20 条会话历史（每条截断 300 字符）
    ├─ 本会话挂载的可用 Agent 列表
    └─ 当前轮次任务图（所有 Thread 的 id/status/blocked_by）
```

### 3.2 为什么 Layer 2 是空的

这是一个有意思的设计决策。工具信息通过 Anthropic SDK 的 `tools=` 参数传递，LLM 天然知道每个工具的 `name`、`description`、`input_schema`。如果在 System Prompt 里再列一遍，有两个问题：
1. 浪费约 3000 个 token
2. 维护两处，容易不同步（改了 schema 忘了改 prompt）

### 3.3 Progressive Disclosure（渐进式披露）

Layer 3、5 都用了同一个设计模式：Prompt 里只放索引（名称 + 一句话描述），LLM 需要详情时自己调工具去拿。

```markdown
## 你的长期记忆索引

以下是当前会话累积的长期记忆。
如需查看某条记忆的完整内容，调用 read_file 工具，path 参数填记忆文件名。
先按需要读，不要每条都读——索引足够你判断哪些相关。

- [project_context.md] — 费用报销系统，Phase 2 权限层进行中
- [user_preferences.md] — 用户偏好简洁代码风格，不喜欢过多注释
```

好处：避免把大量可能无关的内容强塞进上下文，减少 token 消耗，同时让 LLM 主动按需检索。

### 3.4 静态层缓存策略

```python
# _agent_loop 里，static_prompt 在 loop 开始时算一次
static_prompt = await prompt_builder.build_static(prompt_ctx)  # 缓存！

while True:
    # 每轮只重新计算动态层（任务图状态可能变化）
    dynamic_prompt = await prompt_builder.build_dynamic(prompt_ctx)
    system_prompt = static_prompt + DYNAMIC_BOUNDARY + dynamic_prompt
    # ...
```

`orchestrator.md` 在类级别有进程级缓存：第一次读文件后存 `_core_instructions_cache`，后续直接返回，避免重复 IO。

### 3.5 AGENTHUB.md 链（Layer 4）

设计类似 Claude Code 的 `CLAUDE.md`：
- `{项目根}/AGENTHUB.md`：随代码版本化，团队共享的全局指令
- `{部署 cwd}/AGENTHUB.md`：运维覆盖配置，不进 git

两个文件都存在时，用 `---` 分隔拼接（后写的在 LLM 注意力里优先级更高）。路径用 `resolve()` 去重，避免 `cwd` 与项目根重合时重复加载。

---

## 四、orchestrator.md：Prompt 工程核心

这是系统最重要的 Prompt 文件（900+ 行），位于 `backend/prompts/orchestrator.md`。

### 4.1 主从职责划分（铁律）

```markdown
你和子 Agent 的本质区别：
- 子 Agent 只输出文本——写代码（以 filepath: 注释代码块形式）、写报告、回答问题。
  子 Agent 没有任何工具权限。
- 所有真实操作（写文件、修改文件、部署应用）100% 由你完成。
```

这段话在 Prompt 里被三次重申，因为这是 LLM 最容易犯的错：试图让子 Agent 使用工具。子 Agent 看到"请使用 create_file 工具"这类指令只会输出废话，不会真正执行。

### 4.2 决策树：每条消息如何处理

```
收到消息
    ↓
判断消息类型：
├── 闲聊/问候 → 直接回复，立即 end_turn
│   例外：涉及团队成员 → 派活让对应 Agent 自我介绍
├── 任务请求 → 进入派活规则（见 4.3）
├── 子 Thread 完成事件 → 进入结果评估（见 4.4）
├── [用户直接 @ 了某 Agent] → 静默调度，全程不自行回复
└── 已有子 Thread 运行时收到新消息 → 插话处理（见 4.5）
```

### 4.3 派活规则：两阶段筛选 + 拆任务原则

**第一阶段：capabilities 硬过滤**
- 任务必然涉及代码改动 → 候选池只保留 `supports_diff=true` 的 Agent
- 任务可能触发破坏性操作 → 候选池只保留 `supports_approval=true` 的 Agent
- 候选池为空 → 直接告知用户"当前会话没有合适的 Agent"，不降级派给不满足的

**第二阶段：tags + description 择优**
1. tags 命中 → 优先选 tags 与任务关键词命中的 Agent
2. 多个 Agent tags 都命中 → 读 description 选定位最贴近的
3. tags 都不命中 → 读 description 全文按"特长定位"判断

**拆任务原则：默认 1 个，克制拆分**

满足以下任一条件才拆：
- 用户明确表达分阶段（"先 X，然后 Y"）
- 专长区隔明显，后者必须看到前者完整产出
- 单 Agent 容易出错的复合需求

**反例（不要拆）**：
- "写一个爬虫" → 1 个任务，不要替用户加戏"写完再审查"
- "修这个 bug" → 1 个任务，不要拆成"定位+修复"
- 同一 Agent 能搞定的连续动作 → 1 个任务

### 4.4 dispatch_prompt 四段式模板

这是向子 Agent 派活时 prompt 的强制结构：

```
## 任务
[一句话目标，目标导向不是过程导向]

## 背景
[子 Agent 完成任务必须知道的上下文：
 - 项目信息、用户场景
 - 涉及的文件/代码/错误信息（原文贴入）
 - 上游 Thread 的产出（串行任务必须完整粘贴）]

## 要求
[执行约束：风格/语言/格式、必须做/禁止做的事
 注：绝不要求子 Agent "使用 create_file" 等工具，子 Agent 没有]

## 交付物
[预期产出格式：代码+diff？纯文本？分析报告？]
```

**派活前 5 项强制自检**（每次派活前必须过）：
- [ ] Agent 匹配：任务关键词和 Agent 的 description/tags 有交集
- [ ] 四段齐全：任务/背景/要求/交付物都写了
- [ ] 上游产出已粘贴：串行任务必须先调 `read_thread_result` 拿到真实内容完整粘贴
- [ ] 无占位符残留：没有 `{{...}}`、`<这里...>`、"请参考上一步"等空话
- [ ] 无本提示文字：没有把元指令混入发给子 Agent

**工具层的占位符兜底**：`dispatch_to_agent` handler 里有代码检测 `{{...}}` 占位符。检测到时，自动用 `blocked_by` 里上游 Thread 的产出替换。替换后仍有残留则报错，强制 LLM 重派。这是 Prompt 层约束 + 代码层兜底的双重防御。

### 4.5 运行中插话处理（IM 关键场景）

这解决了 IM 产品特有的问题：用户发了任务后，子 Agent 还没跑完就又来一条消息。

| 新消息类型 | 判断特征 | 决策 |
|-----------|---------|------|
| 冲突/撤销 | "等等"、"先别做了"、"改一下需求" | 立即 cancel 相关 Thread → 按新需求重新派活 |
| 任务追问（同向） | "记得加上 Y"、"另外把 Z 也考虑进去" | 不取消，等当前 Thread 完成后基于产出改进重派 |
| 闲聊插话（无关） | 和正在跑的任务毫无关系 | 直接回复用户，不影响正在跑的 Thread |
| 询问进度 | "做完了吗"、"还要多久" | 调 `read_thread_status` 工具查实时状态，简短告知 |

**判断核心**：看新消息有没有改变原任务的目标/范围/取消意图。

### 4.6 子 Thread 结果处理

Orchestrator 收到子 Thread 完成事件后，不是直接转发给用户，而是**先评估产出质量**：

三个评估问题：
1. 任务回应了吗？（有没有答非所问）
2. 要求满足了吗？（格式/风格/边界有没有遵守）
3. 交付物完整吗？（代码/报告/分析有没有都给）

任一为否 → 产出不达标（即使 Thread 状态是 done）

三种处理路径：
- **情况 A（Thread error）**：重派给同 Agent / 改派其他 Agent / 降级 / 报告用户
- **情况 B（done 但不达标）**：改进重派（把产出+问题完整粘贴，重申未满足要求）
- **情况 C（done 且达标）**：正常聚合 → 回复用户

**重派次数硬上限**：同一任务累计重派不超过 3 次。第 4 次仍不达标时停止，把最佳产出+失败原因报告给用户。

### 4.7 何时立即结束本轮（END THE TURN）

满足任一条件立即停止调工具：
1. 已发送最终回复给用户
2. 已发起澄清请求/任务计划审批（等待用户回复）
3. 已派出所有该派的子 Thread（派完等回报，本轮没事可做）

---

## 五、工具系统：22 个工具

### 5.1 工具注册机制

`tool_registry.py` 用装饰器模式注册工具：

```python
@register_tool(
    name="dispatch_to_agent",
    description="派任务给某个子 Agent，立即启动并异步执行，返回 thread_id。",
    input_model=DispatchToAgentInput,
)
async def dispatch_to_agent(tool_input: dict, *, ctx: ToolContext) -> dict:
    ...
```

`input_model` 是 Pydantic BaseModel，注册时自动转成 Anthropic JSON Schema。转换过程中有一个关键处理：Anthropic 对嵌套 `$ref` 支持不稳定（LLM 常常解析不出来导致参数乱填），所以 `pydantic_to_json_schema` 会递归展开所有 `$ref`，inline 成完整结构，并删掉 `title` 字段（节省 token）。

### 5.2 七组工具详解

**A. 任务调度（4个）**
- `dispatch_to_agent`：异步派活，创建 Thread，触发 `schedule_conversation`。内置占位符检测兜底
- `read_thread_status`：查单个 Thread 实时状态（必须 `expire_all()` 绕过 SQLAlchemy identity map 缓存）
- `read_thread_result`：读完整产出；`text_only=true` 模式只返回纯文本，节省 token，降低被 16KB 截断的概率
- `cancel_thread`：取消 Thread 并连带取消所有依赖它的下游 Thread

**B. 任务链管理（5个）**
- `create_task_plan`：一次性创建多个 Thread 含依赖图，`blocked_by` 字段声明串行关系
- `update_task_status`：标记为 cancelled（其他状态由系统自动管理）
- `read_task_plan`：读当前轮所有 Thread 状态全貌
- `add_task`：追加任务节点（适合动态扩展计划）
- `remove_task`：硬删除未启动的 Thread

**C. 用户交互（3个）**
- `respond_to_user`：主 Agent 向用户回复。先落库，再依次推 `AgentStart → BlockStart → BlockStop → AgentDone` 四个 SSE 事件
- `request_user_clarification`：向用户提问，先落库+`mark_suspended`（同一 session），再推 SSE（DB 先于 SSE，避免用户秒回时 DB 状态不一致）
- `present_task_plan_for_review`：向用户展示任务计划等审批，使用 `asyncio.Event` 阻塞等待，与 ApprovalHook 机制相同

**D. 上下文检索（3个）**
- `read_conversation_history`：读最近 N 条消息，反转为正序（LLM 需要时间线正序推理）
- `list_available_agents`：列本会话挂载的所有 Agent 概要
- `get_agent_capabilities`：查某 Agent 详情，system_prompt 只返回前 500 字预览

**E. 文件沙箱（4个）**
- `create_file`：新建文件，写后只返回 `{ok, path, size}`，不返回文件内容（避免 LLM 看到自己刚写的内容陷入"再验证"循环）
- `read_file`：读文件，可 `limit` 截断行数
- `edit_file`：精确替换 `old_text → new_text`，`old_text` 必须唯一出现，多次出现报错要求 LLM 补充上下文
- `list_directory`：列目录，非递归

所有文件操作都通过 `_resolve_sandbox_path` 做路径校验，防止路径穿越攻击（`../`、绝对路径、symlink 跳出），沙箱根固定为 `runtime/memory/{user_id}/{conversation_id}/`。

**F. 部署（3个）**
- `deploy_app`：8 步部署流程（见 5.3）
- `stop_app`：停止并销毁容器，沙箱目录保留
- `read_app_logs`：读容器内 `/app/.deploy.log` 末尾 N 行

**G. 网络（1个）**
- `fetch_url`：HTTP GET，自动跟随重定向，二进制内容返回摘要，文本内容可截断

**H. MCP 工具（动态）**
运行时从 MCP 服务器收集工具 schema，和内置工具合并后一起传给 LLM。MCP 工具通过 `tool_client_map` 路由，不走 `dispatch_tool_call`，走 `mcp_client.call_tool`。

### 5.3 deploy_app 八步流程

```
Step 1：检查沙箱内 entry_point 文件存在
Step 2：ensure_image()  确保 Docker 镜像就绪（首次构建/拉取）
Step 3：get_container 复用已有容器 / start_container 起新容器
         容器挂载沙箱目录到 /app
Step 4：pkill -f uvicorn  杀旧进程（支持重复部署）
Step 5：pip install -r requirements.txt（如有，失败则报错）
Step 6：nohup uvicorn {entry_module}:app --host 0.0.0.0 --port 8000 > /app/.deploy.log 2>&1 &
Step 7：健康检查  轮询 10 次，每次 0.5s，curl localhost:8000/，2xx/3xx/4xx 均视为健康
Step 8：返回 {status: "running", url: "http://localhost:{host_port}/", logs: "..."}
```

### 5.4 工具结果截断

所有工具结果在 `wrap_tool_result` 里做硬截断，上限 16KB：

```python
_TOOL_RESULT_MAX_BYTES = 16 * 1024

def wrap_tool_result(result: ToolResult) -> dict:
    payload = json.dumps(result.output, ensure_ascii=False)
    encoded = payload.encode("utf-8")
    if len(encoded) > _TOOL_RESULT_MAX_BYTES:
        suffix = "...truncated"
        budget = _TOOL_RESULT_MAX_BYTES - len(suffix.encode("utf-8"))
        payload = encoded[:budget].decode("utf-8", errors="ignore") + suffix
    return {"type": "tool_result", "tool_use_id": ..., "content": payload}
```

为什么是 16KB？
- 4KB 太小，`read_conversation_history` 返回 30KB+ 会被截掉 87%，LLM 看不到关键上下文
- 50KB+ 太大，多个工具结果累加进 prompt 会显著增加 token 成本
- 16KB 能装一二十条短消息，同时单轮多个 `tool_result` 累加仍在 Claude 200K context 合理范围

---

## 六、Hook 体系

### 6.1 Hook 注册与事件类型

```python
# main.py 启动时注册
hook_manager.register_sync(HookEvent.PRE_TOOL_USE, PreExecutionHook())   # 黑名单+路径校验
hook_manager.register_sync(HookEvent.PRE_TOOL_USE, ApprovalHook())       # 高危审批
hook_manager.register_async(HookEvent.POST_TOOL_USE, PostExecutionHook()) # 异步审计
```

| Hook 事件 | 类型 | 时机 | 用途 |
|----------|------|------|------|
| `PRE_TOOL_USE` | 同步 | 工具执行前 | 黑名单、路径校验、审批拦截 |
| `POST_TOOL_USE` | 异步 | 工具执行后 | 审计日志落库、CodeBlock SSE |
| `PRE_ORCHESTRATE` | 保留 | Loop 开始前 | 扩展用 |
| `POST_ORCHESTRATE` | 保留 | Loop 结束后 | 扩展用 |
| `APPROVAL_REQUESTED` | 异步 | 审批创建时 | 审计 |
| `APPROVAL_DECIDED` | 异步 | 审批完成时 | 审计 |

### 6.2 ApprovalHook：审批闭环完整实现

高危工具清单：`create_file`、`edit_file`、`deploy_app`

```python
class ApprovalHook(SyncHook):
    async def handle(self, ctx: HookContext) -> HookResult:
        # 非高危工具直接放行
        if tool_name not in _HIGH_RISK_TOOLS:
            return HookResult(decision="continue")
        
        # 批量审批已通过：跳过逐一审批
        if ctx.extra.get("batch_approved"):
            return HookResult(decision="continue")
        
        # 1. 创建 ApprovalBlock 落库
        #    注意：用 MessageAppendedEvent 推 SSE（非 BlockStartEvent）
        #    原因：BlockStartEvent 会把 approval 块塞进主 Agent 的 streaming 气泡
        #    导致前端拿到错误的 message_id，审批后状态不更新
        message_id = await self._publish_approval_block(ctx, block_id, tool_name)
        
        # 2. 注册待审批记录（asyncio.Event）
        pending = _PendingApproval(block_id, message_id, asyncio.Event())
        _pending_approvals[block_id] = pending
        
        # 3. 阻塞等待用户决策（最多 120 秒）
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=120)
        except asyncio.TimeoutError:
            # 超时自动 reject，持久化状态，返回 block
            return HookResult(decision="block", block_reason="审批超时自动拒绝")
        
        # 4. 处理决策结果
        if pending.decision == "approve":
            return HookResult(decision="continue")
        else:
            return HookResult(decision="block", block_reason=f"被用户拒绝：{pending.reject_reason}")
```

**`decide()` 入口**（WS/HTTP Handler 调用）：

```python
async def decide(block_id, decision, reject_reason=None) -> bool:
    pending = _pending_approvals.get(block_id)
    
    # 必须先写库再 set event
    # 顺序约束：如果先 set event，主 Agent loop 立即继续
    # 用户刷新页面可能读到旧的 pending 状态
    await message_service.update_approval_block(
        pending.message_id, block_id,
        status="approved"/"rejected",
        decided_at=now,
        reject_reason=reject_reason,
    )
    
    pending.decision = decision
    pending.reject_reason = reject_reason
    pending.event.set()  # 唤醒 ApprovalHook 中的 await
```

### 6.3 批量文件审批

同一轮有 ≥2 个文件写工具时，`service.py` 检测到后先调 `batch_request_file_approval`，合并成一个审批弹窗（列出所有文件路径和操作类型）。用户一次点 Approve/Reject 即可，避免为每个文件单独弹窗。

批量审批通过的文件写工具在逐一 `PRE_TOOL_USE` 时通过 `ctx.extra["batch_approved"] = True` 跳过 `ApprovalHook`。

### 6.4 HookBlockedException 的处理设计

Hook 返回 `block` 时抛出 `HookBlockedException`，但 `service.py` 不让它冒到 `start_loop`（那样会 mark_error，前端永远收不到 round_done）。而是：

```python
try:
    pre_result = await hook_manager.fire(HookEvent.PRE_TOOL_USE, pre_ctx)
except HookBlockedException as exc:
    blocked_calls[call.id] = str(exc.reason)
    resolved_calls.append((call, call.input))  # 仍要进列表，保证 tool_use/tool_result 成对
    continue
```

被 block 的 tool_call 对应一个 `is_error=True` 的 tool_result 回传给 LLM，LLM 自己决定下一步（换思路/重试/收手），不崩整个 loop。

---

## 七、Adapter 抽象层

### 7.1 接口设计

```python
class AgentAdapter(ABC):
    @abstractmethod
    async def stream(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:
        """流式生成，yield AgentEvent"""
    
    @abstractmethod
    def get_capabilities(self) -> AgentCapabilities:
        """声明支持 diff/code/approval/image 等特性"""
```

`StreamInput` 包含：system_prompt、conversation history、dispatch_prompt、model 配置、cancel_event（用于取消）。

### 7.2 四种 Adapter 实现

| Adapter | 调用方式 | 适用场景 |
|---------|---------|---------|
| `ClaudeAdapter` | `claude-code` CLI 子进程 + stdin/stdout | 内置 Claude（绕 Windows 8191 字符 CLI 限制：用 stdin 喂 prompt） |
| `CodexAdapter` | MCP 子进程协议 | MCP 兼容 LLM |
| `CustomAdapter` | OpenAI SDK HTTP | Deepseek/Qwen/Ollama 等兼容接口 |
| `OpencodeAdapter` | `opencode` CLI 子进程 | OpenCode |

### 7.3 AgentEvent 统一事件模型

无论哪种 Adapter，都 yield 同一套事件：
- `AgentStartEvent`
- `BlockStartEvent(block: ContentBlock)`
- `BlockDeltaEvent(block_id, delta)`
- `BlockStopEvent(block_id, final_fields)`
- `AgentDoneEvent(tokens_input, tokens_output)`
- `AgentErrorEvent(error)`

ThreadService 消费这些事件，统一推给 SSE，前端无需感知 Adapter 差异。

---

## 八、SSE 块级协议与前端状态机

### 8.1 完整事件序列

```
GET /api/v1/chat/stream/{conversation_id}
    ↓ 长连接，按时序推送 JSON 事件

agent_start     {agent_id, thread_id, message_id, agent_name, agent_avatar}
block_start     {agent_id, thread_id, message_id, block: {block_id, type, content}}
block_delta     {agent_id, thread_id, block_id, delta}   ← 可重复，流式增量
block_stop      {agent_id, thread_id, block_id, final_fields}
    ↑── 以上三个事件一组，对应一个块（text/thinking/tool_use/code/approval）
agent_done      {agent_id, thread_id, message_id, tokens_input, tokens_output}
    ↑── 一个 Agent 的完整输出结束

round_done      {conversation_id}  ← 本轮主 Agent loop 完全结束
message_appended {message}         ← 审批块等非 streaming 消息（走独立路径）
read_receipt    {agent_id}         ← Broadcast 模式"已读不回"
queue_drained   {}                 ← 最后一个事件，前端可断开连接
```

### 8.2 为什么审批块用 `message_appended` 而不用 `block_start`

这是一个踩过坑才有的设计。

`BlockStartEvent` 会被前端 `chatStore.appendBlock` 追加到当前正在 streaming 的 Agent 气泡里。但审批块是一条**独立消息**（有自己的 `message_id`），不属于任何 streaming 气泡。如果走 `block_start`：
1. 审批组件拿到的 `message_id` 是 streaming 占位用的 `thread_id`，不是真实的 `message_id`
2. 用户点 Approve 后，前端在 `messageMap` 里找不到对应消息，状态永远显示 Waiting
3. 后续 streaming 状态错位，用户必须刷新页面

`MessageAppendedEvent` 走非 streaming 路径，前端直接 append 一条完整消息，与主 Agent 气泡完全解耦。

### 8.3 前端状态机（核心 Pinia Store）

```typescript
// stores/chat.ts
streamingMap: {
  "conv_id_1": {
    "orchestrator": { blocks: [...], agentName: "Orchestrator" },
    "coder":        { blocks: [...], agentName: "Coder" },
    "reviewer":     { blocks: [...], agentName: "Reviewer" },
  }
}
```

三个 Agent 可以同时在前端显示各自的打字气泡（Teams 风格），互不干扰，按 `agentId` 独立维护。

SSE 事件路由（`useSSE.ts`）：

```typescript
function handleEvent(convId, event) {
    switch (event.type) {
        case "agent_start":
            // 创建新的 AgentStreamingState
            streamingMap[convId][agentId] = new AgentStreamingState()
            workflowStore.onAgentStart(...)
            break
        
        case "block_start":
            // 追加块到对应 Agent 的 streaming 气泡
            // 如果是 code 块且有 filename，触发沙箱文件刷新
            streamingMap[convId][agentId].blocks.push(block)
            break
        
        case "block_delta":
            // 追加增量文本
            streamingMap[convId][agentId].updateBlock(blockId, delta)
            break
        
        case "block_stop":
            // 块完成，记录 final_fields（status/output/tool_name）
            // 如果 tool_name=deploy_app，同步到 deployments store
            break
        
        case "agent_done":
            // 把 streaming 气泡转为正式消息，存入 messages
            message = convertStreamingToMessage(streamingState)
            messages.push(message)
            delete streamingMap[convId][agentId]
            break
        
        case "round_done":
            // 本轮完全结束，清理 streaming 状态
            workflowStore.persistCurrent(convId)  // 快照持久化，支持历史回看
            break
    }
}
```

### 8.4 SSE 先于 HTTP POST 的发送顺序

```typescript
async function sendMessage(req: ChatRequest) {
    await connectSSE(conversationId)  // 先建立 SSE 连接
    await chatApi.send(request)       // 再发送消息
}
```

顺序不能反。如果先发 POST，后端立刻开始推 SSE 事件，而此时 SSE 连接还没建立，前几条事件就丢了。

---

## 九、数据库模型

11 张核心表：

```
users               认证（id, username, password_hash）
agents              Agent 配置（name, type, system_prompt, capabilities, tags）
skills              Skill 库（name, description, content 内联 MD）
agent_skills        Agent-Skill 关联表
conversations       会话（mode: single/group/broadcast, title）
conversation_agents 会话参与者（agent_id, joined_at）
messages            消息（role, content: JSON ContentBlock[], sender, feedback）
threads             执行线程（status, blocked_by: JSON, tokens_total）
read_receipts       Broadcast 已读回执
audit_logs          工具调用审计（tool_name, input, output）
workflows           工作流快照（snapshot: JSON，支持历史回看）
mcp_servers         MCP 服务器配置（transport, command/url, env, headers）
```

### Thread 状态机

```
init → running → done
              ↘ error
              ↘ cancelled
init/running → suspended（主动挂起，等用户澄清）
suspended → running（用户回复后重新激活）
```

---

## 十、核心设计权衡总结

| 决策点 | 选择 | 背后理由 |
|-------|------|---------|
| 工具权限归属 | 全部归 Orchestrator | 可审计、可审批，子 Agent 无需感知工具，接口简单 |
| 子 Agent 等待机制 | `asyncio.Event` | 不轮询，零开销挂起，`wait_for` 自然支持超时 |
| Prompt 静态/动态分离 | 静态缓存，动态每轮 | 减少文件 IO；任务图状态实时更新 |
| 工具结果截断阈值 | 16KB | 平衡上下文完整性与 token 成本 |
| 流式协议 | SSE（审批走独立 WS） | HTTP 友好，负载均衡兼容；审批需要双向通信故单独用 WS |
| 审批消息推送 | `MessageAppendedEvent` | 独立消息路径，避免与主 Agent streaming 气泡混淆 |
| 占位符检测 | Prompt 约束 + 代码层双重兜底 | Prompt 约束 LLM，代码层检测兜底，两层防御 |
| Session 生命周期 | 短 Session，每次用完关 | 避免跨 `await` 长事务，防连接池泄漏 |
| 工具 Schema 传递 | `tools=` 参数，不在 Prompt 重复 | 节省约 3K token，避免维护两处不同步 |

---

## 十一、关键文件速查

| 功能 | 文件 | 核心类/函数 |
|------|------|-----------|
| 主 Agent 八步 Loop | `backend/services/orchestrator/service.py` | `OrchestratorService._agent_loop` |
| 六层 Prompt 管道 | `backend/services/orchestrator/prompt_builder.py` | `SystemPromptBuilder` |
| 主 Agent 核心指令 | `backend/prompts/orchestrator.md` | 900+ 行 Prompt 工程文件 |
| 22 个工具实现 | `backend/services/orchestrator/orchestrator_tools.py` | `@register_tool` 装饰的 handler |
| 工具注册与派发 | `backend/services/orchestrator/tool_registry.py` | `dispatch_tool_call`, `wrap_tool_result` |
| 审批闭环 | `backend/hooks/approval.py` | `ApprovalHook`, `decide()` |
| 消息分流 | `backend/services/chat_service.py` | `ChatService.handle_chat` |
| SSE 推送 | `backend/services/stream_service.py` | `stream_service.push_event` |
| 子 Thread 调度 | `backend/services/thread_service.py` | `ThreadService` |
| Adapter 抽象基类 | `backend/adapters/base.py` | `AgentAdapter` |
| Claude CLI Adapter | `backend/adapters/claude.py` | `ClaudeAdapter.stream` |
| 前端 SSE 路由 | `frontend/src/composables/useSSE.ts` | `handleEvent` |
| 前端多 Agent 状态 | `frontend/src/stores/chat.ts` | `streamingMap` |
| 前端工作流追踪 | `frontend/src/stores/workflow.ts` | `WorkflowStore` |
| HTTP/SSE API 端点 | `backend/api/v1/chat.py` | `post_chat`, `get_stream` |
