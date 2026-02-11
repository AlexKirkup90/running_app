from __future__ import annotations

REQUIRED_COLUMNS = ["date", "duration", "distance", "avg_hr", "max_hr", "avg_pace", "session_type"]


def _as_rows(data):
    if hasattr(data, "to_dict"):
        return data.to_dict("records")
    if isinstance(data, list):
        return data
    return []


def validate_csv(data) -> tuple[bool, list[str]]:
    rows = _as_rows(data)
    errors = []
    cols = set(rows[0].keys()) if rows else set()
    for c in REQUIRED_COLUMNS:
        if c not in cols:
            errors.append(f"missing: {c}")
    for row in rows:
        if row.get("duration", 0) < 0:
            errors.append("duration must be non-negative")
            break
    return (len(errors) == 0, errors)
