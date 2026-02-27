"""add compiled session fields to plan_day_sessions

Revision ID: 20260223_0006
Revises: 20260223_0005
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20260223_0006"
down_revision = "20260223_0005"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    bind = op.get_bind()
    return bool(bind is not None and bind.dialect.name == "sqlite")


def upgrade() -> None:
    op.add_column("plan_day_sessions", sa.Column("source_template_id", sa.Integer(), nullable=True))
    op.add_column(
        "plan_day_sessions",
        sa.Column("compiled_session_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "plan_day_sessions",
        sa.Column("compiled_methodology", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column("plan_day_sessions", sa.Column("compiled_vdot", sa.Float(), nullable=True))
    op.add_column("plan_day_sessions", sa.Column("compiled_at", sa.DateTime(), nullable=True))
    op.add_column(
        "plan_day_sessions",
        sa.Column("compile_context_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_plan_day_sessions_source_template_id", "plan_day_sessions", ["source_template_id"])
    if not _is_sqlite():
        op.create_foreign_key(
            "fk_plan_day_sessions_source_template_id_sessions_library",
            "plan_day_sessions",
            "sessions_library",
            ["source_template_id"],
            ["id"],
        )


def downgrade() -> None:
    if not _is_sqlite():
        op.drop_constraint("fk_plan_day_sessions_source_template_id_sessions_library", "plan_day_sessions", type_="foreignkey")
    op.drop_index("ix_plan_day_sessions_source_template_id", table_name="plan_day_sessions")
    op.drop_column("plan_day_sessions", "compile_context_json")
    op.drop_column("plan_day_sessions", "compiled_at")
    op.drop_column("plan_day_sessions", "compiled_vdot")
    op.drop_column("plan_day_sessions", "compiled_methodology")
    op.drop_column("plan_day_sessions", "compiled_session_json")
    op.drop_column("plan_day_sessions", "source_template_id")
