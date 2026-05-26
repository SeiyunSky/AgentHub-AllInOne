"""
MessageService —— 消息存储 / 查询 / 状态更新

业务编排层,封装 messages 表的写入(同步刷新 conversations 冗余字段)、
读取分页、token 字段回写、软删除等业务动作。

风格:**stateless façade** —— 模块级单例,每个方法内部用 SessionLocal() 起 session
自管事务。chat_service 顶层 import 单例直接用,不需要传 session。

(注:与 thread_service 的"实例 + 注入 session"风格不同,这里跟 chat_service 现有
调用方式对齐:`from backend.services.message_service import message_service`,
然后 `await message_service.create_user_message(...)` 不传 session。)

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.core.database import SessionLocal
from backend.core.utils import gen_uuid
from backend.domain.message import ContentBlock
from backend.models.message import Message
from backend.repositories.conversation_repo import ConversationRepository
from backend.repositories.message_repo import MessageRepository


logger = logging.getLogger(__name__)


# ============================================================
# 工具:从 ContentBlock 数组提取摘要(给 conversations.last_message_preview)
# ============================================================

def _extract_preview(content_blocks: list[Any]) -> str:
    """
    从 ContentBlock 列表里提取一段可读的摘要,200 字以内。
    优先取 text 块的 content;没有 text 块时回退到块类型标签。
    """
    parts: list[str] = []
    for block in content_blocks:
        if block is None:
            continue
        # block 可能是 ContentBlock pydantic 实例,也可能是 dict
        btype = getattr(block, "type", None) or (
            block.get("type") if isinstance(block, dict) else None
        )
        if btype == "text":
            content = getattr(block, "content", None) or (
                block.get("content") if isinstance(block, dict) else ""
            )
            if content:
                parts.append(str(content))
        elif btype:
            parts.append(f"[{btype}]")
    text = " ".join(parts).strip()
    return text[:200] if text else ""


def _serialize_blocks(blocks: list[Any]) -> list[dict[str, Any]]:
    """
    把 ContentBlock 列表序列化成可直接写 JSON 字段的 dict 列表。
    pydantic BaseModel 走 model_dump(mode='json'),已经是 dict 的原样保留。
    """
    out: list[dict[str, Any]] = []
    for b in blocks:
        if b is None:
            continue
        if isinstance(b, dict):
            out.append(b)
        elif hasattr(b, "model_dump"):
            out.append(b.model_dump(mode="json"))
        else:
            # 兜底:repr 化
            out.append({"type": "text", "content": repr(b), "block_id": gen_uuid()})
    return out


# ============================================================
# MessageService(stateless)
# ============================================================

class MessageService:
    """无状态 façade,每方法自管 session + 事务。"""

    # --------------------------------------------------------
    # 写
    # --------------------------------------------------------

    async def create_user_message(
        self,
        *,
        conversation_id: str,
        user_id: str,
        content_blocks: list[ContentBlock],
        selected_range: Optional[Any] = None,
    ) -> Message:
        """
        落用户消息(role=user)。
        - 落 messages 表 1 行
        - 同步刷新 conversations.last_message_preview / last_message_at / message_count
          (last_message_at 取 DB 端 msg.created_at,与消息时间严格一致)
        - selected_range 非空时落到 selected_range 字段(对话式局部修改用)
        """
        session = SessionLocal()
        try:
            msg_repo = MessageRepository(session)
            conv_repo = ConversationRepository(session)

            sel_range_dump: Optional[dict[str, Any]] = None
            if selected_range is not None:
                if hasattr(selected_range, "model_dump"):
                    sel_range_dump = selected_range.model_dump(mode="json")
                elif isinstance(selected_range, dict):
                    sel_range_dump = selected_range

            msg = msg_repo.create(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=_serialize_blocks(content_blocks),
                status="done",
                selected_range=sel_range_dump,
            )

            preview = _extract_preview(content_blocks)
            # 用 DB 端 created_at(由 server_default=NOW() 生成)对齐 last_message_at,
            # 避免和 Python 端 datetime.now() 之间的毫秒漂移导致排序异常
            conv_repo.touch_last_message(
                conversation_id,
                preview=preview,
                at=msg.created_at,
            )

            session.commit()
            session.refresh(msg)
            return msg
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def create_assistant_message(
        self,
        *,
        conversation_id: str,
        agent_id: str,
        content_blocks: list[ContentBlock],
        thread_id: Optional[str] = None,
        sender: Optional[str] = None,
        model: Optional[str] = None,
        status: str = "done",
        parent_id: Optional[str] = None,
    ) -> Message:
        """
        落 Agent 消息(role=assistant)。

        sender / model 是写入时刻快照——Agent 改名 / 升级模型后历史消息仍展示当时数据。
        status:streaming 中间态可先 create 后续再 update_status,默认直接 done。
        last_message_at 取 DB 端 msg.created_at 保证与消息时间一致。
        """
        session = SessionLocal()
        try:
            msg_repo = MessageRepository(session)
            conv_repo = ConversationRepository(session)

            msg = msg_repo.create(
                conversation_id=conversation_id,
                agent_id=agent_id,
                thread_id=thread_id,
                parent_id=parent_id,
                role="assistant",
                content=_serialize_blocks(content_blocks),
                status=status,
                sender=sender,
                model=model,
            )

            preview = _extract_preview(content_blocks)
            conv_repo.touch_last_message(
                conversation_id,
                preview=preview,
                at=msg.created_at,
            )

            session.commit()
            session.refresh(msg)
            return msg
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --------------------------------------------------------
    # 读
    # --------------------------------------------------------

    async def get(self, message_id: str) -> Optional[Message]:
        """单条消息读取。"""
        session = SessionLocal()
        try:
            return MessageRepository(session).get(message_id)
        finally:
            session.close()

    async def list_recent(
        self,
        conversation_id: str,
        *,
        limit: int = 20,
        before: Optional[str] = None,
    ) -> list[Message]:
        """
        某会话最近 N 条消息(倒序)。
        调用方按时间线展示时需要自行 reversed()。
        """
        session = SessionLocal()
        try:
            return MessageRepository(session).list_recent(
                conversation_id,
                limit=limit,
                before=before,
            )
        finally:
            session.close()

    async def list_by_thread(self, thread_id: str) -> list[Message]:
        """某 Thread 产出的所有消息(正序)。"""
        session = SessionLocal()
        try:
            return MessageRepository(session).list_by_thread(thread_id)
        finally:
            session.close()

    # --------------------------------------------------------
    # 字段更新
    # --------------------------------------------------------

    async def update_tokens(
        self,
        message_id: str,
        *,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        latency_ms: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Optional[Message]:
        """
        子 Adapter / 主 Agent 完成后回写 token / 延迟 / 模型快照。
        只更新非 None 字段。
        """
        session = SessionLocal()
        try:
            result = MessageRepository(session).update_tokens(
                message_id,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                latency_ms=latency_ms,
                model=model,
            )
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def update_status(
        self,
        message_id: str,
        status: str,
        *,
        error_message: Optional[str] = None,
    ) -> Optional[Message]:
        """streaming → done / error 状态切换。"""
        session = SessionLocal()
        try:
            result = MessageRepository(session).update_status(
                message_id,
                status,
                error_message=error_message,
            )
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def soft_delete(self, message_id: str) -> bool:
        """软删除消息。"""
        session = SessionLocal()
        try:
            ok = MessageRepository(session).soft_delete(message_id)
            session.commit()
            return ok
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def set_feedback(
        self,
        message_id: str,
        feedback: Optional[str],
    ) -> Optional[Message]:
        """feedback: 'up' / 'down' / None。"""
        session = SessionLocal()
        try:
            result = MessageRepository(session).set_feedback(message_id, feedback)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# 模块级单例,chat_service / orchestrator handler 直接 import 用
message_service = MessageService()
