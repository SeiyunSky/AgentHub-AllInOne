"""merge_broadcast_and_skill_content

Revision ID: 14b53d6570bf
Revises: 852f435ce836, a1b2c3d4e5f6
Create Date: 2026-06-05 16:25:28.634557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14b53d6570bf'
down_revision: Union[str, Sequence[str], None] = ('852f435ce836', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
