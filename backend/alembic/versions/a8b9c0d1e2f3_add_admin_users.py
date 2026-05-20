"""add_admin_users

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-04-23 00:00:00.000000

Creates the admin_users table for separate admin panel authentication.
Migrates admin_reviews.assigned_to and anti_cheat_log.reviewed_by
FK references from users.id to admin_users.id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, Sequence[str], None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_users',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('api_key_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False, server_default='reviewer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('api_key_hash', name='uq_admin_users_api_key_hash'),
    )

    # admin_reviews.assigned_to → admin_users.id
    op.drop_constraint('admin_reviews_assigned_to_fkey', 'admin_reviews', type_='foreignkey')
    op.create_foreign_key(
        'admin_reviews_assigned_to_fkey',
        'admin_reviews', 'admin_users',
        ['assigned_to'], ['id'],
        ondelete='SET NULL',
    )

    # anti_cheat_log.reviewed_by → admin_users.id
    op.drop_constraint('anti_cheat_log_reviewed_by_fkey', 'anti_cheat_log', type_='foreignkey')
    op.create_foreign_key(
        'anti_cheat_log_reviewed_by_fkey',
        'anti_cheat_log', 'admin_users',
        ['reviewed_by'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('anti_cheat_log_reviewed_by_fkey', 'anti_cheat_log', type_='foreignkey')
    op.create_foreign_key(
        'anti_cheat_log_reviewed_by_fkey',
        'anti_cheat_log', 'users',
        ['reviewed_by'], ['id'],
    )

    op.drop_constraint('admin_reviews_assigned_to_fkey', 'admin_reviews', type_='foreignkey')
    op.create_foreign_key(
        'admin_reviews_assigned_to_fkey',
        'admin_reviews', 'users',
        ['assigned_to'], ['id'],
    )

    op.drop_table('admin_users')
