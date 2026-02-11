from pathlib import Path


def test_intervention_timestamp_migration_present():
    text = Path("alembic/versions/20260211_0004_intervention_timestamps.py").read_text()
    assert "coach_interventions" in text
    assert "created_at" in text
    assert "ix_coach_interventions_created_at" in text

