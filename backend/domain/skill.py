from dataclasses import dataclass, field


@dataclass
class SkillEntity:
    id: str
    name: str
    file_path: str
    trigger_keywords: list[str] = field(default_factory=list)
    applicable_agents: list[str] = field(default_factory=list)
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    # Loaded on demand by skill_service; None means not yet loaded
    content: str | None = None
