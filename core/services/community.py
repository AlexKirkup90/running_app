"""Community & Social service layer.

Provides logic for training groups, challenges, leaderboards, kudos,
and group messaging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


# ── Leaderboard ──────────────────────────────────────────────────────────

@dataclass
class LeaderboardEntry:
    athlete_id: int
    name: str
    value: float
    rank: int


def compute_leaderboard(
    athlete_logs: list[dict[str, Any]],
    metric: str = "distance",
) -> list[LeaderboardEntry]:
    """Compute a ranked leaderboard from training log data.

    Args:
        athlete_logs: List of dicts with keys: athlete_id, name,
                      distance_km, duration_min, load_score, sessions_count
        metric: One of 'distance', 'duration', 'load', 'sessions'

    Returns sorted list of LeaderboardEntry (rank 1 = best).
    """
    key_map = {
        "distance": "distance_km",
        "duration": "duration_min",
        "load": "load_score",
        "sessions": "sessions_count",
    }
    key = key_map.get(metric, "distance_km")

    sorted_logs = sorted(athlete_logs, key=lambda x: x.get(key, 0), reverse=True)
    return [
        LeaderboardEntry(
            athlete_id=entry["athlete_id"],
            name=entry["name"],
            value=entry.get(key, 0),
            rank=i + 1,
        )
        for i, entry in enumerate(sorted_logs)
    ]


# ── Challenge Progress ───────────────────────────────────────────────────

@dataclass
class ChallengeProgress:
    athlete_id: int
    current: float
    target: float
    pct: float
    completed: bool
    days_remaining: int


def compute_challenge_progress(
    current_value: float,
    target_value: float,
    end_date: date,
    today: date | None = None,
) -> ChallengeProgress:
    """Calculate progress toward a challenge target.

    Returns a ChallengeProgress with completion percentage and days remaining.
    """
    if today is None:
        today = date.today()

    pct = min(100.0, (current_value / target_value * 100)) if target_value > 0 else 0.0
    completed = current_value >= target_value
    days_remaining = max(0, (end_date - today).days)

    return ChallengeProgress(
        athlete_id=0,  # Caller fills in
        current=round(current_value, 2),
        target=target_value,
        pct=round(pct, 1),
        completed=completed,
        days_remaining=days_remaining,
    )


def aggregate_challenge_metric(
    logs: list[dict[str, Any]],
    challenge_type: str,
) -> float:
    """Sum the relevant metric from training logs for a challenge type.

    Args:
        logs: List of dicts with keys: distance_km, duration_min, date, elevation_gain_m
        challenge_type: One of 'distance', 'duration', 'streak', 'elevation'

    Returns the aggregated value.
    """
    if challenge_type == "distance":
        return sum(log.get("distance_km", 0) for log in logs)
    elif challenge_type == "duration":
        return sum(log.get("duration_min", 0) for log in logs)
    elif challenge_type == "elevation":
        return sum(log.get("elevation_gain_m", 0) for log in logs)
    elif challenge_type == "streak":
        # Count consecutive days with at least one log
        if not logs:
            return 0
        dates = sorted({log["date"] for log in logs if "date" in log})
        if not dates:
            return 0
        max_streak = current_streak = 1
        for i in range(1, len(dates)):
            prev = dates[i - 1] if isinstance(dates[i - 1], date) else date.fromisoformat(str(dates[i - 1]))
            curr = dates[i] if isinstance(dates[i], date) else date.fromisoformat(str(dates[i]))
            if (curr - prev).days == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        return max_streak
    return 0


# ── Group Activity Feed ──────────────────────────────────────────────────

@dataclass
class ActivityFeedItem:
    athlete_id: int
    athlete_name: str
    activity_summary: str
    timestamp: datetime
    kudos_count: int = 0


def format_activity_summary(
    session_category: str,
    duration_min: int,
    distance_km: float,
) -> str:
    """Format a training log into a human-readable feed summary."""
    parts = [session_category]
    if duration_min > 0:
        h, m = divmod(duration_min, 60)
        if h > 0:
            parts.append(f"{h}h{m:02d}m")
        else:
            parts.append(f"{m}min")
    if distance_km > 0:
        parts.append(f"{distance_km:.1f}km")
    return " — ".join(parts)


# ── Streak tracking ─────────────────────────────────────────────────────

def compute_training_streak(log_dates: list[date]) -> int:
    """Compute the current consecutive-day training streak ending today.

    Args:
        log_dates: List of dates with training logs (need not be sorted/unique).

    Returns number of consecutive days ending at the most recent date.
    """
    if not log_dates:
        return 0
    unique_dates = sorted(set(log_dates), reverse=True)
    streak = 1
    for i in range(1, len(unique_dates)):
        if (unique_dates[i - 1] - unique_dates[i]).days == 1:
            streak += 1
        else:
            break
    return streak
