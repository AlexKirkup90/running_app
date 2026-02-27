from __future__ import annotations

from core.config import get_settings


def readiness_score(sleep: int, energy: int, recovery: int, stress: int) -> float:
    # stress inverted
    return round((sleep + energy + recovery + (6 - stress)) / 4.0, 2)


def readiness_band(score: float) -> str:
    settings = get_settings()
    if score >= settings.readiness_green_min:
        return "green"
    if score >= settings.readiness_amber_min:
        return "amber"
    return "red"
