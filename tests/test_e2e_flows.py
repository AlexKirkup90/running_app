from datetime import date

from core.services.interventions import generate_recommendation
from core.services.planning import generate_plan_weeks
from core.services.readiness import readiness_score


def test_critical_flow_plan_readiness_reco():
    weeks = generate_plan_weeks(date.today(), 12, "Half Marathon", 4)
    assert weeks[0]["week_number"] == 1
    readiness = readiness_score(2, 2, 2, 4)
    rec = generate_recommendation(readiness, adherence=0.5, days_since_log=5, days_to_event=10)
    assert rec.action in {"taper_week", "contact_athlete", "recovery_week"}
