from __future__ import annotations


def readiness_score(sleep: int, energy: int, recovery: int, stress: int) -> float:
    stress_adj = 6 - stress
    return round((sleep + energy + recovery + stress_adj) / 4, 2)


def readiness_trend(scores: list[float]) -> float:
    if len(scores) < 2:
        return 0.0
    return round(scores[-1] - sum(scores[:-1]) / (len(scores) - 1), 2)
