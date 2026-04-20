"""add_notification_templates_and_goal_notification_log

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-18 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reusable enum references — create_type=False prevents automatic CREATE TYPE
event_enum = postgresql.ENUM(
    'goal_missed', 'goal_reminder_24h', 'goal_reminder_2h', 'sweep_results',
    name='notification_event_type', create_type=False,
)
tone_enum = postgresql.ENUM(
    'normal', 'friendly_banter', 'harsh',
    name='notification_tone', create_type=False,
)


def upgrade() -> None:
    # Create the new enum type if it doesn't already exist
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE notification_event_type AS ENUM (
                'goal_missed', 'goal_reminder_24h', 'goal_reminder_2h', 'sweep_results'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))

    # ── notification_templates ─────────────────────────────────────────────────
    op.create_table(
        'notification_templates',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_type', event_enum, nullable=False),
        sa.Column('tone', tone_enum, nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── goal_notification_log ──────────────────────────────────────────────────
    op.create_table(
        'goal_notification_log',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('goal_id', sa.UUID(), nullable=False),
        sa.Column('event_type', event_enum, nullable=False),
        sa.Column('sent_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('goal_id', 'event_type', name='uq_goal_notification_log_goal_event'),
    )
    op.create_index('idx_goal_notification_log_goal', 'goal_notification_log', ['goal_id'])

    # ── Seed default template copy ─────────────────────────────────────────────
    # Use raw SQL with explicit casts — asyncpg won't auto-cast VARCHAR to enum
    op.execute(sa.text("""
        INSERT INTO notification_templates (id, event_type, tone, title, body) VALUES
        -- goal_reminder_24h
        (gen_random_uuid(), 'goal_reminder_24h'::notification_event_type, 'normal'::notification_tone,          'Goal due tomorrow',       'Your {goal_name} goal expires in 24 hours. Make sure you verify it before time runs out.'),
        (gen_random_uuid(), 'goal_reminder_24h'::notification_event_type, 'friendly_banter'::notification_tone, 'Heads up! ⏳',             'Your {goal_name} goal is due tomorrow! Get it done and keep that streak alive!'),
        (gen_random_uuid(), 'goal_reminder_24h'::notification_event_type, 'harsh'::notification_tone,           '24 hours left.',          'You have 24 hours to finish your {goal_name} goal. No excuses.'),
        -- goal_reminder_2h
        (gen_random_uuid(), 'goal_reminder_2h'::notification_event_type,  'normal'::notification_tone,          'Goal expiring soon',      'Your {goal_name} goal expires in 2 hours. Don''t forget to verify it!'),
        (gen_random_uuid(), 'goal_reminder_2h'::notification_event_type,  'friendly_banter'::notification_tone, 'Tick tock! ⏰',           'Only 2 hours left on your {goal_name} goal. Go crush it before time''s up!'),
        (gen_random_uuid(), 'goal_reminder_2h'::notification_event_type,  'harsh'::notification_tone,           '2 hours. Move.',          'Your {goal_name} goal expires in 2 hours. Stop stalling and go do it.'),
        -- goal_missed
        (gen_random_uuid(), 'goal_missed'::notification_event_type,       'normal'::notification_tone,          'Goal not completed',      'Your {goal_name} goal expired without a verified submission. Try again tomorrow.'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type,       'friendly_banter'::notification_tone, 'Missed it this time 😬',  'Your {goal_name} goal slipped away! Shake it off and come back stronger tomorrow.'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type,       'harsh'::notification_tone,           'You missed it.',          'Your {goal_name} goal expired. You didn''t verify it. Do better tomorrow.'),
        -- sweep_results
        (gen_random_uuid(), 'sweep_results'::notification_event_type,     'normal'::notification_tone,          'Sweepstakes results are in!',    'The sweepstakes results have been announced. Open the app to see the outcome.'),
        (gen_random_uuid(), 'sweep_results'::notification_event_type,     'friendly_banter'::notification_tone, 'The results are in! 🎉',         'Drumroll please... the sweepstakes results are live! Tap to find out if you won!'),
        (gen_random_uuid(), 'sweep_results'::notification_event_type,     'harsh'::notification_tone,           'Results are out.',               'Sweepstakes results are posted. Open the app and see where you stand.')
    """))


def downgrade() -> None:
    op.drop_index('idx_goal_notification_log_goal', table_name='goal_notification_log')
    op.drop_table('goal_notification_log')
    op.drop_table('notification_templates')
    op.execute(sa.text("DROP TYPE IF EXISTS notification_event_type"))
