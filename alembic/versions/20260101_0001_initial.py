"""initial schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260101_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athletes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_athletes_status", "athletes", ["status"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=120), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "sessions_library",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("tier", sa.String(length=30), nullable=False, server_default="medium"),
        sa.Column("is_treadmill", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("structure_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("prescription", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_sessions_library_category", "sessions_library", ["category"])

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("race_goal", sa.String(length=30), nullable=False),
        sa.Column("weeks", sa.Integer(), nullable=False),
        sa.Column("sessions_per_week", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("max_session_min", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("locked_until_week", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.create_index("ix_plans_athlete_id", "plans", ["athlete_id"])

    op.create_table(
        "plan_weeks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(length=30), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("sessions_order", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("target_load", sa.Float(), nullable=False, server_default="0"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("plan_id", "week_number", name="uq_plan_week"),
    )
    op.create_index("ix_plan_weeks_plan_id", "plan_weeks", ["plan_id"])

    op.create_table(
        "plan_week_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_week_id", sa.Integer(), sa.ForeignKey("plan_weeks.id"), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_load", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("ix_plan_week_metrics_plan_week_id", "plan_week_metrics", ["plan_week_id"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("distance", sa.String(length=30), nullable=False),
    )
    op.create_index("ix_events_athlete_id", "events", ["athlete_id"])

    op.create_table(
        "checkins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("sleep", sa.Integer(), nullable=False),
        sa.Column("energy", sa.Integer(), nullable=False),
        sa.Column("recovery", sa.Integer(), nullable=False),
        sa.Column("stress", sa.Integer(), nullable=False),
        sa.Column("training_today", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("athlete_id", "day", name="uq_checkin_athlete_day"),
        sa.CheckConstraint("sleep between 1 and 5"),
        sa.CheckConstraint("energy between 1 and 5"),
        sa.CheckConstraint("recovery between 1 and 5"),
        sa.CheckConstraint("stress between 1 and 5"),
    )
    op.create_index("ix_checkins_athlete_id", "checkins", ["athlete_id"])

    op.create_table(
        "training_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("session_category", sa.String(length=80), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rpe", sa.Integer(), nullable=False),
        sa.Column("load_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("pain_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("duration_min >= 0"),
        sa.CheckConstraint("distance_km >= 0"),
        sa.CheckConstraint("rpe between 1 and 10"),
        sa.CheckConstraint("load_score >= 0"),
    )
    op.create_index("ix_training_logs_athlete_id", "training_logs", ["athlete_id"])
    op.create_index("ix_training_logs_date", "training_logs", ["date"])
    op.create_index("ix_logs_athlete_date", "training_logs", ["athlete_id", "date"])

    op.create_table("session_reflections", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("training_log_id", sa.Integer(), sa.ForeignKey("training_logs.id"), nullable=False, unique=True), sa.Column("confidence", sa.Integer(), nullable=False, server_default="3"), sa.Column("reflection", sa.Text(), nullable=False, server_default=""))

    op.create_table("coach_action_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("coach_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False), sa.Column("action", sa.String(length=80), nullable=False), sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_coach_action_logs_athlete_id", "coach_action_logs", ["athlete_id"])

    op.create_table("coach_notes_tasks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False), sa.Column("note", sa.Text(), nullable=False), sa.Column("due_date", sa.Date(), nullable=True), sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("ix_coach_notes_tasks_athlete_id", "coach_notes_tasks", ["athlete_id"])

    op.create_table("coach_interventions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False), sa.Column("action_type", sa.String(length=80), nullable=False), sa.Column("status", sa.String(length=30), nullable=False, server_default="open"), sa.Column("risk_score", sa.Float(), nullable=False, server_default="0"), sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"), sa.Column("expected_impact", sa.JSON(), nullable=False, server_default="{}"), sa.Column("why_factors", sa.JSON(), nullable=False, server_default="[]"), sa.Column("guardrail_pass", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("guardrail_reason", sa.String(length=255), nullable=False, server_default="ok"), sa.Column("cooldown_until", sa.DateTime(), nullable=True))
    op.create_index("ix_coach_interventions_athlete_id", "coach_interventions", ["athlete_id"])
    op.execute("CREATE UNIQUE INDEX uq_open_recommendation ON coach_interventions (athlete_id, action_type) WHERE status = 'open'")

    op.create_table("athlete_preferences", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False, unique=True), sa.Column("reminder_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("reminder_training_days", sa.JSON(), nullable=False, server_default="[]"), sa.Column("privacy_ack", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("automation_mode", sa.String(length=20), nullable=False, server_default="manual"), sa.Column("auto_apply_low_risk", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("auto_apply_confidence_min", sa.Float(), nullable=False, server_default="0.8"), sa.Column("auto_apply_risk_max", sa.Float(), nullable=False, server_default="0.3"))

    op.create_table("app_write_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("scope", sa.String(length=80), nullable=False), sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True), sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_table("app_runtime_errors", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("page", sa.String(length=80), nullable=False), sa.Column("error_message", sa.Text(), nullable=False), sa.Column("traceback", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))

    op.create_table("import_runs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("adapter_name", sa.String(length=80), nullable=False), sa.Column("status", sa.String(length=20), nullable=False, server_default="started"), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_table("import_items", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("import_run_id", sa.Integer(), sa.ForeignKey("import_runs.id"), nullable=False), sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=True), sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"), sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"), sa.Column("message", sa.String(length=255), nullable=False, server_default=""))
    op.create_index("ix_import_items_import_run_id", "import_items", ["import_run_id"])


def downgrade() -> None:
    for table in [
        "import_items","import_runs","app_runtime_errors","app_write_logs","athlete_preferences","coach_interventions","coach_notes_tasks","coach_action_logs","session_reflections","training_logs","checkins","events","plan_week_metrics","plan_weeks","plans","sessions_library","users","athletes",
    ]:
        op.drop_table(table)
