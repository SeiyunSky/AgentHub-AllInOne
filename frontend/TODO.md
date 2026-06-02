
## Chat

- [ ] 会话列表：`include_archived` 参数支持查看已归档会话
  - 方案  B：Recent 加"加载更多"Pinned 全量拿（一般很少Recent 第一屏 limit=20，底部加"Load more"按钮，offset 递增. Archived 同方案 A，展开时懒加载. 缺点：需要后端支持按 pinned/archived 过滤分类请求
- [ ] conversation 排序/PIN
- [ ] 聊天总体宽度限制，居中展示
- [ ] 丰富聊天展示信息：头像、参与的 agent 列表，更像 IM
- [ ] Approval 流程
  - [ ] approval 块始终 pending，真实审批需要 WebSocket 或轮询接收 block_stop 更新
  - [ ] 创建 approvalsApi，审批按钮接入 HTTP 调用（当前只改本地状态）

## Agents

- [ ] **AgentForm 缺失字段控件**
  - `avatar`：无上传控件
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
