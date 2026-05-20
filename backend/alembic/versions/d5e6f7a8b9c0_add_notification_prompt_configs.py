"""add_notification_prompt_configs

Revision ID: d5e6f7a8b9c0
Revises: 5a4d5f25ff5a
Create Date: 2026-04-20 00:00:00.000000

Stores per-(goal_type, tone, event_type) prompt context used by the daily
AI template generation task. NULL goal_type_id = generic fallback for all
goal types. Specific rows take priority over generic via the handler's
NULLS LAST ordering.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = '5a4d5f25ff5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_prompt_configs',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('goal_type_id', sa.UUID(), nullable=True),
        sa.Column('tone', sa.Text(), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('prompt_context', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['goal_type_id'], ['goal_types.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    # One specific config per (goal_type, tone, event_type)
    op.create_index(
        'uq_prompt_configs_specific',
        'notification_prompt_configs',
        ['goal_type_id', 'tone', 'event_type'],
        unique=True,
        postgresql_where=sa.text('goal_type_id IS NOT NULL'),
    )
    # One generic fallback per (tone, event_type)
    op.create_index(
        'uq_prompt_configs_generic',
        'notification_prompt_configs',
        ['tone', 'event_type'],
        unique=True,
        postgresql_where=sa.text('goal_type_id IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_prompt_configs_generic', table_name='notification_prompt_configs')
    op.drop_index('uq_prompt_configs_specific', table_name='notification_prompt_configs')
    op.drop_table('notification_prompt_configs')
