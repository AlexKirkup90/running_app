from __future__ import annotations


def simulate_missed_week(target_load: float) -> dict:
    """Simulate the effect of a missed training week by applying a conservative 15% deload.

    Returns a dict with new_target_load and a descriptive note.
    """
    return {"new_target_load": round(target_load * 0.85, 2), "note": "Applied conservative deload after missed week"}
