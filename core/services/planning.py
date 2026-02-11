from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

RACE_LONG_RUN_TARGET = {"5K": 90, "10K": 105, "Half Marathon": 140, "Marathon": 190}


@dataclass
class WeekPlan:
    week_index: int
    start_date: dt.date
    phase: str
    focus: str
    target_load: float
    sessions_order: list[str]


def _phase_for_week(week: int, total: int) -> str:
    ratio = week / total
    if ratio < 0.4:
        return "Base"
    if ratio < 0.75:
        return "Build"
    if ratio < 0.9:
        return "Peak"
    return "Taper"


def generate_plan(start_date: dt.date, race_goal: str, weeks: int, sessions_per_week: int = 4) -> list[WeekPlan]:
    long_cap = RACE_LONG_RUN_TARGET[race_goal]
    plans: list[WeekPlan] = []
    for i in range(1, weeks + 1):
        phase = _phase_for_week(i, weeks)
        cutback = i % 4 == 0
        base_load = 180 + i * (8 if race_goal in {"Half Marathon", "Marathon"} else 5)
        load = base_load * (0.75 if cutback else 1.0)
        long_run = min(long_cap, int(50 + i * (long_cap - 50) / weeks))
        focus = f"{phase} focus with long run {long_run} min"
        sessions = ["Easy Run", "Quality", "Easy Run", "Long Run", "Recovery Run", "Strides"][:sessions_per_week]
        plans.append(
            WeekPlan(
                week_index=i,
                start_date=start_date + dt.timedelta(days=(i - 1) * 7),
                phase=phase,
                focus=focus,
                target_load=round(load, 2),
                sessions_order=sessions,
            )
        )
    return plans
