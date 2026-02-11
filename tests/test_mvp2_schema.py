from pathlib import Path


def test_plan_day_sessions_migration_present():
    text = Path("alembic/versions/20260211_0003_plan_day_sessions.py").read_text()
    assert "plan_day_sessions" in text
    assert "uq_plan_day_session_athlete_day" in text
