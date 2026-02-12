"""VDOT-based pacing system inspired by Jack Daniels' Running Formula.

VDOT is a measure of running ability derived from race performances.
This module maps VDOT scores to five Daniels training paces (E, M, T, I, R)
expressed in seconds-per-kilometre, and provides utilities for pace lookup,
VDOT estimation from race results, and zone resolution.

Reference: Daniels' Running Formula, 3rd Edition (2013).
Pace tables are simplified approximations of the published tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp


@dataclass(frozen=True)
class DanielsPaces:
    """Five Daniels training paces in seconds per kilometre."""
    vdot: int
    easy: int       # E pace — aerobic development
    marathon: int   # M pace — marathon-specific endurance
    threshold: int  # T pace — lactate clearance (cruise/tempo)
    interval: int   # I pace — VO2max stimulus
    repetition: int # R pace — speed/economy


# Daniels pace table: VDOT → (E, M, T, I, R) in sec/km
# Spans VDOT 30–85, covering recreational to elite runners.
_PACE_TABLE: dict[int, tuple[int, int, int, int, int]] = {
    30: (447, 404, 379, 351, 327),
    31: (438, 396, 372, 344, 321),
    32: (429, 388, 364, 337, 314),
    33: (421, 381, 357, 331, 308),
    34: (413, 374, 350, 324, 302),
    35: (405, 367, 344, 318, 296),
    36: (398, 360, 337, 312, 291),
    37: (390, 354, 331, 307, 286),
    38: (383, 347, 325, 301, 280),
    39: (377, 341, 320, 296, 275),
    40: (370, 335, 314, 291, 270),
    41: (364, 330, 309, 286, 266),
    42: (358, 324, 304, 281, 261),
    43: (352, 319, 299, 277, 257),
    44: (346, 314, 294, 272, 253),
    45: (341, 309, 289, 268, 249),
    46: (336, 304, 285, 264, 245),
    47: (330, 300, 281, 260, 241),
    48: (326, 295, 277, 256, 237),
    49: (321, 291, 273, 252, 234),
    50: (316, 287, 269, 248, 230),
    51: (312, 283, 265, 245, 227),
    52: (307, 279, 261, 241, 224),
    53: (303, 275, 258, 238, 221),
    54: (299, 271, 254, 235, 218),
    55: (295, 268, 251, 232, 215),
    56: (291, 264, 248, 229, 212),
    57: (287, 261, 245, 226, 210),
    58: (284, 258, 242, 223, 207),
    59: (280, 255, 239, 220, 205),
    60: (277, 252, 236, 218, 202),
    61: (274, 249, 233, 215, 200),
    62: (270, 246, 231, 213, 198),
    63: (267, 243, 228, 210, 195),
    64: (264, 241, 226, 208, 193),
    65: (261, 238, 223, 206, 191),
    66: (258, 235, 221, 204, 189),
    67: (256, 233, 219, 201, 187),
    68: (253, 231, 216, 199, 185),
    69: (250, 228, 214, 197, 183),
    70: (248, 226, 212, 195, 181),
    71: (245, 224, 210, 193, 179),
    72: (243, 222, 208, 191, 178),
    73: (241, 220, 206, 190, 176),
    74: (238, 218, 204, 188, 174),
    75: (236, 216, 202, 186, 173),
    76: (234, 214, 200, 184, 171),
    77: (232, 212, 198, 183, 170),
    78: (230, 210, 196, 181, 168),
    79: (228, 208, 195, 179, 167),
    80: (226, 206, 193, 178, 165),
    81: (224, 205, 191, 176, 164),
    82: (222, 203, 190, 175, 162),
    83: (220, 201, 188, 173, 161),
    84: (218, 200, 187, 172, 160),
    85: (217, 198, 185, 170, 158),
}

VDOT_MIN = min(_PACE_TABLE)
VDOT_MAX = max(_PACE_TABLE)


def get_paces(vdot: int) -> DanielsPaces:
    """Look up the five Daniels training paces for a given VDOT score.

    Clamps to the table range [30, 85]. For intermediate values between
    table entries, interpolates linearly.
    """
    clamped = max(VDOT_MIN, min(VDOT_MAX, vdot))
    if clamped in _PACE_TABLE:
        e, m, t, i, r = _PACE_TABLE[clamped]
        return DanielsPaces(vdot=clamped, easy=e, marathon=m, threshold=t, interval=i, repetition=r)

    lo = max(k for k in _PACE_TABLE if k <= clamped)
    hi = min(k for k in _PACE_TABLE if k >= clamped)
    frac = (clamped - lo) / (hi - lo) if hi != lo else 0
    lo_p, hi_p = _PACE_TABLE[lo], _PACE_TABLE[hi]
    return DanielsPaces(
        vdot=clamped,
        easy=round(lo_p[0] + frac * (hi_p[0] - lo_p[0])),
        marathon=round(lo_p[1] + frac * (hi_p[1] - lo_p[1])),
        threshold=round(lo_p[2] + frac * (hi_p[2] - lo_p[2])),
        interval=round(lo_p[3] + frac * (hi_p[3] - lo_p[3])),
        repetition=round(lo_p[4] + frac * (hi_p[4] - lo_p[4])),
    )


def pace_display(sec_per_km: int) -> str:
    """Format seconds-per-km as 'M:SS/km' for display."""
    if sec_per_km <= 0:
        return "n/a"
    return f"{sec_per_km // 60}:{sec_per_km % 60:02d}/km"


def pace_range_display(lo: int, hi: int) -> str:
    """Format a pace band as 'M:SS - M:SS /km'."""
    return f"{pace_display(lo)} - {pace_display(hi)}"


# --- VDOT estimation from race result ---

# Standard race distances in metres
RACE_DISTANCES_M = {
    "1500m": 1500,
    "Mile": 1609.34,
    "3K": 3000,
    "5K": 5000,
    "10K": 10000,
    "15K": 15000,
    "Half Marathon": 21097.5,
    "Marathon": 42195,
}


def _vo2_from_velocity(v: float) -> float:
    """Daniels' oxygen cost equation: mL/kg/min from velocity in m/min."""
    return -4.60 + 0.182258 * v + 0.000104 * v * v


def _percent_max(t_min: float) -> float:
    """Fraction of VO2max sustainable for t_min minutes (Daniels' drop-off curve)."""
    return 0.8 + 0.1894393 * exp(-0.012778 * t_min) + 0.2989558 * exp(-0.1932605 * t_min)


def estimate_vdot(distance_m: float, time_seconds: float) -> float:
    """Estimate VDOT from a race distance (m) and finish time (seconds).

    Uses the Daniels/Gilbert VO2 and percent-max equations.
    Returns a float VDOT; round to int for table lookup.
    """
    if distance_m <= 0 or time_seconds <= 0:
        return 30.0
    t_min = time_seconds / 60.0
    velocity = distance_m / t_min  # m/min
    vo2 = _vo2_from_velocity(velocity)
    pct = _percent_max(t_min)
    if pct <= 0:
        return 30.0
    return round(vo2 / pct, 1)


def vdot_from_race(distance_label: str, time_seconds: float) -> float:
    """Convenience wrapper: estimate VDOT from a named distance and finish time."""
    dist_m = RACE_DISTANCES_M.get(distance_label)
    if dist_m is None:
        raise ValueError(f"Unknown distance: {distance_label}. Use one of {sorted(RACE_DISTANCES_M)}")
    return estimate_vdot(dist_m, time_seconds)


def resolve_daniels_pace(pace_label: str, vdot: int) -> int | None:
    """Map a Daniels pace label ('E', 'M', 'T', 'I', 'R') to sec/km for a VDOT.

    Returns None if pace_label is not a Daniels label.
    """
    paces = get_paces(vdot)
    mapping = {"E": paces.easy, "M": paces.marathon, "T": paces.threshold, "I": paces.interval, "R": paces.repetition}
    return mapping.get(pace_label.upper()) if pace_label else None


def daniels_pace_band(pace_label: str, vdot: int) -> tuple[int, int]:
    """Return a (fast, slow) sec/km band for a Daniels pace label.

    Bands are ±3% for easy/marathon, ±2% for threshold/interval/repetition.
    """
    centre = resolve_daniels_pace(pace_label, vdot)
    if centre is None:
        return (0, 0)
    if pace_label.upper() in ("E", "M"):
        margin = max(1, round(centre * 0.03))
    else:
        margin = max(1, round(centre * 0.02))
    return (centre - margin, centre + margin)
