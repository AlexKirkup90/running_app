"""Abstract base adapter for wearable device integrations.

Every wearable service (Garmin, Strava, etc.) implements this interface so
the sync pipeline can treat them uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NormalizedActivity:
    """Adapter-agnostic representation of a single training activity."""

    remote_id: str
    service: str  # "garmin" | "strava"
    activity_type: str  # raw type from the service
    start_time: datetime
    duration_sec: int
    distance_m: float
    avg_hr: int | None = None
    max_hr: int | None = None
    avg_pace_sec_per_km: float | None = None
    calories: int | None = None
    elevation_gain_m: float | None = None
    avg_cadence: int | None = None
    name: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)


# Maps wearable activity types → our session categories.
ACTIVITY_TYPE_MAP: dict[str, str] = {
    # Garmin types
    "running": "Easy Run",
    "trail_running": "Easy Run",
    "track_running": "VO2max Intervals",
    "treadmill_running": "Easy Run",
    "race": "Race",
    # Strava types
    "Run": "Easy Run",
    "TrailRun": "Easy Run",
    "VirtualRun": "Easy Run",
    "Race": "Race",
}


def classify_session(activity: NormalizedActivity) -> str:
    """Map a wearable activity type to our session catalog category.

    Uses pace heuristics when the generic type is "Easy Run":
    - Very fast pace (<4:00/km) → VO2max Intervals
    - Fast pace (<4:30/km) → Tempo Run
    - Moderate pace (<5:15/km) → Easy Run
    - Slow pace → Long Run (if duration > 60 min) or Recovery Run
    """
    base = ACTIVITY_TYPE_MAP.get(activity.activity_type, "Easy Run")
    if base == "Race":
        return "Race"

    pace = activity.avg_pace_sec_per_km
    dur_min = activity.duration_sec / 60

    if pace and pace > 0:
        if pace < 240:
            return "VO2max Intervals"
        if pace < 270:
            return "Tempo Run"
        if dur_min > 60 and pace < 360:
            return "Long Run"
        if dur_min > 75:
            return "Long Run"
        if pace > 390:
            return "Recovery Run"

    return base


def estimate_rpe_from_hr(avg_hr: int | None, max_hr: int | None, resting_hr: int | None) -> int:
    """Estimate RPE 1-10 from heart rate using Karvonen %HRR.

    Falls back to RPE 5 when HR data is missing.
    """
    if not avg_hr or not max_hr or max_hr <= 0:
        return 5
    rhr = resting_hr or 50
    if max_hr <= rhr:
        return 5
    hrr_pct = (avg_hr - rhr) / (max_hr - rhr)
    hrr_pct = max(0.0, min(1.0, hrr_pct))
    # Map 0-100% HRR → RPE 1-10
    rpe = round(1 + hrr_pct * 9)
    return max(1, min(10, rpe))


class WearableAdapter(ABC):
    """Interface that each wearable service must implement."""

    SERVICE_NAME: str = ""

    @abstractmethod
    def build_auth_url(self, redirect_uri: str, state: str) -> str:
        """Return the OAuth authorization URL for the user to visit."""

    @abstractmethod
    def exchange_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange an OAuth authorization code for access + refresh tokens.

        Returns dict with keys: access_token, refresh_token, expires_at,
        athlete_id (external), scope.
        """

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expired access token.

        Returns dict with keys: access_token, refresh_token, expires_at.
        """

    @abstractmethod
    def fetch_activities(
        self, access_token: str, after: datetime | None = None, page: int = 1
    ) -> list[NormalizedActivity]:
        """Fetch a page of activities from the service.

        Args:
            access_token: Valid OAuth access token.
            after: Only return activities after this timestamp.
            page: Page number for pagination.

        Returns list of NormalizedActivity.
        """

    @abstractmethod
    def test_connection(self, access_token: str) -> bool:
        """Verify the access token is still valid."""
