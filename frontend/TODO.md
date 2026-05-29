## Bug / Critical

- [ ] **AgentCreate camelCase/snake_case 不匹配**
  - `AgentBuilderView.vue` 直接传 store `currentDraft`（camelCase: `systemPrompt`, `supportsCode`…）给 `agentsApi.create()`，后端 Pydantic 期望 snake_case
  - 影响字段：`system_prompt`、`capabilities` 下所有子字段（`supports_code`/`supports_diff`/`supports_approval`/`supports_image`）
  - 方案 A：http.ts 加请求拦截器自动转 snake_case；方案 B：AgentBuilderView 提交前做字段映射

## Chat

- [x] 会话创建 dialog：title 输入 + agent 选择器
- [ ] **ConversationCreate.mode 硬编码 `'single'`**
  - NewChatDialog 中 `createChat` 写死 `'single'`，缺少 single/group 切换 UI
- [x] 停止生成按钮：chatApi.stop() 已接通
- [ ] 消息分页：useInfiniteScroll + `conversations/:id/messages` 的 limit/before 参数
- [ ] CodeRangeSelector：`selected_range` 的 UI 组件（类型和 composable 参数已有，无组件传入）
- [ ] 会话列表：`include_archived` 参数支持查看已归档会话
- [ ] conversation 排序/PIN
- [ ] 聊天总体宽度限制，居中展示
- [ ] 丰富聊天展示信息：头像、参与的 agent 列表，更像 IM
- [ ] Approval 流程
  - [ ] approval 块始终 pending，真实审批需要 WebSocket 或轮询接收 block_stop 更新
  - [ ] 创建 approvalsApi，审批按钮接入 HTTP 调用（当前只改本地状态）

## Agents

- [ ] **编辑模式 Save 按钮 → agentsApi.update()**
  - 当前编辑模式加载了 agent 但隐藏保存按钮，保存仍走 create
- [ ] **AgentForm 缺失字段控件**
  - `avatar`：无上传控件
  - `is_public`：store 默认 `false`，无可见性开关
  - `skill_ids`：`AgentDraft` 类型中无此字段，无 Skill 选择器
  - `is_active`：只读展示，无启停开关
- [ ] AgentBuilderDialog 对话式构建流程（`agentsApi.build()` + `agentsApi.buildConfirm()`）
  - 当前 Builder Assistant 面板仅返回 mock 数据，未调 API
- [ ] AgentContactList 展示优化（is_active 状态等）

## Skills

- [ ] "New Skill" 按钮 → 创建表单/弹窗 → `skillsApi.create()`
- [ ] Skill 详情/编辑页面 → `skillsApi.get()` / `skillsApi.update()`
- [ ] `skillsApi` create/update body 补充 TypeScript 类型定义（当前为 `any`）

## Stub 模块（后端接口未实现）

- [ ] Auth — 登录接口接入
- [ ] Artifacts — one-click diff apply / deploy
- [ ] WebSocket — 状态/审批/部署进度

## 增强功能

- [ ] 搜索 Conversation（搜 agent / message / title）
- [ ] Agent 详情页显示相关对话
- [ ] Conversation list 增加时间戳显示
- [ ] Message reply
  - [ ] 添加 API 参数（`parent_id`）
  - [ ] 展示 replied message 引用
