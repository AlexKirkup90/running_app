"""Tests for advanced analytics engine."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from core.services.analytics import (
    VdotDataPoint,
    compute_fitness_fatigue,
    compute_intensity_distribution,
    compute_pace_trends,
    compute_vdot_history,
    compute_volume_distribution,
    race_readiness_score,
    vdot_trend,
    weekly_summary,
)


# --- Weekly summary (existing) ---

def test_weekly_summary_basic():
    df = pd.DataFrame([
        {"id": 1, "date": date(2026, 1, 5), "duration_min": 40, "load_score": 20},
        {"id": 2, "date": date(2026, 1, 6), "duration_min": 50, "load_score": 30},
    ])
    w = weekly_summary(df)
    assert len(w) == 1
    assert w.iloc[0]["duration_min"] == 90
    assert w.iloc[0]["sessions"] == 2


def test_weekly_summary_empty():
    df = pd.DataFrame(columns=["id", "date", "duration_min", "load_score"])
    w = weekly_summary(df)
    assert w.empty


# --- VDOT progression ---

def test_compute_vdot_history():
    results = [
        {"date": date(2026, 1, 1), "distance_km": 5.0, "duration_min": 20.0, "source": "race"},
        {"date": date(2026, 2, 1), "distance_km": 5.0, "duration_min": 19.5, "source": "race"},
    ]
    history = compute_vdot_history(results)
    assert len(history) == 2
    assert history[0].vdot < history[1].vdot  # Faster time = higher VDOT
    assert history[0].source == "race"


def test_compute_vdot_history_skips_invalid():
    results = [
        {"date": date(2026, 1, 1), "distance_km": 0, "duration_min": 20},
        {"date": date(2026, 1, 2), "distance_km": 5.0, "duration_min": 0},
    ]
    history = compute_vdot_history(results)
    assert len(history) == 0


def test_vdot_trend_improving():
    history = [
        VdotDataPoint(event_date=date(2026, 1, 1), distance_m=5000, time_seconds=1200, vdot=48.0, source="race"),
        VdotDataPoint(event_date=date(2026, 4, 1), distance_m=5000, time_seconds=1140, vdot=52.0, source="race"),
    ]
    trend = vdot_trend(history)
    assert trend["current_vdot"] == 52.0
    assert trend["peak_vdot"] == 52.0
    assert trend["trend"] == "improving"
    assert trend["improvement_per_month"] > 0


def test_vdot_trend_insufficient():
    history = [VdotDataPoint(event_date=date(2026, 1, 1), distance_m=5000, time_seconds=1200, vdot=48.0, source="race")]
    trend = vdot_trend(history)
    assert trend["trend"] == "insufficient_data"


def test_vdot_trend_empty():
    assert vdot_trend([])["current_vdot"] is None


# --- Fitness / Fatigue ---

def test_fitness_fatigue_basic():
    loads = [{"date": date(2026, 1, 1) + timedelta(days=i), "load": 50.0} for i in range(28)]
    points = compute_fitness_fatigue(loads)
    assert len(points) == 28
    assert points[-1].ctl > 0
    assert points[-1].atl > 0
    # ATL should be closer to 50 than CTL (shorter window)
    assert points[-1].atl > points[-1].ctl


def test_fitness_fatigue_rest_day_filled():
    loads = [
        {"date": date(2026, 1, 1), "load": 100},
        {"date": date(2026, 1, 5), "load": 100},
    ]
    points = compute_fitness_fatigue(loads)
    assert len(points) == 5  # Days 1-5 inclusive
    assert points[1].daily_load == 0  # Rest day filled


def test_fitness_fatigue_empty():
    assert compute_fitness_fatigue([]) == []


def test_race_readiness_score():
    assert race_readiness_score(15) == "race_ready"
    assert race_readiness_score(5) == "fresh"
    assert race_readiness_score(-5) == "slightly_fatigued"
    assert race_readiness_score(-15) == "fatigued"
    assert race_readiness_score(-25) == "overreached"
    assert race_readiness_score(30) == "detrained"


# --- Pace trends ---

def test_pace_trends_basic():
    logs = [
        {"date": date(2026, 1, 1), "session_category": "Easy Run", "avg_pace_sec_per_km": 340, "distance_km": 8},
        {"date": date(2026, 1, 2), "session_category": "Easy Run", "avg_pace_sec_per_km": 335, "distance_km": 8},
        {"date": date(2026, 1, 3), "session_category": "Tempo Run", "avg_pace_sec_per_km": 270, "distance_km": 6},
    ]
    df = compute_pace_trends(logs)
    assert not df.empty
    assert "rolling_avg_pace" in df.columns
    categories = df["category"].unique()
    assert "Easy Run" in categories
    assert "Tempo Run" in categories


def test_pace_trends_empty():
    df = compute_pace_trends([])
    assert df.empty


def test_pace_trends_skips_zero_pace():
    logs = [{"date": date(2026, 1, 1), "session_category": "Easy", "avg_pace_sec_per_km": 0}]
    df = compute_pace_trends(logs)
    assert df.empty


# --- Volume / Intensity distribution ---

def test_volume_distribution():
    logs = [
        {"session_category": "Easy Run", "duration_min": 120},
        {"session_category": "Tempo Run", "duration_min": 30},
    ]
    vol = compute_volume_distribution(logs)
    assert vol["Easy Run"] == 80.0
    assert vol["Tempo Run"] == 20.0


def test_volume_distribution_empty():
    assert compute_volume_distribution([]) == {}


def test_intensity_distribution():
    logs = [
        {"duration_min": 80, "rpe": 3},  # easy
        {"duration_min": 10, "rpe": 6},  # moderate
        {"duration_min": 10, "rpe": 9},  # hard
    ]
    dist = compute_intensity_distribution(logs)
    assert dist["easy"] == 80.0
    assert dist["moderate"] == 10.0
    assert dist["hard"] == 10.0


def test_intensity_distribution_empty():
    dist = compute_intensity_distribution([])
    assert dist == {"easy": 0.0, "moderate": 0.0, "hard": 0.0}
