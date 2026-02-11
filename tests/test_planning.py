import datetime as dt

from core.services.planning import generate_plan


def test_generate_plan_length_and_cutbacks():
    plan = generate_plan(dt.date(2025, 1, 6), "Marathon", 12, 4)
    assert len(plan) == 12
    assert plan[3].target_load < plan[2].target_load
    assert "long run" in plan[-1].focus.lower()
