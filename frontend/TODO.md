
## Misc
[P0]用户操作体验优化——这个得你自己摸，发现有问题的地方去改。就好比一个区块爆的超长挡住按钮这种。
[P1]setting里实现色系切换、系统语言切换。
[P1]SKILL那边的图标太简陋单一，和用户头像库一样，都需要做一份系统默认的可选项。
[P1]群聊内点击头像快捷@功能。这一点的优化除了点击头像，你可以通过自己玩一会单聊找出来不舒服的地方。
[P0]Skill library 和 agents library的显示现在太简陋，每个块简介显示不全导致多了以后看过去很难受。前端有很多风格化的修改方式。
[P0000000]用户个人界面和登录界面、总TOKEN用量界面，之前发的那个截图的风格特别好但不知道为什么只是发了截图而已，前端UI的风格化大改动应该是早就该做的内容。
- [ ] i18n（目前只有按钮）

## Chat

- [ ] @/upload file优化显示

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
