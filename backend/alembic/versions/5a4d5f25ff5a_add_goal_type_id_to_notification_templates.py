"""add_goal_type_id_to_notification_templates

Revision ID: 5a4d5f25ff5a
Revises: c3d4e5f6a7b8
Create Date: 2026-04-19 00:00:00.000000

Adds a nullable goal_type_id FK to notification_templates.
NULL = generic fallback template (applies to all goal types).
When set, the template is specific to that goal type and takes
priority over generic templates at query time.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '5a4d5f25ff5a'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'notification_templates',
        sa.Column('goal_type_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_notification_templates_goal_type_id',
        'notification_templates', 'goal_types',
        ['goal_type_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_notification_templates_goal_type_id',
        'notification_templates',
        type_='foreignkey',
    )
    op.drop_column('notification_templates', 'goal_type_id')
