from datetime import date, datetime

from core.services.case_management import athlete_risk_bucket, build_case_timeline


def test_athlete_risk_bucket():
    assert athlete_risk_bucket(2.8, 0.9) == "at-risk"
    assert athlete_risk_bucket(3.2, 0.8) == "watch"
    assert athlete_risk_bucket(4.0, 0.9) == "stable"


def test_build_case_timeline_orders_desc():
    rows = build_case_timeline(
        coach_actions=[{"action": "intervention_accept", "created_at": datetime(2026, 2, 10, 8, 30), "payload": {"id": 1}}],
        training_logs=[{"date": date(2026, 2, 9), "session_category": "Easy Run", "rpe": 5, "pain_flag": False}],
        checkins=[{"day": date(2026, 2, 11), "sleep": 4, "energy": 4, "recovery": 3, "stress": 2}],
        events=[{"event_date": date(2026, 3, 1), "name": "Half Marathon", "distance": "Half Marathon"}],
        notes_tasks=[{"due_date": date(2026, 2, 12), "completed": False, "note": "Review long run file"}],
    )
    assert len(rows) == 5
    assert rows[0]["source"] == "event"
    assert rows[1]["source"] == "note_task"
    assert rows[2]["source"] == "checkin"

