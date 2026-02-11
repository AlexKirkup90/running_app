from __future__ import annotations


def readiness_score(sleep: int, energy: int, recovery: int, stress: int) -> float:
    # stress inverted
    return round((sleep + energy + recovery + (6 - stress)) / 4.0, 2)


def readiness_band(score: float) -> str:
    if score >= 4:
        return "green"
    if score >= 3:
        return "amber"
    return "red"
