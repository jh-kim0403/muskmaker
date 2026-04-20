"""seed_goal_missed_templates

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO notification_templates (id, event_type, tone, title, body, created_at) VALUES
        -- friendly_banter goal_missed (1-30)
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The gym checked attendance and wrote "mysteriously absent."', now() + interval '1 second'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your dumbbells filed a missing person report.', now() + interval '2 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The treadmill waited for you like a sad golden retriever.', now() + interval '3 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your pre-workout got stood up again.', now() + interval '4 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The squat rack has trust issues now.', now() + interval '5 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your gym shoes had the day off against their will.', now() + interval '6 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Even the elliptical was like, "So... we got ghosted?"', now() + interval '7 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The barbell is posting breakup quotes tonight.', now() + interval '8 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Calories celebrated like they won a championship.', now() + interval '9 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your muscles called. They said, "bro?"', now() + interval '10 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The gym playlist dropped three bangers and you missed all of them.', now() + interval '11 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Somewhere, a bench is feeling personally rejected.', now() + interval '12 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your water bottle was ready for war and got sent back to the cabinet.', now() + interval '13 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The mirrors were robbed of your dramatic post-set stare.', now() + interval '14 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'You skipped the gym so hard even your hoodie looked disappointed.', now() + interval '15 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The treadmill had nobody to dramatically speed up on for 45 seconds.', now() + interval '16 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your gains are outside refreshing the tracking page.', now() + interval '17 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The dumbbells are wondering if this is still a serious relationship.', now() + interval '18 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your fitness goals just sent "u up?"', now() + interval '19 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The gym staff almost put your photo on a milk carton.', now() + interval '20 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your abs remain in witness protection for another day.', now() + interval '21 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The stairmaster survived another day without your betrayal.', now() + interval '22 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your gym bag had one job and still got benched.', now() + interval '23 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your future self just shook their head and stole your snacks.', now() + interval '24 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The squat rack lit a candle and whispered, "maybe tomorrow."', now() + interval '25 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'You missed the gym today, but congratulations to your couch on another dominant performance.', now() + interval '26 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'The protein powder watched all this happen and said nothing.', now() + interval '27 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your motivation hit "remind me later" and never came back.', now() + interval '28 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'NASA called. They detected zero lift-off today.', now() + interval '29 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'friendly_banter'::notification_tone, 'Missed it this time', 'Your gains are loading… very, very slowly.', now() + interval '30 seconds'),
        -- harsh goal_missed (31-60)
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You didn''t skip the gym. You chose comfort over progress.', now() + interval '31 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Every goal you talk about sounds fake on days like this.', now() + interval '32 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Nobody cares about your excuses. The work still didn''t get done.', now() + interval '33 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You say you want results, but today your actions said otherwise.', now() + interval '34 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Missing one day is easy. Becoming soft is easier.', now() + interval '35 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You had time. You just didn''t have discipline.', now() + interval '36 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Your future physique lost to your current laziness today.', now() + interval '37 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Motivation didn''t fail you. Your standards did.', now() + interval '38 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You keep wanting the reward without respecting the process.', now() + interval '39 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'The body you want is built on days exactly like this, and you folded.', now() + interval '40 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Today you let convenience make your decisions.', now() + interval '41 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You''re not stuck. You''re avoiding effort.', now() + interval '42 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You can dress it up however you want. You still bailed on yourself.', now() + interval '43 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Progress is never impressed by intentions. Only by reps.', now() + interval '44 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'The gap between who you are and who you want to be got wider today.', now() + interval '45 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You keep delaying the hard part and wondering why nothing changes.', now() + interval '46 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Today was weak. Fix it tomorrow.', now() + interval '47 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You''re capable of more, which makes today even worse.', now() + interval '48 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You made a promise to yourself and broke it for nothing important.', now() + interval '49 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Results don''t disappear overnight, but standards do.', now() + interval '50 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'This is how people stay average: one justified skip at a time.', now() + interval '51 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Today you practiced quitting, not winning.', now() + interval '52 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Your excuses are getting stronger than you are.', now() + interval '53 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'If this keeps up, don''t act surprised when the mirror tells the truth.', now() + interval '54 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You don''t need another pep talk. You need to stop being soft.', now() + interval '55 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Discipline was required; excuses showed up instead.', now() + interval '56 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You knew what needed to happen and still chose the easier path.', now() + interval '57 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'No one sabotaged you today but you.', now() + interval '58 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'You want confidence, but today you trained disappointment.', now() + interval '59 seconds'),
        (gen_random_uuid(), 'goal_missed'::notification_event_type, 'harsh'::notification_tone, 'You missed it.', 'Be honest: today wasn''t rest, it was avoidance.', now() + interval '60 seconds')
    """))


def downgrade() -> None:
    # Delete the 60 rows added by this migration.
    # Original seed rows use {goal_name} placeholder; these new ones do not.
    op.execute(sa.text("""
        DELETE FROM notification_templates
        WHERE event_type = 'goal_missed'::notification_event_type
          AND tone IN ('friendly_banter'::notification_tone, 'harsh'::notification_tone)
          AND body NOT LIKE '%{goal_name}%'
    """))
