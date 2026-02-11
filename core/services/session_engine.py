from __future__ import annotations

from copy import deepcopy
from typing import Any


ZONE_ORDER = ["Z1", "Z2", "Z3", "Z4", "Z5"]


def compute_acute_chronic_ratio(loads_28d: list[float]) -> float:
    if not loads_28d:
        return 1.0
    recent = sum(loads_28d[-7:])
    base_window = loads_28d[:-7] if len(loads_28d) > 7 else loads_28d
    baseline = sum(base_window) / max(1, len(base_window))
    if baseline <= 0:
        return 1.0
    return round((recent / 7.0) / baseline, 2)


def pace_from_sec_per_km(sec: int | None) -> str:
    if not sec or sec <= 0:
        return "n/a"
    mins = sec // 60
    rem = sec % 60
    return f"{mins}:{rem:02d}/km"


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
