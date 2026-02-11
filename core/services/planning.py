from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

RACE_LONG_RUN_TARGET = {"5K": 75, "10K": 95, "Half Marathon": 130, "Marathon": 180}


@dataclass
class WeekPlan:
    week_number: int
    phase: str
    target_load: float
    long_run_minutes: int
    sessions_order: list[str]


def _phase_for_week(week: int, total: int) -> str:
    if week % 4 == 0:
        return "Recovery"
    ratio = week / total
    if ratio < 0.4:
        return "Base"
    if ratio < 0.75:
        return "Build"
    if ratio < 0.92:
        return "Peak"
    return "Taper"


def _sessions_for_phase(phase: str, sessions_per_week: int) -> list[str]:
    phase_templates = {
        "Base": ["Easy Run", "Long Run", "Strides / Neuromuscular", "Recovery Run", "Easy Run", "Cross-Training Optional"],
        "Build": ["Tempo / Threshold", "VO2 Intervals", "Long Run", "Easy Run", "Hill Repeats", "Recovery Run"],
        "Peak": ["Race Pace", "VO2 Intervals", "Long Run", "Recovery Run", "Tempo / Threshold", "Easy Run"],
        "Taper": ["Taper / Openers", "Easy Run", "Race Pace", "Recovery Run", "Easy Run", "Cross-Training Optional"],
        "Recovery": ["Recovery Run", "Easy Run", "Cross-Training Optional", "Easy Run", "Recovery Run", "Cross-Training Optional"],
    }
    base = phase_templates.get(phase, phase_templates["Base"])
    return base[:sessions_per_week]


def generate_plan_weeks(start_date: date, weeks: int, race_goal: str, sessions_per_week: int = 4, max_session_min: int = 120) -> list[dict]:
    target_lr = RACE_LONG_RUN_TARGET[race_goal]
    rows: list[dict] = []
    for wk in range(1, weeks + 1):
        phase = _phase_for_week(wk, weeks)
        long_run = min(max_session_min, int(target_lr * min(1.0, wk / (weeks * 0.8))))
        if phase == "Recovery":
            long_run = int(long_run * 0.75)
        target_load = long_run * sessions_per_week * (1.1 if phase in {"Build", "Peak"} else 0.9)
        week_start = start_date + timedelta(days=(wk - 1) * 7)
        week_end = week_start + timedelta(days=6)
        sessions_order = _sessions_for_phase(phase, sessions_per_week)
        rows.append(
            {
                "week_number": wk,
                "phase": phase,
                "week_start": week_start,
                "week_end": week_end,
                "target_load": round(target_load, 1),
                "sessions_order": sessions_order,
            }
        )
    return rows
