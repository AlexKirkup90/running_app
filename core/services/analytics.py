from __future__ import annotations

import math
from typing import Any

import pandas as pd


def weekly_summary(logs_df: pd.DataFrame) -> pd.DataFrame:
    if logs_df.empty:
        return pd.DataFrame(columns=["week", "duration_min", "load_score", "sessions"])
    d = logs_df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["week"] = d["date"].dt.to_period("W").astype(str)
    out = d.groupby("week", as_index=False).agg(duration_min=("duration_min", "sum"), load_score=("load_score", "sum"), sessions=("id", "count"))
    return out


def _prepare_logs(logs_df: pd.DataFrame) -> pd.DataFrame:
    if logs_df is None or logs_df.empty:
        return pd.DataFrame()
    frame = logs_df.copy()
    if "date" not in frame.columns and "log_date" in frame.columns:
        frame["date"] = frame["log_date"]
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for col in ["duration_min", "load_score", "distance_km", "rpe", "avg_pace_sec_per_km"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        else:
            frame[col] = pd.NA
    return frame.sort_values("date").reset_index(drop=True)


def _ewma_series(values: list[float], tau_days: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (tau_days + 1.0)
    out: list[float] = []
    running = 0.0
    for idx, val in enumerate(values):
        v = float(val or 0.0)
        running = v if idx == 0 else ((alpha * v) + ((1 - alpha) * running))
        out.append(round(running, 2))
    return out


def compute_fitness_fatigue(logs_df: pd.DataFrame, ctl_tau_days: int = 42, atl_tau_days: int = 7) -> dict[str, Any]:
    frame = _prepare_logs(logs_df)
    if frame.empty:
        return {"series": [], "latest": None, "params": {"ctl_tau_days": ctl_tau_days, "atl_tau_days": atl_tau_days}}

    daily = (
        frame.groupby("date", as_index=False)
        .agg(load_score=("load_score", "sum"), duration_min=("duration_min", "sum"))
        .sort_values("date")
        .reset_index(drop=True)
    )
    loads = [float(v or 0.0) for v in daily["load_score"].tolist()]
    ctl = _ewma_series(loads, ctl_tau_days)
    atl = _ewma_series(loads, atl_tau_days)
    series: list[dict[str, Any]] = []
    for idx, row in daily.iterrows():
        ctl_i = ctl[idx]
        atl_i = atl[idx]
        tsb_i = round(ctl_i - atl_i, 2)
        series.append(
            {
                "date": row["date"].isoformat(),
                "load_score": round(float(row["load_score"] or 0.0), 2),
                "duration_min": int(row["duration_min"] or 0),
                "ctl": ctl_i,
                "atl": atl_i,
                "tsb": tsb_i,
            }
        )
    return {
        "series": series,
        "latest": series[-1] if series else None,
        "params": {"ctl_tau_days": ctl_tau_days, "atl_tau_days": atl_tau_days},
    }


def estimate_vdot(distance_km: float, duration_min: float) -> float | None:
    if not distance_km or not duration_min or distance_km <= 0 or duration_min <= 0:
        return None
    distance_m = float(distance_km) * 1000.0
    time_min = float(duration_min)
    speed_m_per_min = distance_m / time_min
    # Jack Daniels VO2 cost and percent of VO2max equations.
    vo2 = -4.60 + (0.182258 * speed_m_per_min) + (0.000104 * (speed_m_per_min**2))
    pct = 0.8 + (0.1894393 * math.exp(-0.012778 * time_min)) + (0.2989558 * math.exp(-0.1932605 * time_min))
    if pct <= 0:
        return None
    vdot = vo2 / pct
    if not math.isfinite(vdot):
        return None
    return round(float(vdot), 2)


def compute_vdot_history(logs_df: pd.DataFrame) -> dict[str, Any]:
    frame = _prepare_logs(logs_df)
    if frame.empty:
        return {"series": [], "latest": None}

    eligible = frame[
        (frame["distance_km"].fillna(0) >= 1.5)
        & (frame["duration_min"].fillna(0) >= 5)
        & (frame["duration_min"].fillna(0) <= 240)
    ].copy()
    if eligible.empty:
        return {"series": [], "latest": None}

    eligible["vdot"] = eligible.apply(
        lambda r: estimate_vdot(float(r.get("distance_km") or 0.0), float(r.get("duration_min") or 0.0)),
        axis=1,
    )
    eligible = eligible[eligible["vdot"].notna()].copy()
    if eligible.empty:
        return {"series": [], "latest": None}

    # Use best performance for each day as the benchmark snapshot.
    daily_best = (
        eligible.groupby("date", as_index=False)
        .agg(vdot=("vdot", "max"), distance_km=("distance_km", "max"), duration_min=("duration_min", "min"))
        .sort_values("date")
    )
    series = [
        {
            "date": row["date"].isoformat(),
            "vdot": round(float(row["vdot"]), 2),
            "distance_km": round(float(row["distance_km"] or 0.0), 2),
            "duration_min": round(float(row["duration_min"] or 0.0), 2),
        }
        for _, row in daily_best.iterrows()
    ]
    return {"series": series, "latest": (series[-1] if series else None)}


def compute_intensity_distribution(logs_df: pd.DataFrame) -> dict[str, Any]:
    frame = _prepare_logs(logs_df)
    if frame.empty:
        return {
            "buckets": [
                {"label": "Low", "value": 0.0, "percent": 0.0},
                {"label": "Moderate", "value": 0.0, "percent": 0.0},
                {"label": "High", "value": 0.0, "percent": 0.0},
            ],
            "total_minutes": 0.0,
            "basis": "duration_min_weighted_by_rpe",
        }

    def classify(row: pd.Series) -> str:
        rpe = row.get("rpe")
        if pd.notna(rpe):
            rpe_i = int(float(rpe))
            if rpe_i <= 4:
                return "Low"
            if rpe_i >= 7:
                return "High"
            return "Moderate"
        category = str(row.get("session_category") or "").lower()
        if any(token in category for token in ["tempo", "interval", "vo2", "race", "hill"]):
            return "High"
        if "recovery" in category:
            return "Low"
        return "Moderate"

    frame["bucket"] = frame.apply(classify, axis=1)
    frame["duration_min"] = frame["duration_min"].fillna(0)
    grouped = frame.groupby("bucket", as_index=False).agg(minutes=("duration_min", "sum"))
    totals = {str(r["bucket"]): float(r["minutes"] or 0.0) for _, r in grouped.iterrows()}
    total_minutes = round(sum(totals.values()), 2)
    buckets = []
    for label in ["Low", "Moderate", "High"]:
        value = round(float(totals.get(label, 0.0)), 2)
        pct = round((value / total_minutes) * 100.0, 1) if total_minutes > 0 else 0.0
        buckets.append({"label": label, "value": value, "percent": pct})
    return {"buckets": buckets, "total_minutes": total_minutes, "basis": "duration_min_weighted_by_rpe"}
