"""add plan names

Revision ID: 20260224_0009
Revises: 20260224_0008
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20260224_0009"
down_revision = "20260224_0008"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    bind = op.get_bind()
    return bool(bind is not None and bind.dialect.name == "sqlite")


def upgrade() -> None:
    op.add_column("plans", sa.Column("name", sa.String(length=200), nullable=True))
    op.execute(
        """
        UPDATE plans
        SET name = COALESCE(NULLIF(TRIM(race_goal), ''), 'Plan') || ' Plan #' || id
        WHERE name IS NULL OR TRIM(name) = ''
        """
    )
    if _is_sqlite():
        with op.batch_alter_table("plans") as batch_op:
            batch_op.alter_column("name", existing_type=sa.String(length=200), nullable=False)
    else:
        op.alter_column("plans", "name", existing_type=sa.String(length=200), nullable=False)


def downgrade() -> None:
    op.drop_column("plans", "name")
