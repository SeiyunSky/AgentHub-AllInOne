"""add_anthropic_sdk_agent_type

Revision ID: 811ed44c244d
Revises: 4762e0ccd2c1
Create Date: 2026-06-18 15:15:53.974279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '811ed44c244d'
down_revision: Union[str, Sequence[str], None] = '4762e0ccd2c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add anthropic_sdk to agents.type ENUM."""
    op.execute(
        "ALTER TABLE agents MODIFY COLUMN type "
        "ENUM('claude','codex','opencode','custom','anthropic_sdk') NOT NULL"
    )


def downgrade() -> None:
    """Remove anthropic_sdk from agents.type ENUM."""
    op.execute(
        "ALTER TABLE agents MODIFY COLUMN type "
        "ENUM('claude','codex','opencode','custom') NOT NULL"
    )
