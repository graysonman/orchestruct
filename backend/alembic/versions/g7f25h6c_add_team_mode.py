"""add team mode

Revision ID: g7f25h6c
Revises: f6e14g5b
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g7f25h6c"
down_revision = "f6e14g5b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "team_memberships",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "plan_items",
        sa.Column(
            "assigned_to_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        None, "plan_items", "users", ["assigned_to_user_id"], ["id"]
    )


def downgrade():
    op.drop_constraint(None, "plan_items", type_="foreignkey")
    op.drop_column("plan_items", "assigned_to_user_id")
    op.drop_column("team_memberships", "is_admin")
