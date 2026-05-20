"""restore_prompt_config_unique_indexes

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-04-21 00:00:00.000000

Restores the two partial unique indexes on notification_prompt_configs
that were dropped by migration a14eaaf7a74f.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_prompt_configs_specific',
        'notification_prompt_configs',
        ['goal_type_id', 'tone', 'event_type'],
        unique=True,
        postgresql_where=sa.text('goal_type_id IS NOT NULL'),
    )
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
