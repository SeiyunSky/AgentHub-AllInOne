# 前端代码审查报告

**分支:** `dev/wch` vs `master`
**日期:** 2026-05-31
**范围:** ~93 文件变更, +7024 / -768 行
**力度:** High (recall-biased, 7 angles × 6 candidates → 1-vote verify)

---

## ✅ CONFIRMED (高置信 Bug)

### 1. SSE 泄漏 — POST 失败后连接未关闭
**文件:** `src/composables/useChat.ts:30`

`sse.connect(id)` 在 POST **之前**调用。如果 POST 抛异常（网络错误 / 500），`sendMessage` 没有 catch 块来调用 `sse.disconnect()`，SSE 控制器会泄漏。

> **复现:** 用户在服务端宕机时发消息 → SSE 已连接 → POST 抛异常 → 无 `disconnect()` → 聊天 UI 永远停在 streaming 状态。

---

### 2. AgentsPanel 旁路 Store 直接调 API，导致引用过期
**文件:** `src/components/layout/AgentsPanel.vue:168`

```ts
const agents = agentsStore.agents  // ← 取的是当前 .value 的数组引用
```

当 Store 稍后通过 `agentsStore.agents = data.map(...)` 替换整个数组时，本地 `agents` 仍指向旧的空数组。`filteredAgents` computed 和空状态判断都用的是过期数据。

> **复现:** 组件挂载 → `agents` 为 `[]` → API 返回数据 → Store 替换数组 → 本地 `agents` 仍为旧 `[]` → `filteredAgents` 返回空 → 显示空状态而非卡片列表。

---

### 3. "Delete" 调 deactivate 后 splice — 语义不匹配，刷新后 Agent 重现
**文件:** `src/components/layout/AgentsPanel.vue:244-252`

`confirmDelete` 调用 `agentsApi.deactivate(agent.id)`（软删除），但紧接着从 Store 里 splice 掉该 Agent。下次刷新时 `loadAgents()` 会拉取所有 Agent（含已停用的），已删除的 Agent 会重新出现。

> **复现:** 用户删除 Agent → 从列表消失 → 刷新页面 → Agent 重新出现（is_active=false），用户困惑。

---

### 4. 死代码 Node.js import + 生产 console.log
**文件:** `src/components/layout/AgentFormPanel.vue:74` & `:184`

- `import { log } from 'console'` — Node.js 内置模块，浏览器环境无法使用，且 `log` 从未被调用。
- `console.log(localDraft)` — 每次保存时将完整 Agent Draft（含 systemPrompt、capabilities）输出到浏览器控制台。

> **影响:** 敏感 Agent 配置泄露到生产环境控制台；死 import 可能导致构建警告。

---

### 5. 诊断 console.log 留在生产代码 — 每个 SSE 事件触发一次
**文件:** `src/composables/useSSE.ts:10`

```ts
// 临时诊断:打印每个 SSE 事件,确认前端实际收到了什么
console.log('[SSE]', convId, event)
```

注释已标明是临时诊断，但未移除。

> **影响:** 高频聊天场景下每秒数百条控制台输出，拖慢浏览器性能并泄露会话事件数据。

---

## ⚠️ PLAUSIBLE (可能真实的问题)

### 6. onMounted + watch(agentId) 重复请求同一 Agent
**文件:** `src/components/layout/AgentFormPanel.vue:101-164`

组件挂载时 `onMounted` 获取 Agent 数据，随后 `watch(agentId, ...)` 也会因相同的 agentId 立即触发，导致双重 HTTP 请求。创建完成后 `router.replace` 又触发 watcher 再次重新拉取。

> **影响:** 冗余网络请求 + 可见的 loading 闪烁。

---

### 7. clearRound 不清理 pendingApprovals — 潜在残留状态
**文件:** `src/stores/chat.ts:265-269`

`clearRound` 删除了 `streamingConvIds` 但有意跳过 `pendingApprovals`。如果多 Agent 轮次结束时有一个 pending approval 且用户未操作，该 approval 将一直残留在状态中。

> **影响:** 审批提示可能跨轮次残留显示。

---

### 8. 浅 spread 未深合并 AI Builder 传入的 capabilities
**文件:** `src/components/layout/AgentFormPanel.vue:129`

```ts
localDraft.value = { ...defaultDraft, ...agentsStore.initialDraft }
```

如果 `initialDraft.capabilities` 是部分对象（如 `{ supportsCode: true }`），spread 会整体替换 capabilities 而非逐字段合并，缺失的 key 变为 `undefined` 而非 `false`。

> **影响:** `!undefined === true` 虽然可以工作，但产生隐式空洞，增加后续维护风险。

---

### 9. AgentContactList 中 agentAvatarClass 返回空字符串
**文件:** `src/components/sidebar/AgentContactList.vue:70-76`

```ts
function agentAvatarClass(type: string) {
  const map: Record<string, string> = {
    claude: '',
    codex: '',
    opencode: '',
  }
  return map[type] || 'bg-surface-container border-outline-variant'
}
```

claude/codex/opencode 的映射返回空字符串，头像 div 没有背景/边框样式。与 AgentsPanel 中正确的渐变样式不一致。

> **影响:** 侧边栏中 Claude/Codex/OpenCode 的 Agent 头像无样式，看起来像是未渲染。

---

## 🧹 CLEANUP (非崩溃，建议修复)

### 10. rawToAgent 与 Store 中 mapAgentResponse 重复 (×5)
**文件:** `src/components/layout/AgentsPanel.vue:202`

snake→camelCase 的映射逻辑存在于 5 个独立位置：
- `stores/agents.ts` — `mapAgentResponse`
- `AgentsPanel.vue` — `rawToAgent`
- `AgentFormPanel.vue` — `onMounted` 内联 ×1 + `watch` 内联 ×1
- Skills 领域也有类似重复 (`SkillFormPanel.toSkill` vs `stores/skills.mapSkillResponse`)

> **成本:** 新增 API 字段时需同步更新 5+ 处，遗漏一处即导致该字段在某些路径下为 undefined。

---

## 其他值得关注的问题

| # | 类型 | 文件 | 说明 |
|---|------|------|------|
| 11 | 效率 | `AgentsPanel.vue:190` | `onMounted` 直接调 `agentsApi.list()` 绕过 `agentsStore.loadAgents()` 的去重逻辑，与侧边栏 `AgentContactList` 可能触发双重请求 |
| 12 | 效率 | `AgentContactList.vue:83` / `SkillsList.vue:61` | `onMounted` 无条件调用 store load，每次切 Tab 都重新 fetch |
| 13 | 复用 | `AgentsPanel` / `SkillsPanel` | Loading skeleton、filter bar、empty state、confirmDelete 模式几乎完全重复 |
| 14 | 复用 | `AgentContactList` / `AgentsPanel` | `hideImg` 函数、avatar 渲染模式重复 |
| 15 | 简化 | `AgentForm.vue:210` | `import type { Component } from 'vue'` 可以用 `import type { Component } from 'vue'` 内联推断，无需显式导入 |
| 16 | 简化 | `AgentForm.vue:234` | `selectedSkills` computed 仅用于 `.length` 检查，可直接用 `activeSkillDefs.length` |
| 17 | 简化 | `AgentForm.vue:255` | `PlatformOption.iconClass` 字段已填充但模板中从未使用 |
| 18 | 架构 | `useSidebarTab.ts` / `NavRail.vue` | 路由→Tab 映射在 composable 和 NavRail 中各写一份 if/else，新增路由需同步两处 |
| 19 | 架构 | `SkillsPanel.vue:162` | Filter 选项硬编码中文字符串（代码/安全/领域知识/通用），与 AgentsPanel 的英文标签不一致 |
