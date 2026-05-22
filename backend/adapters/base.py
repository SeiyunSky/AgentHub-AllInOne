from abc import ABC, abstractmethod
from typing import AsyncGenerator

from backend.adapters.events import AgentEvent
from backend.domain.message import MessageEntity
from backend.domain.skill import SkillEntity


class AgentAdapter(ABC):
    """Abstract base class for all agent adapters.

    Concrete implementations must yield AgentStartEvent first, then
    any number of content/artifact/approval events, and finally
    AgentDoneEvent or AgentErrorEvent.
    """

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        history: list[MessageEntity],
        skills: list[SkillEntity],
    ) -> AsyncGenerator[AgentEvent, None]:
        """Stream AgentEvent objects for a given prompt."""
        # This body is unreachable; the yield below satisfies the type checker
        # for async generator return type inference.
        yield  # type: ignore[misc]

    @abstractmethod
    def get_capabilities(self) -> dict[str, bool]:
        """Return capability flags: {supports_diff, supports_approval}."""
        ...

    async def close(self) -> None:
        """Optional cleanup called by the registry on shutdown."""
