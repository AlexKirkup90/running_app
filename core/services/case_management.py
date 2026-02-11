from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


def athlete_risk_bucket(readiness: float, adherence: float) -> str:
    if readiness < 3 or adherence < 0.7:
        return "at-risk"
    if readiness < 3.5:
        return "watch"
    return "stable"


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(hour=12, minute=0))
    return datetime.min


def build_case_timeline(
    coach_actions: list[dict[str, Any]],
    training_logs: list[dict[str, Any]],
    checkins: list[dict[str, Any]],
    events: list[dict[str, Any]],
    notes_tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []

    for row in coach_actions:
        when = _as_dt(row.get("created_at"))
        payload = row.get("payload") or {}
        timeline.append(
            {
                "when": when,
                "source": "coach_action",
                "title": str(row.get("action") or "coach_action"),
                "detail": str(payload) if payload else "",
            }
        )

    for row in training_logs:
        when = _as_dt(row.get("date"))
        timeline.append(
            {
                "when": when,
                "source": "training_log",
                "title": f"Logged {row.get('session_category') or 'session'}",
                "detail": f"RPE {row.get('rpe')} | pain={bool(row.get('pain_flag'))}",
            }
        )

    for row in checkins:
        when = _as_dt(row.get("day"))
        timeline.append(
            {
                "when": when,
                "source": "checkin",
                "title": "Daily check-in",
                "detail": (
                    f"sleep={row.get('sleep')} energy={row.get('energy')} "
                    f"recovery={row.get('recovery')} stress={row.get('stress')}"
                ),
            }
        )

    for row in events:
        when = _as_dt(row.get("event_date"))
        timeline.append(
            {
                "when": when,
                "source": "event",
                "title": f"Event: {row.get('name') or 'event'}",
                "detail": f"distance={row.get('distance')}",
            }
        )

    for row in notes_tasks:
        when = _as_dt(row.get("due_date"))
        timeline.append(
            {
                "when": when,
                "source": "note_task",
                "title": "Coach task completed" if row.get("completed") else "Coach task open",
                "detail": str(row.get("note") or ""),
            }
        )

    timeline.sort(key=lambda r: r["when"], reverse=True)
    return timeline
