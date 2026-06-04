# 6.2 剩余需求汇总

## Diff模块

Diff应该理解为Agent使用Edit时修改的内容进行Diff（参考claude code本体），并且可能包括**审批**。至于需求中提到的应用Diff，我认为只是审批Edit。

### 需求实现：

现在前端已有DiffBlock组件，如果能后端SSE发送`tool_use: edit`或者`approve`中包含新旧代码，前端展示内联DiffBlock就够了，应用Diff只要审批通过就行

## Artifact

Artifact需要支持：
- [ ] 代码编辑
- [x] 网页预览
- [ ] 一键部署

### 需求分析
- 代码编辑：我认为代码编辑的场景主要适用于Agent Write/Edit实际创建的本地文件，因此需要**本地文件支持**，MD中代码块不支持编辑。本地文件同时也是为了支持后续的一键部署。
- 网页预览：如果Agent Write/Edit的是html文件可以直接预览（多文件，比如一个html一个css分开的问题待讨论）。
- 一键部署：待讨论

**现状**：前端artifact触发逻辑是，后端SSE发送`{block_start: {block: {type: artifact}}}`才会触发，只有artifact可以预览。无代码编辑功能。

### 需求实现

**代码编辑**

前端：
- 聊天右侧栏加入代码编辑，触发时机为SSE发送`tool_use: write/edit`，在block上加入edit/preview按钮，跳转代码编辑器/预览。
- 代码编辑/预览时向后端请求文件内容`GET ?filePath=xxxx`,`POST {filePath: "xxxx", content: "xxxx"}`

后端：
- 增加本地文件读/更新接口



## Approval


## 比赛提交产物

