from __future__ import annotations


def athlete_risk_bucket(readiness: float, adherence: float) -> str:
    if readiness < 3 or adherence < 0.7:
        return "at-risk"
    if readiness < 3.5:
        return "watch"
    return "stable"
