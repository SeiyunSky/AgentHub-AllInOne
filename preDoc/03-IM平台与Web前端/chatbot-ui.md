# Chatbot-UI

## 1. 项目基本信息

- **项目名**：Chatbot-UI（mckaywrigley/chatbot-ui）
- **GitHub**：https://github.com/mckaywrigley/chatbot-ui
- **Star 数 / 主要语言**：33k / TypeScript
- **简介**（≤200 字）：

最早流行的 ChatGPT 开源克隆，代码极简清晰，是学习 AI 聊天应用前端实现的最佳入门项目。基于 Next.js + Vercel AI SDK，流式 SSE 接口是整个项目最值得参考的部分——用不到 50 行代码实现了标准的流式对话接口。数据库用 Supabase（PostgreSQL）+ Row Level Security。功能相对薄弱：无多 Agent、无群聊、无产物预览。作者已表示在重写，维护状态不稳定，不适合作为架构基础，但流式实现代码可直接参考。

- **核心创新（一句话）**：用 Vercel AI SDK 把流式对话接口压缩到最小实现，是理解 SSE + Next.js API Route 最清晰的参考代码。

## 2. 项目架构概览

### 技术栈

- **语言**：TypeScript
- **框架**：Next.js 14（App Router）+ React 18
- **UI 组件**：Tailwind CSS + Radix UI
- **AI 流式**：Vercel AI SDK（`ai` 包）
- **数据库**：Supabase（PostgreSQL + Row Level Security）
- **状态管理**：React Context + useReducer

### 目录结构

```
chatbot-ui/
├── app/
│   ├── api/
│   │   └── chat/
│   │       └── route.ts        ← 核心：流式聊天 API（约 40 行）
│   └── [locale]/               ← 国际化路由
│       └── [workspaceid]/chat/ ← 聊天页面
├── components/
│   ├── chat/
│   │   ├── chat-messages.tsx   ← 消息列表
│   │   ├── chat-input.tsx      ← 输入框
│   │   └── chat-ui.tsx         ← 聊天布局
│   └── sidebar/                ← 左侧会话列表
├── context/
│   └── context.tsx             ← 全局状态（Context + useReducer）
├── db/
│   └── messages.ts             ← Supabase 消息 CRUD
└── types/                      ← TypeScript 类型定义
```

### 核心机制

**一句话**：前端 `useChat` hook 调用 `/api/chat` → Next.js API Route 用 Vercel AI SDK 调模型 → `StreamingTextResponse` 直接把流返回给前端 → `useChat` 自动追加 token 到消息列表。

整个流式实现核心只有 `app/api/chat/route.ts` 这一个文件，约 40 行：接收 messages 数组，调用 `streamText()`，返回 `result.toDataStreamResponse()`。前端 `useChat` hook 自动处理 SSE 消费、token 追加、loading 状态。代码量极小，适合作为"理解流式 AI 接口"的第一份参考代码。

## 3. 可参考的设计点

**最值得关注的 2 个设计**：

1. **Vercel AI SDK 最小流式实现**：`route.ts` 约 40 行代码跑通完整流式对话，是理解 SSE + LLM API 集成的最清晰范本。AgentHub 后端无论用什么栈，理解这份代码有助于掌握流式接口的本质。
2. **`useChat` hook 封装**：Vercel AI SDK 的 `useChat` 把 SSE 消费、消息追加、错误处理、loading 状态全部封装成一个 React hook，调用方只需要 `const { messages, input, handleSubmit } = useChat()`。如果 AgentHub 前端用 Next.js，可以直接用这个 hook 作为单聊的基础，群聊再在此之上扩展。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `app/api/chat/route.ts` | 流式聊天接口 | Vercel AI SDK `streamText` + `toDataStreamResponse` |
| `components/chat/` | 聊天 UI 组件 | React 组件，Tailwind 样式，无第三方 UI 库 |
| `context/context.tsx` | 全局状态管理 | React Context + useReducer（轻量，无需 Zustand） |
| `db/messages.ts` | 消息持久化 | Supabase client，Row Level Security 控制访问 |

### 详细说明

- **核心 API Route（最值得读的代码）**：
  ```typescript
  // app/api/chat/route.ts
  import { streamText } from 'ai'
  import { openai } from '@ai-sdk/openai'

  export async function POST(req: Request) {
    const { messages } = await req.json()
    const result = await streamText({
      model: openai('gpt-4'),
      messages,
    })
    return result.toDataStreamResponse()
  }
  ```
  这 10 行代码就是一个完整的流式 AI 接口。`toDataStreamResponse()` 自动生成标准 SSE 格式，前端 `useChat` 自动消费。AgentHub 即使不用 Next.js，这个模式也是适配器层接口设计的参考基准。

- **Supabase Row Level Security**：消息表开启 RLS，每行数据带 `user_id`，查询自动过滤只返回当前用户的数据，不需要在应用层写 `WHERE user_id = ?`。对 AgentHub 的多用户场景有参考价值，但 MySQL 没有 RLS，需要在 ORM 层手动实现。

## 4. 关键细节

- **适合作为入门参考，不适合作为架构基础**：代码极简的代价是功能薄弱——无 Agent 系统、无群聊、无产物预览、无多用户权限。直接在此基础上扩展成本比从 LibreChat 裁剪更高。
- **Vercel AI SDK SSE 数据格式**：`0:"token"\n`（文本）、`d:{finishReason}\n`（完成）、`3:"error"\n`（错误）。这是 Vercel 定义的私有协议，不是标准 OpenAI SSE 格式。如果 AgentHub 后端不用 Vercel AI SDK，需要自己在前端解析，或者统一改用 OpenAI 标准 SSE 格式（`data: {json}\n\n`）。
- **作者重写声明**：2024 年作者在 README 明确说"正在用新架构重写"，当前版本停止维护。不要基于这个版本做二次开发，只做代码阅读参考。
- **无 Redis、无 WebSocket**：最简架构，适合单用户本地部署。生产化的 AgentHub 需要 Redis（session、流式缓冲）和 WebSocket/Socket.IO（状态推送），这些在 Chatbot-UI 里找不到参考。
