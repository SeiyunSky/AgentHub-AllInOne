"""
Agent 领域实体

定义跟数据库 / 框架无关的 Agent 核心概念,供 schemas / adapters / models 三方共享:
- AgentType:Agent 类型枚举(决定 Adapter 路由)
- AgentCapabilities:Agent 能力声明(决定 UI 是否展示对应交互)
为了让 schemas(DTO 传输)、adapters(基础设施)、models(ORM)三方共用同一份定义,
本模块虽然位于 domain 层,但允许使用 pydantic 作为基础设施。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """单个 MCP 服务器的连接配置。由 registry._to_mcp_configs() 从 mcp_servers 表行转换而来，
    传给 ClaudeAdapter / OpencodeAdapter 用于写临时配置文件。

    transport="stdio": 启动本地子进程 MCP server（如 uvx mcp-server-time）。
    transport="sse":   连接远端 SSE/HTTP MCP server。
    """

    server_id: str = Field(description="对应 mcp_servers.id，注册到 MCPRegistry 的唯一 key")
    transport: Literal["stdio", "sse", "streamable_http"] = Field(description="连接方式")

    # stdio 字段
    command: str | None = Field(default=None, description="stdio 模式：可执行文件，如 'uvx'")
    args: list[str] = Field(default_factory=list, description="stdio 模式：命令参数，如 ['mcp-server-time']")
    env: dict[str, str] = Field(default_factory=dict, description="stdio 模式：额外环境变量")

    # sse 字段
    url: str | None = Field(default=None, description="sse 模式：MCP server URL")
    headers: dict[str, str] = Field(default_factory=dict, description="sse 模式：请求头，如 Authorization")


class AgentType(str, Enum):
    """Agent 类型,决定 Adapter 路由(claude / codex / opencode / custom / anthropic_sdk)"""
    CLAUDE = "claude"
    CODEX = "codex"
    OPENCODE = "opencode"
    CUSTOM = "custom"
    ANTHROPIC_SDK = "anthropic_sdk"


class AgentCapabilities(BaseModel):
    """
    Agent 能力声明。

    用途:
    - 数据库 agents.capabilities JSON 字段反序列化目标
    - Adapter.get_capabilities() 返回类型
    - 前端按字段决定是否渲染对应 UI(如 supports_diff=False 时不显示 Diff 卡片应用按钮;
      supports_image=False 时不展示图片消息块)
    """

    supports_code: bool = Field(
        default=False,
        description="是否能产出代码块(CodeBlock,含 / 不含 diff)",
    )
    supports_diff: bool = Field(
        default=False,
        description="是否能产出可应用的 diff(CodeBlock 含 old_code)",
    )
    supports_approval: bool = Field(
        default=False,
        description="是否会触发 ApprovalBlock 审批",
    )
    supports_image: bool = Field(
        default=False,
        description="是否能产出图片块(ImageBlock)",
    )
