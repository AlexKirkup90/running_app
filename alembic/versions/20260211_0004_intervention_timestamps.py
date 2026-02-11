"""add intervention created_at timestamp

Revision ID: 20260211_0004
Revises: 20260211_0003
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260211_0004"
down_revision = "20260211_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "coach_interventions",
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_coach_interventions_created_at", "coach_interventions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_coach_interventions_created_at", table_name="coach_interventions")
    op.drop_column("coach_interventions", "created_at")

