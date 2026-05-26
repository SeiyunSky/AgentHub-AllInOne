"""
PromptService —— Prompt 模板读取 / 变量渲染

封装 backend/prompts/*.md 模板文件的加载、frontmatter 解析、{{var}} 变量渲染。
当前唯一消费方是 chat_service._local_edit_flow(对话式局部修改流程),
但局部修改链路需要前端发 selected_range + API 接收(Step 11),
两端都没接通,所以本服务暂时没有真实调用方。

[TODO/H3]: 等以下任一条件就绪后实装:
1. Step 11 API 层接通 selected_range 入参 → 局部修改流程能从 HTTP 进来
2. 主 Agent 工具需要按模板生成 prompt(目前没这个需求)

实装时参考 backend/prompts/local_edit.md 的 frontmatter 结构,
用 backend/core/frontmatter.py(已实装)解析 metadata + 正文,
然后用 str.replace 或 jinja2 简单替换 {{var}} 占位符。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""
