from datetime import date

from core.services.planning import _phase_for_week, assign_week_sessions, generate_plan_weeks


def test_plan_generation_length_and_cutback():
    weeks = generate_plan_weeks(date(2026, 1, 5), 12, "10K", sessions_per_week=4)
    assert len(weeks) == 12
    assert weeks[3]["phase"] == "Recovery"


def test_assign_week_sessions_spreads_days():
    week_start = date(2026, 1, 5)
    assignments = assign_week_sessions(week_start, ["A", "B", "C", "D"])
    assert [a["session_day"] for a in assignments] == [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 8), date(2026, 1, 10)]


# --- Distance-specific phase allocation tests ---

def test_5k_plan_has_vo2max_in_build():
    weeks = generate_plan_weeks(date(2026, 1, 5), 16, "5K", sessions_per_week=4)
    build_weeks = [w for w in weeks if w["phase"] == "Build"]
    assert len(build_weeks) > 0
    for bw in build_weeks:
        assert "VO2max Intervals" in bw["sessions_order"]


def test_marathon_plan_has_mpace_in_build():
    weeks = generate_plan_weeks(date(2026, 1, 5), 24, "Marathon", sessions_per_week=5)
    build_weeks = [w for w in weeks if w["phase"] == "Build"]
    assert len(build_weeks) > 0
    for bw in build_weeks:
        assert "Long Run with M-Pace Finish" in bw["sessions_order"]


def test_half_marathon_build_has_tempo():
    weeks = generate_plan_weeks(date(2026, 1, 5), 20, "Half Marathon", sessions_per_week=4)
    build_weeks = [w for w in weeks if w["phase"] == "Build"]
    assert len(build_weeks) > 0
    for bw in build_weeks:
        assert "Tempo Run" in bw["sessions_order"]


def test_mile_build_has_repetitions():
    weeks = generate_plan_weeks(date(2026, 1, 5), 12, "Mile", sessions_per_week=4)
    build_weeks = [w for w in weeks if w["phase"] == "Build"]
    assert len(build_weeks) > 0
    for bw in build_weeks:
        assert "Repetitions" in bw["sessions_order"]


def test_5k_and_marathon_have_different_sessions():
    """5K and Marathon plans in Build phase should produce different session mixes."""
    plan_5k = generate_plan_weeks(date(2026, 1, 5), 16, "5K", sessions_per_week=5)
    plan_mar = generate_plan_weeks(date(2026, 1, 5), 24, "Marathon", sessions_per_week=5)
    build_5k = next(w for w in plan_5k if w["phase"] == "Build")
    build_mar = next(w for w in plan_mar if w["phase"] == "Build")
    assert build_5k["sessions_order"] != build_mar["sessions_order"]


def test_phase_allocation_marathon_longer_base():
    """Marathon should have more base weeks than 5K for same total plan length."""
    total = 20
    marathon_base = sum(1 for w in range(1, total + 1) if _phase_for_week(w, total, "Marathon") == "Base")
    fivek_base = sum(1 for w in range(1, total + 1) if _phase_for_week(w, total, "5K") == "Base")
    assert marathon_base >= fivek_base


def test_plan_unknown_distance_uses_fallback():
    """Unknown distance should still produce a valid plan using generic templates."""
    weeks = generate_plan_weeks(date(2026, 1, 5), 12, "50K", sessions_per_week=4)
    assert len(weeks) == 12
    assert all(len(w["sessions_order"]) == 4 for w in weeks)


def test_phase_for_week_recovery_every_4th():
    for total in [12, 16, 20, 24]:
        assert _phase_for_week(4, total) == "Recovery"
        assert _phase_for_week(8, total) == "Recovery"


def test_all_supported_distances_generate_plans():
    for goal in ["800m", "1500m", "Mile", "5K", "10K", "Half Marathon", "Marathon"]:
        weeks = generate_plan_weeks(date(2026, 1, 5), 12, goal, sessions_per_week=4)
        assert len(weeks) == 12, f"Failed for {goal}"
        assert all(len(w["sessions_order"]) == 4 for w in weeks), f"Session count wrong for {goal}"
