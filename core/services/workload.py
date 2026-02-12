from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any


@dataclass
class QueueSnapshot:
    open_count: int
    high_priority: int
    actionable_now: int
    snoozed: int
    sla_due_24h: int
    sla_due_72h: int
    median_age_hours: float
    oldest_age_hours: float


def intervention_age_hours(created_at: datetime, now: datetime) -> float:
    """Calculate the age of an intervention in hours from its creation time to now."""
    return round(max(0.0, (now - created_at).total_seconds() / 3600.0), 1)


def queue_snapshot(rows: list[dict[str, Any]], now: datetime) -> QueueSnapshot:
    """Build a QueueSnapshot summary from a list of open intervention dicts.

    Computes counts (open, high-priority, actionable, snoozed), SLA buckets, and age statistics.
    """
    ages = [intervention_age_hours(r["created_at"], now) for r in rows if isinstance(r.get("created_at"), datetime)]

    actionable = [r for r in rows if not bool(r.get("is_snoozed"))]
    due_24h = [r for r in actionable if isinstance(r.get("created_at"), datetime) and intervention_age_hours(r["created_at"], now) >= 24.0]
    due_72h = [r for r in actionable if isinstance(r.get("created_at"), datetime) and intervention_age_hours(r["created_at"], now) >= 72.0]

    return QueueSnapshot(
        open_count=len(rows),
        high_priority=len([r for r in rows if float(r.get("risk") or 0.0) >= 0.75]),
        actionable_now=len(actionable),
        snoozed=len([r for r in rows if bool(r.get("is_snoozed"))]),
        sla_due_24h=len(due_24h),
        sla_due_72h=len(due_72h),
        median_age_hours=round(float(median(ages)) if ages else 0.0, 1),
        oldest_age_hours=max(ages) if ages else 0.0,
    )

