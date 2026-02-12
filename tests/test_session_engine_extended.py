"""Extended tests for session engine covering more adaptation and zone scenarios."""

from __future__ import annotations

from core.services.session_engine import (
    adapt_session_structure,
    compute_acute_chronic_ratio,
    hr_range_for_label,
    hr_zone_bounds,
    pace_from_sec_per_km,
    pace_range_for_label,
)


def test_adapt_taper_on_event_proximity():
    structure = {
        "blocks": [
            {"phase": "warmup", "duration_min": 10, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
            {"phase": "main_set", "duration_min": 30, "target": {"pace_zone": "Z3", "hr_zone": "Z3", "rpe_range": [6, 7]}},
            {"phase": "cooldown", "duration_min": 8, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
        ]
    }
    result = adapt_session_structure(structure, 4.0, False, 1.0, 5)
    assert result["action"] == "taper"
    main_block = [b for b in result["session"]["blocks"] if b["phase"] == "main_set"][0]
    assert main_block["duration_min"] < 30


def test_adapt_progress_on_high_readiness():
    structure = {
        "blocks": [
            {"phase": "warmup", "duration_min": 10, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
            {"phase": "main_set", "duration_min": 30, "target": {"pace_zone": "Z3", "hr_zone": "Z3", "rpe_range": [6, 7]}},
            {"phase": "cooldown", "duration_min": 8, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
        ]
    }
    result = adapt_session_structure(structure, 4.5, False, 0.8, None)
    assert result["action"] == "progress"
    main_block = [b for b in result["session"]["blocks"] if b["phase"] == "main_set"][0]
    assert main_block["duration_min"] == 33  # 30 * 1.1


def test_adapt_keep_when_normal():
    structure = {
        "blocks": [
            {"phase": "warmup", "duration_min": 10, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
            {"phase": "main_set", "duration_min": 30, "target": {"pace_zone": "Z3", "hr_zone": "Z3", "rpe_range": [6, 7]}},
            {"phase": "cooldown", "duration_min": 8, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
        ]
    }
    result = adapt_session_structure(structure, 3.5, False, 1.0, None)
    assert result["action"] == "keep"


def test_adapt_downshift_on_pain():
    structure = {
        "blocks": [
            {"phase": "warmup", "duration_min": 10, "target": {"pace_zone": "Z2", "hr_zone": "Z2", "rpe_range": [3, 4]}},
            {"phase": "main_set", "duration_min": 20, "target": {"pace_zone": "Z4", "hr_zone": "Z4", "rpe_range": [7, 8]}},
            {"phase": "cooldown", "duration_min": 8, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
        ]
    }
    result = adapt_session_structure(structure, 4.0, True, 1.0, None)
    assert result["action"] == "downshift"
    main_block = [b for b in result["session"]["blocks"] if b["phase"] == "main_set"][0]
    assert main_block["duration_min"] == 15  # 20 * 0.75


def test_compute_acr_empty():
    assert compute_acute_chronic_ratio([]) == 1.0


def test_compute_acr_short_window():
    loads = [10.0] * 5
    ratio = compute_acute_chronic_ratio(loads)
    # With <=7 entries, uses all as baseline: recent=50, baseline=50/5=10, ratio=(50/7)/10
    assert 0.5 < ratio < 1.5


def test_compute_acr_increasing_load():
    loads = [10.0] * 14 + [20.0] * 7
    ratio = compute_acute_chronic_ratio(loads)
    assert ratio > 1.0  # recent load higher than baseline


def test_pace_from_sec_per_km_formats():
    assert pace_from_sec_per_km(300) == "5:00/km"
    assert pace_from_sec_per_km(330) == "5:30/km"
    assert pace_from_sec_per_km(None) == "n/a"
    assert pace_from_sec_per_km(0) == "n/a"


def test_hr_zone_bounds_valid():
    bounds = hr_zone_bounds(190, 50)
    assert "Z1" in bounds
    assert "Z5" in bounds
    assert bounds["Z1"][0] < bounds["Z5"][0]
    assert bounds["Z5"][1] == 190  # max_hr


def test_hr_zone_bounds_invalid():
    assert hr_zone_bounds(None, 50) == {}
    assert hr_zone_bounds(50, 50) == {}
    assert hr_zone_bounds(40, 50) == {}


def test_pace_range_for_label_zones():
    result = pace_range_for_label("Z2", 240, 300)
    assert "/km" in result
    assert result != "n/a"


def test_pace_range_no_data():
    assert pace_range_for_label("Z2", None, None) == "n/a"
    assert pace_range_for_label("", 240, 300) == "n/a"


def test_hr_range_for_label_valid():
    result = hr_range_for_label("Z3", 190, 50)
    assert "bpm" in result


def test_hr_range_for_label_no_data():
    assert hr_range_for_label("Z3", None, None) == "n/a"
