"""
AgentBuilderService —— 对话式创建 Agent（LLM 生成草稿 → 用户确认 → 落库）

流程：
  1. build(user_id, description)
       → 调 LLM 生成 AgentBuildDraft（name / description / system_prompt / capabilities）
       → 把草稿存到 _draft_store（内存字典；接口与 Redis 兼容，上量时直接换实现）
       → 返回 (session_id, draft)

  2. confirm(user_id, session_id, edited_draft)
       → 从 _draft_store 取原草稿（session 校验）
       → 把 edited_draft.suggested_skill_names 按 name 查 skill_id
       → 调 AgentRepository.create + SkillRepository.sync_agent_skills 落库
       → 删 _draft_store 中的草稿
       → 返回落库后的 Agent ORM 对象

草稿存储设计：
  - MVP：threading.Lock 保护的进程内字典，key = f"agent_draft:{user_id}:{session_id}"
  - 生产：换成 redis.setex(key, 3600, json)，接口签名不变
  - 不依赖 Redis 的好处：本地开发零依赖，CI 无需起 Redis

LLM prompt 策略：
  - 让 LLM 返回结构化 JSON（AgentBuildDraft 字段）
  - 用 response_format={"type":"json_object"} 强制 JSON（openai-compatible）
  - 解析失败时抛 ValueError，上层 API 层转 422

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-28
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Optional

from sqlalchemy.orm import Session

from backend.core.utils import gen_uuid
from backend.domain.agent import AgentCapabilities, AgentType
from backend.repositories.agent_repo import AgentRepository
from backend.repositories.skill_repo import SkillRepository
from backend.schemas.agent import AgentBuildDraft
from backend.services.orchestrator.llm_client import OrchestratorLLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 内存草稿存储（Redis 可替换）
# ---------------------------------------------------------------------------
_store_lock = threading.Lock()
_draft_store: dict[str, dict] = {}  # key → {"user_id": ..., "draft": {...}, "expires_at": float}

_DRAFT_TTL = 3600  # 秒，内存版主动 evict；Redis 版用 setex


def _store_put(user_id: str, session_id: str, draft: AgentBuildDraft) -> None:
    key = f"agent_draft:{user_id}:{session_id}"
    with _store_lock:
        _draft_store[key] = {
            "user_id": user_id,
            "draft": draft.model_dump(),
            "expires_at": time.monotonic() + _DRAFT_TTL,
        }
        # 顺手清理已过期条目，防止长跑进程内存泄漏
        _evict_expired()


def _evict_expired() -> None:
    """删除已超过 TTL 的草稿（调用方持锁）。"""
    now = time.monotonic()
    expired = [k for k, v in _draft_store.items() if v.get("expires_at", 0) < now]
    for k in expired:
        del _draft_store[k]


def _store_get(user_id: str, session_id: str) -> Optional[AgentBuildDraft]:
    key = f"agent_draft:{user_id}:{session_id}"
    with _store_lock:
        entry = _draft_store.get(key)
    if entry is None or entry["user_id"] != user_id:
        return None
    if time.monotonic() > entry.get("expires_at", 0):
        _store_delete(user_id, session_id)
        return None
    return AgentBuildDraft.model_validate(entry["draft"])


def _store_delete(user_id: str, session_id: str) -> None:
    key = f"agent_draft:{user_id}:{session_id}"
    with _store_lock:
        _draft_store.pop(key, None)


# ---------------------------------------------------------------------------
# LLM system prompt
# ---------------------------------------------------------------------------

_BUILDER_SYSTEM_PROMPT = """\
你是 AgentHub 的 Agent 设计助手。用户会用自然语言描述他们需要的 Agent，你的工作是生成一个完整的 Agent 配置草稿。

输出必须是合法的 JSON 对象，字段如下：
- name (string, 必填)：简短的 Agent 名称，中英文均可，10字以内
- description (string, 必填)：1-2句话介绍 Agent 的用途
- type (string, 必填)：选 "claude" / "codex" / "custom" 之一，codex 仅用于纯代码场景
- system_prompt (string, 必填)：完整的 system prompt，用中文，包含角色定义/核心职责/工作原则/输出格式
- capabilities (object, 必填)：{"supports_code":bool, "supports_diff":bool, "supports_approval":bool, "supports_image":bool}
- tags (array of string, 可选)：1-3个分类标签
- suggested_skill_names (array of string, 可选)：建议挂载的 skill 名称，没有合适的留空数组

只输出 JSON，不要有任何解释文字。
"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AgentBuilderService:
    """
    对话式创建 Agent 的业务逻辑。

    db 由调用方（API 层）注入，service 只 flush，不 commit——commit 在 API 层。
    llm_client 默认用模块级单例，测试时可注入 mock。
    """

    def __init__(
        self,
        db: Session,
        *,
        llm_client: Optional[OrchestratorLLMClient] = None,
    ) -> None:
        self._db = db
        self._llm = llm_client or _default_llm_client()

    async def build(self, user_id: str, description: str) -> tuple[str, AgentBuildDraft]:
        """
        第一步：LLM 生成草稿，存入 _draft_store，返回 (session_id, draft)。

        Raises:
            ValueError: LLM 输出无法解析为合法 AgentBuildDraft
        """
        messages = [{"role": "user", "content": description}]
        resp = await self._llm.chat_completion(
            system=_BUILDER_SYSTEM_PROMPT,
            messages=messages,
            tools=[],
            max_tokens=2048,
        )

        raw_text = resp.content_text or ""
        draft = _parse_draft(raw_text)

        session_id = gen_uuid()
        _store_put(user_id, session_id, draft)
        logger.info("AgentBuilder draft created: session=%s user=%s name=%s",
                    session_id, user_id, draft.name)
        return session_id, draft

    def confirm(
        self,
        user_id: str,
        session_id: str,
        edited_draft: AgentBuildDraft,
    ):
        """
        第二步：用户确认（含编辑），落库，删草稿，返回 Agent ORM 对象。

        Raises:
            LookupError: session_id 不存在或不属于 user_id
            LookupError: suggested_skill_names 中有找不到的 skill name
        """
        # 校验 session（防止 session 伪造 / TTL 过期）。
        # 用户提交的 edited_draft 可能与原草稿不同（用户可以修改），
        # 所以落库以 edited_draft 为准，stored 仅作 session 合法性校验。
        stored = _store_get(user_id, session_id)
        if stored is None:
            raise LookupError(f"Draft session not found: {session_id}")

        agent_repo = AgentRepository(self._db)
        skill_repo = SkillRepository(self._db)

        # suggested_skill_names → skill_id
        skill_ids: list[str] = []
        missing: list[str] = []
        for name in (edited_draft.suggested_skill_names or []):
            skill = skill_repo.get_by_name(name, "GUGA") or skill_repo.get_by_name(name, user_id)
            if skill is None:
                missing.append(name)
            else:
                skill_ids.append(skill.id)
        if missing:
            raise LookupError(f"Skill names not found: {missing}")

        caps = edited_draft.capabilities
        agent = agent_repo.create(
            user_id=user_id,
            name=edited_draft.name,
            description=edited_draft.description,
            avatar=edited_draft.avatar,
            type=edited_draft.type,
            system_prompt=edited_draft.system_prompt,
            capabilities={
                "supports_code": caps.supports_code,
                "supports_diff": caps.supports_diff,
                "supports_approval": caps.supports_approval,
                "supports_image": caps.supports_image,
            },
            tags=edited_draft.tags,
            is_public=0,
            is_active=1,
        )

        if skill_ids:
            skill_repo.sync_agent_skills(agent.id, skill_ids)

        _store_delete(user_id, session_id)
        logger.info("AgentBuilder confirmed: agent_id=%s user=%s", agent.id, user_id)
        return agent


# ---------------------------------------------------------------------------
# 辅助：JSON 解析
# ---------------------------------------------------------------------------

def _parse_draft(raw: str) -> AgentBuildDraft:
    """
    从 LLM 输出中提取 JSON 并解析为 AgentBuildDraft。

    兼容两种格式：
    1. 纯 JSON 字符串
    2. Markdown 代码块包裹的 JSON（```json ... ```）
    """
    text = raw.strip()
    # 剥掉 markdown 代码块（只取第一个代码块内容，防止 LLM 在 ``` 后附加额外文字）
    if text.startswith("```"):
        # 找到第一行结束和闭合的 ``` 行
        first_newline = text.find("\n")
        if first_newline != -1:
            rest = text[first_newline + 1:]
            close = rest.find("\n```")
            if close != -1:
                text = rest[:close].strip()
            else:
                # 没有找到闭合标记，取第一行之后的全部内容
                text = rest.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}\nRaw: {raw[:300]}") from exc

    # 兼容 LLM 可能输出 "claude-3" 等非法 type
    raw_type = data.get("type", "claude")
    allowed = {"claude", "codex", "opencode", "custom"}
    if raw_type not in allowed:
        data["type"] = "claude"

    # capabilities 字段容错：LLM 可能漏字段
    caps_raw = data.get("capabilities") or {}
    data["capabilities"] = AgentCapabilities(
        supports_code=bool(caps_raw.get("supports_code", False)),
        supports_diff=bool(caps_raw.get("supports_diff", False)),
        supports_approval=bool(caps_raw.get("supports_approval", False)),
        supports_image=bool(caps_raw.get("supports_image", False)),
    )

    try:
        return AgentBuildDraft.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Failed to validate AgentBuildDraft: {exc}") from exc


# ---------------------------------------------------------------------------
# 默认 LLM client（懒初始化，避免 import 时 settings 未就绪）
# ---------------------------------------------------------------------------
_llm_singleton: Optional[OrchestratorLLMClient] = None
_llm_lock = threading.Lock()


def _default_llm_client() -> OrchestratorLLMClient:
    global _llm_singleton
    if _llm_singleton is None:
        with _llm_lock:
            if _llm_singleton is None:
                _llm_singleton = OrchestratorLLMClient()
    return _llm_singleton
