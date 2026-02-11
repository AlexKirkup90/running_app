from __future__ import annotations


def simulate_missed_week(target_load: float) -> dict:
    return {"new_target_load": round(target_load * 0.85, 2), "note": "Applied conservative deload after missed week"}
