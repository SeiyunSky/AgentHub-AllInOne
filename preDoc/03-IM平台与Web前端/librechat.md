# LibreChat

## 1. 项目基本信息

- **项目名**：LibreChat（danny-avila/LibreChat）
- **GitHub**：https://github.com/danny-avila/LibreChat
- **Star 数 / 主要语言**：37k / TypeScript + JavaScript
- **简介**（≤200 字）：

功能最全的 ChatGPT 克隆式开源平台，支持 Claude、OpenAI、Azure、Bedrock、Gemini、Vertex AI 等所有主流模型。有完整的 Agents 系统（Agent builder + Subagents 委托 + 技能工具集）、Resumable SSE（断线续传流式）、Code Artifacts（React/HTML/Mermaid 内联渲染）、多用户认证（JWT + Redis session）。后端 Node.js Express + MongoDB + Redis + Socket.IO 的分层架构是所有候选项目中与 AgentHub 后端需求最接近的。

- **核心创新（一句话）**：Resumable SSE（流中断后从断点续传）和完整的 Agents 系统（含 Subagents 委托）是其他项目没有的工程亮点。

## 2. 项目架构概览

### 技术栈

- **语言**：TypeScript / JavaScript（全栈）
- **后端框架**：Node.js Express 5
- **前端框架**：React 18 + Vite + Tailwind CSS
- **实时通信**：SSE（流式回复）+ Socket.IO（状态推送）
- **数据库**：MongoDB（Mongoose ORM）
- **缓存 / Session**：Redis（ioredis）
- **认证**：JWT + Passport.js

### 目录结构

```
LibreChat/
├── api/                            ← Node.js 后端
│   ├── app/
│   │   ├── clients/                ← 核心：各模型客户端
│   │   │   ├── BaseClient.js       ← 所有模型客户端的基类（Resumable SSE 在此）
│   │   │   ├── AnthropicClient.js  ← Claude 适配
│   │   │   ├── OpenAIClient.js     ← OpenAI 适配
│   │   │   └── AgentClient.js      ← Agent 模式客户端
│   │   └── agents/                 ← Agent 系统
│   │       ├── agent.js            ← Agent 实体与执行
│   │       └── tools/              ← Agent 工具集
│   ├── models/                     ← MongoDB Schema
│   │   ├── Conversation.js         ← 会话模型
│   │   ├── Message.js              ← 消息模型（独立集合）
│   │   └── Agent.js                ← Agent 配置模型
│   ├── routes/                     ← Express 路由
│   │   ├── ask/                    ← 核心聊天接口（SSE 端点）
│   │   └── agents/                 ← Agent CRUD API
│   └── server/
│       └── index.js                ← Socket.IO 初始化
├── client/                         ← React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat/               ← 聊天核心组件
│   │   │   │   ├── Messages/       ← 消息列表 + 气泡
│   │   │   │   └── Input/          ← 输入框
│   │   │   └── Artifacts/          ← 代码产物渲染
│   │   ├── hooks/
│   │   │   └── SSE/                ← SSE 消费 hook
│   │   └── store/                  ← Recoil 状态管理
└── packages/                       ← Monorepo 子包
    ├── data-provider/              ← API 请求层（React Query）
    └── data-schemas/               ← 共享类型定义
```

### 核心机制

**一句话**：用户发消息 → Express `/api/ask` 接口 → 路由到对应模型 Client → BaseClient 启动流式生成 → SSE 逐 token 推送（携带 messageId）→ 前端 SSE hook 追加 token 到 Recoil store → Socket.IO 推送会话状态变更。

`BaseClient.js` 是整个项目的核心：所有模型适配器继承它，流式逻辑、Resumable SSE、消息持久化都在这里。流程是：调用模型 API 拿到 stream → 监听 `data` 事件 → 写入 MongoDB Message 文档（实时更新 content 字段）→ 同时 SSE 推给前端。如果连接中断，前端重连时携带 messageId，BaseClient 查 MongoDB 找到已写入的 content，从断点继续推送。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **Resumable SSE（断线续传）**：流式回复中途断网，前端重连携带 messageId，后端从 MongoDB 读已生成内容继续推。这解决了长回复的网络抖动问题，是生产级 SSE 的必备能力，AgentHub 应直接实现此模式。
2. **BaseClient 继承体系（适配器层）**：`BaseClient.js` 定义统一的流式接口，`AnthropicClient`、`OpenAIClient` 继承并覆写模型调用逻辑。新增一个 Agent 类型只需继承 BaseClient 并实现 `getCompletion()`，其余流式、持久化、SSE 全部继承。
3. **Conversation + Message 独立集合**：MongoDB 里 Conversation 和 Message 分开存，Message 有独立 `_id`，支持消息级操作（重新生成、引用、pin）。这是 AgentHub 消息数据模型的直接参考。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `api/app/clients/BaseClient.js` | 所有模型的统一流式基类 | 继承体系，子类只需覆写 `getCompletion()` |
| `api/app/clients/AnthropicClient.js` | Claude API 适配 | 继承 BaseClient，调用 Anthropic SDK |
| `api/app/clients/AgentClient.js` | Agent 模式执行 | Tool calling 循环 + Subagents 委托 |
| `api/models/Message.js` | 消息数据模型 | 独立集合，支持消息级查询和操作 |
| `api/routes/ask/` | SSE 聊天端点 | Express SSE，Resumable 断点续传 |
| `client/src/hooks/SSE/` | 前端 SSE 消费 | 自定义 hook，处理重连和 token 追加 |
| `packages/data-provider/` | API 请求层 | React Query 封装，与后端解耦 |

### 详细说明

- **BaseClient Resumable SSE 实现**：
  ```javascript
  // 前端重连时携带 messageId
  GET /api/ask?messageId=msg_123&resumeFrom=true
  
  // BaseClient 处理
  if (resumeFrom) {
    const saved = await Message.findById(messageId)
    // 先把已生成的内容推给前端
    res.write(`data: ${JSON.stringify({text: saved.content, resumed: true})}\n\n`)
    // 然后继续从模型流式生成（如果还没完成）
  }
  ```
  这个模式对 AgentHub 尤其重要——多个 Agent 并行流式时，任一 Agent 的连接中断都可以独立恢复，不影响其他 Agent。

- **Message 数据模型关键字段**：
  ```javascript
  {
    _id, conversationId, parentMessageId,  // 树形结构支持分支对话
    role,          // user / assistant / agent_A / agent_B
    text,          // 消息内容（流式过程中实时更新）
    agentId,       // 来自哪个 Agent
    isStreaming,   // 是否仍在流式输出
    createdAt
  }
  ```
  `parentMessageId` 支持树形对话（分支、重新生成）。AgentHub 可以简化为线性，但这个字段值得保留以支持"重新生成"功能。

- **Socket.IO 的职责**：LibreChat 里 Socket.IO 不负责消息内容推送（那是 SSE 的职责），而是推送会话状态变更（如 Agent 开始/停止、工具调用状态、错误通知）。这种"内容走 SSE、状态走 WebSocket"的分离是常见的工程实践，AgentHub 可以直接采用。

## 4. 关键细节

- **Monorepo 结构（`packages/`）**：`data-provider` 把所有 API 请求封装成 React Query hooks，前端组件不直接 `fetch`，而是调用 `useGetConversations()`、`useSendMessage()` 等。这种分层让前后端联调时接口边界清晰，AgentHub 建议采用。
- **Recoil vs Zustand**：LibreChat 用 Recoil（Facebook 出的状态库），比 Zustand 更重。AgentHub 如果用 React，Zustand 更简单，同样能实现多 Agent 并行气泡的状态管理。
- **MongoDB vs MySQL**：LibreChat 用 MongoDB 存 Message，好处是 content 字段可以是任意结构（文本、代码块、Artifacts JSON 混合）。AgentHub 用 MySQL 时，建议 content 存 JSON 字符串，类型用 `TEXT` 或 `JSON` 列。
- **Agent 工具集（`api/app/agents/tools/`）**：每个工具是一个 class，实现 `call(input)` 方法。Agent 执行时 LLM 决定调用哪个工具，AgentClient 执行后把结果追加到消息流。这是 AgentHub 自建 Agent 工具集的实现参考。
- **多用户认证完整**：JWT token + Redis 存 session blacklist（登出时加入黑名单）。如果 AgentHub 需要多用户，直接参考这套实现。
