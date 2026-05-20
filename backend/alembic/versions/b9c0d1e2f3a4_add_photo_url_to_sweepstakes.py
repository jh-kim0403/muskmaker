"""add_photo_url_to_sweepstakes

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-04-29 00:00:00.000000

Adds an optional image URL for sweepstakes prizes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b9c0d1e2f3a4'
down_revision: Union[str, Sequence[str], None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sweepstakes', sa.Column('photo_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('sweepstakes', 'photo_url')
