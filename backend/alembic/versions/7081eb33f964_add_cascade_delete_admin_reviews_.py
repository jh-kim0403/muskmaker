"""add_cascade_delete_admin_reviews_verification

Revision ID: 7081eb33f964
Revises: 9610e1f86632
Create Date: 2026-04-18 00:50:08.067893

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7081eb33f964'
down_revision: Union[str, Sequence[str], None] = '9610e1f86632'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("admin_reviews_verification_id_fkey", "admin_reviews", type_="foreignkey")
    op.create_foreign_key(
        "admin_reviews_verification_id_fkey",
        "admin_reviews", "verifications",
        ["verification_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("admin_reviews_verification_id_fkey", "admin_reviews", type_="foreignkey")
    op.create_foreign_key(
        "admin_reviews_verification_id_fkey",
        "admin_reviews", "verifications",
        ["verification_id"], ["id"],
    )
