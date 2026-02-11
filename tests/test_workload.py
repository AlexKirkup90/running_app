from datetime import datetime, timedelta

from core.services.workload import intervention_age_hours, queue_snapshot


def test_intervention_age_hours():
    now = datetime(2026, 2, 11, 12, 0, 0)
    created = now - timedelta(hours=25, minutes=30)
    assert intervention_age_hours(created, now) == 25.5


def test_queue_snapshot_sla():
    now = datetime(2026, 2, 11, 12, 0, 0)
    rows = [
        {"risk": 0.8, "is_snoozed": False, "created_at": now - timedelta(hours=80)},
        {"risk": 0.6, "is_snoozed": False, "created_at": now - timedelta(hours=30)},
        {"risk": 0.3, "is_snoozed": True, "created_at": now - timedelta(hours=10)},
    ]
    snap = queue_snapshot(rows, now)
    assert snap.open_count == 3
    assert snap.high_priority == 1
    assert snap.actionable_now == 2
    assert snap.snoozed == 1
    assert snap.sla_due_24h == 2
    assert snap.sla_due_72h == 1
    assert snap.median_age_hours == 30.0
    assert snap.oldest_age_hours == 80.0

