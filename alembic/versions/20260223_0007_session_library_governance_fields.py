"""add session library governance fields

Revision ID: 20260223_0007
Revises: 20260223_0006
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20260223_0007"
down_revision = "20260223_0006"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    bind = op.get_bind()
    return bool(bind is not None and bind.dialect.name == "sqlite")


def upgrade() -> None:
    op.add_column(
        "sessions_library",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column("sessions_library", sa.Column("duplicate_of_template_id", sa.Integer(), nullable=True))
    op.create_index("ix_sessions_library_status", "sessions_library", ["status"])
    if not _is_sqlite():
        op.create_foreign_key(
            "fk_sessions_library_duplicate_of_template_id_sessions_library",
            "sessions_library",
            "sessions_library",
            ["duplicate_of_template_id"],
            ["id"],
        )


def downgrade() -> None:
    if not _is_sqlite():
        op.drop_constraint(
            "fk_sessions_library_duplicate_of_template_id_sessions_library",
            "sessions_library",
            type_="foreignkey",
        )
    op.drop_index("ix_sessions_library_status", table_name="sessions_library")
    op.drop_column("sessions_library", "duplicate_of_template_id")
    op.drop_column("sessions_library", "status")
