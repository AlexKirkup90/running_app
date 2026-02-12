from __future__ import annotations

from copy import deepcopy
from typing import Any


ZONE_ORDER = ["Z1", "Z2", "Z3", "Z4", "Z5"]


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


def adapt_session_structure(
    structure_json: dict[str, Any],
    readiness: float | None,
    pain_flag: bool,
    acute_chronic_ratio: float,
    days_to_event: int | None,
) -> dict[str, Any]:
    """Adapt a session structure based on readiness, pain, workload ratio, and event proximity.

    Returns a dict with keys: action ('keep'|'downshift'|'taper'|'progress'), reason, and the adjusted session.
    """
    session = deepcopy(structure_json or {})
    blocks = session.get("blocks", [])
    action = "keep"
    reason = "No adaptation required."
    main_factor = 1.0
    zone_shift = 0

    if pain_flag or (readiness is not None and readiness < 3.0):
        action = "downshift"
        reason = "Low readiness or pain flag detected."
        main_factor = 0.75
        zone_shift = -1
    elif days_to_event is not None and 0 <= days_to_event <= 10:
        action = "taper"
        reason = "Event proximity taper applied."
        main_factor = 0.85
        zone_shift = -1
    elif (readiness is not None and readiness >= 4.2) and acute_chronic_ratio <= 0.9:
        action = "progress"
        reason = "High readiness with manageable load."
        main_factor = 1.1
        zone_shift = 0

    adjusted_blocks: list[dict[str, Any]] = []
    for block in blocks:
        row = deepcopy(block)
        if row.get("phase") == "main_set":
            duration = int(row.get("duration_min", 0) or 0)
            row["duration_min"] = max(8, int(round(duration * main_factor)))
        target = row.get("target")
        if isinstance(target, dict):
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
