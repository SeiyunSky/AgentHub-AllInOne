# Open WebUI

## 1. 项目基本信息

- **项目名**：Open WebUI（open-webui/open-webui）
- **GitHub**：https://github.com/open-webui/open-webui
- **Star 数 / 主要语言**：138k / Python + Svelte
- **简介**（≤200 字）：

功能最完整的自托管 AI 聊天平台，Star 数全类目最高。前端 SvelteKit，后端 Python FastAPI，支持 Ollama 本地模型和所有 OpenAI 兼容 API。核心亮点是"Many Models Conversations"——同一个问题可以同时发给多个模型，各自并行流式回复展示在同一界面。还支持 RAG 知识库、MCP 工具、Pipeline 插件系统、多用户权限管理。后端架构分层清晰，SSE 流式实现是开源项目中工程质量最高的之一。

- **核心创新（一句话）**：同一问题并行发给多个模型、各自流式回复的"多模型对话"模式，是所有开源项目中最接近 AgentHub 群聊并行回复需求的现有实现。

## 2. 项目架构概览

### 技术栈

- **语言**：Python（后端）+ TypeScript（前端）
- **后端框架**：FastAPI + SQLAlchemy + Alembic
- **前端框架**：SvelteKit 2 + Svelte 5 + Tailwind CSS 4
- **实时通信**：SSE（流式）+ WebSocket（部分功能）
- **数据库**：SQLite（默认）/ PostgreSQL（生产）
- **缓存**：Redis
- **任务队列**：无（直接 async/await）

### 目录结构

```
open-webui/
├── backend/
│   ├── open_webui/
│   │   ├── main.py              ← FastAPI 应用入口
│   │   ├── routers/
│   │   │   ├── chats.py         ← 会话 CRUD API
│   │   │   ├── ollama.py        ← Ollama 模型适配
│   │   │   └── openai.py        ← OpenAI 兼容 API 适配
│   │   ├── models/              ← SQLAlchemy ORM 模型
│   │   │   ├── chats.py         ← Conversation / Message 表
│   │   │   └── users.py         ← 用户表
│   │   ├── utils/
│   │   │   └── chat.py          ← 流式 SSE 生成器
│   │   └── pipeline/            ← Pipeline 插件系统
├── src/                         ← SvelteKit 前端
│   ├── lib/
│   │   ├── components/
│   │   │   ├── chat/            ← 聊天核心组件
│   │   │   │   ├── Messages/    ← 消息列表渲染
│   │   │   │   └── MessageInput.svelte ← 输入框
│   │   │   └── sidebar/         ← 左侧会话列表
│   │   └── stores/              ← Svelte store（状态管理）
│   └── routes/                  ← SvelteKit 路由页面
```

### 核心机制

**一句话**：用户发消息 → FastAPI 接收 → 根据选择的模型列表并行启动多个 async 生成器 → 每个生成器 SSE 流式推送各自的 token，携带 modelId 区分 → 前端 Svelte store 按 modelId 路由追加到对应气泡。

多模型并行的核心在后端：`POST /api/chat/completions` 接收 `models: ["gpt-4", "claude-3"]` 数组，后端 `asyncio.gather()` 同时调两个模型的流式接口，把两个 async generator 合并成一个 SSE 流，每个事件带 `model` 字段标识来源。前端收到后按 model 字段分拣到不同 Svelte store，各自渲染各自气泡。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **多模型并行 SSE 合并流**：后端用 `asyncio.gather()` 并行跑多个模型，把多个 async generator 合并成一个 SSE 连接推给前端，每个事件带 modelId。这是 AgentHub 群聊"多 Agent 并行流式回复"后端实现的直接参考。
2. **Pipeline 插件系统**：类似 Agent 适配器层——每个 Pipeline 是一个 Python 类，实现统一接口（`pipe()` 方法），可以接入任意 LLM、做预处理/后处理、实现 RAG。新增一个 Agent 类型 = 写一个 Pipeline 类。
3. **SQLAlchemy + Alembic 数据库迁移**：后端数据库层设计规范，ORM 模型 + 迁移文件完整。Conversation/Message 的表设计可以直接参考迁移到 AgentHub 的 MySQL。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `backend/routers/openai.py` | 统一适配多种 OpenAI 兼容 API | 代理转发 + 流式透传，base_url 可配置 |
| `backend/utils/chat.py` | 流式 SSE 生成器 | Python async generator + `yield` SSE 格式 |
| `backend/pipeline/` | Agent 适配器层 | 统一 `pipe()` 接口，每个 Pipeline 一个类 |
| `src/lib/stores/` | 多模型并行状态管理 | Svelte store，按 modelId 分别维护流式状态 |
| `src/lib/components/chat/Messages/` | 消息列表渲染 | 支持多个并行气泡同时 streaming |

### 详细说明

- **多模型并行 SSE 后端实现**：
  ```python
  async def generate_multi_model_stream(models, messages):
      tasks = [call_model(m, messages) for m in models]
      # 合并多个 async generator
      async for chunk in merge_async_generators(tasks):
          yield f"data: {json.dumps({**chunk, 'model': chunk['model']})}\n\n"
  ```
  前端按 `chunk.model` 字段路由到对应 store，各自追加内容。这和 AgentHub 的 `agentId` 路由逻辑完全一致，可以直接迁移思路。

- **Pipeline 插件接口**：每个 Pipeline 实现 `pipe(user_message, model_id, messages, body) -> Generator`。统一接口让 Bridge 层不感知具体模型实现——新增 Claude、Codex 只需要各写一个 Pipeline 类。这是 AgentHub 适配器层的设计参考。

- **Conversation/Message 数据模型**：`models/chats.py` 里 `Chat` 表含 `id, user_id, title, chat(JSON), created_at, updated_at`，其中 `chat` 字段是整个对话历史的 JSON blob。这种"历史存 JSON blob"的方案查询简单但不利于消息级操作；AgentHub 需要消息级查询（pin消息、重新生成），建议改为独立 Message 表。

## 4. 关键细节

- **`merge_async_generators` 模式**：Python 没有内置的多 async generator 合并工具，Open WebUI 自己实现了一个基于 `asyncio.Queue` 的合并器——每个 generator 向同一个 Queue 推数据，一个消费者从 Queue 取并 yield。这是 AgentHub 后端多 Agent 并行 SSE 的核心实现参考。
- **SSE 格式**：严格遵循 OpenAI SSE 协议——`data: {json}\n\n`，结束时 `data: [DONE]\n\n`。前端用标准 `EventSource` 消费。AgentHub 可以复用这套格式，只需在 JSON 里加 `agentId` 字段。
- **前端是 Svelte 不是 React**：直接复用代码成本高。但状态管理逻辑（按 modelId 分拣 token）的思路可以照搬到 React + Zustand。
- **Pipeline 和 Function 的区别**：Pipeline 是服务端插件（后端 Python 类），Function 是前端工具（JS）。两者都能扩展能力，Pipeline 更适合接入外部 API（如 Claude、Codex）。
- **Docker 一键部署**：官方 `docker-compose.yml` 包含完整服务栈，生产环境用 PostgreSQL + Redis。参考其 docker-compose 可以直接搭 AgentHub 的本地开发环境。
