"""merge_oauth_and_streamable_http

Revision ID: 4762e0ccd2c1
Revises: 642b2725e844, d3e9f1a2b4c5
Create Date: 2026-06-12 15:42:58.944517

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4762e0ccd2c1'
down_revision: Union[str, Sequence[str], None] = ('642b2725e844', 'd3e9f1a2b4c5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
