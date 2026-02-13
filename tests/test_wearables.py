"""Tests for Phase 3 — Wearable Integration layer.

Covers: base adapter abstractions, activity classification, RPE estimation,
Garmin/Strava activity parsing, sync pipeline (deduplication, candidate building,
training log dict generation).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from core.services.wearables.base import (
    ACTIVITY_TYPE_MAP,
    NormalizedActivity,
    classify_session,
    estimate_rpe_from_hr,
)
from core.services.wearables.garmin import _parse_garmin_activity
from core.services.wearables.strava import _parse_strava_activity, verify_strava_webhook
from core.services.wearables.sync import (
    SyncResult,
    build_training_log_dict,
    deduplicate,
    default_lookback,
    prepare_import_batch,
    _build_candidate,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

def _make_activity(**overrides) -> NormalizedActivity:
    defaults = {
        "remote_id": "act_001",
        "service": "garmin",
        "activity_type": "running",
        "start_time": datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
        "duration_sec": 3600,
        "distance_m": 10000,
        "avg_hr": 145,
        "max_hr": 165,
        "avg_pace_sec_per_km": 360.0,
        "name": "Morning run",
    }
    defaults.update(overrides)
    return NormalizedActivity(**defaults)


# ── Base adapter tests ────────────────────────────────────────────────────

class TestActivityTypeMap:
    def test_running_types_present(self):
        assert "running" in ACTIVITY_TYPE_MAP
        assert "Run" in ACTIVITY_TYPE_MAP

    def test_garmin_types(self):
        assert ACTIVITY_TYPE_MAP["trail_running"] == "Easy Run"
        assert ACTIVITY_TYPE_MAP["track_running"] == "VO2max Intervals"
        assert ACTIVITY_TYPE_MAP["race"] == "Race"

    def test_strava_types(self):
        assert ACTIVITY_TYPE_MAP["Run"] == "Easy Run"
        assert ACTIVITY_TYPE_MAP["VirtualRun"] == "Easy Run"
        assert ACTIVITY_TYPE_MAP["Race"] == "Race"


class TestClassifySession:
    def test_race_type(self):
        act = _make_activity(activity_type="race")
        assert classify_session(act) == "Race"

    def test_very_fast_pace_is_vo2max(self):
        act = _make_activity(avg_pace_sec_per_km=220.0)  # ~3:40/km
        assert classify_session(act) == "VO2max Intervals"

    def test_fast_pace_is_tempo(self):
        act = _make_activity(avg_pace_sec_per_km=260.0)  # ~4:20/km
        assert classify_session(act) == "Tempo Run"

    def test_long_duration_is_long_run(self):
        act = _make_activity(avg_pace_sec_per_km=330.0, duration_sec=80 * 60)
        assert classify_session(act) == "Long Run"

    def test_slow_pace_is_recovery(self):
        act = _make_activity(avg_pace_sec_per_km=400.0, duration_sec=30 * 60)
        assert classify_session(act) == "Recovery Run"

    def test_moderate_pace_is_easy(self):
        act = _make_activity(avg_pace_sec_per_km=300.0, duration_sec=45 * 60)
        assert classify_session(act) == "Easy Run"

    def test_no_pace_fallback(self):
        act = _make_activity(avg_pace_sec_per_km=None)
        assert classify_session(act) == "Easy Run"

    def test_unknown_type_fallback(self):
        act = _make_activity(activity_type="cycling", avg_pace_sec_per_km=None)
        assert classify_session(act) == "Easy Run"


class TestEstimateRpe:
    def test_missing_hr_returns_5(self):
        assert estimate_rpe_from_hr(None, None, None) == 5

    def test_zero_max_hr_returns_5(self):
        assert estimate_rpe_from_hr(120, 0, 50) == 5

    def test_low_hr_gives_low_rpe(self):
        rpe = estimate_rpe_from_hr(80, 180, 50)
        assert 1 <= rpe <= 4

    def test_high_hr_gives_high_rpe(self):
        rpe = estimate_rpe_from_hr(170, 180, 50)
        assert rpe >= 8

    def test_moderate_hr(self):
        rpe = estimate_rpe_from_hr(130, 180, 50)
        assert 4 <= rpe <= 7

    def test_rpe_clamped_1_10(self):
        rpe = estimate_rpe_from_hr(200, 180, 50)  # Over max
        assert rpe == 10


# ── Garmin parser tests ───────────────────────────────────────────────────

class TestGarminParser:
    def test_parse_basic_activity(self):
        raw = {
            "activityId": 12345,
            "activityName": "5K Run",
            "activityType": {"typeKey": "running"},
            "startTimeLocal": "2026-01-15T08:00:00",
            "duration": 1800,
            "distance": 5000,
            "averageHR": 150,
            "maxHR": 170,
            "calories": 350,
            "elevationGain": 42,
        }
        act = _parse_garmin_activity(raw)
        assert act.remote_id == "12345"
        assert act.service == "garmin"
        assert act.duration_sec == 1800
        assert act.distance_m == 5000
        assert act.avg_hr == 150
        assert act.max_hr == 170
        assert act.avg_pace_sec_per_km == pytest.approx(360.0, abs=1)
        assert act.name == "5K Run"

    def test_parse_missing_hr(self):
        raw = {
            "activityId": 99,
            "activityType": "running",
            "startTimeLocal": "2026-02-01T07:00:00",
            "duration": 600,
            "distance": 2000,
        }
        act = _parse_garmin_activity(raw)
        assert act.avg_hr is None
        assert act.max_hr is None

    def test_parse_zero_distance(self):
        raw = {
            "activityId": 100,
            "activityType": "running",
            "startTimeLocal": "2026-02-01T07:00:00",
            "duration": 600,
            "distance": 0,
        }
        act = _parse_garmin_activity(raw)
        assert act.avg_pace_sec_per_km is None


# ── Strava parser tests ──────────────────────────────────────────────────

class TestStravaParser:
    def test_parse_basic_activity(self):
        raw = {
            "id": 67890,
            "name": "Evening Jog",
            "type": "Run",
            "start_date": "2026-01-20T18:00:00Z",
            "elapsed_time": 2400,
            "distance": 7500,
            "average_heartrate": 142,
            "max_heartrate": 160,
            "total_elevation_gain": 25,
            "average_cadence": 85,
        }
        act = _parse_strava_activity(raw)
        assert act.remote_id == "67890"
        assert act.service == "strava"
        assert act.duration_sec == 2400
        assert act.distance_m == 7500
        assert act.avg_hr == 142
        assert act.avg_cadence == 170  # Strava reports half-cadence
        assert act.name == "Evening Jog"

    def test_parse_no_hr(self):
        raw = {
            "id": 111,
            "type": "Run",
            "start_date": "2026-01-25T10:00:00Z",
            "elapsed_time": 1200,
            "distance": 3000,
        }
        act = _parse_strava_activity(raw)
        assert act.avg_hr is None
        assert act.max_hr is None


class TestStravaWebhook:
    def test_valid_verification(self):
        result = verify_strava_webhook("subscribe", "challenge123", "mytoken", "mytoken")
        assert result == "challenge123"

    def test_invalid_token(self):
        result = verify_strava_webhook("subscribe", "challenge123", "wrong", "mytoken")
        assert result is None

    def test_wrong_mode(self):
        result = verify_strava_webhook("unsubscribe", "challenge123", "mytoken", "mytoken")
        assert result is None


# ── Sync pipeline tests ──────────────────────────────────────────────────

class TestDeduplicate:
    def test_removes_existing_source_ids(self):
        activities = [_make_activity(remote_id="a1"), _make_activity(remote_id="a2")]
        unique, skipped = deduplicate(activities, {"a1"}, set())
        assert len(unique) == 1
        assert unique[0].remote_id == "a2"
        assert skipped == 1

    def test_removes_existing_dates(self):
        activities = [
            _make_activity(remote_id="b1", start_time=datetime(2026, 1, 15, tzinfo=timezone.utc)),
            _make_activity(remote_id="b2", start_time=datetime(2026, 1, 16, tzinfo=timezone.utc)),
        ]
        unique, skipped = deduplicate(activities, set(), {date(2026, 1, 15)})
        assert len(unique) == 1
        assert unique[0].remote_id == "b2"

    def test_all_unique(self):
        activities = [_make_activity(remote_id="c1"), _make_activity(remote_id="c2")]
        unique, skipped = deduplicate(activities, set(), set())
        assert len(unique) == 2
        assert skipped == 0

    def test_empty_list(self):
        unique, skipped = deduplicate([], set(), set())
        assert unique == []
        assert skipped == 0


class TestBuildCandidate:
    def test_basic_candidate(self):
        act = _make_activity(duration_sec=3600, distance_m=10000, avg_hr=145)
        cand = _build_candidate(act, athlete_max_hr=180, athlete_resting_hr=50)
        assert cand.duration_min == 60
        assert cand.distance_km == 10.0
        assert cand.date == date(2026, 1, 15)
        assert 1 <= cand.estimated_rpe <= 10
        assert cand.load_score > 0

    def test_session_category_assigned(self):
        act = _make_activity(avg_pace_sec_per_km=220.0)
        cand = _build_candidate(act)
        assert cand.session_category == "VO2max Intervals"


class TestPrepareImportBatch:
    def test_full_pipeline(self):
        activities = [
            _make_activity(remote_id="x1", start_time=datetime(2026, 1, 15, tzinfo=timezone.utc)),
            _make_activity(remote_id="x2", start_time=datetime(2026, 1, 16, tzinfo=timezone.utc)),
            _make_activity(remote_id="x3", start_time=datetime(2026, 1, 17, tzinfo=timezone.utc)),
        ]
        candidates, skipped = prepare_import_batch(
            activities, existing_source_ids={"x1"}, existing_dates=set(),
            athlete_max_hr=180, athlete_resting_hr=50,
        )
        assert len(candidates) == 2
        assert skipped == 1

    def test_empty_input(self):
        candidates, skipped = prepare_import_batch([], set(), set())
        assert candidates == []
        assert skipped == 0


class TestBuildTrainingLogDict:
    def test_produces_valid_dict(self):
        act = _make_activity()
        cand = _build_candidate(act, athlete_max_hr=180, athlete_resting_hr=50)
        d = build_training_log_dict(cand, athlete_id=42)
        assert d["athlete_id"] == 42
        assert d["source"] == "garmin"
        assert d["source_id"] == "act_001"
        assert d["date"] == date(2026, 1, 15)
        assert d["duration_min"] == 60
        assert d["distance_km"] == 10.0
        assert 1 <= d["rpe"] <= 10
        assert d["load_score"] > 0
        assert d["pain_flag"] is False


class TestSyncResult:
    def test_defaults(self):
        sr = SyncResult(service="garmin")
        assert sr.activities_found == 0
        assert sr.errors == []


class TestDefaultLookback:
    def test_with_last_sync(self):
        ts = datetime(2026, 1, 10, tzinfo=timezone.utc)
        assert default_lookback(ts) == ts

    def test_without_last_sync(self):
        result = default_lookback(None)
        assert result.date() < date.today()
