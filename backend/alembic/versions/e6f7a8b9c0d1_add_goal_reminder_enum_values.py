"""add_goal_reminder_enum_values

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-04-21 00:00:00.000000

Adds 'goal_reminder' and 'goal_reminder_2hr' to the notification_event_type
PostgreSQL enum. The NotificationTemplate model was updated to use these
simplified names instead of 'goal_reminder_24h' / 'goal_reminder_2h'.

The old values remain in the enum (PostgreSQL does not support removing
enum values) — they continue to be used by GoalNotificationLog.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'b97b225c0b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'goal_reminder'")
    op.execute("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'goal_reminder_2hr'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values — downgrade is a no-op.
    pass
