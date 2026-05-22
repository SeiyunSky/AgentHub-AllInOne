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

