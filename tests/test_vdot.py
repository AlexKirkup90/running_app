"""Tests for VDOT pacing module."""

from __future__ import annotations

import pytest

from core.services.vdot import (
    VDOT_MAX,
    VDOT_MIN,
    DanielsPaces,
    daniels_pace_band,
    estimate_vdot,
    get_paces,
    pace_display,
    pace_range_display,
    resolve_daniels_pace,
    vdot_from_race,
)


def test_get_paces_known_vdot():
    p = get_paces(50)
    assert isinstance(p, DanielsPaces)
    assert p.vdot == 50
    assert p.easy == 316
    assert p.marathon == 287
    assert p.threshold == 269
    assert p.interval == 248
    assert p.repetition == 230


def test_get_paces_clamps_low():
    p = get_paces(10)
    assert p.vdot == VDOT_MIN


def test_get_paces_clamps_high():
    p = get_paces(100)
    assert p.vdot == VDOT_MAX


def test_paces_decrease_with_higher_vdot():
    low = get_paces(35)
    high = get_paces(65)
    assert high.easy < low.easy
    assert high.threshold < low.threshold
    assert high.interval < low.interval


def test_pace_hierarchy():
    """E > M > T > I > R (slower to faster)."""
    p = get_paces(50)
    assert p.easy > p.marathon > p.threshold > p.interval > p.repetition


def test_pace_display():
    assert pace_display(300) == "5:00/km"
    assert pace_display(269) == "4:29/km"
    assert pace_display(0) == "n/a"


def test_pace_range_display():
    result = pace_range_display(269, 316)
    assert "4:29/km" in result
    assert "5:16/km" in result


def test_estimate_vdot_5k():
    # ~20 min 5K = roughly VDOT 49-51 per Daniels tables
    vdot = estimate_vdot(5000, 20 * 60)
    assert 48 <= vdot <= 52


def test_estimate_vdot_marathon():
    # ~3:30 marathon = roughly VDOT 43-45
    vdot = estimate_vdot(42195, 3.5 * 3600)
    assert 40 <= vdot <= 48


def test_estimate_vdot_invalid():
    assert estimate_vdot(0, 100) == 30.0
    assert estimate_vdot(5000, 0) == 30.0


def test_vdot_from_race_5k():
    vdot = vdot_from_race("5K", 20 * 60)
    assert 48 <= vdot <= 52


def test_vdot_from_race_invalid_distance():
    with pytest.raises(ValueError, match="Unknown distance"):
        vdot_from_race("50K", 100)


def test_resolve_daniels_pace():
    assert resolve_daniels_pace("E", 50) == 316
    assert resolve_daniels_pace("T", 50) == 269
    assert resolve_daniels_pace("I", 50) == 248
    assert resolve_daniels_pace("R", 50) == 230
    assert resolve_daniels_pace("X", 50) is None


def test_daniels_pace_band():
    fast, slow = daniels_pace_band("T", 50)
    assert fast < 269 < slow
    assert slow - fast <= 15  # ±2% of ~269


def test_daniels_pace_band_easy_wider():
    fast_e, slow_e = daniels_pace_band("E", 50)
    fast_t, slow_t = daniels_pace_band("T", 50)
    # Easy band should be wider (±3%) than threshold (±2%)
    assert (slow_e - fast_e) >= (slow_t - fast_t)


def test_daniels_pace_band_invalid():
    assert daniels_pace_band("X", 50) == (0, 0)
