"""add_calendar

Revision ID: b4c92d3e
Revises: a3f92b1c
Create Date: 2026-03-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b4c92d3e'
down_revision: Union[str, None] = 'a3f92b1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ScheduleType enum
    schedule_type_enum = postgresql.ENUM(
        'work', 'personal', 'blocked',
        name='scheduletype',
        create_type=False
    )
    schedule_type_enum.create(op.get_bind(), checkfirst=True)

    # Create user_schedule_configs table
    op.create_table(
        'user_schedule_configs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'),
        sa.Column('work_days', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('work_start_time', sa.Time(), nullable=False),
        sa.Column('work_end_time', sa.Time(), nullable=False),
        sa.Column('day_overrides', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_schedule_configs_user_id', 'user_schedule_configs', ['user_id'], unique=True)

    # Create calendar_events table
    op.create_table(
        'calendar_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('schedule_type', postgresql.ENUM(name='scheduletype', create_type=False), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_datetime', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_datetime', sa.DateTime(timezone=True), nullable=False),
        sa.Column('all_day', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('rrule', sa.String(length=512), nullable=True),
        sa.Column('recurrence_end', sa.Date(), nullable=True),
        sa.Column('exdates', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('parent_event_id', sa.Uuid(), nullable=True),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_event_id'], ['calendar_events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_calendar_events_user_id', 'calendar_events', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_calendar_events_user_id', table_name='calendar_events')
    op.drop_table('calendar_events')
    op.drop_index('ix_user_schedule_configs_user_id', table_name='user_schedule_configs')
    op.drop_table('user_schedule_configs')
    op.execute('DROP TYPE IF EXISTS scheduletype')
