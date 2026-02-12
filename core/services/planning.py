from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

RACE_LONG_RUN_TARGET = {"5K": 75, "10K": 95, "Half Marathon": 130, "Marathon": 180}
SESSION_DAY_OFFSETS = [0, 1, 3, 5, 6, 2, 4]


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


def default_phase_session_tokens(phase: str, sessions_per_week: int) -> list[str]:
    """Return the default ordered list of session-type tokens for a training phase.

    Truncates the phase template to sessions_per_week entries.
    """
    phase_templates = {
        "Base": ["Easy Run", "Long Run", "Strides / Neuromuscular", "Recovery Run", "Easy Run", "Cross-Training Optional"],
        "Build": ["Tempo / Threshold", "VO2 Intervals", "Long Run", "Easy Run", "Hill Repeats", "Recovery Run"],
        "Peak": ["Race Pace", "VO2 Intervals", "Long Run", "Recovery Run", "Tempo / Threshold", "Easy Run"],
        "Taper": ["Taper / Openers", "Easy Run", "Race Pace", "Recovery Run", "Easy Run", "Cross-Training Optional"],
        "Recovery": ["Recovery Run", "Easy Run", "Cross-Training Optional", "Easy Run", "Recovery Run", "Cross-Training Optional"],
    }
    base = phase_templates.get(phase, phase_templates["Base"])
    return base[:sessions_per_week]


def assign_week_sessions(week_start: date, session_names: list[str]) -> list[dict]:
    """Assign session names to specific calendar days within a training week.

    Returns a list of dicts with keys: session_day (date), session_name (str).
    """
    assignments: list[dict] = []
    for idx, session_name in enumerate(session_names):
        offset = SESSION_DAY_OFFSETS[idx % len(SESSION_DAY_OFFSETS)]
        assignments.append({"session_day": week_start + timedelta(days=offset), "session_name": session_name})
    return assignments


def generate_plan_weeks(start_date: date, weeks: int, race_goal: str, sessions_per_week: int = 4, max_session_min: int = 120) -> list[dict]:
    """Generate a multi-week training plan with phased periodization for a given race goal.

    Returns a list of week dicts containing phase, target load, and session order.
    """
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
        sessions_order = default_phase_session_tokens(phase, sessions_per_week)
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
