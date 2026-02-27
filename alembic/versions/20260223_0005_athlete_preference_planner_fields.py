"""add athlete preference planner fields

Revision ID: 20260223_0005
Revises: 20260211_0004
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20260223_0005"
down_revision = "20260211_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "athlete_preferences",
        sa.Column("preferred_training_days", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "athlete_preferences",
        sa.Column("preferred_long_run_day", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("athlete_preferences", "preferred_long_run_day")
    op.drop_column("athlete_preferences", "preferred_training_days")
