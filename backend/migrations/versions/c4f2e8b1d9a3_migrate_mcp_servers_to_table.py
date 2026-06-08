"""add mcp_servers and agent_mcp_servers tables

Revision ID: c4f2e8b1d9a3
Revises: 14b53d6570bf
Create Date: 2026-06-08 00:00:00.000000

新建 mcp_servers 表（MCP 服务器独立实体，与 skills 表结构对齐）
新建 agent_mcp_servers 关联表（多对多，与 agent_skills 对齐）
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c4f2e8b1d9a3'
down_revision: Union[str, Sequence[str], None] = '14b53d6570bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mcp_servers',
        sa.Column('id', sa.String(36), primary_key=True, comment='UUID'),
        sa.Column('name', sa.String(100), nullable=False, comment='名称'),
        sa.Column('description', sa.String(500), nullable=True, comment='功能简介'),
        sa.Column(
            'transport',
            sa.Enum('stdio', 'sse', name='mcp_transport'),
            nullable=False,
            comment='连接方式',
        ),
        sa.Column('command', sa.String(500), nullable=True, comment='stdio: 可执行文件路径'),
        sa.Column('args', sa.JSON(), nullable=True, comment='stdio args'),
        sa.Column('env', sa.JSON(), nullable=True, comment='stdio env'),
        sa.Column('url', sa.String(500), nullable=True, comment='sse: 端点 URL'),
        sa.Column('headers', sa.JSON(), nullable=True, comment='sse headers'),
        sa.Column('author_id', sa.String(36), nullable=False, comment="创建者；'GUGA'=系统内置"),
        sa.Column('is_public', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_mcp_servers_public_active', 'mcp_servers', ['is_public', 'is_active'])

    op.create_table(
        'agent_mcp_servers',
        sa.Column('agent_id', sa.String(36), primary_key=True, comment='agents.id'),
        sa.Column('mcp_server_id', sa.String(36), primary_key=True, comment='mcp_servers.id'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_agent_mcp_servers_mcp', 'agent_mcp_servers', ['mcp_server_id'])


def downgrade() -> None:
    op.drop_index('ix_agent_mcp_servers_mcp', table_name='agent_mcp_servers')
    op.drop_table('agent_mcp_servers')

    op.drop_index('ix_mcp_servers_public_active', table_name='mcp_servers')
    op.drop_table('mcp_servers')
    # Note: Enum type 'mcp_transport' is dropped automatically on PostgreSQL;
    # on MySQL it is embedded in the column definition so no extra drop needed.
