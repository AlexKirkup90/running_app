"""Garmin Connect adapter.

Implements the WearableAdapter interface for syncing activities from
Garmin Connect via their OAuth 2.0 / REST API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from core.services.wearables.base import NormalizedActivity, WearableAdapter

logger = logging.getLogger(__name__)

# Garmin Connect API endpoints
GARMIN_AUTH_URL = "https://connect.garmin.com/oauthConfirm"
GARMIN_TOKEN_URL = "https://connectapi.garmin.com/oauth-service/oauth/token"
GARMIN_API_BASE = "https://apis.garmin.com"
GARMIN_ACTIVITIES_URL = f"{GARMIN_API_BASE}/wellness-api/rest/activities"

# Page size for activity listing
PAGE_SIZE = 50


def _parse_garmin_activity(raw: dict[str, Any]) -> NormalizedActivity:
    """Convert a raw Garmin activity JSON to NormalizedActivity."""
    start_str = raw.get("startTimeLocal") or raw.get("startTimeGMT", "")
    try:
        start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        start_time = datetime.now(tz=timezone.utc)

    duration_sec = int(raw.get("duration", 0))
    distance_m = float(raw.get("distance", 0))
    avg_hr = raw.get("averageHR") or raw.get("averageHeartRateInBeatsPerMinute")
    max_hr = raw.get("maxHR") or raw.get("maxHeartRateInBeatsPerMinute")

    avg_pace = None
    if distance_m > 0 and duration_sec > 0:
        avg_pace = (duration_sec / distance_m) * 1000  # sec per km

    activity_type = (raw.get("activityType", {}).get("typeKey", "") if isinstance(raw.get("activityType"), dict) else str(raw.get("activityType", "")))

    return NormalizedActivity(
        remote_id=str(raw.get("activityId", raw.get("summaryId", ""))),
        service="garmin",
        activity_type=activity_type,
        start_time=start_time,
        duration_sec=duration_sec,
        distance_m=distance_m,
        avg_hr=int(avg_hr) if avg_hr else None,
        max_hr=int(max_hr) if max_hr else None,
        avg_pace_sec_per_km=round(avg_pace, 1) if avg_pace else None,
        calories=raw.get("calories"),
        elevation_gain_m=raw.get("elevationGain"),
        avg_cadence=raw.get("averageRunningCadenceInStepsPerMinute"),
        name=raw.get("activityName", ""),
        raw_payload=raw,
    )


class GarminAdapter(WearableAdapter):
    """Garmin Connect wearable adapter."""

    SERVICE_NAME = "garmin"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def build_auth_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "activity_read",
            "state": state,
        }
        return f"{GARMIN_AUTH_URL}?{urlencode(params)}"

    def exchange_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        resp = httpx.post(
            GARMIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        expires_at = None
        if data.get("expires_in"):
            expires_at = datetime.now(tz=timezone.utc).timestamp() + int(data["expires_in"])
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc) if expires_at else None,
            "athlete_id": data.get("userId", ""),
            "scope": data.get("scope", "activity_read"),
        }

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        resp = httpx.post(
            GARMIN_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        expires_at = None
        if data.get("expires_in"):
            expires_at = datetime.now(tz=timezone.utc).timestamp() + int(data["expires_in"])
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", refresh_token),
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc) if expires_at else None,
        }

    def fetch_activities(
        self, access_token: str, after: datetime | None = None, page: int = 1
    ) -> list[NormalizedActivity]:
        params: dict[str, Any] = {"limit": PAGE_SIZE, "start": (page - 1) * PAGE_SIZE}
        if after:
            params["uploadStartTimeInSeconds"] = int(after.timestamp())

        resp = httpx.get(
            GARMIN_ACTIVITIES_URL,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        activities_raw = resp.json()
        if not isinstance(activities_raw, list):
            activities_raw = activities_raw.get("activities", [])

        results = []
        for raw in activities_raw:
            try:
                results.append(_parse_garmin_activity(raw))
            except Exception:
                logger.warning("Failed to parse Garmin activity: %s", raw.get("activityId", "unknown"))
        return results

    def test_connection(self, access_token: str) -> bool:
        try:
            resp = httpx.get(
                f"{GARMIN_API_BASE}/wellness-api/rest/user/id",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15,
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
