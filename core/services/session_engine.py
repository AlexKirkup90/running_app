"""Session engine: adapts session structures based on athlete state.

Handles both legacy v2 structures (zone-based) and v3 structures
(Daniels pace labels with prescriptive intervals). Phase-aware adaptation
adjusts differently in Base, Build, Peak, and Taper phases.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


ZONE_ORDER = ["Z1", "Z2", "Z3", "Z4", "Z5"]

# Daniels pace hierarchy from easiest to hardest
DANIELS_PACE_ORDER = ["E", "M", "T", "I", "R"]


def compute_acute_chronic_ratio(loads_28d: list[float]) -> float:
    """Compute the acute-to-chronic workload ratio from up to 28 days of load values.

    Compares the most recent 7-day average against the preceding baseline. Returns 1.0 if data is empty.
    """
    if not loads_28d:
        return 1.0
    recent = sum(loads_28d[-7:])
    base_window = loads_28d[:-7] if len(loads_28d) > 7 else loads_28d
    baseline = sum(base_window) / max(1, len(base_window))
    if baseline <= 0:
        return 1.0
    return round((recent / 7.0) / baseline, 2)


def pace_from_sec_per_km(sec: int | None) -> str:
    """Convert seconds-per-kilometre to a 'M:SS/km' display string. Returns 'n/a' for invalid input."""
    if not sec or sec <= 0:
        return "n/a"
    mins = sec // 60
    rem = sec % 60
    return f"{mins}:{rem:02d}/km"


def _zones_from_label(label: str) -> list[str]:
    return [zone for zone in ZONE_ORDER if zone in (label or "")]


def _pace_sec_for_zone(zone: str, threshold_pace_sec_per_km: int | None, easy_pace_sec_per_km: int | None) -> int | None:
    if threshold_pace_sec_per_km is None or easy_pace_sec_per_km is None:
        return None
    table = {
        "Z1": easy_pace_sec_per_km + 30,
        "Z2": easy_pace_sec_per_km,
        "Z3": int(round((easy_pace_sec_per_km + threshold_pace_sec_per_km) / 2)),
        "Z4": threshold_pace_sec_per_km,
        "Z5": max(150, threshold_pace_sec_per_km - 20),
    }
    return table.get(zone)


def pace_range_for_label(label: str, threshold_pace_sec_per_km: int | None, easy_pace_sec_per_km: int | None) -> str:
    """Derive a human-readable pace range string for a zone label given threshold and easy paces.

    Returns a single pace or a 'lo - hi' range, or 'n/a' if zones cannot be resolved.
    """
    zones = _zones_from_label(label)
    if not zones:
        return "n/a"
    secs = [s for s in (_pace_sec_for_zone(z, threshold_pace_sec_per_km, easy_pace_sec_per_km) for z in zones) if s is not None]
    if not secs:
        return "n/a"
    lo, hi = min(secs), max(secs)
    return pace_from_sec_per_km(lo) if lo == hi else f"{pace_from_sec_per_km(lo)} - {pace_from_sec_per_km(hi)}"


def hr_zone_bounds(max_hr: int | None, resting_hr: int | None) -> dict[str, tuple[int, int]]:
    """Calculate heart-rate zone boundaries (Z1-Z5) using the Karvonen heart-rate reserve method.

    Returns a dict mapping zone labels to (low_bpm, high_bpm) tuples, or empty dict if inputs are invalid.
    """
    if not max_hr or not resting_hr or max_hr <= resting_hr:
        return {}
    hrr = max_hr - resting_hr
    return {
        "Z1": (round(resting_hr + 0.50 * hrr), round(resting_hr + 0.60 * hrr)),
        "Z2": (round(resting_hr + 0.60 * hrr), round(resting_hr + 0.70 * hrr)),
        "Z3": (round(resting_hr + 0.70 * hrr), round(resting_hr + 0.80 * hrr)),
        "Z4": (round(resting_hr + 0.80 * hrr), round(resting_hr + 0.90 * hrr)),
        "Z5": (round(resting_hr + 0.90 * hrr), round(resting_hr + 1.00 * hrr)),
    }


def hr_range_for_label(label: str, max_hr: int | None, resting_hr: int | None) -> str:
    """Return a 'lo-hi bpm' heart-rate range string for a zone label. Returns 'n/a' if unresolvable."""
    zones = _zones_from_label(label)
    bounds = hr_zone_bounds(max_hr, resting_hr)
    if not zones or not bounds:
        return "n/a"
    vals = [bounds[z] for z in zones if z in bounds]
    if not vals:
        return "n/a"
    lo = min(v[0] for v in vals)
    hi = max(v[1] for v in vals)
    return f"{lo}-{hi} bpm"


def _shift_zone_label(label: str, delta: int) -> str:
    if not label:
        return label
    updated = label
    for zone in ZONE_ORDER:
        if zone in updated:
            idx = ZONE_ORDER.index(zone)
            nidx = max(0, min(len(ZONE_ORDER) - 1, idx + delta))
            updated = updated.replace(zone, ZONE_ORDER[nidx])
    return updated


def _shift_daniels_pace(pace: str, delta: int) -> str:
    """Shift a Daniels pace label up or down the intensity scale.

    Negative delta = easier (E direction), positive delta = harder (R direction).
    """
    if pace not in DANIELS_PACE_ORDER:
        return pace
    idx = DANIELS_PACE_ORDER.index(pace)
    nidx = max(0, min(len(DANIELS_PACE_ORDER) - 1, idx + delta))
    return DANIELS_PACE_ORDER[nidx]


def _adapt_intervals(intervals: list[dict], action: str, rep_delta: int) -> list[dict]:
    """Adapt interval blocks at the rep/duration level based on action.

    - downshift: reduce reps, extend recovery
    - taper: reduce reps significantly, shorten work
    - progress: add reps
    """
    adapted = []
    for ivl in intervals:
        row = deepcopy(ivl)
        reps = int(row.get("reps", 1))
        work_dur = float(row.get("work_duration_min", 1))
        recovery_dur = float(row.get("recovery_duration_min", 1))

        if action == "downshift":
            reps = max(1, reps + rep_delta)  # rep_delta is negative
            recovery_dur = round(recovery_dur * 1.25, 2)
            row["work_pace"] = _shift_daniels_pace(row.get("work_pace", "E"), -1)
        elif action == "taper":
            reps = max(1, reps - max(1, reps // 3))
            work_dur = round(work_dur * 0.85, 2)
        elif action == "progress":
            reps = reps + rep_delta  # rep_delta is positive
            work_dur = round(work_dur * 1.05, 2)

        row["reps"] = reps
        row["work_duration_min"] = work_dur
        row["recovery_duration_min"] = recovery_dur
        adapted.append(row)
    return adapted


def _determine_phase_factors(action: str, phase: str | None) -> dict:
    """Apply phase-aware multipliers to the base adaptation action.

    Returns dict with main_factor, zone_shift, rep_delta adjustments.
    """
    # Base defaults per action
    defaults = {
        "downshift": {"main_factor": 0.75, "zone_shift": -1, "rep_delta": -1},
        "taper": {"main_factor": 0.85, "zone_shift": -1, "rep_delta": 0},
        "progress": {"main_factor": 1.1, "zone_shift": 0, "rep_delta": 1},
        "keep": {"main_factor": 1.0, "zone_shift": 0, "rep_delta": 0},
    }
    factors = dict(defaults.get(action, defaults["keep"]))

    if not phase:
        return factors

    if action == "downshift":
        if phase == "Base":
            # Protect aerobic volume — less duration cut, same zone shift
            factors["main_factor"] = 0.85
        elif phase in ("Build", "Peak"):
            # Protect intensity — cut volume more, keep zones closer
            factors["main_factor"] = 0.70
            factors["rep_delta"] = -2
        elif phase == "Taper":
            factors["main_factor"] = 0.80
    elif action == "taper":
        if phase == "Peak":
            # Maintain 1-2 intensity touches
            factors["main_factor"] = 0.60
            factors["zone_shift"] = 0  # Keep intensity, cut volume hard
        else:
            factors["main_factor"] = 0.85
    elif action == "progress":
        if phase == "Base":
            # Progress via duration, not intensity
            factors["main_factor"] = 1.15
            factors["rep_delta"] = 0
        elif phase in ("Build", "Peak"):
            # Progress via reps, moderate duration increase
            factors["main_factor"] = 1.05
            factors["rep_delta"] = 1

    return factors


def adapt_session_structure(
    structure_json: dict[str, Any],
    readiness: float | None,
    pain_flag: bool,
    acute_chronic_ratio: float,
    days_to_event: int | None,
    phase: str | None = None,
) -> dict[str, Any]:
    """Adapt a session structure based on readiness, pain, workload ratio, event proximity, and phase.

    Handles both v2 (zone-based) and v3 (Daniels pace + intervals) structures.
    Phase-aware adaptation adjusts volume/intensity priorities per training phase.
    Returns a dict with keys: action, reason, and the adjusted session.
    """
    session = deepcopy(structure_json or {})
    blocks = session.get("blocks", [])
    action = "keep"
    reason = "No adaptation required."

    # Determine action
    if pain_flag or (readiness is not None and readiness < 3.0):
        action = "downshift"
        reason = "Low readiness or pain flag detected."
    elif days_to_event is not None and 0 <= days_to_event <= 10:
        action = "taper"
        reason = "Event proximity taper applied."
    elif (readiness is not None and readiness >= 4.2) and acute_chronic_ratio <= 0.9:
        action = "progress"
        reason = "High readiness with manageable load."

    # Get phase-aware factors
    factors = _determine_phase_factors(action, phase)
    main_factor = factors["main_factor"]
    zone_shift = factors["zone_shift"]
    rep_delta = factors["rep_delta"]

    is_v3 = session.get("version", 2) >= 3

    adjusted_blocks: list[dict[str, Any]] = []
    for block in blocks:
        row = deepcopy(block)

        if row.get("phase") == "main_set":
            duration = int(row.get("duration_min", 0) or 0)
            row["duration_min"] = max(8, int(round(duration * main_factor)))

            # Adapt intervals (v3)
            intervals = row.get("intervals")
            if isinstance(intervals, list) and intervals:
                row["intervals"] = _adapt_intervals(intervals, action, rep_delta)

        target = row.get("target")
        if isinstance(target, dict):
            # v3: shift Daniels pace labels
            if is_v3 and "pace_label" in target and isinstance(target["pace_label"], str):
                target["pace_label"] = _shift_daniels_pace(target["pace_label"], zone_shift)

            # v2 compatibility: shift zone labels
            if "pace_zone" in target and isinstance(target["pace_zone"], str):
                target["pace_zone"] = _shift_zone_label(target["pace_zone"], zone_shift)
            if "hr_zone" in target and isinstance(target["hr_zone"], str):
                target["hr_zone"] = _shift_zone_label(target["hr_zone"], zone_shift)

            rpe = target.get("rpe_range")
            if isinstance(rpe, list) and len(rpe) == 2:
                lo, hi = int(rpe[0]), int(rpe[1])
                if action in {"downshift", "taper"}:
                    lo = max(1, lo - 1)
                    hi = max(lo, hi - 1)
                elif action == "progress":
                    lo = min(10, lo + 1)
                    hi = min(10, hi + 1)
                target["rpe_range"] = [lo, hi]
            row["target"] = target
        adjusted_blocks.append(row)

    session["blocks"] = adjusted_blocks
    return {"action": action, "reason": reason, "session": session}
