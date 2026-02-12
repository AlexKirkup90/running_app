"""Tests for TRIMP, monotony, strain, and training load metrics."""

from __future__ import annotations

from core.services.training_load import (
    compute_session_load,
    compute_srpe_load,
    compute_trimp,
    compute_weekly_metrics,
    overtraining_risk,
)


def test_srpe_load():
    assert compute_srpe_load(60, 7) == 420.0
    assert compute_srpe_load(0, 7) == 0.0
    assert compute_srpe_load(60, 0) == 60.0  # clamp to 1


def test_trimp_with_hr():
    trimp = compute_trimp(60, avg_hr=150, max_hr=190, resting_hr=50, rpe=7)
    assert trimp > 0
    # Higher HR → higher TRIMP
    trimp_high = compute_trimp(60, avg_hr=170, max_hr=190, resting_hr=50, rpe=7)
    assert trimp_high > trimp


def test_trimp_without_hr():
    trimp = compute_trimp(60, avg_hr=None, max_hr=None, resting_hr=None, rpe=7)
    assert trimp > 0
    # Higher RPE → higher estimated TRIMP
    trimp_low = compute_trimp(60, avg_hr=None, max_hr=None, resting_hr=None, rpe=3)
    assert trimp > trimp_low


def test_trimp_longer_duration_higher():
    short = compute_trimp(30, avg_hr=150, max_hr=190, resting_hr=50, rpe=7)
    long = compute_trimp(90, avg_hr=150, max_hr=190, resting_hr=50, rpe=7)
    assert long > short


def test_compute_session_load():
    load = compute_session_load(60, 7, avg_hr=150, max_hr=190, resting_hr=50)
    assert load.srpe_load == 420.0
    assert load.trimp > 0
    assert load.duration_min == 60
    assert load.rpe == 7


def test_weekly_metrics_uniform():
    # 7 days of equal load → high monotony
    daily = [300.0] * 7
    metrics = compute_weekly_metrics(daily)
    assert metrics.session_count == 7
    assert metrics.total_srpe == 2100.0
    assert metrics.avg_daily_load == 300.0


def test_weekly_metrics_varied():
    daily = [500.0, 200.0, 0.0, 400.0, 0.0, 300.0, 600.0]
    metrics = compute_weekly_metrics(daily)
    assert metrics.session_count == 5
    assert metrics.total_srpe == 2000.0
    assert metrics.monotony > 0


def test_weekly_metrics_empty():
    metrics = compute_weekly_metrics([])
    assert metrics.total_srpe == 0
    assert metrics.session_count == 0
    assert metrics.monotony == 0


def test_weekly_metrics_rest_week():
    daily = [0.0] * 7
    metrics = compute_weekly_metrics(daily)
    assert metrics.session_count == 0
    assert metrics.total_srpe == 0


def test_overtraining_risk_low():
    assert overtraining_risk(0.8, 1500) == "low"


def test_overtraining_risk_moderate():
    assert overtraining_risk(1.5, 3000) == "moderate"
    assert overtraining_risk(1.0, 4500) == "moderate"


def test_overtraining_risk_high():
    assert overtraining_risk(2.5, 7000) == "high"


def test_monotony_zero_stdev():
    # All same load → stdev=0 → monotony=0 (protected division)
    daily = [300.0] * 7
    metrics = compute_weekly_metrics(daily)
    assert metrics.monotony == 0.0  # stdev is 0 for uniform data
