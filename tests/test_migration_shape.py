from pathlib import Path


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
