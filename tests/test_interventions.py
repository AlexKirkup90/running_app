from core.services.interventions import can_auto_apply, generate_recommendation


def test_recommendation_mapping():
    rec = generate_recommendation(readiness=2.4, adherence=0.9, days_since_log=1, days_to_event=40)
    assert rec.action == "recovery_week"
    assert rec.risk_score > 0.2


def test_auto_apply_logic():
    rec = generate_recommendation(readiness=4.0, adherence=0.95, days_since_log=0, days_to_event=60)
    assert can_auto_apply("assisted", True, 0.7, 0.5, rec)
