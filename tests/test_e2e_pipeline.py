"""Integration tests for the full check-in → readiness → recommendation → intervention pipeline."""

from __future__ import annotations

from core.services.command_center import compose_recommendation, AthleteSignals
from core.services.interventions import generate_recommendation, can_auto_apply
from core.services.readiness import readiness_band, readiness_score


def test_full_pipeline_healthy_athlete():
    """Healthy athlete: high readiness, good adherence → monitor action."""
    sleep, energy, recovery, stress = 5, 4, 5, 1
    readiness = readiness_score(sleep, energy, recovery, stress)
    assert readiness >= 4.0
    assert readiness_band(readiness) == "green"

    rec = generate_recommendation(readiness=readiness, adherence=0.9, days_since_log=1, days_to_event=60)
    assert rec.action == "monitor"
    assert rec.risk_score <= 0.35
    assert rec.guardrail_pass is True


def test_full_pipeline_struggling_athlete():
    """Struggling athlete: low readiness, poor adherence → contact_athlete."""
    sleep, energy, recovery, stress = 1, 2, 1, 5
    readiness = readiness_score(sleep, energy, recovery, stress)
    assert readiness < 3.0
    assert readiness_band(readiness) == "red"

    rec = generate_recommendation(readiness=readiness, adherence=0.4, days_since_log=5, days_to_event=999)
    assert rec.action == "contact_athlete"
    assert rec.risk_score > 0.5


def test_full_pipeline_event_proximity_taper():
    """Athlete near race → taper recommendation."""
    readiness = readiness_score(4, 4, 4, 2)
    rec = generate_recommendation(readiness=readiness, adherence=0.8, days_since_log=1, days_to_event=7)
    assert rec.action == "taper_week"
    assert "event_proximity" in rec.why


def test_full_pipeline_compose_with_pain():
    """Pain flag escalates monitor to recovery_week."""
    signals = AthleteSignals(
        athlete_id=1,
        readiness=3.5,
        adherence=0.8,
        days_since_log=1,
        days_to_event=999,
        pain_recent=True,
        planned_sessions_14d=8,
        completed_sessions_14d=6,
    )
    rec = compose_recommendation(signals)
    assert rec.action == "recovery_week"
    assert "pain_flag_recent" in rec.why
    assert rec.risk_score > 0.2


def test_auto_apply_blocks_manual_mode():
    rec = generate_recommendation(readiness=4.0, adherence=0.9, days_since_log=1, days_to_event=999)
    assert can_auto_apply("manual", True, 0.7, 0.5, rec) is False


def test_auto_apply_allows_automatic_mode():
    rec = generate_recommendation(readiness=4.0, adherence=0.9, days_since_log=1, days_to_event=999)
    result = can_auto_apply("automatic", True, 0.5, 0.5, rec)
    assert result is True


def test_guardrail_blocks_high_risk():
    """Very high risk triggers guardrail."""
    rec = generate_recommendation(readiness=1.0, adherence=0.3, days_since_log=7, days_to_event=999)
    assert rec.risk_score > 0.5
    # Guardrail should block if risk > 0.85
    if rec.risk_score > 0.85:
        assert rec.guardrail_pass is False
