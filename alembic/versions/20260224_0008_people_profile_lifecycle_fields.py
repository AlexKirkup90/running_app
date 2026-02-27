"""add people profile and lifecycle fields

Revision ID: 20260224_0008
Revises: 20260223_0007
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20260224_0008"
down_revision = "20260223_0007"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    bind = op.get_bind()
    return bool(bind is not None and bind.dialect.name == "sqlite")


def upgrade() -> None:
    op.add_column("users", sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))
    op.create_index("ix_users_status", "users", ["status"])

    op.add_column("athletes", sa.Column("vdot_seed", sa.Float(), nullable=True))
    op.add_column("athletes", sa.Column("pace_source", sa.String(length=30), nullable=False, server_default="manual"))
    op.add_column("athletes", sa.Column("assigned_coach_user_id", sa.Integer(), nullable=True))
    op.create_index("ix_athletes_assigned_coach_user_id", "athletes", ["assigned_coach_user_id"])
    if not _is_sqlite():
        op.create_foreign_key(
            "fk_athletes_assigned_coach_user_id_users",
            "athletes",
            "users",
            ["assigned_coach_user_id"],
            ["id"],
        )


def downgrade() -> None:
    if not _is_sqlite():
        op.drop_constraint("fk_athletes_assigned_coach_user_id_users", "athletes", type_="foreignkey")
    op.drop_index("ix_athletes_assigned_coach_user_id", table_name="athletes")
    op.drop_column("athletes", "assigned_coach_user_id")
    op.drop_column("athletes", "pace_source")
    op.drop_column("athletes", "vdot_seed")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_column("users", "status")
