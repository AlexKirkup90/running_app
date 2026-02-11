from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Recommendation:
    action: str
    risk_score: float
    confidence_score: float
    expected_impact: dict
    factors: list[str]
    guardrail_pass: bool
    guardrail_reason: str


def make_recommendation(
    readiness_trend_value: float,
    adherence: float,
    days_since_last_log: int,
    days_to_event: int | None,
) -> Recommendation:
    factors: list[str] = []
    if readiness_trend_value < -0.8:
        factors.append("Readiness dropped")
    if adherence < 0.7:
        factors.append("Low adherence")
    if days_since_last_log > 4:
        factors.append("Missing logs")

    action = "monitor"
    if days_to_event is not None and days_to_event <= 14:
        action = "taper_week"
    elif readiness_trend_value < -1 and adherence < 0.6:
        action = "recovery_week"
    elif days_since_last_log > 6:
        action = "contact_athlete"

    risk = min(1.0, max(0.05, 0.6 - adherence + (0.2 if action == "recovery_week" else 0.05)))
    confidence = min(0.99, max(0.4, 0.7 + (-readiness_trend_value * 0.1)))
    guardrail = not (days_to_event is not None and days_to_event <= 7 and action in {"recovery_week", "taper_week"})
    reason = "race-week guardrail" if not guardrail else "pass"
    return Recommendation(
        action=action,
        risk_score=round(risk, 2),
        confidence_score=round(confidence, 2),
        expected_impact={"load_delta_pct": -18 if action in {"recovery_week", "taper_week"} else 0},
        factors=factors or ["Stable signals"],
        guardrail_pass=guardrail,
        guardrail_reason=reason,
    )
