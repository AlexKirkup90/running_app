"""Strava API v3 adapter.

Implements the WearableAdapter interface for syncing activities from Strava.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from core.services.wearables.base import NormalizedActivity, WearableAdapter

logger = logging.getLogger(__name__)

# Strava API endpoints
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

PAGE_SIZE = 50


def _parse_strava_activity(raw: dict[str, Any]) -> NormalizedActivity:
    """Convert a raw Strava activity JSON to NormalizedActivity."""
    start_str = raw.get("start_date", "")
    try:
        start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        start_time = datetime.now(tz=timezone.utc)

    duration_sec = int(raw.get("elapsed_time", 0))
    distance_m = float(raw.get("distance", 0))

    avg_pace = None
    if distance_m > 0 and duration_sec > 0:
        avg_pace = (duration_sec / distance_m) * 1000  # sec per km

    return NormalizedActivity(
        remote_id=str(raw.get("id", "")),
        service="strava",
        activity_type=raw.get("type", raw.get("sport_type", "Run")),
        start_time=start_time,
        duration_sec=duration_sec,
        distance_m=distance_m,
        avg_hr=int(raw["average_heartrate"]) if raw.get("average_heartrate") else None,
        max_hr=int(raw["max_heartrate"]) if raw.get("max_heartrate") else None,
        avg_pace_sec_per_km=round(avg_pace, 1) if avg_pace else None,
        calories=raw.get("calories"),
        elevation_gain_m=raw.get("total_elevation_gain"),
        avg_cadence=int(raw["average_cadence"] * 2) if raw.get("average_cadence") else None,
        name=raw.get("name", ""),
        raw_payload=raw,
    )


class StravaAdapter(WearableAdapter):
    """Strava REST API v3 adapter."""

    SERVICE_NAME = "strava"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def build_auth_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "activity:read_all",
            "state": state,
            "approval_prompt": "auto",
        }
        return f"{STRAVA_AUTH_URL}?{urlencode(params)}"

    def exchange_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        resp = httpx.post(
            STRAVA_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        expires_at = data.get("expires_at")
        athlete_data = data.get("athlete", {})
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc) if expires_at else None,
            "athlete_id": str(athlete_data.get("id", "")),
            "scope": data.get("scope", "activity:read_all"),
        }

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        resp = httpx.post(
            STRAVA_TOKEN_URL,
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
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", refresh_token),
            "expires_at": datetime.fromtimestamp(data["expires_at"], tz=timezone.utc) if data.get("expires_at") else None,
        }

    def fetch_activities(
        self, access_token: str, after: datetime | None = None, page: int = 1
    ) -> list[NormalizedActivity]:
        params: dict[str, Any] = {"per_page": PAGE_SIZE, "page": page}
        if after:
            params["after"] = int(after.timestamp())

        resp = httpx.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        activities_raw = resp.json()

        results = []
        for raw in activities_raw:
            # Only import running activities
            sport = raw.get("type", raw.get("sport_type", ""))
            if sport not in ("Run", "TrailRun", "VirtualRun", "Race"):
                continue
            try:
                results.append(_parse_strava_activity(raw))
            except Exception:
                logger.warning("Failed to parse Strava activity: %s", raw.get("id", "unknown"))
        return results

    def test_connection(self, access_token: str) -> bool:
        try:
            resp = httpx.get(
                f"{STRAVA_API_BASE}/athlete",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15,
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False


def verify_strava_webhook(hub_mode: str, hub_challenge: str, verify_token: str, expected_token: str) -> str | None:
    """Verify a Strava webhook subscription callback.

    Returns hub_challenge if valid, None otherwise.
    """
    if hub_mode == "subscribe" and verify_token == expected_token:
        return hub_challenge
    return None
