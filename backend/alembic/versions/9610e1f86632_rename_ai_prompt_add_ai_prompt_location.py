"""rename_ai_prompt_add_ai_prompt_location

Revision ID: 9610e1f86632
Revises: 47ed5e394027
Create Date: 2026-04-17 06:20:54.852862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9610e1f86632'
down_revision: Union[str, Sequence[str], None] = '47ed5e394027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Rename ai_prompt → ai_prompt_standard and make nullable=False.
    # Existing rows already have values so the NOT NULL constraint is safe.
    op.alter_column("goal_types", "ai_prompt",
        new_column_name="ai_prompt_standard",
        existing_type=sa.Text(),
        nullable=False,
    )

    # Step 2: Add ai_prompt_location as nullable to handle existing rows.
    op.add_column("goal_types",
        sa.Column("ai_prompt_location", sa.Text(), nullable=True),
    )

    # Step 3: Populate existing rows — copy ai_prompt_standard as a starting
    # point. Admin should update these with proper location-specific prompts.
    op.execute(
        "UPDATE goal_types SET ai_prompt_location = ai_prompt_standard"
    )

    # Step 4: Now that all rows have a value, enforce NOT NULL.
    op.alter_column("goal_types", "ai_prompt_location",
        existing_type=sa.Text(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("goal_types", "ai_prompt_location")
    op.alter_column("goal_types", "ai_prompt_standard",
        new_column_name="ai_prompt",
        existing_type=sa.Text(),
        nullable=True,
    )
