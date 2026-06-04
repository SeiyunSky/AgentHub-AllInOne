
## Misc

- [ ] i18n（目前只有按钮）

## Chat

- [ ] @/upload file优化显示
- [ ] feedback ui位置
- [ ] Agent Group名字未覆盖

## Skill

- [ ] Title实际是文件名，前端本地检测重复+修改位置

## Agents

- [ ] **AgentForm 缺失字段控件**
  - `avatar`：无上传控件
- [ ] AgentBuilderDialog 对话式构建流程（`agentsApi.build()` + `agentsApi.buildConfirm()`）
  - 当前 Builder Assistant 面板仅返回 mock 数据，未调 API
- [ ] AgentContactList 展示优化（is_active 状态等）

## 增强功能

- [ ] 搜索 Conversation（搜 agent / message / title）
- [ ] Agent 详情页显示相关对话
- [ ] Conversation list 增加时间戳显示
- [ ] Message reply
  - [ ] 添加 API 参数（`parent_id`）
  - [ ] 展示 replied message 引用
