from __future__ import annotations

from datetime import date


def days_to_event(event_date: date, today: date | None = None) -> int:
    t = today or date.today()
    return (event_date - t).days
