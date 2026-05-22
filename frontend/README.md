# AgentHub Frontend

Vue 3 + TypeScript + Vite 实现的 AgentHub 前端，对接 FastAPI 后端（默认 `:8000`）。

## 技术栈

| 库 | 版本 | 用途 |
|---|---|---|
| Vue 3 | ^3.5 | 渲染框架（Composition API） |
| Vite | ^6.0 | 构建工具 / 开发服务器 |
| Pinia | ^2.2 | 状态管理 |
| Vue Router | ^4.5 | 客户端路由 |
| Axios | ^1.7 | HTTP 客户端 |
| markdown-it | ^14.1 | Markdown 渲染 |
| TypeScript | ^5.7 | 类型系统 |

## 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器（http://localhost:5173）
npm run dev

# 类型检查
npm run typecheck

# 生产构建（先类型检查再 build）
npm run build

# 预览生产包
npm run preview
```

> 开发时需确保后端已在 `:8000` 运行，Vite dev server 会自动将 `/api` 和 `/ws` 请求代理过去。

## 目录结构

```
src/
├── api/            # Axios 请求封装（http.ts 为基础实例）
│   ├── http.ts     # Axios 实例 + JWT 拦截器
│   ├── auth.ts
│   ├── agents.ts
│   ├── chat.ts     # SSE 流式接口
│   ├── conversations.ts
│   ├── messages.ts
│   ├── artifacts.ts
│   ├── skills.ts
│   ├── sse.ts      # SSE 工具
│   └── ws.ts       # WebSocket 工具
├── components/
│   ├── agents/     # Agent 构建 / 配置组件
│   ├── chat/       # 消息列表、输入框、Artifact 卡片
│   │   ├── bubbles/    # UserBubble / AgentBubble
│   │   └── artifacts/  # ApprovalCard / DiffCard / PreviewCard
│   ├── common/     # CodeBlock / MarkdownRenderer / 通用弹窗
│   ├── layout/     # AppLayout / LeftPanel / ChatPanel / RightPanel
│   └── sidebar/    # 会话列表 / Agent 联系人列表
├── composables/    # 可复用逻辑钩子
│   ├── useChat.ts
│   ├── useWebSocket.ts
│   ├── useSSE.ts
│   ├── useAgentBuilder.ts
│   ├── useApproval.ts
│   ├── useArtifactPreview.ts
│   ├── useDiff.ts
│   └── useInfiniteScroll.ts
├── router/
│   └── index.ts    # 路由表 + JWT 导航守卫
├── stores/         # Pinia stores
│   ├── auth.ts     # JWT token / 用户信息
│   ├── chat.ts
│   ├── agents.ts
│   ├── conversations.ts
│   └── ui.ts
├── types/          # 全局 TypeScript 类型定义
│   ├── api.ts
│   ├── agent.ts
│   ├── conversation.ts
│   ├── message.ts
│   └── artifact.ts
├── views/
│   ├── LoginView.vue
│   ├── ChatView.vue    # /chat/:conversationId
│   └── AgentsView.vue  # /agents
├── App.vue
└── main.ts
```

## 路由

| 路径 | 组件 | 说明 |
|---|---|---|
| `/login` | LoginView | 登录页，未登录时自动跳转 |
| `/` | — | 重定向至 `/chat` |
| `/chat` | ChatView | 会话主界面 |
| `/chat/:conversationId` | ChatView | 指定会话 |
| `/agents` | AgentsView | Agent 管理 |

所有非 `/login` 路由均需 JWT 登录态，由导航守卫统一拦截。

## 环境变量

复制 `.env.example` 为 `.env.development`（本地开发）或 `.env.production`（生产）：

```bash
cp .env.example .env.development
```

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | REST API 基础地址 |
| `VITE_WS_BASE_URL` | `ws://localhost:8000` | WebSocket 基础地址 |

## 代理配置

开发服务器（`vite.config.ts`）已配置代理，无需改动前端代码即可切换后端地址：

```
/api/** → http://localhost:8000
/ws/**  → ws://localhost:8000
```

生产部署时由 Nginx 或反向代理接管，前端只需正确设置环境变量。
