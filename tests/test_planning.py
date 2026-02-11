from datetime import date

from core.services.planning import assign_week_sessions, generate_plan_weeks


def test_plan_generation_length_and_cutback():
    weeks = generate_plan_weeks(date(2026, 1, 5), 12, "10K", sessions_per_week=4)
    assert len(weeks) == 12
    assert weeks[3]["phase"] == "Recovery"


def test_assign_week_sessions_spreads_days():
    week_start = date(2026, 1, 5)
    assignments = assign_week_sessions(week_start, ["A", "B", "C", "D"])
    assert [a["session_day"] for a in assignments] == [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 8), date(2026, 1, 10)]
