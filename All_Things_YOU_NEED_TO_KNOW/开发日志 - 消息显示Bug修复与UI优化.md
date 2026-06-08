# AgentHub 开发日志 — 消息显示 Bug 修复 & UI 优化

**最后更新：** 2026-06-08  
**分支：** `master`  
**涉及文件：**
- `backend/api/v1/chat.py`
- `frontend/src/composables/useSSE.ts`
- `frontend/src/views/LoginView.vue`
- `frontend/src/components/layout/NavRail.vue`
- `frontend/src/components/layout/ChatPanel.vue`
- `frontend/vite.config.ts`
- `backend/services/thread_service.py`
- `backend/main.py`
- `run.py`
- `backend/skills/meme_library.json`

---

## 一、核心 Bug：消息发送后卡住，F5 才恢复

### 现象

用户发送消息后，Agent 回复不出现；刷新页面（F5）后，消息正常显示。

### 根因分析

SSE 连接生命周期与消息发送时序存在竞态条件，链路如下：

1. `conversations.select()` 进入会话时调用 `connect(id, afterMessageId)`，带 `after_message_id` 参数连接 SSE
2. 后端 SSE 端点（`chat.py`）检查有无活跃 Thread 可回放；正常情况下上一轮已结束，无活跃 Thread
3. **Bug 所在**：后端有如下逻辑，检测到"无回放内容"就立刻 `return`，关闭 SSE：
   ```python
   if after_message_id is not None and not has_replay:
       return  # 直接结束生成器，断开 SSE 连接
   ```
4. SSE 关闭 → 前端 `onClose` 触发 → `controllers.delete(convId)`，连接记录清除
5. 用户发消息：`sendMessage()` 调 `sse.connect(id)`，发起新 SSE GET 请求，同时立刻发 POST
6. 新 SSE GET 请求尚在网络传输中，后端还未调 `stream_service.open()` 注册 session
7. POST 先到达后端，后端 `broadcast()` 推事件时没有任何 SSE subscriber → 事件全部丢失
8. 前端永远等不到 agent 回复 → 消息"卡住"

### 修复方案

**两处改动，合计删除 ~6 行：**

#### 1. `backend/api/v1/chat.py` — 删除过早返回

删除"无回放内容就关闭 SSE"的 early-return 块。SSE 始终走到 `stream_service.consume(session)` 等待新事件：

```python
# 删除以下 6 行（原 lines 197–203）：
# if after_message_id is not None and not has_replay:
#     logger.info(
#         "No active threads or replay events for conv=%s, close SSE",
#         conversation_id,
#     )
#     return
```

修复后：`select()` 建立的 SSE 连接保持存活，等待新一轮事件到来。

#### 2. `frontend/src/composables/useSSE.ts` — 删除 `round_done` 里的主动断开

```typescript
// 删除以下 2 行（round_done case 末尾）：
// // 关闭连接，让下一轮发消息时重新建立 SSE
// disconnect(convId)
```

修复后：`round_done` 只清理流式状态，不断开 SSE。SSE 等 `queue_drained`（后端发、前端断）或后端主动关闭时再清理，保证 `sendMessage()` 调用时连接已就绪。

### 修复后的连接生命周期

```
select(id)
  └─ connect(id, afterMessageId)  ← SSE 建立，backend 进入 consume() 等待
       │
       ├─ sendMessage()
       │    └─ connect(id)  ← 命中 early-return guard，复用已有连接
       │    └─ chatApi.send()  ← POST 到达时 SSE 已注册，事件正常推送
       │
       ├─ round_done  ← clearRound()，流式状态清理，SSE 继续存活
       │
       └─ queue_drained  ← disconnect(id)，SSE 关闭，controller 清除
```

---

## 二、表情包系统修复

### 问题

1. Vite CSS 报错 `ENOENT: not_stonks.svg`：旧 SVG 表情包文件已删除，Vite 缓存残留引用
2. 新表情包（JPG）放入 `backend/memes/`，但前端图片不显示，只显示文字描述

### 修复

**`backend/skills/meme_library.json`** — 全量替换为 15 个新 JPG 表情包：

| ID | 文件名 |
|----|--------|
| `yudi_happy` / `yudi_coy` / `yudi_angry` / `yudi_cry_laugh` / `yudi_shocked` | 鱼缇系列 |
| `ximei_serious` / `ximei_speechless` | 西梅系列 |
| `ganna` | ganna |
| `nianjie_happy` / `nianjie_stifle` | 年姐系列 |
| `nianbao_affirm` | 年宝 |
| `good_morning` | 早安 |
| `wangge_angry` / `wangge_shocked` | 王哥系列 |
| `wang_seen` | 已读 |

**`frontend/vite.config.ts`** — 新增 `/memes` 代理，转发到后端静态文件服务：
```typescript
'/memes': {
  target: 'http://localhost:18888',
  changeOrigin: true,
},
```

**`backend/services/thread_service.py`** — 修复系统提示示例表情包 ID（`pepe_laugh` → `nianjie_stifle`）

**Vite 缓存清理：** `rm -rf frontend/node_modules/.vite`

---

## 三、UV_HANDLE_CLOSING Windows 断言错误

### 现象

Windows 11 + Python 3.13 环境下，后端关闭时反复出现 `UV_HANDLE_CLOSING` 断言失败。

### 根因

`backend/main.py` 中存在重复的 `asyncio.WindowsProactorEventLoopPolicy` 初始化，与 `run.py` 中的同类设置冲突，导致 uvicorn shutdown 时 libuv 状态异常。

### 修复

- `backend/main.py`：删除重复的 `asyncio.set_event_loop_policy()` 调用
- `run.py`：`uvicorn.run()` 增加 `loop="asyncio"` 参数，统一事件循环策略

---

## 四、Support 页面 UI 升级

两处 Support 弹窗（LoginView 登录页 + NavRail Hub 主界面）同步更新：

### 贡献者名单调整

移除低贡献度成员（冯瑜轩、刘盘），保留三位核心贡献者：

| 成员 | Alias | 角色 | 占比 |
|------|-------|------|------|
| 沫路 | Adam Zhang | Core Architect | 50% |
| 玛叔叔 | Wang / Uzemiu | Frontend Lead | 28% |
| 令姐姐 | Wu Lvsheng / Musuyin | Adapter Layer | 20% |

### SVG 甜甜圈图表

LoginView Support 弹窗新增内联 SVG 甜甜圈图，可视化三人贡献比例，配色与品牌色系一致（indigo / cyan / emerald）。弹窗宽度从 420px 扩展至 460px。

### 贡献者头像卡片

三人均配置真实头像路径（`/contributors/adam.png`、`/contributors/uzemiu.png`、`/contributors/musuyin.png`），Support 弹窗展示头像 + 姓名 + 角色 + 占比进度条。

---

## 五、Git Merge 冲突处理（跨分支合并）

合并 i18n 分支至 master，共解决 10 处冲突。策略：**保留 HEAD（完整品牌页）结构，从 other 分支引入 i18n 字符串调用**。

涉及文件：
- `frontend/src/components/layout/ChatPanel.vue` — 1 处（`群聊设置` → `t('conversationSettings.settings')`）
- `frontend/src/views/LoginView.vue` — 8 处，新增 `const { t } = useI18n()`，修复 `.orbit-hub` CSS 缺失闭合 `}`
- `frontend/src/components/skills/AgentFormPanel.vue`、`SkillFormPanel.vue`、`SkillsPanel.vue`、`SkillForm.vue` — 各 1 处

---

## 六、已知待解决

| 问题 | 状态 |
|------|------|
| UV_HANDLE_CLOSING 在某些场景仍偶发 | 部分修复，Python 3.13 + ProactorEventLoop 深层 timing 问题 |
| Moonshot `kimi-k2.5` API 限速（RPM 429，60s 重试）| 账号配额限制，非代码问题 |
| GitHub Pages 私有仓库不支持（免费计划）| 仓库权限限制 |
