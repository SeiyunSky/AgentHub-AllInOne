"""add streamable_http to mcp_transport enum

Revision ID: d3e9f1a2b4c5
Revises: c4f2e8b1d9a3
Create Date: 2026-06-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd3e9f1a2b4c5'
down_revision: Union[str, Sequence[str], None] = 'c4f2e8b1d9a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite does not support ALTER TYPE; recreate the check constraint by
    # modifying the column via batch mode (no-op on databases with native enums
    # that support ADD VALUE, but safe on SQLite).
    with op.batch_alter_table('mcp_servers') as batch_op:
        batch_op.alter_column(
            'transport',
            existing_type=__import__('sqlalchemy').Enum('stdio', 'sse', name='mcp_transport'),
            type_=__import__('sqlalchemy').Enum('stdio', 'sse', 'streamable_http', name='mcp_transport'),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('mcp_servers') as batch_op:
        batch_op.alter_column(
            'transport',
            existing_type=__import__('sqlalchemy').Enum('stdio', 'sse', 'streamable_http', name='mcp_transport'),
            type_=__import__('sqlalchemy').Enum('stdio', 'sse', name='mcp_transport'),
            existing_nullable=False,
        )
