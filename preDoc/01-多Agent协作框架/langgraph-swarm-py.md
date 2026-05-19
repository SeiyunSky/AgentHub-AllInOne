# langgraph-swarm-py

## 1. 项目基本信息

- **项目名**：LangGraph Multi-Agent Swarm（langchain-ai/langgraph-swarm-py）
- **GitHub**：https://github.com/langchain-ai/langgraph-swarm-py
- **Star 数 / 主要语言**：1.5k / Python
- **简介**（≤200 字）：

LangChain 团队出的轻量级多 Agent swarm 框架，基于 LangGraph 构建。Agent 之间通过 handoff tool 动态移交主控权（Agent A 调用 `transfer_to_B` 工具就把对话切给 Agent B）。系统通过 `active_agent` 状态字段记住当前主控 Agent，下一轮交互自动从该 Agent 继续。开箱支持 streaming、短期/长期 memory、human-in-the-loop。整个核心包只有 `swarm.py` + `handoff.py` 两个文件，约 14 KB Python，是 swarm 模式最纯粹的参考实现。

- **核心创新（一句话）**：用 LangGraph 的状态图把 swarm 模式实现到极简——Agent 平级共存，handoff tool 切换主控权，`active_agent` 字段记忆当前 Agent，14 KB Python 跑通完整模式。

## 2. 项目架构概览

### 技术栈

- **语言**：Python（3.10+ 推测）
- **核心依赖**：LangGraph（langchain-ai 官方多 Agent 框架）、LangChain（Agent 与 Tool 抽象）
- **包管理**：uv（生成 `uv.lock` 250 KB）
- **License**：MIT

### 目录结构

```
langgraph-swarm-py/
├── langgraph_swarm/                ← 核心包（仅 4 个文件）
│   ├── __init__.py     (251 B)     ← 包导出
│   ├── swarm.py     (9.8 KB)       ← swarm 主体（create_swarm + active_agent_router）
│   ├── handoff.py   (3.9 KB)       ← handoff tool 实现
│   └── py.typed                    ← PEP 561 类型标记
├── examples/                       ← 示例代码
├── tests/                          ← 测试
├── static/img/swarm.png            ← 架构图
├── pyproject.toml      (2 KB)
├── uv.lock           (251 KB)      ← 依赖锁文件
├── Makefile          (1.5 KB)
└── README.md          (10 KB)      ← 详细教程文档
```

### 核心机制

**一句话**：所有 Agent 平级共存于一个 LangGraph 状态图里，每个 Agent 都有 handoff tool；当某个 Agent 调用 handoff tool，状态图把控制权转给目标 Agent，`active_agent` 字段记忆当前谁在话筒上。

`create_swarm([alice, bob], default_active_agent="Alice")` 把多个 Agent 组装成一个 LangGraph `StateGraph`：每个 Agent 是图里的一个节点，节点之间的边由 handoff 决定。状态包含 `messages`（所有 Agent 共享的对话历史）和 `active_agent`（当前主控 Agent 名字）。`add_active_agent_router` 在图入口加一个路由节点，根据 `active_agent` 字段决定本轮跑哪个 Agent。Agent 内部用 LangGraph prebuilt `create_agent` 构造（标准 ReAct 模式：LLM + tools + tool node）。`create_handoff_tool(agent_name="Bob")` 生成一个特殊工具——LLM 调用它时返回 `Command(goto="Bob", update={"active_agent": "Bob", ...})`，告诉 LangGraph 跳转到 Bob 节点并更新 active_agent。下一轮用户消息进来时，路由器读 `active_agent="Bob"`，直接把控制权交给 Bob。配合 checkpointer（短期记忆）和 store（长期记忆），swarm 状态跨多轮对话持久化。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **`active_agent` 状态字段 + 路由器模式**：所有 Agent 平级，但有一个全局字段记忆"当前谁在话筒上"。每轮用户消息进来先看这个字段决定走哪个 Agent。这是 swarm 模式的最简实现，避免了"指定下一个 Agent"的复杂协议。
2. **handoff tool 作为 Agent 切换机制**：把"切换主控 Agent"这个动作设计成一个工具调用。LLM 自己决定要不要调用、何时调用。`Command(goto=..., update=...)` 一行同时完成"跳转节点"和"更新状态"两件事。
3. **共享 messages + 可选独立 messages 双模式**：默认所有 Agent 共享一个 `messages` 列表（全部对话历史可见）；可选模式让每个 Agent 有自己独立的 messages key（如 `alice_messages`），保护内部历史不外泄。同一框架支持两种隐私模型。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `swarm.py` `create_swarm()` | 把多个 Agent 组装成 swarm | 构造 LangGraph StateGraph，每个 Agent 是节点 |
| `swarm.py` `add_active_agent_router()` | swarm 入口路由 | 读 `active_agent` 状态字段决定本轮跑哪个 Agent |
| `swarm.py` `SwarmState` | swarm 共享状态 schema | TypedDict 含 `messages` + `active_agent` |
| `handoff.py` `create_handoff_tool()` | Agent 切换主控权 | 生成返回 `Command(goto=..., update=...)` 的工具 |
| `Command(goto=agent_name, update={"active_agent": ...})` | 节点跳转 + 状态更新 | LangGraph 的 Command 模式，原子更新 |
| `Command.PARENT` | 子图向父图发命令 | 让 Agent 子图能改 swarm 父图状态 |
| `InjectedState` + `InjectedToolCallId` | 工具读取上下文 | 工具参数注入当前状态和 tool_call_id |
| 自定义 handoff tool 添加 `task_description` 参数 | 切换时传任务描述 | 在 handoff 工具的参数里让 LLM 填写任务描述 |
| 自定义 Agent 用独立 messages key | 隐藏 Agent 内部历史 | 用 `alice_messages` 等独立 key + wrapper 函数转换状态 |
| Checkpointer + Store | 短期 + 长期记忆 | LangGraph 标准 BaseCheckpointSaver / BaseStore，编译时注入 |

### 详细说明

- **`active_agent` 路由模式**：swarm 状态里有一个 `active_agent: str` 字段，每轮对话开始时路由器读这个字段决定走哪个 Agent。Agent A 调用 `transfer_to_B` 工具时，工具返回的 Command 同时更新 `active_agent="B"` 和 `goto="B"`。下一轮用户再发消息，路由器看到 `active_agent="B"`，直接跳到 B。这是 swarm 模式记忆机制的核心——不是 A 主动告诉 B"接下去你来"，而是 swarm 框架统一记忆"当前谁负责"。

- **handoff tool 设计**：`create_handoff_tool(agent_name="Bob", description="Transfer to Bob")` 生成一个工具，LLM 调用时执行如下逻辑：
  ```python
  return Command(
      goto="Bob",
      graph=Command.PARENT,
      update={
          "messages": messages + [tool_message],
          "active_agent": "Bob",
      },
  )
  ```
  这是 LangGraph 的 `Command` 模式——工具不直接返回内容，而是返回"对状态图的指令"。`graph=Command.PARENT` 让子 Agent 图的工具能改父 swarm 图的状态。

- **可定制 handoff tool 加任务描述**：默认 handoff tool 不传任何额外信息，新 Agent 看到的就是完整 messages 历史。可以扩展工具加一个 `task_description` 参数让 LLM 填，handoff 时把任务描述存到 swarm 状态里。这是 swarm 模式下"显式任务交接"的实现。

- **共享 vs 独立 messages**：默认所有 Agent 共享 `messages` key——Alice 和 Bob 都看到所有历史。这种模式信息透明但暴露内部对话。可选模式让每个 Agent 用独立 key（如 `alice_messages`），通过 wrapper 函数在父图和子 Agent 状态间转换：
  ```python
  def call_alice(state: SwarmState):
      response = alice.invoke({"alice_messages": state["messages"]})
      return {"messages": response["alice_messages"]}
  ```
  父图传完整 messages 给 Alice 当 alice_messages，Alice 跑完后把结果合并回父图 messages。

- **Checkpointer / Store 双层记忆**：
  - **Checkpointer（短期）**：保存 swarm 在每个时刻的完整状态（messages + active_agent），跨多轮对话保持上下文。
  - **Store（长期）**：跨 thread 持久化（不同对话之间共享）。例如 Alice 学到的知识可以在新对话里继续用。
  
  README 强调"如果不加 checkpointer，swarm 会忘记上次哪个 Agent 在主控"——这是 swarm 模式工程实践的关键。

- **基于 LangGraph 的 Command 模式**：LangGraph 的核心抽象之一是 `Command`——工具或节点返回 Command 对象告诉框架"下一步去哪、状态怎么更新"。swarm 完全建立在 Command 之上：handoff tool 返回 `Command(goto=...)` 实现节点跳转。这是声明式状态机的优雅模式。

- **极简代码量**：核心包就 2 个文件、~14 KB Python。这种"小而精"的实现非常适合阅读学习——一两个小时能读完整个 swarm 模式的代码。

- **prebuilt `create_agent` 集成**：每个 Agent 用 LangGraph 的 `create_agent` prebuilt 函数构造（标准 ReAct 循环：LLM 调用 → tool_use → tool 执行 → 回写 → 循环）。swarm 不重新发明 Agent Loop，复用 LangGraph 的 prebuilt。

- **InjectedState + InjectedToolCallId**：LangChain 的工具参数注入机制。工具签名里用 `Annotated[dict, InjectedState]` 标记的参数会自动被注入当前 swarm 状态。这种"无侵入注入"让工具能读全局状态而不用通过 LLM 显式传参。

## 4. 关键细节

- **`__init__.py` 251 字节**：包导出极简，只暴露 `create_swarm`、`add_active_agent_router`、`create_handoff_tool`、`SwarmState` 几个 API。最小公开接口。
- **`swarm.py` 9.8 KB**：包含 `SwarmState` TypedDict、`create_swarm` 主函数、`add_active_agent_router` 路由器实现。这是 swarm 模式实现的全部核心。
- **`handoff.py` 3.9 KB**：仅实现 `create_handoff_tool` 和它的内部逻辑。整个 handoff 机制 4 KB 完成。
- **`py.typed`（空文件）**：PEP 561 类型标记，告诉类型检查器（mypy/pyright）这个包带类型注解。这是现代 Python 库的工程规范。
- **`uv.lock` 251 KB**：用 uv 锁定依赖，反映项目跟随 Python 现代工具链。
- **`examples/` 目录**：包含可运行示例。README 里的 quickstart 代码就是基于 examples 简化。
- **README 10 KB 的详细教程**：除快速开始外，详细讲了 memory 集成、handoff tool 定制、Agent 实现定制三个进阶话题。每个话题给完整代码片段。这是开源项目里少见的"教程级 README"。
- **`Makefile`**：包含测试、lint、发布命令。Python 项目里用 Makefile 不常见，反映 LangChain 团队的工程习惯。
- **基于 LangGraph 而非自己写 Agent Loop**：与 OMC、ruflo 这类自己造轮子的项目不同，langgraph-swarm 完全建立在 LangGraph 之上。优点：①站在巨人肩膀上；②兼容 LangSmith 等 LangChain 生态工具；③更新由 LangGraph 维护。缺点：①受 LangGraph 设计约束；②需要先理解 LangGraph 才能改 swarm。
- **官方背书**：langchain-ai 组织出品，意味着维护稳定、文档完善、和 LangChain 生态深度兼容（LangSmith Trace 自动可用）。
- **MIT 协议**：可商用、可派生、最友好的协议。
- **swarm 模式与 Orchestrator 模式的代码差异**：Orchestrator 模式需要"老板 Agent + 子 Agent"两层结构；swarm 模式所有 Agent 平级 + 一个 active_agent 状态字段。后者代码量小一个数量级。
- **handoff vs 群聊 @ 的设计映射**：handoff tool（Agent 主动调用切换）对应 IM 里的"用户 @ 某 Agent"——都是"决定主控权"的机制。区别在于 handoff 由 LLM 自己决定，@ 由用户决定。混合模式可以两者并存：默认按 active_agent 走，用户 @ 时强制切换。
