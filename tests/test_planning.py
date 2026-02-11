from datetime import date

from core.services.planning import generate_plan_weeks


def test_plan_generation_length_and_cutback():
    weeks = generate_plan_weeks(date(2026, 1, 5), 12, "10K", sessions_per_week=4)
    assert len(weeks) == 12
    assert weeks[3]["phase"] == "Recovery"
