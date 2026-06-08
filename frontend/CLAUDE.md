# AgentHub Frontend

Vue 3 + TypeScript + Vite。多 Agent IM 界面，群聊里多个 AI Agent 并行回复，流式输出，支持产物预览/Diff/审批。

后端 FastAPI `:8000`，通信走 SSE（流式事件）+ REST（CRUD）。

## 快速开始

```bash
npm install
npm run dev          # http://localhost:5173，需后端在 :8000
npm run typecheck    # 只做类型检查，不编译
npm run build        # tsc + vite build
```

## 目录

```
src/
├── api/          # 所有网络请求。组件不直接 fetch，走这里
├── composables/  # 可复用逻辑
├── stores/       # Pinia
├── components/   # layout / chat / agents / common
├── views/        # 页面级组件
└── types/        # 类型定义，与后端 schema 对齐
```

---

## 维护规则

开发过程中如果发现需要全局遵守的新规则（比如"所有 X 必须 Y"、"禁止 Z"），在完成当前任务后把它追加到下方**开发规则**一节，格式和现有条目保持一致。

---

## 开发规则

### UI 尽可能组件化，减少重复代码

写新 UI 尽可能复用现有组件。超过两处复用的 UI 片段抽成组件，不要在多个地方写相同的模板代码。

### 改后端接口时同步改 `src/types/`

`src/types/` 里的类型是手动维护的，后端改了 response 结构前端不会报错，只会运行时出问题。  
改后端接口时一定同步改对应的类型定义，否则类型检查通过但线上静默出错。

### 组件不直接调 store action，走 composable

现有模式是 `View → composable → store`，不要在组件里直接 `import useChatStore` 然后调 action。  
composable 里包着副作用（比如 `useChat` 管着 SSE 连接），绕过它直接操作 store 会让这些副作用不触发。

### 所有 UI 文字必须走 i18n，不能硬编码

项目已接入 `vue-i18n@9`（legacy: false）。语言包在 `src/locales/zh-CN.ts` 和 `src/locales/en.ts`，按模块分组（`auth` / `chat` / `approval` / `workflow` 等）。

**新增任何 UI 文字时**：
1. 同时在两个语言包里加对应 key（中文 + 英文）
2. Vue SFC 里用 `const { t } = useI18n()`，模板写 `{{ t('key') }}`，属性写 `:placeholder="t('key')"`
3. 普通 `.ts` 文件（store / composable / api）不能用 `useI18n()`，改用 `import { i18n } from '@/i18n'` 然后 `i18n.global.t('key')`
4. 语言切换由 `stores/theme.ts` 的 `lang`（`'zh' | 'en'`）驱动，`App.vue` 里的 `watch` 负责同步给 vue-i18n；**不要**自己改 `i18n.global.locale`

**不需要翻译的内容**：代码注释、专有名词（AgentHub、Claude、Codex 等品牌名）、emoji、动态数据（来自后端的字符串）。

### 颜色用 CSS 变量，不硬编码

品牌色由 `stores/theme.ts` 在运行时写入 CSS 变量（6 套 accent，亮/暗各一份）。  
新写任何组件，要用品牌色就写 `var(--color-brand)`，**不要写 `#6366f1`**，不然换主题时不跟。

---

## 现有实现的背景（读代码时用）

理解这些能避免"看起来像 bug 其实是故意的"的误改。

**SSE 先连后 POST**（`useChat.ts`）：`sse.connect(id)` 在 `chatApi.send()` 前面不是笔误。后端 group 路径的 `POST /chat` 会阻塞到整个 orchestrator 循环跑完才返回，SSE 不回放，顺序反了就漏掉所有事件。

**停止生成乐观 UI**（`useChat.ts` `stopGeneration`）：点停止后先立即清 streaming 状态，后端 stop 响应到之前不等。后端最终推 `round_done` 兜底。

**PreviewCard iframe 的 sandbox**：`allow-scripts` 故意不加 `allow-same-origin`，防止 Agent 产出的 HTML 访问父页面 DOM。不是漏写，不要"修复"它。

**http.ts 401 不走 refresh**：收到 401 直接清 token 跳登录页。`/auth/login`、`/auth/refresh`、`/auth/register` 在 `SKIP_AUTH_PATHS` 豁免列表里。

**deploy_app 结果在 SSE 里**：部署信息不走独立接口，从 `block_stop` 事件的 `final_fields`（`tool_name === 'deploy_app'`）里解析，存到 `deploymentsStore`。后端改 deploy_app 输出结构时这里要同步。

---

## 状态边界

| 放哪 | 什么状态 |
|---|---|
| 组件内 `ref` | 弹窗开关、单个表单的 loading |
| `ui.ts` store | 跨组件共享的 UI 状态：右栏展开、`diffCardStates` |
| 对应 store | 服务端数据：agents、conversations、messages |
| `chat.ts` store | 当前轮流式状态：`streamingAgents`、`blocks` |

不要把临时 UI 状态放进 store，也不要在 store 里写组件逻辑。

---

## 当前未完成（不要重复实现）

详见 [TODO.md](TODO.md)。
