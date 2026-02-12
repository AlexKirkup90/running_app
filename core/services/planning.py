from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from core.services.session_catalog import DISTANCE_PHASE_SPLITS, get_phase_sessions

RACE_LONG_RUN_TARGET = {
    "800m": 50,
    "1500m": 55,
    "Mile": 55,
    "3K": 65,
    "5K": 75,
    "10K": 95,
    "Half Marathon": 130,
    "Marathon": 180,
}
SESSION_DAY_OFFSETS = [0, 1, 3, 5, 6, 2, 4]


@dataclass
class WeekPlan:
    week_number: int
    phase: str
    target_load: float
    long_run_minutes: int
    sessions_order: list[str]


def _phase_for_week(week: int, total: int, race_goal: str | None = None) -> str:
    """Determine training phase for a given week using distance-aware splits.

    Every 4th week is a Recovery week. Otherwise the phase is determined by
    the week's position relative to distance-specific phase boundaries.
    """
    if week % 4 == 0:
        return "Recovery"

    splits = DISTANCE_PHASE_SPLITS.get(race_goal or "", (0.40, 0.70, 0.90))
    base_end, build_end, peak_end = splits

    ratio = week / total
    if ratio < base_end:
        return "Base"
    if ratio < build_end:
        return "Build"
    if ratio < peak_end:
        return "Peak"
    return "Taper"


def default_phase_session_tokens(
    phase: str,
    sessions_per_week: int,
    race_goal: str | None = None,
) -> list[str]:
    """Return the Daniels-informed session sequence for a training phase.

    Uses the session_catalog phase templates with specific workout types
    (Tempo Run, Cruise Intervals, VO2max Intervals, etc.) and selects
    distance-appropriate sessions when race_goal is provided.
    """
    return get_phase_sessions(phase, sessions_per_week, race_goal=race_goal)


def assign_week_sessions(week_start: date, session_names: list[str]) -> list[dict]:
    """Assign session names to specific calendar days within a training week.

    Returns a list of dicts with keys: session_day (date), session_name (str).
    """
    assignments: list[dict] = []
    for idx, session_name in enumerate(session_names):
        offset = SESSION_DAY_OFFSETS[idx % len(SESSION_DAY_OFFSETS)]
        assignments.append({"session_day": week_start + timedelta(days=offset), "session_name": session_name})
    return assignments


def generate_plan_weeks(
    start_date: date,
    weeks: int,
    race_goal: str,
    sessions_per_week: int = 4,
    max_session_min: int = 120,
) -> list[dict]:
    """Generate a multi-week training plan with Daniels-informed, distance-specific periodization.

    Uses distance-aware phase boundaries, race-goal-appropriate long-run
    targets, and distance-specific session templates. Returns a list of
    week dicts containing phase, target load, and session order.
    """
    target_lr = RACE_LONG_RUN_TARGET.get(race_goal, 90)
    rows: list[dict] = []
    for wk in range(1, weeks + 1):
        phase = _phase_for_week(wk, weeks, race_goal=race_goal)
        long_run = min(max_session_min, int(target_lr * min(1.0, wk / (weeks * 0.8))))
        if phase == "Recovery":
            long_run = int(long_run * 0.75)
        target_load = long_run * sessions_per_week * (1.1 if phase in {"Build", "Peak"} else 0.9)
        week_start = start_date + timedelta(days=(wk - 1) * 7)
        week_end = week_start + timedelta(days=6)
        sessions_order = default_phase_session_tokens(phase, sessions_per_week, race_goal=race_goal)
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
