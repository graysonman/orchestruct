"""add google oauth fields to users

Revision ID: h8g36i7d
Revises: g7f25h6c
Create Date: 2026-03-31

"""
from alembic import op
import sqlalchemy as sa

revision = "h8g36i7d"
down_revision = "g7f25h6c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("google_id", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_users_google_id", "users", ["google_id"])
    op.add_column("users", sa.Column("google_access_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_refresh_token", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("google_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("users", "hashed_password", nullable=True)


def downgrade():
    op.alter_column("users", "hashed_password", nullable=False)
    op.drop_column("users", "google_token_expires_at")
    op.drop_column("users", "google_refresh_token")
    op.drop_column("users", "google_access_token")
    op.drop_constraint("uq_users_google_id", "users", type_="unique")
    op.drop_column("users", "google_id")
