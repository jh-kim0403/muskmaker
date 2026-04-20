"""rename_slug_to_maps_query_word_goal_types

Revision ID: a1b2c3d4e5f6
Revises: 5d3278a3a328
Create Date: 2026-04-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5d3278a3a328'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # The rename may have already been applied manually — only act if slug still exists
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='goal_types' AND column_name='slug'"
    ))
    if result.fetchone():
        op.alter_column('goal_types', 'slug', new_column_name='maps_query_word')
        op.drop_index('idx_goal_types_slug', table_name='goal_types', if_exists=True)
        op.create_index('idx_goal_types_maps_query_word', 'goal_types', ['maps_query_word'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_goal_types_maps_query_word', table_name='goal_types')
    op.create_index('idx_goal_types_slug', 'goal_types', ['slug'], unique=False)
    op.alter_column('goal_types', 'maps_query_word', new_column_name='slug')
