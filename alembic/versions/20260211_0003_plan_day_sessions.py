"""add plan day sessions

Revision ID: 20260211_0003
Revises: 20260211_0002
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260211_0003"
down_revision = "20260211_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_day_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_week_id", sa.Integer(), sa.ForeignKey("plan_weeks.id"), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("session_day", sa.Date(), nullable=False),
        sa.Column("session_name", sa.String(length=200), nullable=False),
        sa.Column("source_template_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.UniqueConstraint("athlete_id", "session_day", name="uq_plan_day_session_athlete_day"),
        sa.UniqueConstraint("plan_week_id", "session_day", name="uq_plan_day_session_week_day"),
    )
    op.create_index("ix_plan_day_sessions_plan_week_id", "plan_day_sessions", ["plan_week_id"])
    op.create_index("ix_plan_day_sessions_athlete_id", "plan_day_sessions", ["athlete_id"])
    op.create_index("ix_plan_day_sessions_session_day", "plan_day_sessions", ["session_day"])


def downgrade() -> None:
    op.drop_table("plan_day_sessions")
