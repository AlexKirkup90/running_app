from core.services.interventions import make_recommendation


def test_intervention_mapping_recovery():
    rec = make_recommendation(-1.2, 0.5, 2, 40)
    assert rec.action == "recovery_week"
    assert rec.guardrail_pass


def test_intervention_guardrail():
    rec = make_recommendation(-1.5, 0.4, 1, 5)
    assert not rec.guardrail_pass
