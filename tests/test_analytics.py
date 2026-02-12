"""Tests for analytics service."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from core.services.analytics import weekly_summary


def test_weekly_summary_empty():
    df = pd.DataFrame(columns=["id", "date", "duration_min", "load_score"])
    result = weekly_summary(df)
    assert result.empty
    assert list(result.columns) == ["week", "duration_min", "load_score", "sessions"]


def test_weekly_summary_groups_by_week():
    today = date.today()
    df = pd.DataFrame([
        {"id": 1, "date": today, "duration_min": 30, "load_score": 15.0},
        {"id": 2, "date": today - timedelta(days=1), "duration_min": 45, "load_score": 22.5},
        {"id": 3, "date": today - timedelta(days=8), "duration_min": 60, "load_score": 30.0},
    ])
    result = weekly_summary(df)
    assert len(result) >= 1
    assert "duration_min" in result.columns
    assert "sessions" in result.columns


def test_weekly_summary_sums_correctly():
    today = date(2026, 1, 5)  # known Monday
    df = pd.DataFrame([
        {"id": 1, "date": today, "duration_min": 30, "load_score": 10.0},
        {"id": 2, "date": today + timedelta(days=1), "duration_min": 40, "load_score": 20.0},
    ])
    result = weekly_summary(df)
    # Both entries in the same week
    assert result.iloc[0]["duration_min"] == 70
    assert result.iloc[0]["load_score"] == 30.0
    assert result.iloc[0]["sessions"] == 2
