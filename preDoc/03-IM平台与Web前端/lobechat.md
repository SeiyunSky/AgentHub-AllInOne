# LobeChat

## 1. 项目基本信息

- **项目名**：LobeChat（lobehub/lobe-chat）
- **GitHub**：https://github.com/lobehub/lobe-chat
- **Star 数 / 主要语言**：77k / TypeScript
- **简介**（≤200 字）：

开源的现代化 AI 聊天框架，UI 风格最接近飞书/微信的 IM 体验——左侧会话列表、右侧聊天窗口、Agent 市场。支持 Claude、OpenAI、DeepSeek、Gemini 等主流模型，内置 Artifacts（HTML/React 内联渲染）、文件上传、图片生成、MCP 插件市场。有 Agent Groups 概念支持多 Agent 在同一页面协作。前后端一体化，基于 Next.js App Router，数据库支持本地 IndexedDB 和远端 PostgreSQL。

- **核心创新（一句话）**：把 AI 聊天界面做成最接近 IM 产品体验的开源实现，Artifacts 内联渲染和 Agent 市场是核心差异点。

## 2. 项目架构概览

### 技术栈

- **语言**：TypeScript
- **框架**：Next.js 15（App Router）+ React 19
- **UI 组件**：Ant Design 6 + Lobe UI（自研组件库）
- **状态管理**：Zustand
- **AI 流式**：Vercel AI SDK（`ai` 包，标准 SSE）
- **数据库**：本地 IndexedDB（默认）/ PostgreSQL（多用户部署）
- **认证**：Clerk / NextAuth

### 目录结构

```
lobe-chat/
├── src/
│   ├── app/                    ← Next.js App Router 页面
│   │   ├── (main)/chat/        ← 核心聊天页面
│   │   └── (main)/discover/    ← Agent 市场
│   ├── components/             ← 通用 UI 组件
│   │   ├── Conversation/       ← 对话消息列表
│   │   ├── ChatInput/          ← 消息输入框
│   │   └── Artifacts/          ← 产物内联渲染组件
│   ├── features/               ← 业务功能模块
│   │   ├── Conversation/       ← 会话管理
│   │   ├── AgentSetting/       ← Agent 配置
│   │   └── PluginStore/        ← 插件市场
│   ├── store/                  ← Zustand 状态管理
│   │   ├── chat/               ← 聊天状态（消息列表、流式状态）
│   │   └── session/            ← 会话列表状态
│   ├── server/                 ← Next.js API Routes（后端）
│   │   └── routers/chat/       ← 流式聊天接口
│   └── database/               ← 数据库 ORM（Drizzle）
```

### 核心机制

**一句话**：用户发消息 → Next.js API Route 接收 → Vercel AI SDK 调用对应模型 → SSE 流式回传 → 前端 Zustand store 追加 token 到消息气泡 → Artifacts 组件检测到代码块自动渲染 iframe。

前端状态管理核心在 `store/chat/`：维护 `messages[]` 数组，每条消息有 `streaming: boolean` 标志；收到 SSE token 时找到对应消息 id 追加内容，收到 `done` 事件时设 `streaming: false`。Zustand 的 immer 中间件保证不可变更新。Agent Groups 功能允许在同一会话里配置多个 Agent，消息发出后按配置路由到不同模型，各自回复各自气泡。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **Artifacts 内联渲染**：Agent 回复中含 HTML/React 代码时，自动生成 sandboxed iframe 展示在气泡内，用户可点击展开全屏。这是 AgentHub"产物预览卡片"的直接参考实现。
2. **Zustand 流式消息状态机**：`store/chat/` 里维护每条消息的 streaming 状态，token 追加和 done 事件处理的模式可以直接迁移到 AgentHub 的多 Agent 并行气泡场景。
3. **Agent 市场 + 自建 Agent**：`discover/` 页面展示 Agent 卡片（头像、名称、能力标签），用户可一键安装或自定义 System Prompt 创建 Agent。这是 AgentHub Agent 管理页面的 UI 参考。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `store/chat/` | 流式消息状态管理 | Zustand + immer，messages 数组 + streaming 标志 |
| `components/Artifacts/` | 产物内联预览 | sandboxed iframe，检测代码块类型自动渲染 |
| `server/routers/chat/` | 多模型流式接口 | Vercel AI SDK，统一 SSE 出口 |
| `features/AgentSetting/` | Agent 配置管理 | System Prompt + 工具集 + 模型选择的配置 UI |
| `app/(main)/discover/` | Agent 市场 | Agent 卡片展示、一键安装、分类检索 |

### 详细说明

- **`store/chat/` 流式状态机**：每条消息对象包含 `{ id, role, content, streaming, agentId }`。SSE 事件处理器用 `set(state => { message.content += token })` 追加。多 Agent 并行时，不同 agentId 的消息独立维护，互不干扰。这是 AgentHub B 方案（并行交错气泡）最直接的参考。

- **Artifacts 渲染**：消息内容解析后，若含 `<artifact type="html">` 标签，Artifacts 组件创建 `<iframe sandbox="allow-scripts">` 并注入内容。sandboxed 属性防止 XSS。全屏预览通过 Portal 实现，不影响聊天流布局。

- **Vercel AI SDK 统一适配**：`server/routers/chat/` 里通过 `createOpenAI`、`createAnthropic` 等 provider 工厂函数构建模型实例，统一调用 `streamText()`，输出标准 SSE 格式。切换模型只需换 provider，业务逻辑不变。这是适配器层最轻量的实现方式。

## 4. 关键细节

- **Vercel AI SDK 的 SSE 格式**：`data: 0:"token"\n\n`（文本块）、`data: d:{finishReason}\n\n`（完成信号）。前端用 `useChat` hook 消费，自动处理追加和完成。如果不用 Vercel AI SDK，需要自己实现同等解析逻辑。
- **多 Agent 气泡排序**：Agent Groups 里每个 Agent 的回复按开始时间排序，先开口的气泡在上——这和 AgentHub 的 B 方案设计一致，直接验证了该排序策略的产品合理性。
- **IndexedDB 本地存储**：默认不需要后端数据库，消息历史存浏览器本地。对 AgentHub 来说不适用（需要多端同步），但这个设计让项目极易本地部署，值得借鉴其"零后端可用"的降级策略。
- **`lobe-ui` 自研组件库**：LobeChat 把聊天相关 UI 组件单独抽成 npm 包发布，可以直接 `npm install @lobehub/ui` 使用其气泡、输入框、Agent 卡片等组件，不需要从零写。
- **仓库已更名为 lobehub**：原 `lobe-chat` 仓库迁移至 `lobehub/lobe-chat`，定位从"聊天工具"扩展为"Agent 操作平台"，最新版本界面更偏工作台风格。参考 UI 时建议看历史版本截图（v1.x 系列最接近纯 IM 体验）。
