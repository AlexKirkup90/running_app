"""Tests for simulation service."""

from __future__ import annotations

from core.services.simulation import simulate_missed_week


def test_simulate_missed_week_reduces_load():
    result = simulate_missed_week(100.0)
    assert result["new_target_load"] == 85.0
    assert "deload" in result["note"].lower()


def test_simulate_missed_week_zero_load():
    result = simulate_missed_week(0.0)
    assert result["new_target_load"] == 0.0


def test_simulate_missed_week_large_load():
    result = simulate_missed_week(500.0)
    assert result["new_target_load"] == 425.0
