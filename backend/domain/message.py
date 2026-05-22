from dataclasses import dataclass


@dataclass
class MessageEntity:
    id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    content_type: str = "text"  # "text" | "artifact_diff" | "artifact_html"
    agent_id: str | None = None
    agent_name: str | None = None  # Snapshot for display; denormalized
    status: str = "done"  # "streaming" | "done" | "error"
