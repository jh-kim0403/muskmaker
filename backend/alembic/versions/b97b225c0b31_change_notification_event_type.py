"""change notification_event_type

Revision ID: b97b225c0b31
Revises: a14eaaf7a74f
Create Date: 2026-04-21 12:56:32.017860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b97b225c0b31'
down_revision: Union[str, Sequence[str], None] = 'a14eaaf7a74f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
