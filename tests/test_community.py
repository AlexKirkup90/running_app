"""Tests for Phase 7 — Community & Social features.

Covers: leaderboards, challenge progress, activity feed formatting,
streak tracking, challenge metric aggregation.
"""

from __future__ import annotations

from datetime import date

from core.services.community import (
    aggregate_challenge_metric,
    compute_challenge_progress,
    compute_leaderboard,
    compute_training_streak,
    format_activity_summary,
)


# ── Leaderboard tests ────────────────────────────────────────────────────

class TestLeaderboard:
    def test_ranks_by_distance(self):
        data = [
            {"athlete_id": 1, "name": "Alice", "distance_km": 50, "duration_min": 300, "sessions_count": 5},
            {"athlete_id": 2, "name": "Bob", "distance_km": 80, "duration_min": 400, "sessions_count": 6},
            {"athlete_id": 3, "name": "Charlie", "distance_km": 30, "duration_min": 200, "sessions_count": 3},
        ]
        lb = compute_leaderboard(data, metric="distance")
        assert len(lb) == 3
        assert lb[0].rank == 1
        assert lb[0].name == "Bob"
        assert lb[0].value == 80
        assert lb[2].rank == 3
        assert lb[2].name == "Charlie"

    def test_ranks_by_duration(self):
        data = [
            {"athlete_id": 1, "name": "Alice", "distance_km": 50, "duration_min": 500},
            {"athlete_id": 2, "name": "Bob", "distance_km": 80, "duration_min": 300},
        ]
        lb = compute_leaderboard(data, metric="duration")
        assert lb[0].name == "Alice"
        assert lb[0].value == 500

    def test_ranks_by_sessions(self):
        data = [
            {"athlete_id": 1, "name": "A", "sessions_count": 7},
            {"athlete_id": 2, "name": "B", "sessions_count": 3},
        ]
        lb = compute_leaderboard(data, metric="sessions")
        assert lb[0].name == "A"

    def test_empty_list(self):
        lb = compute_leaderboard([], metric="distance")
        assert lb == []

    def test_single_entry(self):
        data = [{"athlete_id": 1, "name": "Solo", "distance_km": 10}]
        lb = compute_leaderboard(data)
        assert len(lb) == 1
        assert lb[0].rank == 1


# ── Challenge Progress tests ─────────────────────────────────────────────

class TestChallengeProgress:
    def test_partial_progress(self):
        prog = compute_challenge_progress(25.0, 100.0, date(2026, 2, 28), today=date(2026, 2, 1))
        assert prog.pct == 25.0
        assert not prog.completed
        assert prog.days_remaining == 27

    def test_completed(self):
        prog = compute_challenge_progress(100.0, 100.0, date(2026, 2, 28), today=date(2026, 2, 15))
        assert prog.pct == 100.0
        assert prog.completed

    def test_over_target(self):
        prog = compute_challenge_progress(150.0, 100.0, date(2026, 2, 28))
        assert prog.pct == 100.0
        assert prog.completed

    def test_zero_target(self):
        prog = compute_challenge_progress(50.0, 0.0, date(2026, 2, 28))
        assert prog.pct == 0.0

    def test_past_end_date(self):
        prog = compute_challenge_progress(50.0, 100.0, date(2026, 1, 1), today=date(2026, 2, 1))
        assert prog.days_remaining == 0


# ── Challenge Metric Aggregation ─────────────────────────────────────────

class TestAggregateChallenge:
    def test_distance(self):
        logs = [{"distance_km": 10}, {"distance_km": 15}]
        assert aggregate_challenge_metric(logs, "distance") == 25

    def test_duration(self):
        logs = [{"duration_min": 30}, {"duration_min": 45}]
        assert aggregate_challenge_metric(logs, "duration") == 75

    def test_elevation(self):
        logs = [{"elevation_gain_m": 100}, {"elevation_gain_m": 200}]
        assert aggregate_challenge_metric(logs, "elevation") == 300

    def test_streak(self):
        logs = [
            {"date": date(2026, 1, 1)},
            {"date": date(2026, 1, 2)},
            {"date": date(2026, 1, 3)},
            {"date": date(2026, 1, 5)},  # gap
            {"date": date(2026, 1, 6)},
        ]
        assert aggregate_challenge_metric(logs, "streak") == 3

    def test_streak_empty(self):
        assert aggregate_challenge_metric([], "streak") == 0

    def test_unknown_type(self):
        assert aggregate_challenge_metric([{"distance_km": 10}], "unknown") == 0


# ── Activity Feed Formatting ─────────────────────────────────────────────

class TestFormatActivitySummary:
    def test_full_format(self):
        result = format_activity_summary("Easy Run", 45, 8.5)
        assert "Easy Run" in result
        assert "45min" in result
        assert "8.5km" in result

    def test_hours_format(self):
        result = format_activity_summary("Long Run", 90, 18.0)
        assert "1h30m" in result

    def test_no_distance(self):
        result = format_activity_summary("Recovery Run", 30, 0)
        assert "km" not in result

    def test_no_duration(self):
        result = format_activity_summary("Sprint", 0, 0.4)
        assert "Sprint" in result


# ── Streak tracking tests ────────────────────────────────────────────────

class TestTrainingStreak:
    def test_consecutive_days(self):
        dates = [date(2026, 1, 10), date(2026, 1, 9), date(2026, 1, 8)]
        assert compute_training_streak(dates) == 3

    def test_with_gap(self):
        dates = [date(2026, 1, 10), date(2026, 1, 9), date(2026, 1, 7)]
        assert compute_training_streak(dates) == 2

    def test_single_day(self):
        assert compute_training_streak([date(2026, 1, 10)]) == 1

    def test_empty(self):
        assert compute_training_streak([]) == 0

    def test_duplicate_dates(self):
        dates = [date(2026, 1, 10), date(2026, 1, 10), date(2026, 1, 9)]
        assert compute_training_streak(dates) == 2

    def test_unsorted_input(self):
        dates = [date(2026, 1, 8), date(2026, 1, 10), date(2026, 1, 9)]
        assert compute_training_streak(dates) == 3
