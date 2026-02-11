from __future__ import annotations

import datetime as dt


def days_to_next_event(event_dates: list[dt.date], today: dt.date | None = None) -> int | None:
    today = today or dt.date.today()
    upcoming = [d for d in event_dates if d >= today]
    if not upcoming:
        return None
    return min((d - today).days for d in upcoming)
