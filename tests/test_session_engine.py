from core.services.session_engine import adapt_session_structure, compute_acute_chronic_ratio, hr_range_for_label, pace_range_for_label


def _sample_session():
    return {
        "blocks": [
            {"phase": "warmup", "duration_min": 10, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
            {"phase": "main_set", "duration_min": 30, "target": {"pace_zone": "Z3", "hr_zone": "Z3", "rpe_range": [6, 7]}},
            {"phase": "cooldown", "duration_min": 8, "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]}},
        ]
    }


def _sample_v3_session():
    return {
        "version": 3,
        "workout_type": "VO2max Intervals",
        "daniels_pace": "I",
        "blocks": [
            {
                "phase": "warmup",
                "duration_min": 10,
                "target": {"pace_label": "E", "rpe_range": [2, 3]},
            },
            {
                "phase": "main_set",
                "duration_min": 24,
                "target": {"pace_label": "I", "rpe_range": [8, 9]},
                "intervals": [
                    {
                        "reps": 5,
                        "work_duration_min": 4.0,
                        "work_pace": "I",
                        "recovery_duration_min": 3.0,
                        "recovery_pace": "E",
                        "description": "Hard intervals at I pace",
                    }
                ],
            },
            {
                "phase": "cooldown",
                "duration_min": 8,
                "target": {"pace_label": "E", "rpe_range": [2, 3]},
            },
        ],
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


# --- VDOT integration tests ---

def test_v3_vdot_resolves_pace_labels():
    """When VDOT is provided, pace labels should be resolved to concrete sec/km."""
    out = adapt_session_structure(
        _sample_v3_session(), readiness=3.5, pain_flag=False,
        acute_chronic_ratio=1.0, days_to_event=30, vdot=50,
    )
    session = out["session"]
    warmup = session["blocks"][0]
    assert "pace_sec_per_km" in warmup["target"]
    assert warmup["target"]["pace_label"] == "E"
    assert warmup["target"]["pace_sec_per_km"] == 316  # VDOT 50 E pace
    assert "5:16/km" in warmup["target"]["pace_display"]


def test_v3_vdot_resolves_interval_paces():
    out = adapt_session_structure(
        _sample_v3_session(), readiness=3.5, pain_flag=False,
        acute_chronic_ratio=1.0, days_to_event=30, vdot=50,
    )
    main = [b for b in out["session"]["blocks"] if b["phase"] == "main_set"][0]
    ivl = main["intervals"][0]
    assert "work_pace_sec_per_km" in ivl
    assert ivl["work_pace_sec_per_km"] == 248  # VDOT 50 I pace
    assert "work_pace_display" in ivl
    assert "work_pace_band" in ivl
    assert ivl["work_pace_band"][0] < 248 < ivl["work_pace_band"][1]


def test_v3_vdot_resolves_recovery_pace():
    out = adapt_session_structure(
        _sample_v3_session(), readiness=3.5, pain_flag=False,
        acute_chronic_ratio=1.0, days_to_event=30, vdot=50,
    )
    main = [b for b in out["session"]["blocks"] if b["phase"] == "main_set"][0]
    ivl = main["intervals"][0]
    assert "recovery_pace_sec_per_km" in ivl
    assert ivl["recovery_pace_sec_per_km"] == 316  # E pace at VDOT 50


def test_v3_without_vdot_no_pace_resolution():
    """Without VDOT, pace labels should remain as labels without sec/km."""
    out = adapt_session_structure(
        _sample_v3_session(), readiness=3.5, pain_flag=False,
        acute_chronic_ratio=1.0, days_to_event=30,
    )
    warmup = out["session"]["blocks"][0]
    assert "pace_sec_per_km" not in warmup["target"]


def test_v3_downshift_with_vdot():
    """Downshift should shift paces AND then resolve to concrete values."""
    out = adapt_session_structure(
        _sample_v3_session(), readiness=2.5, pain_flag=False,
        acute_chronic_ratio=1.0, days_to_event=30, vdot=50,
    )
    assert out["action"] == "downshift"
    main = [b for b in out["session"]["blocks"] if b["phase"] == "main_set"][0]
    # Main target was I pace, downshifted to T
    assert main["target"]["pace_label"] == "T"
    assert main["target"]["pace_sec_per_km"] == 269  # VDOT 50 T pace


def test_v3_progress_with_vdot():
    out = adapt_session_structure(
        _sample_v3_session(), readiness=4.5, pain_flag=False,
        acute_chronic_ratio=0.8, days_to_event=30, vdot=50,
    )
    assert out["action"] == "progress"
    main = [b for b in out["session"]["blocks"] if b["phase"] == "main_set"][0]
    # Intervals should have +1 rep
    assert main["intervals"][0]["reps"] == 6


def test_v3_taper_with_vdot():
    out = adapt_session_structure(
        _sample_v3_session(), readiness=3.5, pain_flag=False,
        acute_chronic_ratio=1.0, days_to_event=5, vdot=50,
    )
    assert out["action"] == "taper"
    main = [b for b in out["session"]["blocks"] if b["phase"] == "main_set"][0]
    assert main["intervals"][0]["reps"] < 5  # Reps reduced
