"""Custom exception classes for the AgentHub service layer."""


class AgentHubError(Exception):
    """Base class for all AgentHub exceptions."""


class AgentNotFoundError(AgentHubError):
    """Raised when no adapter is registered for a given agent_id."""


class ConversationNotFoundError(AgentHubError):
    """Raised when a conversation does not exist or is not accessible."""


class CircuitOpenError(AgentHubError):
    """Raised when a circuit breaker is in OPEN state, blocking the call."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Circuit breaker OPEN for agent_id={agent_id!r}")
        self.agent_id = agent_id


class RateLimitError(AgentHubError):
    """Raised when a user has exceeded their request rate limit."""


class ApprovalRequiredError(AgentHubError):
    """Raised when a tool call requires explicit user approval before proceeding."""

    def __init__(self, action: str, detail: str) -> None:
        super().__init__(f"Approval required for action={action!r}")
        self.action = action
        self.detail = detail


class PermissionDeniedError(AgentHubError):
    """Raised when the current user lacks permission for an operation."""


# ----------------------------------------------------------------
# auth (登录 / token) 相关
# ----------------------------------------------------------------


class AuthenticationError(AgentHubError):
    """登录凭据错误(用户名不存在 / 密码错)。统一一种异常,避免给攻击者枚举用户名的机会。"""


class TokenInvalidError(AgentHubError):
    """JWT 解码失败、签名错误、过期、被吊销(在黑名单里)等情况统一抛这个。"""


class UserAlreadyExistsError(AgentHubError):
    """注册时 username 或 email 已被占用。"""

    def __init__(self, field: str, value: str) -> None:
        super().__init__(f"{field}={value!r} 已被占用")
        self.field = field
        self.value = value

