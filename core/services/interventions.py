from __future__ import annotations

from dataclasses import dataclass


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
    """Generate a coaching Recommendation based on athlete readiness, adherence, and event proximity.

    Returns a Recommendation with action, risk/confidence scores, and guardrail status.
    """
    factors: list[str] = []
    risk = 0.2
    conf = 0.75
    action = "monitor"

    if readiness < 2.8:
        factors.append("low_readiness")
        risk += 0.25
        action = "recovery_week"
    if adherence < 0.6:
        factors.append("low_adherence")
        action = "contact_athlete"
        conf += 0.05
    if days_since_log > 4:
        factors.append("no_recent_logs")
        action = "contact_athlete"
        risk += 0.1
    if 0 < days_to_event <= 14:
        factors.append("event_proximity")
        action = "taper_week"

    risk = min(1.0, round(risk, 2))
    conf = min(0.99, round(conf, 2))
    guardrail_pass = risk <= 0.85
    reason = "ok" if guardrail_pass else "risk_too_high"

    return Recommendation(
        action=action,
        risk_score=risk,
        confidence_score=conf,
        expected_impact={"fatigue_delta": -0.2 if action in {"recovery_week", "taper_week"} else 0.0},
        why=factors or ["stable"],
        guardrail_pass=guardrail_pass,
        guardrail_reason=reason,
    )


def can_auto_apply(mode: str, low_risk_only: bool, confidence_min: float, risk_max: float, recommendation: Recommendation) -> bool:
    """Determine whether a recommendation can be auto-applied given automation settings.

    Checks guardrail status, mode constraints, and confidence/risk thresholds. Returns True if eligible.
    """
    if not recommendation.guardrail_pass:
        return False
    if mode == "manual":
        return False
    if mode == "assisted" and not low_risk_only:
        return False
    return recommendation.confidence_score >= confidence_min and recommendation.risk_score <= risk_max
