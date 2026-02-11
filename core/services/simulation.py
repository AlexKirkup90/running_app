from __future__ import annotations


def scenario_missed_week(target_load: float) -> float:
    return round(target_load * 0.85, 2)


def scenario_injury_week(target_load: float) -> float:
    return round(target_load * 0.55, 2)
