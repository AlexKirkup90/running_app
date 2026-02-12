"""Training load metrics: TRIMP, monotony, strain, and weekly summaries.

TRIMP (Training Impulse) provides a more physiologically meaningful load
metric than simple duration * RPE. Combined with monotony and strain
calculations, these metrics enable overtraining detection.

Reference: Banister (1991), Foster (1998) session-RPE method.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, stdev


@dataclass(frozen=True)
class SessionLoad:
    """Load metrics for a single training session."""
    duration_min: int
    rpe: int
    avg_hr: int | None
    max_hr: int | None
    resting_hr: int | None
    srpe_load: float       # session RPE load = duration * RPE
    trimp: float           # Training Impulse (HR-based if available, else estimated)


@dataclass(frozen=True)
class WeeklyLoadMetrics:
    """Aggregated load metrics for a 7-day window."""
    total_srpe: float
    total_trimp: float
    session_count: int
    monotony: float       # mean daily load / stdev (high = uniform stress = risky)
    strain: float         # total load * monotony (overtraining risk indicator)
    avg_daily_load: float
    peak_session_load: float


def compute_srpe_load(duration_min: int, rpe: int) -> float:
    """Compute session-RPE load (Foster method): duration * RPE."""
    return float(max(0, duration_min)) * max(1, min(10, rpe))


def compute_trimp(
    duration_min: int,
    avg_hr: int | None,
    max_hr: int | None,
    resting_hr: int | None,
    rpe: int,
    gender_factor: float = 1.92,
) -> float:
    """Compute TRIMP (Training Impulse) from session data.

    Uses Banister's exponential HR method when HR data is available,
    falls back to an RPE-estimated TRIMP otherwise.

    gender_factor: 1.92 for male, 1.67 for female (default male).
    """
    if avg_hr and max_hr and resting_hr and max_hr > resting_hr:
        hrr = (avg_hr - resting_hr) / (max_hr - resting_hr)
        hrr = max(0.0, min(1.0, hrr))
        # Banister formula: duration * HRR * 0.64 * e^(gender_factor * HRR)
        import math
        trimp = duration_min * hrr * 0.64 * math.exp(gender_factor * hrr)
        return round(trimp, 1)

    # Fallback: estimate from RPE (roughly maps RPE 1-10 to HR fraction)
    estimated_hrr = (rpe - 1) / 9.0  # RPE 1 → 0.0, RPE 10 → 1.0
    return round(duration_min * estimated_hrr * 0.8, 1)


def compute_session_load(
    duration_min: int,
    rpe: int,
    avg_hr: int | None = None,
    max_hr: int | None = None,
    resting_hr: int | None = None,
) -> SessionLoad:
    """Compute all load metrics for a single session."""
    srpe = compute_srpe_load(duration_min, rpe)
    trimp = compute_trimp(duration_min, avg_hr, max_hr, resting_hr, rpe)
    return SessionLoad(
        duration_min=duration_min,
        rpe=rpe,
        avg_hr=avg_hr,
        max_hr=max_hr,
        resting_hr=resting_hr,
        srpe_load=srpe,
        trimp=trimp,
    )


def compute_weekly_metrics(daily_loads: list[float]) -> WeeklyLoadMetrics:
    """Compute weekly load summary from 7 daily load values.

    Daily loads should be the sum of all session loads for each day.
    Pass 0.0 for rest days. Expects exactly 7 values but handles any length.
    """
    if not daily_loads:
        return WeeklyLoadMetrics(
            total_srpe=0, total_trimp=0, session_count=0,
            monotony=0, strain=0, avg_daily_load=0, peak_session_load=0,
        )

    total = sum(daily_loads)
    count = sum(1 for d in daily_loads if d > 0)
    avg = mean(daily_loads) if daily_loads else 0
    sd = stdev(daily_loads) if len(daily_loads) > 1 else 0
    monotony = round(avg / sd, 2) if sd > 0 else 0.0
    strain = round(total * monotony, 1)

    return WeeklyLoadMetrics(
        total_srpe=round(total, 1),
        total_trimp=round(total, 1),
        session_count=count,
        monotony=monotony,
        strain=strain,
        avg_daily_load=round(avg, 1),
        peak_session_load=max(daily_loads) if daily_loads else 0,
    )


def overtraining_risk(monotony: float, strain: float) -> str:
    """Classify overtraining risk from monotony and strain values.

    Returns: 'low', 'moderate', or 'high'.
    Reference thresholds from Foster (1998).
    """
    if monotony >= 2.0 and strain >= 6000:
        return "high"
    if monotony >= 1.5 or strain >= 4000:
        return "moderate"
    return "low"
