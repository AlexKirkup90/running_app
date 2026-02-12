from __future__ import annotations

from datetime import date


def days_to_event(event_date: date, today: date | None = None) -> int:
    """Calculate the number of days from today (or a given date) until the event date."""
    t = today or date.today()
    return (event_date - t).days
