"""add_cascade_delete_verifications_goal

Revision ID: 5d3278a3a328
Revises: 7081eb33f964
Create Date: 2026-04-18 00:51:53.931940

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d3278a3a328'
down_revision: Union[str, Sequence[str], None] = '7081eb33f964'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("verifications_goal_id_fkey", "verifications", type_="foreignkey")
    op.create_foreign_key(
        "verifications_goal_id_fkey",
        "verifications", "goals",
        ["goal_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("verifications_goal_id_fkey", "verifications", type_="foreignkey")
    op.create_foreign_key(
        "verifications_goal_id_fkey",
        "verifications", "goals",
        ["goal_id"], ["id"],
    )
