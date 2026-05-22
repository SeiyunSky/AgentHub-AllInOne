from dataclasses import dataclass, field


@dataclass
class AgentCapabilities:
    supports_diff: bool = False
    supports_approval: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "AgentCapabilities":
        if not data:
            return cls()
        return cls(
            supports_diff=data.get("supports_diff", False),
            supports_approval=data.get("supports_approval", False),
        )

    def to_dict(self) -> dict:
        return {
            "supports_diff": self.supports_diff,
            "supports_approval": self.supports_approval,
        }


@dataclass
class AgentEntity:
    id: str
    name: str
    type: str  # "claude" | "codex" | "opencode" | "custom"
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    system_prompt: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    is_public: bool = False
