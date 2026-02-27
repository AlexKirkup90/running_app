"""compatibility alias for missing historical revision

This is a no-op bridge revision used to reconnect environments that were
previously stamped/migrated with historical revision id ``20260211_0005``
which is no longer present in the local migration tree.

Revision ID: 20260211_0005
Revises: 20260211_0004
Create Date: 2026-02-23
"""

revision = "20260211_0005"
down_revision = "20260211_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Intentionally no-op. This revision exists only to bridge a missing
    # historical migration id referenced by some deployed databases.
    pass


def downgrade() -> None:
    # Intentionally no-op.
    pass
