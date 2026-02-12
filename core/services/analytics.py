"""Advanced analytics engine: VDOT tracking, fitness/fatigue, pace trends.

Provides time-series computations for the analytics dashboard including:
- VDOT progression tracking from race results and benchmarks
- Chronic Training Load (CTL), Acute Training Load (ATL), and Training
  Stress Balance (TSB) using an exponential weighted moving average model
- Pace trend analysis across training zones
- Volume/intensity distribution by phase
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from core.services.vdot import estimate_vdot


# ---------------------------------------------------------------------------
# Weekly summary (preserved from original)
# ---------------------------------------------------------------------------

def weekly_summary(logs_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate training logs into weekly totals of duration, load, and session count.

    Returns a DataFrame with columns: week, duration_min, load_score, sessions.
    """
    if logs_df.empty:
        return pd.DataFrame(columns=["week", "duration_min", "load_score", "sessions"])
    d = logs_df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["week"] = d["date"].dt.to_period("W").astype(str)
    out = d.groupby("week", as_index=False).agg(duration_min=("duration_min", "sum"), load_score=("load_score", "sum"), sessions=("id", "count"))
    return out


# ---------------------------------------------------------------------------
# VDOT Progression Tracking
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VdotDataPoint:
    """A single VDOT estimate from a race or benchmark."""
    event_date: date
    distance_m: float
    time_seconds: float
    vdot: float
    source: str  # "race", "benchmark", "time_trial"


def compute_vdot_history(race_results: list[dict]) -> list[VdotDataPoint]:
    """Compute VDOT estimates from a series of race/benchmark results.

    Each result dict should have: date, distance_km, duration_min, source.
    Returns a chronologically sorted list of VdotDataPoints.
    """
    points: list[VdotDataPoint] = []
    for r in race_results:
        distance_km = float(r.get("distance_km", 0))
        duration_min = float(r.get("duration_min", 0))
        if distance_km <= 0 or duration_min <= 0:
            continue
        distance_m = distance_km * 1000
        time_sec = duration_min * 60
        vdot = estimate_vdot(distance_m, time_sec)
        if vdot > 0:
            points.append(VdotDataPoint(
                event_date=r["date"],
                distance_m=distance_m,
                time_seconds=time_sec,
                vdot=round(vdot, 1),
                source=r.get("source", "benchmark"),
            ))
    return sorted(points, key=lambda p: p.event_date)


def vdot_trend(history: list[VdotDataPoint]) -> dict:
    """Analyse VDOT progression: current, peak, improvement rate.

    Returns dict with current_vdot, peak_vdot, trend (improving/stable/declining),
    and improvement_per_month.
    """
    if not history:
        return {"current_vdot": None, "peak_vdot": None, "trend": "insufficient_data", "improvement_per_month": 0.0}

    current = history[-1].vdot
    peak = max(p.vdot for p in history)

    if len(history) < 2:
        return {"current_vdot": current, "peak_vdot": peak, "trend": "insufficient_data", "improvement_per_month": 0.0}

    first = history[0]
    last = history[-1]
    days_span = max(1, (last.event_date - first.event_date).days)
    months = days_span / 30.44
    improvement_per_month = (last.vdot - first.vdot) / months if months > 0 else 0.0

    if improvement_per_month > 0.2:
        trend = "improving"
    elif improvement_per_month < -0.2:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "current_vdot": current,
        "peak_vdot": peak,
        "trend": trend,
        "improvement_per_month": round(improvement_per_month, 2),
    }


# ---------------------------------------------------------------------------
# Fitness / Fatigue Model (CTL / ATL / TSB)
# ---------------------------------------------------------------------------

@dataclass
class FitnessFatiguePoint:
    """A single day's fitness/fatigue state."""
    day: date
    daily_load: float
    ctl: float  # Chronic Training Load (fitness)
    atl: float  # Acute Training Load (fatigue)
    tsb: float  # Training Stress Balance (form)


def compute_fitness_fatigue(
    daily_loads: list[dict],
    ctl_decay: int = 42,
    atl_decay: int = 7,
) -> list[FitnessFatiguePoint]:
    """Compute CTL/ATL/TSB time series from daily training loads.

    Uses exponential weighted moving averages:
    - CTL (fitness): 42-day decay constant
    - ATL (fatigue): 7-day decay constant
    - TSB (form): CTL - ATL

    Each entry in daily_loads should have: date, load.
    Missing days are filled with zero load.
    """
    if not daily_loads:
        return []

    loads_by_date: dict[date, float] = {}
    for entry in daily_loads:
        d = entry["date"] if isinstance(entry["date"], date) else date.fromisoformat(str(entry["date"]))
        loads_by_date[d] = loads_by_date.get(d, 0) + float(entry.get("load", 0))

    start = min(loads_by_date.keys())
    end = max(loads_by_date.keys())

    ctl_alpha = 2.0 / (ctl_decay + 1)
    atl_alpha = 2.0 / (atl_decay + 1)

    ctl = 0.0
    atl = 0.0
    points: list[FitnessFatiguePoint] = []

    current = start
    while current <= end:
        load = loads_by_date.get(current, 0.0)
        ctl = ctl + ctl_alpha * (load - ctl)
        atl = atl + atl_alpha * (load - atl)
        tsb = ctl - atl
        points.append(FitnessFatiguePoint(
            day=current,
            daily_load=load,
            ctl=round(ctl, 1),
            atl=round(atl, 1),
            tsb=round(tsb, 1),
        ))
        current += timedelta(days=1)

    return points


def race_readiness_score(tsb: float) -> str:
    """Classify race readiness based on TSB (Training Stress Balance).

    Positive TSB = fresh/ready; negative = fatigued; very positive = detrained.
    """
    if tsb > 25:
        return "detrained"
    if tsb > 10:
        return "race_ready"
    if tsb > 0:
        return "fresh"
    if tsb > -10:
        return "slightly_fatigued"
    if tsb > -20:
        return "fatigued"
    return "overreached"


# ---------------------------------------------------------------------------
# Pace Trend Analysis
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaceTrendPoint:
    """A pace data point for trend analysis."""
    log_date: date
    category: str
    avg_pace_sec_per_km: float
    distance_km: float


def compute_pace_trends(logs: list[dict]) -> pd.DataFrame:
    """Compute rolling average pace trends by session category.

    Returns a DataFrame with columns: date, category, avg_pace, rolling_avg_pace (7-session).
    """
    rows = []
    for log in logs:
        pace = log.get("avg_pace_sec_per_km")
        if pace and float(pace) > 0:
            rows.append({
                "date": log["date"],
                "category": log.get("session_category", "Unknown"),
                "avg_pace": float(pace),
                "distance_km": float(log.get("distance_km", 0)),
            })
    if not rows:
        return pd.DataFrame(columns=["date", "category", "avg_pace", "rolling_avg_pace"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # Rolling average per category
    result_frames = []
    for cat in df["category"].unique():
        cat_df = df[df["category"] == cat].copy()
        cat_df["rolling_avg_pace"] = cat_df["avg_pace"].rolling(window=min(7, len(cat_df)), min_periods=1).mean()
        result_frames.append(cat_df)

    return pd.concat(result_frames).sort_values("date") if result_frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# Volume / Intensity Distribution
# ---------------------------------------------------------------------------

def compute_volume_distribution(logs: list[dict]) -> dict[str, float]:
    """Compute percentage of total volume by session category.

    Returns dict mapping category to percentage of total duration.
    """
    totals: dict[str, float] = {}
    grand_total = 0.0
    for log in logs:
        cat = log.get("session_category", "Unknown")
        dur = float(log.get("duration_min", 0))
        totals[cat] = totals.get(cat, 0) + dur
        grand_total += dur
    if grand_total == 0:
        return {}
    return {cat: round(100 * dur / grand_total, 1) for cat, dur in sorted(totals.items(), key=lambda x: -x[1])}


def compute_intensity_distribution(logs: list[dict]) -> dict[str, float]:
    """Compute easy/moderate/hard percentage by RPE buckets.

    RPE 1-4 = easy, 5-7 = moderate, 8-10 = hard.
    """
    buckets = {"easy": 0.0, "moderate": 0.0, "hard": 0.0}
    total = 0.0
    for log in logs:
        dur = float(log.get("duration_min", 0))
        rpe = int(log.get("rpe", 5))
        total += dur
        if rpe <= 4:
            buckets["easy"] += dur
        elif rpe <= 7:
            buckets["moderate"] += dur
        else:
            buckets["hard"] += dur
    if total == 0:
        return buckets
    return {k: round(100 * v / total, 1) for k, v in buckets.items()}
