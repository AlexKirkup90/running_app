from datetime import date

from core.services.planning import assign_week_sessions, generate_plan_weeks


def test_plan_generation_length_and_cutback():
    weeks = generate_plan_weeks(date(2026, 1, 5), 12, "10K", sessions_per_week=4)
    assert len(weeks) == 12
    assert weeks[3]["phase"] == "Recovery"
    assert weeks[3]["target_load"] <= weeks[2]["target_load"] * 0.8
    assert weeks[3]["long_run_minutes"] <= weeks[2]["long_run_minutes"] * 0.8
    assert weeks[4]["target_load"] > weeks[3]["target_load"]


def test_assign_week_sessions_spreads_days():
    week_start = date(2026, 1, 5)
    assignments = assign_week_sessions(week_start, ["A", "B", "C", "D"])
    assert [a["session_day"] for a in assignments] == [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 8), date(2026, 1, 10)]


def test_assign_week_sessions_respects_preferences_and_long_run_day():
    week_start = date(2026, 1, 5)  # Monday
    sessions = ["Tempo / Threshold", "VO2 Intervals", "Long Run", "Easy Run"]
    assignments = assign_week_sessions(
        week_start,
        sessions,
        preferred_days=["Mon", "Wed", "Fri", "Sun"],
        preferred_long_run_day="Sun",
    )
    by_name = {row["session_name"]: row["session_day"] for row in assignments}
    assert by_name["Long Run"] == date(2026, 1, 11)  # Sunday
    assert by_name["Tempo / Threshold"].weekday() in {0, 2, 4, 6}
    assert by_name["VO2 Intervals"].weekday() in {0, 2, 4, 6}
    # Quality sessions should not be back-to-back.
    assert abs((by_name["Tempo / Threshold"] - by_name["VO2 Intervals"]).days) >= 2
