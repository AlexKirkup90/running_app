"""Tests for Daniels-informed session catalog."""

from __future__ import annotations

from core.services.session_catalog import (
    CATALOG,
    PHASE_TEMPLATES,
    build_prescriptive_progression,
    build_prescriptive_regression,
    build_prescriptive_structure,
    build_prescriptive_targets,
    get_phase_sessions,
    get_workout_type,
)


def test_catalog_has_all_core_types():
    expected = [
        "Easy Run", "Recovery Run", "Long Run", "Long Run with M-Pace Finish",
        "Marathon Pace Run", "Tempo Run", "Cruise Intervals", "Threshold Repeats",
        "VO2max Intervals", "VO2max Short Intervals", "Repetitions",
        "Hill Repeats", "Fartlek", "Strides", "Race Pace Run", "Race Rehearsal",
        "Benchmark / Time Trial", "Taper / Openers", "Cross-Training",
    ]
    for name in expected:
        assert name in CATALOG, f"Missing workout type: {name}"


def test_catalog_count():
    assert len(CATALOG) >= 19


def test_all_workouts_have_daniels_pace():
    for name, wt in CATALOG.items():
        assert wt.daniels_pace in ("E", "M", "T", "I", "R"), f"{name} has invalid pace: {wt.daniels_pace}"


def test_all_workouts_have_phase_affinity():
    for name, wt in CATALOG.items():
        assert len(wt.phase_affinity) > 0, f"{name} has no phase affinity"


def test_all_workouts_have_rpe_range():
    for name, wt in CATALOG.items():
        lo, hi = wt.rpe_range
        assert 1 <= lo <= hi <= 10, f"{name} has invalid RPE: {wt.rpe_range}"


def test_interval_workouts_have_prescriptions():
    interval_types = ["Cruise Intervals", "Threshold Repeats", "VO2max Intervals",
                      "VO2max Short Intervals", "Repetitions", "Hill Repeats"]
    for name in interval_types:
        wt = CATALOG[name]
        assert len(wt.intervals) > 0, f"{name} should have intervals"
        ivl = wt.intervals[0]
        assert ivl.reps > 0
        assert ivl.work_duration_min > 0
        assert ivl.work_pace in ("E", "M", "T", "I", "R")


def test_get_workout_type():
    wt = get_workout_type("Tempo Run")
    assert wt is not None
    assert wt.daniels_pace == "T"


def test_get_workout_type_missing():
    assert get_workout_type("Nonexistent") is None


def test_phase_templates_all_phases():
    for phase in ["Base", "Build", "Peak", "Taper", "Recovery"]:
        assert phase in PHASE_TEMPLATES
        assert len(PHASE_TEMPLATES[phase]) >= 3


def test_get_phase_sessions_caps():
    sessions = get_phase_sessions("Build", 4)
    assert len(sessions) == 4
    assert "Tempo Run" in sessions


def test_get_phase_sessions_unknown_phase():
    sessions = get_phase_sessions("Unknown", 3)
    assert len(sessions) == 3  # Falls back to Base


def test_build_prescriptive_structure_v3():
    wt = CATALOG["VO2max Intervals"]
    structure = build_prescriptive_structure(wt, 50)
    assert structure["version"] == 3
    assert structure["workout_type"] == "VO2max Intervals"
    assert structure["daniels_pace"] == "I"
    blocks = structure["blocks"]
    assert len(blocks) == 3
    phases = [b["phase"] for b in blocks]
    assert "warmup" in phases
    assert "main_set" in phases
    assert "cooldown" in phases
    main = [b for b in blocks if b["phase"] == "main_set"][0]
    assert "intervals" in main
    assert main["intervals"][0]["reps"] > 0
    assert main["intervals"][0]["work_pace"] == "I"


def test_build_prescriptive_structure_easy_run():
    wt = CATALOG["Easy Run"]
    structure = build_prescriptive_structure(wt, 40)
    main = [b for b in structure["blocks"] if b["phase"] == "main_set"][0]
    assert main["target"]["pace_label"] == "E"
    # Easy runs have no intervals
    assert main["intervals"] == []


def test_build_prescriptive_targets():
    wt = CATALOG["Cruise Intervals"]
    targets = build_prescriptive_targets(wt)
    assert targets["primary"]["pace_label"] == "T"
    assert targets["primary"]["rpe_range"] == [6, 7]


def test_build_prescriptive_progression():
    wt = CATALOG["Cruise Intervals"]
    prog = build_prescriptive_progression(wt)
    assert len(prog) >= 1
    assert "trigger" in list(prog.values())[0]
    assert "action" in list(prog.values())[0]


def test_build_prescriptive_regression():
    wt = CATALOG["Cruise Intervals"]
    reg = build_prescriptive_regression(wt)
    assert len(reg) >= 1
    assert "trigger" in list(reg.values())[0]


def test_progression_defaults_when_empty():
    wt = CATALOG["Benchmark / Time Trial"]
    prog = build_prescriptive_progression(wt)
    assert "rule_1" in prog


def test_regression_defaults_when_empty():
    wt = CATALOG["Cross-Training"]
    reg = build_prescriptive_regression(wt)
    assert "rule_1" in reg


def test_build_phase_sessions_build():
    sessions = get_phase_sessions("Build", 5)
    assert "Tempo Run" in sessions
    assert "VO2max Intervals" in sessions
    assert "Long Run with M-Pace Finish" in sessions


def test_build_phase_sessions_peak():
    sessions = get_phase_sessions("Peak", 5)
    assert "Race Pace Run" in sessions
    assert "VO2max Intervals" in sessions


def test_build_phase_sessions_taper():
    sessions = get_phase_sessions("Taper", 4)
    assert "Taper / Openers" in sessions
