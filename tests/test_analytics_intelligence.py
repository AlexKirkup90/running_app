from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from core.services.analytics import (
    compute_fitness_fatigue,
    compute_intensity_distribution,
    compute_vdot_history,
)
from core.services.race_predictor import predict_all_distances


def _sample_logs_df() -> pd.DataFrame:
    today = date(2026, 2, 1)
    rows = []
    for i in range(21):
        rows.append(
            {
                "id": i + 1,
                "date": today - timedelta(days=i),
                "duration_min": 40 + (i % 4) * 10,
                "load_score": 35 + (i % 5) * 4,
                "rpe": 4 + (i % 4),
                "session_category": "run" if i % 3 else "tempo",
                "distance_km": 8 + (i % 4),
                "avg_pace_sec_per_km": 300 - (i % 3) * 5,
            }
        )
    return pd.DataFrame(rows)


def test_compute_fitness_fatigue_returns_ctl_atl_tsb_series():
    out = compute_fitness_fatigue(_sample_logs_df())
    assert out["latest"] is not None
    assert len(out["series"]) >= 1
    latest = out["series"][-1]
    assert {"ctl", "atl", "tsb", "load_score"} <= set(latest.keys())


def test_compute_vdot_and_intensity_distribution():
    logs_df = _sample_logs_df()
    vdot = compute_vdot_history(logs_df)
    intensity = compute_intensity_distribution(logs_df)
    assert len(vdot["series"]) >= 1
    assert vdot["latest"]["vdot"] > 0
    assert len(intensity["buckets"]) == 3
    assert intensity["total_minutes"] > 0


def test_predict_all_distances_from_benchmark():
    preds = predict_all_distances({"distance_km": 10.0, "duration_min": 45.0})
    assert preds["vdot"] is not None
    assert preds["distances"]["5K"]["predicted_seconds"] > 0
    assert preds["distances"]["Marathon"]["predicted_seconds"] > preds["distances"]["10K"]["predicted_seconds"]
