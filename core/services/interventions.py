from __future__ import annotations

from dataclasses import dataclass

from core.config import get_settings


@dataclass
class Recommendation:
    action: str
    risk_score: float
    confidence_score: float
    expected_impact: dict
    why: list[str]
    guardrail_pass: bool
    guardrail_reason: str


def generate_recommendation(readiness: float, adherence: float, days_since_log: int, days_to_event: int) -> Recommendation:
    settings = get_settings()
    factors: list[str] = []
    risk = settings.intervention_base_risk
    conf = settings.intervention_base_confidence
    action = settings.intervention_action_monitor

    if readiness < settings.intervention_low_readiness_threshold:
        factors.append("low_readiness")
        risk += settings.intervention_low_readiness_risk_bump
        action = settings.intervention_action_recovery_week
    if adherence < settings.intervention_low_adherence_threshold:
        factors.append("low_adherence")
        action = settings.intervention_action_contact_athlete
        conf += settings.intervention_low_adherence_confidence_bump
    if days_since_log > settings.intervention_no_recent_logs_days:
        factors.append("no_recent_logs")
        action = settings.intervention_action_contact_athlete
        risk += settings.intervention_no_recent_logs_risk_bump
    if 0 < days_to_event <= settings.intervention_event_proximity_days:
        factors.append("event_proximity")
        action = settings.intervention_action_taper_week

    risk = min(1.0, round(risk, 2))
    conf = min(0.99, round(conf, 2))
    guardrail_pass = risk <= settings.intervention_guardrail_risk_max
    reason = "ok" if guardrail_pass else "risk_too_high"

    return Recommendation(
        action=action,
        risk_score=risk,
        confidence_score=conf,
        expected_impact={
            "fatigue_delta": -0.2
            if action in {settings.intervention_action_recovery_week, settings.intervention_action_taper_week}
            else 0.0
        },
        why=factors or ["stable"],
        guardrail_pass=guardrail_pass,
        guardrail_reason=reason,
    )


def can_auto_apply(mode: str, low_risk_only: bool, confidence_min: float, risk_max: float, recommendation: Recommendation) -> bool:
    if not recommendation.guardrail_pass:
        return False
    if mode == "manual":
        return False
    if mode == "assisted" and not low_risk_only:
        return False
    return recommendation.confidence_score >= confidence_min and recommendation.risk_score <= risk_max
