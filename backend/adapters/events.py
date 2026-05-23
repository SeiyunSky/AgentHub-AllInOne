from typing import Literal, Union, Annotated

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    """Base class that serializes field names as camelCase for the frontend."""

    model_config = {
        "alias_generator": to_camel,
        "populate_by_name": True,
    }


class AgentStartEvent(_CamelModel):
    type: Literal["agent_start"] = "agent_start"
    agent_id: str
    agent_name: str
    message_id: str


class TokenEvent(_CamelModel):
    type: Literal["token"] = "token"
    agent_id: str
    message_id: str
    content: str


class ArtifactHtmlEvent(_CamelModel):
    type: Literal["artifact_html"] = "artifact_html"
    agent_id: str
    message_id: str
    preview_url: str
    html: str = ""


class ArtifactDiffEvent(_CamelModel):
    type: Literal["artifact_diff"] = "artifact_diff"
    agent_id: str
    message_id: str
    file: str
    patch: str
    additions: int = 0
    deletions: int = 0


class ApprovalRequestEvent(_CamelModel):
    type: Literal["approval_request"] = "approval_request"
    agent_id: str
    message_id: str
    action: str
    detail: str


class SubAgentSpawnEvent(_CamelModel):
    type: Literal["sub_agent_spawn"] = "sub_agent_spawn"
    agent_id: str
    message_id: str
    sub_task: str


class DeployProgressEvent(_CamelModel):
    type: Literal["deploy_progress"] = "deploy_progress"
    stage: str
    percent: int


class DeployDoneEvent(_CamelModel):
    type: Literal["deploy_done"] = "deploy_done"
    url: str


class AgentDoneEvent(_CamelModel):
    type: Literal["agent_done"] = "agent_done"
    agent_id: str
    message_id: str


class AgentErrorEvent(_CamelModel):
    type: Literal["agent_error"] = "agent_error"
    agent_id: str
    message_id: str
    error: str


class RoundDoneEvent(_CamelModel):
    type: Literal["round_done"] = "round_done"


AgentEvent = Annotated[
    Union[
        AgentStartEvent,
        TokenEvent,
        ArtifactHtmlEvent,
        ArtifactDiffEvent,
        ApprovalRequestEvent,
        SubAgentSpawnEvent,
        DeployProgressEvent,
        DeployDoneEvent,
        AgentDoneEvent,
        AgentErrorEvent,
        RoundDoneEvent,
    ],
    Field(discriminator="type"),
]
