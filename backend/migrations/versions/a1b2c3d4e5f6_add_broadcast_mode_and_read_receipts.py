"""add_broadcast_mode_and_read_receipts

Revision ID: a1b2c3d4e5f6
Revises: 909725750cbd
Create Date: 2026-06-05 00:00:00.000000

变更：
1. conversations.mode enum 新增 'broadcast' 值
2. 新建 read_receipts 表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '909725750cbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. MySQL ALTER ENUM：修改 conversations.mode 列加入 'broadcast'
    op.execute(
        "ALTER TABLE conversations MODIFY COLUMN mode "
        "ENUM('single','group','broadcast') NOT NULL "
        "COMMENT 'chat_service 路由分支用'"
    )

    # 2. 新建 read_receipts 表
    op.create_table(
        'read_receipts',
        sa.Column('id', sa.String(36), nullable=False, comment='UUID'),
        sa.Column('conversation_id', sa.String(36), nullable=False),
        sa.Column('message_id', sa.String(36), nullable=False,
                  comment='触发本回执的用户消息 ID'),
        sa.Column('agent_id', sa.String(36), nullable=False,
                  comment='已读的 Agent ID'),
        sa.Column('read_at', sa.TIMESTAMP(), nullable=False,
                  comment='Agent 处理完成时间（UTC）'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id', 'agent_id',
                            name='uq_read_receipt_msg_agent'),
    )
    op.create_index('ix_read_receipts_message_id', 'read_receipts', ['message_id'])


def downgrade() -> None:
    op.drop_index('ix_read_receipts_message_id', table_name='read_receipts')
    op.drop_table('read_receipts')

    op.execute(
        "ALTER TABLE conversations MODIFY COLUMN mode "
        "ENUM('single','group') NOT NULL "
        "COMMENT 'chat_service 路由分支用'"
    )
