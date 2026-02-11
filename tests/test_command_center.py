from core.services.command_center import AthleteSignals, compose_recommendation, derive_adherence, risk_priority


def test_risk_priority_bands():
    assert risk_priority(0.2) == "low"
    assert risk_priority(0.55) == "medium"
    assert risk_priority(0.8) == "high"


def test_derive_adherence_prefers_planned_completion():
    assert derive_adherence(10, 8, 9) == 0.8
    assert derive_adherence(0, 0, 3) == 1.0
    assert derive_adherence(0, 0, 0) == 0.5


def test_compose_recommendation_escalates_on_recent_pain():
    signals = AthleteSignals(
        athlete_id=1,
        readiness=4.2,
        adherence=0.95,
        days_since_log=0,
        days_to_event=42,
        pain_recent=True,
        planned_sessions_14d=8,
        completed_sessions_14d=8,
    )
    rec = compose_recommendation(signals)
    assert rec.action == "recovery_week"
    assert "pain_flag_recent" in rec.why
    assert rec.risk_score >= 0.35

