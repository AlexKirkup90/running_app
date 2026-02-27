from pathlib import Path

from alembic import command
from alembic.config import Config

from core.config import get_settings


def test_required_tables_present_in_migration():
    text = Path("alembic/versions/20260101_0001_initial.py").read_text()
    required = [
        "athletes",
        "users",
        "sessions_library",
        "plans",
        "plan_weeks",
        "plan_week_metrics",
        "events",
        "checkins",
        "training_logs",
        "session_reflections",
        "coach_action_logs",
        "coach_notes_tasks",
        "coach_interventions",
        "athlete_preferences",
        "app_write_logs",
        "app_runtime_errors",
        "import_runs",
        "import_items",
    ]
    for t in required:
        assert f'"{t}"' in text


def test_migrations_avoid_postgres_now_function_for_portability():
    migrations_dir = Path("alembic/versions")
    for migration_file in migrations_dir.glob("*.py"):
        text = migration_file.read_text(encoding="utf-8").lower()
        assert "now()" not in text, f"Non-portable now() found in {migration_file.name}"


def test_alembic_upgrade_head_succeeds_on_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    get_settings.cache_clear()
