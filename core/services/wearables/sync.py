"""Wearable sync orchestrator.

Coordinates fetching activities from connected wearable services, deduplicating
against existing TrainingLog entries, and importing new activities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.services.wearables.base import (
    NormalizedActivity,
    WearableAdapter,
    classify_session,
    estimate_rpe_from_hr,
)

logger = logging.getLogger(__name__)

# Maximum number of pages to fetch in a single sync run
MAX_PAGES = 10
# Default lookback window for first sync
DEFAULT_LOOKBACK_DAYS = 90


@dataclass
class SyncResult:
    """Summary of a sync operation."""

    service: str
    activities_found: int = 0
    activities_imported: int = 0
    activities_skipped: int = 0
    errors: list[str] | None = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class ImportCandidate:
    """An activity ready to become a TrainingLog entry."""

    activity: NormalizedActivity
    session_category: str
    estimated_rpe: int
    load_score: float
    date: date
    duration_min: int
    distance_km: float


def _build_candidate(
    activity: NormalizedActivity,
    athlete_max_hr: int | None = None,
    athlete_resting_hr: int | None = None,
) -> ImportCandidate:
    """Convert a NormalizedActivity into an ImportCandidate."""
    category = classify_session(activity)
    rpe = estimate_rpe_from_hr(activity.avg_hr, athlete_max_hr, athlete_resting_hr)
    dur_min = round(activity.duration_sec / 60)
    load = dur_min * (rpe / 10)

    return ImportCandidate(
        activity=activity,
        session_category=category,
        estimated_rpe=rpe,
        load_score=round(load, 1),
        date=activity.start_time.date(),
        duration_min=dur_min,
        distance_km=round(activity.distance_m / 1000, 2),
    )


def fetch_all_activities(
    adapter: WearableAdapter,
    access_token: str,
    after: datetime | None = None,
) -> list[NormalizedActivity]:
    """Fetch all available activities from the service, paginating as needed."""
    all_activities: list[NormalizedActivity] = []

    for page in range(1, MAX_PAGES + 1):
        batch = adapter.fetch_activities(access_token, after=after, page=page)
        if not batch:
            break
        all_activities.extend(batch)
        if len(batch) < 50:
            break

    return all_activities


def deduplicate(
    activities: list[NormalizedActivity],
    existing_source_ids: set[str],
    existing_dates: set[date],
) -> tuple[list[NormalizedActivity], int]:
    """Remove activities that have already been imported.

    Checks both source_id (exact match) and date (fuzzy duplicate).
    Returns (unique_activities, skipped_count).
    """
    unique = []
    skipped = 0

    for act in activities:
        # Exact match: same source_id already imported
        if act.remote_id and act.remote_id in existing_source_ids:
            skipped += 1
            continue
        # Date match: already have a log for that date (avoid double-logging)
        if act.start_time.date() in existing_dates:
            skipped += 1
            continue
        unique.append(act)

    return unique, skipped


def prepare_import_batch(
    activities: list[NormalizedActivity],
    existing_source_ids: set[str],
    existing_dates: set[date],
    athlete_max_hr: int | None = None,
    athlete_resting_hr: int | None = None,
) -> tuple[list[ImportCandidate], int]:
    """Full pipeline: deduplicate → classify → estimate RPE → build candidates.

    Returns (candidates, skipped_count).
    """
    unique, skipped = deduplicate(activities, existing_source_ids, existing_dates)

    candidates = []
    for act in unique:
        try:
            candidate = _build_candidate(act, athlete_max_hr, athlete_resting_hr)
            candidates.append(candidate)
        except Exception as e:
            logger.warning("Failed to build candidate for %s: %s", act.remote_id, e)
            skipped += 1

    return candidates, skipped


def build_training_log_dict(candidate: ImportCandidate, athlete_id: int) -> dict[str, Any]:
    """Convert an ImportCandidate to a dict suitable for creating a TrainingLog."""
    return {
        "athlete_id": athlete_id,
        "date": candidate.date,
        "session_category": candidate.session_category,
        "duration_min": candidate.duration_min,
        "distance_km": candidate.distance_km,
        "avg_hr": candidate.activity.avg_hr,
        "max_hr": candidate.activity.max_hr,
        "avg_pace_sec_per_km": candidate.activity.avg_pace_sec_per_km,
        "rpe": candidate.estimated_rpe,
        "load_score": candidate.load_score,
        "notes": candidate.activity.name,
        "pain_flag": False,
        "source": candidate.activity.service,
        "source_id": candidate.activity.remote_id,
    }


def default_lookback(last_sync: datetime | None) -> datetime:
    """Determine the 'after' timestamp for fetching activities."""
    if last_sync:
        return last_sync
    return datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_LOOKBACK_DAYS)
