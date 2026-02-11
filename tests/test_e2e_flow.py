import datetime as dt

from core.services.planning import generate_plan
from core.services.readiness import readiness_score


def test_critical_flow_plan_and_readiness():
    plan = generate_plan(dt.date.today(), "10K", 12, 4)
    assert plan[0].sessions_order
    score = readiness_score(4, 4, 3, 2)
    assert score > 3
