"""baseline schema"""

from pathlib import Path

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_sql = Path("db/schema.sql").read_text(encoding="utf-8")
    op.execute(schema_sql)


def downgrade() -> None:
    for t in [
        "import_items",
        "import_runs",
        "app_runtime_errors",
        "app_write_logs",
        "athlete_preferences",
        "coach_interventions",
        "coach_notes_tasks",
        "coach_action_logs",
        "session_reflections",
        "training_logs",
        "checkins",
        "events",
        "plan_week_metrics",
        "plan_weeks",
        "plans",
        "sessions_library",
        "users",
        "athletes",
    ]:
        op.execute(f"drop table if exists {t} cascade")
