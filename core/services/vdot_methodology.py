from __future__ import annotations

import math
from typing import Any, Optional


def _solve_speed_m_per_min_for_vo2(vo2_cost: float) -> Optional[float]:
    # Daniels running VO2 cost equation:
    # VO2 = -4.60 + 0.182258*v + 0.000104*v^2
    a = 0.000104
    b = 0.182258
    c = -4.60 - float(vo2_cost)
    disc = (b * b) - (4 * a * c)
    if disc <= 0:
        return None
    root = (-b + math.sqrt(disc)) / (2 * a)
    if not math.isfinite(root) or root <= 0:
        return None
    return float(root)


def _pace_sec_per_km_from_speed_m_per_min(speed_m_per_min: float) -> Optional[int]:
    if not speed_m_per_min or speed_m_per_min <= 0:
        return None
    sec = (1000.0 / float(speed_m_per_min)) * 60.0
    if not math.isfinite(sec) or sec <= 0:
        return None
    return int(round(sec))


def pace_str_from_sec_per_km(sec: Optional[int]) -> str:
    if sec is None or sec <= 0:
        return "n/a"
    return f"{sec // 60}:{sec % 60:02d}/km"


# Practical training intensity bands aligned to Daniels/VDOT usage (approximate ranges)
_VDOT_CODE_FRACTIONS: dict[str, tuple[float, float]] = {
    "E": (0.59, 0.74),
    "M": (0.75, 0.84),
    "T": (0.83, 0.88),
    "I": (0.95, 1.00),
    # R is neuromuscular/repetition and not strictly %VO2 in the same way; use a slightly faster speed than I.
    "R": (1.03, 1.10),
}


def vdot_pace_band(vdot: float, code: str) -> Optional[dict[str, Any]]:
    token = str(code or "").strip().upper()
    if token not in _VDOT_CODE_FRACTIONS:
        return None
    if not vdot or float(vdot) <= 0:
        return None
    lo_frac, hi_frac = _VDOT_CODE_FRACTIONS[token]
    speeds: list[float] = []
    for frac in (lo_frac, hi_frac):
        speed = _solve_speed_m_per_min_for_vo2(float(vdot) * float(frac))
        if speed is None:
            return None
        speeds.append(speed)
    if token == "R":
        i_band = vdot_pace_band(vdot, "I")
        if i_band and i_band.get("fast_sec_per_km") is not None:
            i_fast = int(i_band["fast_sec_per_km"])
            # Approximate repetition pace faster than I pace by 3-8%
            fast_sec = max(130, int(round(i_fast * 0.92)))
            slow_sec = max(fast_sec, int(round(i_fast * 0.97)))
            return {
                "code": token,
                "fast_sec_per_km": min(fast_sec, slow_sec),
                "slow_sec_per_km": max(fast_sec, slow_sec),
                "display": f"{pace_str_from_sec_per_km(min(fast_sec, slow_sec))} - {pace_str_from_sec_per_km(max(fast_sec, slow_sec))}",
                "methodology": "daniels_vdot",
            }

    secs = [_pace_sec_per_km_from_speed_m_per_min(v) for v in speeds]
    if any(s is None for s in secs):
        return None
    # Faster pace = lower sec/km
    fast_sec = min(int(secs[0]), int(secs[1]))
    slow_sec = max(int(secs[0]), int(secs[1]))
    return {
        "code": token,
        "fast_sec_per_km": fast_sec,
        "slow_sec_per_km": slow_sec,
        "display": f"{pace_str_from_sec_per_km(fast_sec)} - {pace_str_from_sec_per_km(slow_sec)}",
        "methodology": "daniels_vdot",
    }


def vdot_pace_bands(vdot: float) -> dict[str, dict[str, Any]]:
    bands: dict[str, dict[str, Any]] = {}
    for code in ("E", "M", "T", "I", "R"):
        band = vdot_pace_band(vdot, code)
        if band is not None:
            bands[code] = band
    return bands


def derived_profile_pace_anchors(vdot: float) -> Optional[dict[str, Any]]:
    """Return coach profile anchor paces derived from JD/VDOT bands.

    We use midpoint anchors for profile defaults:
    - easy pace anchor from E band midpoint
    - threshold pace anchor from T band midpoint
    """
    bands = vdot_pace_bands(vdot)
    easy = bands.get("E")
    threshold = bands.get("T")
    if not easy or not threshold:
        return None
    try:
        easy_mid = int(round((int(easy["fast_sec_per_km"]) + int(easy["slow_sec_per_km"])) / 2.0))
        t_mid = int(round((int(threshold["fast_sec_per_km"]) + int(threshold["slow_sec_per_km"])) / 2.0))
    except Exception:
        return None
    return {
        "vdot": float(vdot),
        "easy_pace_sec_per_km": easy_mid,
        "threshold_pace_sec_per_km": t_mid,
        "bands": bands,
        "methodology": "daniels_vdot",
    }
