from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Optional

RACE_LONG_RUN_TARGET = {"5K": 75, "10K": 95, "Half Marathon": 130, "Marathon": 180}
SESSION_DAY_OFFSETS = [0, 1, 3, 5, 6, 2, 4]
DAY_TO_INDEX = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
INDEX_TO_DAY = {v: k for k, v in DAY_TO_INDEX.items()}
QUALITY_PATTERNS = [
    re.compile(r"\btempo\b", re.I),
    re.compile(r"\bthreshold\b", re.I),
    re.compile(r"\bvo2\b", re.I),
    re.compile(r"\binterval", re.I),
    re.compile(r"\bhill", re.I),
    re.compile(r"\brace pace\b", re.I),
    re.compile(r"\b(?:T|I|R)\s*pace", re.I),
]


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
    phase_templates = {
        "Base": ["Easy Run", "Long Run", "Strides / Neuromuscular", "Recovery Run", "Easy Run", "Cross-Training Optional"],
        "Build": ["Tempo / Threshold", "VO2 Intervals", "Long Run", "Easy Run", "Hill Repeats", "Recovery Run"],
        "Peak": ["Race Pace", "VO2 Intervals", "Long Run", "Recovery Run", "Tempo / Threshold", "Easy Run"],
        "Taper": ["Taper / Openers", "Easy Run", "Race Pace", "Recovery Run", "Easy Run", "Cross-Training Optional"],
        "Recovery": ["Recovery Run", "Easy Run", "Cross-Training Optional", "Easy Run", "Recovery Run", "Cross-Training Optional"],
    }
    base = phase_templates.get(phase, phase_templates["Base"])
    return base[:sessions_per_week]


def _is_long_run(session_name: str) -> bool:
    text = (session_name or "").strip().lower()
    return ("long run" in text) or ("marathon pace run" in text)


def _is_quality_session(session_name: str) -> bool:
    text = (session_name or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if "recovery" in lowered or "easy run" in lowered:
        return False
    if "marathon pace run" in lowered:
        return True
    return any(p.search(text) for p in QUALITY_PATTERNS)


def _normalize_preferred_days(preferred_days: Optional[list[str]]) -> list[int]:
    if not preferred_days:
        return []
    seen: set[int] = set()
    order: list[int] = []
    for day in preferred_days:
        key = str(day or "").strip()[:3].title()
        idx = DAY_TO_INDEX.get(key)
        if idx is None or idx in seen:
            continue
        seen.add(idx)
        order.append(idx)
    return order


def _choose_day_for_session(
    available_days: set[int],
    ordered_candidates: list[int],
    is_quality: bool,
    quality_days: set[int],
) -> int:
    if not available_days:
        raise ValueError("No available days remain for session assignment")
    ranked = [d for d in ordered_candidates if d in available_days]
    ranked.extend(sorted(d for d in available_days if d not in ranked))
    if not is_quality:
        return ranked[0]

    def violates(day: int) -> bool:
        return (day - 1 in quality_days) or (day + 1 in quality_days)

    safe = [d for d in ranked if not violates(d)]
    return safe[0] if safe else ranked[0]


def assign_week_sessions(
    week_start: date,
    session_names: list[str],
    preferred_days: Optional[list[str]] = None,
    preferred_long_run_day: Optional[str] = None,
) -> list[dict]:
    if not preferred_days and preferred_long_run_day is None:
        assignments: list[dict] = []
        for idx, session_name in enumerate(session_names):
            offset = SESSION_DAY_OFFSETS[idx % len(SESSION_DAY_OFFSETS)]
            assignments.append({"session_day": week_start + timedelta(days=offset), "session_name": session_name})
        return assignments

    preferred_day_indices = _normalize_preferred_days(preferred_days)
    if not preferred_day_indices:
        preferred_day_indices = [0, 2, 4, 6]

    if preferred_long_run_day:
        long_run_key = str(preferred_long_run_day).strip()[:3].title()
        long_run_day_idx = DAY_TO_INDEX.get(long_run_key, 6)
    else:
        long_run_day_idx = preferred_day_indices[-1] if preferred_day_indices else 6

    # Preferred ordering first, then the rest of the week to keep the scheduler flexible.
    ordered_candidates = list(preferred_day_indices)
    if long_run_day_idx not in ordered_candidates:
        ordered_candidates.append(long_run_day_idx)
    ordered_candidates.extend([d for d in range(7) if d not in ordered_candidates])

    available_days = set(range(7))
    chosen_by_idx: dict[int, int] = {}
    quality_days: set[int] = set()

    # Place the long run anchor first if present.
    for idx, name in enumerate(session_names):
        if _is_long_run(name):
            day_idx = long_run_day_idx if long_run_day_idx in available_days else _choose_day_for_session(
                available_days, ordered_candidates, _is_quality_session(name), quality_days
            )
            chosen_by_idx[idx] = day_idx
            available_days.discard(day_idx)
            if _is_quality_session(name):
                quality_days.add(day_idx)
            break

    for idx, name in enumerate(session_names):
        if idx in chosen_by_idx:
            continue
        quality = _is_quality_session(name)
        day_idx = _choose_day_for_session(available_days, ordered_candidates, quality, quality_days)
        chosen_by_idx[idx] = day_idx
        available_days.discard(day_idx)
        if quality:
            quality_days.add(day_idx)

    assignments: list[dict] = []
    for idx, session_name in enumerate(session_names):
        assignments.append(
            {
                "session_day": week_start + timedelta(days=int(chosen_by_idx[idx])),
                "session_name": session_name,
            }
        )
    return assignments


def generate_plan_weeks(start_date: date, weeks: int, race_goal: str, sessions_per_week: int = 4, max_session_min: int = 120) -> list[dict]:
    target_lr = RACE_LONG_RUN_TARGET[race_goal]
    rows: list[dict] = []
    total_recovery_weeks = weeks // 4
    total_build_like_weeks = max(1, weeks - total_recovery_weeks)
    non_recovery_count = 0
    last_non_recovery_long_run: Optional[int] = None
    last_non_recovery_load: Optional[float] = None

    for wk in range(1, weeks + 1):
        phase = _phase_for_week(wk, weeks)
        if phase == "Recovery":
            anchor_lr = last_non_recovery_long_run if last_non_recovery_long_run is not None else int(target_lr * 0.55)
            long_run = max(45, int(round(anchor_lr * 0.78)))
            anchor_load = last_non_recovery_load if last_non_recovery_load is not None else float(anchor_lr * sessions_per_week)
            target_load = round(float(anchor_load) * 0.78, 1)
        else:
            non_recovery_count += 1
            progress = non_recovery_count / total_build_like_weeks
            lower_bound_factor = 0.52 if race_goal in {"5K", "10K"} else 0.48
            upper_bound_factor = 1.0
            progress_factor = lower_bound_factor + ((upper_bound_factor - lower_bound_factor) * progress)
            long_run = min(max_session_min, int(round(target_lr * progress_factor)))
            if last_non_recovery_long_run is not None:
                long_run = max(long_run, min(max_session_min, int(round(last_non_recovery_long_run * 1.03))))
            phase_multiplier = {
                "Base": 0.88,
                "Build": 1.02,
                "Peak": 1.06,
                "Taper": 0.82,
            }.get(phase, 0.92)
            target_load = round(long_run * sessions_per_week * phase_multiplier, 1)
            if last_non_recovery_load is not None and phase in {"Base", "Build", "Peak"}:
                target_load = round(max(target_load, last_non_recovery_load * 1.02), 1)
            last_non_recovery_long_run = long_run
            last_non_recovery_load = target_load

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
                "long_run_minutes": int(long_run),
                "sessions_order": sessions_order,
            }
        )
    return rows
