"""add_plans

Revision ID: a3f92b1c
Revises: d01dd6f8e87c
Create Date: 2026-03-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a3f92b1c'
down_revision: Union[str, None] = 'd01dd6f8e87c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('plans',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('planning_window_start', sa.Date(), nullable=False),
        sa.Column('planning_window_end', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('risk_summary', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('scope_type', postgresql.ENUM(name='scopetype', create_type=False), nullable=False),
        sa.Column('scope_id', sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('plan_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('plan_id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('rationale', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('plan_items')
    op.drop_table('plans')