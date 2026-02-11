from pathlib import Path


def test_latest_revision_file_exists():
    p = Path("alembic/versions/0002_policy_hardening.py")
    assert p.exists()


def test_schema_contains_required_tables():
    schema = Path("db/schema.sql").read_text(encoding="utf-8")
    for t in ["athlete_preferences", "coach_interventions", "app_runtime_errors"]:
        assert f"create table if not exists {t}" in schema
