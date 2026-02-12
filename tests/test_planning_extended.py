"""Extended tests for planning service covering edge cases."""

from __future__ import annotations

from datetime import date, timedelta

from core.services.planning import (
    RACE_LONG_RUN_TARGET,
    _phase_for_week,
    assign_week_sessions,
    default_phase_session_tokens,
    generate_plan_weeks,
)


def test_phase_for_week_recovery_at_multiples_of_4():
    assert _phase_for_week(4, 24) == "Recovery"
    assert _phase_for_week(8, 24) == "Recovery"
    assert _phase_for_week(12, 24) == "Recovery"


def test_phase_for_week_base_early():
    assert _phase_for_week(1, 24) == "Base"
    assert _phase_for_week(5, 24) == "Base"


def test_phase_for_week_build_mid():
    # 0.4 * 24 = 9.6, so week 10+ is Build
    assert _phase_for_week(11, 24) == "Build"


def test_phase_for_week_peak_late():
    # 0.75 * 24 = 18, 0.92 * 24 = 22.08
    assert _phase_for_week(19, 24) == "Peak"


def test_phase_for_week_taper_end():
    assert _phase_for_week(23, 24) == "Taper"


def test_default_phase_session_tokens_all_phases():
    for phase in ["Base", "Build", "Peak", "Taper", "Recovery"]:
        tokens = default_phase_session_tokens(phase, 4)
        assert len(tokens) == 4
        assert all(isinstance(t, str) for t in tokens)


def test_default_phase_session_tokens_unknown_phase():
    tokens = default_phase_session_tokens("Unknown", 3)
    assert len(tokens) == 3  # Falls back to Base


def test_assign_week_sessions_correct_dates():
    start = date(2026, 1, 5)  # Monday
    names = ["Easy", "Tempo", "Long", "Recovery"]
    result = assign_week_sessions(start, names)
    assert len(result) == 4
    days = [r["session_day"] for r in result]
    assert days[0] == start  # offset 0
    assert days[1] == start + timedelta(days=1)  # offset 1
    assert days[2] == start + timedelta(days=3)  # offset 3
    assert days[3] == start + timedelta(days=5)  # offset 5


def test_generate_plan_all_race_goals():
    for goal in RACE_LONG_RUN_TARGET:
        weeks = generate_plan_weeks(date(2026, 1, 1), 12, goal)
        assert len(weeks) == 12
        assert all(w["phase"] in {"Base", "Build", "Peak", "Taper", "Recovery"} for w in weeks)


def test_generate_plan_48_weeks():
    weeks = generate_plan_weeks(date(2026, 1, 1), 48, "Marathon", 5, 180)
    assert len(weeks) == 48
    recovery_weeks = [w for w in weeks if w["phase"] == "Recovery"]
    assert len(recovery_weeks) >= 10  # every 4th week


def test_generate_plan_target_load_positive():
    weeks = generate_plan_weeks(date(2026, 1, 1), 12, "10K")
    for w in weeks:
        assert w["target_load"] > 0


def test_generate_plan_weeks_contiguous_dates():
    weeks = generate_plan_weeks(date(2026, 1, 1), 12, "5K")
    for i in range(1, len(weeks)):
        prev_end = weeks[i - 1]["week_end"]
        curr_start = weeks[i]["week_start"]
        assert curr_start == prev_end + timedelta(days=1)
