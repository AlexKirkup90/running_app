"""add Phase 3-8 schema: vdot, wearables, community, orgs, training log sources

Revision ID: 20260211_0005
Revises: 20260211_0004
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260211_0005"
down_revision = "20260211_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── athletes: VDOT score ─────────────────────────────────────────────
    op.add_column("athletes", sa.Column("vdot_score", sa.Integer(), nullable=True))

    # ── training_logs: wearable source tracking ──────────────────────────
    op.add_column("training_logs", sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"))
    op.add_column("training_logs", sa.Column("source_id", sa.String(length=120), nullable=True))

    # ── wearable_connections ─────────────────────────────────────────────
    op.create_table(
        "wearable_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("service", sa.String(length=40), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False, server_default=""),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("external_athlete_id", sa.String(length=120), nullable=True),
        sa.Column("scope", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("sync_cursor", sa.String(length=255), nullable=True),
        sa.Column("sync_status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("athlete_id", "service", name="uq_wearable_athlete_service"),
    )
    op.create_index("ix_wearable_connections_athlete_id", "wearable_connections", ["athlete_id"])

    # ── sync_logs ────────────────────────────────────────────────────────
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("service", sa.String(length=40), nullable=False),
        sa.Column("sync_type", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="started"),
        sa.Column("activities_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activities_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activities_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sync_logs_athlete_id", "sync_logs", ["athlete_id"])

    # ── Community & Social ───────────────────────────────────────────────
    op.create_table(
        "training_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("privacy", sa.String(length=20), nullable=False, server_default="public"),
        sa.Column("max_members", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "group_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("training_groups.id"), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("group_id", "athlete_id", name="uq_group_member"),
    )
    op.create_index("ix_group_memberships_group_id", "group_memberships", ["group_id"])
    op.create_index("ix_group_memberships_athlete_id", "group_memberships", ["athlete_id"])

    op.create_table(
        "challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("training_groups.id"), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("challenge_type", sa.String(length=40), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "challenge_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("challenge_id", "athlete_id", name="uq_challenge_entry"),
    )
    op.create_index("ix_challenge_entries_challenge_id", "challenge_entries", ["challenge_id"])
    op.create_index("ix_challenge_entries_athlete_id", "challenge_entries", ["athlete_id"])

    op.create_table(
        "group_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("training_groups.id"), nullable=False),
        sa.Column("author_athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_group_messages_group_id", "group_messages", ["group_id"])

    op.create_table(
        "kudos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("to_athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("training_log_id", sa.Integer(), sa.ForeignKey("training_logs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("from_athlete_id", "to_athlete_id", "training_log_id", name="uq_kudos"),
    )
    op.create_index("ix_kudos_from_athlete_id", "kudos", ["from_athlete_id"])
    op.create_index("ix_kudos_to_athlete_id", "kudos", ["to_athlete_id"])

    # ── Team & Organization ──────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("tier", sa.String(length=30), nullable=False, server_default="free"),
        sa.Column("max_coaches", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_athletes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "org_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("org_role", sa.String(length=30), nullable=False),
        sa.Column("caseload_cap", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_user"),
    )
    op.create_index("ix_org_memberships_org_id", "org_memberships", ["org_id"])
    op.create_index("ix_org_memberships_user_id", "org_memberships", ["user_id"])

    op.create_table(
        "coach_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("coach_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "athlete_id", name="uq_org_athlete_assignment"),
    )
    op.create_index("ix_coach_assignments_org_id", "coach_assignments", ["org_id"])
    op.create_index("ix_coach_assignments_coach_user_id", "coach_assignments", ["coach_user_id"])
    op.create_index("ix_coach_assignments_athlete_id", "coach_assignments", ["athlete_id"])


def downgrade() -> None:
    op.drop_table("coach_assignments")
    op.drop_table("org_memberships")
    op.drop_table("organizations")
    op.drop_table("kudos")
    op.drop_table("group_messages")
    op.drop_table("challenge_entries")
    op.drop_table("challenges")
    op.drop_table("group_memberships")
    op.drop_table("training_groups")
    op.drop_table("sync_logs")
    op.drop_table("wearable_connections")
    op.drop_column("training_logs", "source_id")
    op.drop_column("training_logs", "source")
    op.drop_column("athletes", "vdot_score")
