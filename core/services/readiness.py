from __future__ import annotations


def readiness_score(sleep: int, energy: int, recovery: int, stress: int) -> float:
    """Compute a readiness score (1-5 scale) from daily check-in metrics.

    Stress is inverted so higher stress lowers the score. Returns a rounded float.
    """
    # stress inverted
    return round((sleep + energy + recovery + (6 - stress)) / 4.0, 2)


def readiness_band(score: float) -> str:
    """Map a readiness score to a traffic-light band: 'green', 'amber', or 'red'."""
    if score >= 4:
        return "green"
    if score >= 3:
        return "amber"
    return "red"
