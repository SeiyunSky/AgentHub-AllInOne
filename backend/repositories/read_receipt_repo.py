"""
ReadReceiptRepository —— read_receipts 表数据访问层

broadcast 模式下，Agent 决定不回复时调 save()，幂等写入已读回执。
唯一约束 (message_id, agent_id) 保证重复调用安全。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-06-05
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.core.utils import gen_uuid, now_utc
from backend.models.read_receipt import ReadReceipt


class ReadReceiptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        *,
        conversation_id: str,
        message_id: str,
        agent_id: str,
    ) -> ReadReceipt:
        """
        幂等写入已读回执。
        (message_id, agent_id) 已存在则直接返回既有行，不写重复记录。
        """
        existing = (
            self.session.query(ReadReceipt)
            .filter_by(message_id=message_id, agent_id=agent_id)
            .first()
        )
        if existing is not None:
            return existing
        row = ReadReceipt(
            id=gen_uuid(),
            conversation_id=conversation_id,
            message_id=message_id,
            agent_id=agent_id,
            read_at=now_utc(),
        )
        self.session.add(row)
        self.session.flush()
        return row
