from core.services.session_engine import adapt_session_structure, compute_acute_chronic_ratio, hr_range_for_label, pace_range_for_label


def _sample_session():
    return {
        "blocks": [
            {"phase": "warmup", "duration_min": 10, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
            {"phase": "main_set", "duration_min": 30, "target": {"pace_zone": "Z3", "hr_zone": "Z3", "rpe_range": [6, 7]}},
            {"phase": "cooldown", "duration_min": 8, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
        ]
    }


def test_adaptation_downshifts_on_low_readiness():
    out = adapt_session_structure(_sample_session(), readiness=2.5, pain_flag=False, acute_chronic_ratio=1.0, days_to_event=30)
    assert out["action"] == "downshift"
    main = [b for b in out["session"]["blocks"] if b["phase"] == "main_set"][0]
    assert main["duration_min"] < 30
    assert main["target"]["pace_zone"] == "Z2"


def test_acute_chronic_ratio_baseline():
    loads = [50.0] * 28
    ratio = compute_acute_chronic_ratio(loads)
    assert 0.9 <= ratio <= 1.1


def test_pace_range_for_zone_label():
    pace = pace_range_for_label("Z3-Z4", threshold_pace_sec_per_km=280, easy_pace_sec_per_km=340)
    assert "4:" in pace


def test_hr_range_for_zone_label():
    hr = hr_range_for_label("Z4", max_hr=190, resting_hr=55)
    assert hr.endswith("bpm")
