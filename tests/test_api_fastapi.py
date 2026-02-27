from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import sys

from fastapi.testclient import TestClient


def _reset_runtime_caches():
    import core.db as db_mod
    from core.config import get_settings
    from api.webhooks import dispatcher

    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._SessionLocal = None
    dispatcher.clear_history()


def _purge_api_modules() -> None:
    for name in [
        "api.main",
        "api.routes",
        "api.integrations",
        "api.ratelimit",
    ]:
        sys.modules.pop(name, None)


def _seed_athlete():
    from core.db import session_scope
    from core.models import Athlete, CheckIn, CoachIntervention, Event, Plan, PlanDaySession, PlanWeek, SessionLibrary, TrainingLog, User
    from core.security import hash_password

    with session_scope() as s:
        s.add(
            Athlete(
                id=1,
                first_name="Demo",
                last_name="Runner",
                email="demo.runner@example.com",
                status="active",
                max_hr=190,
                resting_hr=55,
                threshold_pace_sec_per_km=285,
                easy_pace_sec_per_km=345,
            )
        )
        s.add(
            User(
                id=1,
                username="athlete1",
                password_hash=hash_password("AthletePass!234"),
                role="client",
                athlete_id=1,
                must_change_password=False,
            )
        )
        s.add(
            User(
                id=2,
                username="coach1",
                password_hash=hash_password("CoachPass!234"),
                role="coach",
                must_change_password=True,
            )
        )
        s.add(
            User(
                id=3,
                username="locked1",
                password_hash=hash_password("LockedPass!234"),
                role="coach",
                must_change_password=False,
                failed_attempts=5,
                locked_until=datetime.utcnow() + timedelta(minutes=15),
            )
        )
        s.add(
            User(
                id=4,
                username="coach_ok",
                password_hash=hash_password("CoachOkay!234"),
                role="coach",
                must_change_password=False,
            )
        )
        s.add(
            User(
                id=5,
                username="master",
                password_hash=hash_password("MasterPass!234"),
                role="admin",
                must_change_password=False,
            )
        )

        today = date.today()
        s.add(
            CheckIn(
                athlete_id=1,
                day=today,
                sleep=4,
                energy=4,
                recovery=3,
                stress=2,
                training_today=True,
            )
        )
        s.add(
            Event(
                athlete_id=1,
                name="Spring 10K",
                distance="10K",
                event_date=today + timedelta(days=21),
            )
        )
        s.add(
            Plan(
                id=1,
                athlete_id=1,
                race_goal="10K",
                weeks=8,
                sessions_per_week=4,
                max_session_min=120,
                start_date=today - timedelta(days=today.weekday()),
                locked_until_week=0,
                status="active",
            )
        )
        s.add(
            PlanWeek(
                id=1,
                plan_id=1,
                week_number=1,
                phase="Base",
                week_start=today - timedelta(days=today.weekday()),
                week_end=(today - timedelta(days=today.weekday())) + timedelta(days=6),
                sessions_order=["Tempo Builder", "Easy Run", "Long Run", "Recovery Run"],
                target_load=220.0,
                locked=False,
            )
        )
        s.add(
            SessionLibrary(
                id=1,
                name="Tempo Builder",
                category="run",
                intent="threshold",
                energy_system="lactate_threshold",
                tier="medium",
                duration_min=50,
                structure_json={
                    "version": 2,
                    "blocks": [
                        {
                            "phase": "warmup",
                            "duration_min": 12,
                            "instructions": "Easy jog + drills.",
                            "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]},
                        },
                        {
                            "phase": "main_set",
                            "duration_min": 30,
                            "instructions": "Tempo work.",
                            "target": {"pace_zone": "Z3-Z4", "hr_zone": "Z3-Z4", "rpe_range": [6, 7]},
                        },
                        {
                            "phase": "cooldown",
                            "duration_min": 8,
                            "instructions": "Easy cool down.",
                            "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]},
                        },
                    ],
                },
                targets_json={},
                progression_json={"a": "b"},
                regression_json={"a": "b"},
                prescription="Tempo day",
                coaching_notes="Hold form",
            )
        )
        s.add(
            PlanDaySession(
                id=1,
                plan_week_id=1,
                athlete_id=1,
                session_day=today,
                session_name="Tempo Builder",
                source_template_name="Tempo Builder",
                status="planned",
            )
        )
        s.add(
            PlanDaySession(
                id=2,
                plan_week_id=1,
                athlete_id=1,
                session_day=today - timedelta(days=1),
                session_name="Easy Run",
                source_template_name="Tempo Builder",
                status="completed",
            )
        )
        s.add(
            CoachIntervention(
                athlete_id=1,
                action_type="monitor",
                status="open",
                risk_score=0.4,
                confidence_score=0.8,
                expected_impact={},
                why_factors=["stable"],
                guardrail_pass=True,
                guardrail_reason="ok",
            )
        )
        # Seed 28 days of training load to exercise today/workload analytics.
        for idx in range(28):
            d = today - timedelta(days=idx)
            s.add(
                TrainingLog(
                    athlete_id=1,
                    date=d,
                    session_category="run",
                    duration_min=40 + (idx % 3) * 10,
                    distance_km=7.0 + (idx % 4),
                    avg_hr=145,
                    max_hr=168,
                    avg_pace_sec_per_km=320.0,
                    rpe=5 + (idx % 3),
                    load_score=35 + (idx % 5) * 3,
                    notes="seed",
                    pain_flag=(idx == 3),
                )
            )


def _create_schema():
    import core.models  # noqa: F401
    from core.db import Base, get_engine

    Base.metadata.create_all(bind=get_engine())


def _build_client(tmp_path: Path, monkeypatch, env_overrides: dict[str, str] | None = None) -> TestClient:
    db_path = tmp_path / "api_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6399/15")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    if env_overrides:
        for key, value in env_overrides.items():
            monkeypatch.setenv(key, value)

    _reset_runtime_caches()
    _purge_api_modules()
    _create_schema()
    _seed_athlete()

    from api.main import create_app

    return TestClient(create_app())


def _auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_echoes_or_generates_request_id_header(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        custom_request_id = "req-test-123"
        resp = client.get("/api/v1/health", headers={"X-Request-ID": custom_request_id})
        assert resp.status_code == 200, resp.text
        assert resp.headers["X-Request-ID"] == custom_request_id

        generated = client.get("/api/v1/health")
        assert generated.status_code == 200, generated.text
        assert generated.headers.get("X-Request-ID")


def test_auth_token_rate_limit_returns_429_when_enabled(tmp_path, monkeypatch):
    env = {
        "APP_ENV": "dev",
        "RATE_LIMIT_ENABLED": "true",
        "AUTH_TOKEN_RATE_LIMIT": "2/minute",
    }
    with _build_client(tmp_path, monkeypatch, env_overrides=env) as client:
        for _ in range(2):
            resp = client.post("/api/v1/auth/token", json={"username": "nobody", "password": "wrong"})
            assert resp.status_code == 401
        limited = client.post("/api/v1/auth/token", json={"username": "nobody", "password": "wrong"})
        assert limited.status_code == 429, limited.text
        assert limited.json()["detail"]["code"] == "RATE_LIMITED"


def test_training_log_create_and_cached_read_models(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        assert client.app.state.cache_backend == "memory"
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        today = date.today()
        for idx in range(3):
            resp = client.post(
                "/api/v1/training-logs",
                json={
                    "athlete_id": 1,
                    "date": (today - timedelta(days=idx * 3)).isoformat(),
                    "session_category": "run",
                    "duration_min": 45 + idx * 5,
                    "distance_km": 8.0 + idx,
                    "rpe": 6,
                    "load_score": 30 + idx * 4,
                },
                headers=athlete_headers,
            )
            assert resp.status_code == 200, resp.text

        rollups = client.get("/api/v1/analytics/weekly-rollups", params={"athlete_id": 1, "weeks": 8}, headers=athlete_headers)
        assert rollups.status_code == 200
        data = rollups.json()
        assert data["athlete_id"] == 1
        assert len(data["items"]) >= 1

        workload = client.get("/api/v1/athletes/1/workload", params={"weeks": 6}, headers=athlete_headers)
        assert workload.status_code == 200
        workload_body = workload.json()
        assert workload_body["athlete_id"] == 1
        assert "acute_load_7d" in workload_body
        assert isinstance(workload_body["series"], list)

        checkin_resp = client.post(
            "/api/v1/checkins",
            json={"sleep": 5, "energy": 4, "recovery": 4, "stress": 2, "training_today": True},
            headers=athlete_headers,
        )
        assert checkin_resp.status_code == 200, checkin_resp.text
        assert checkin_resp.json()["athlete_id"] == 1


def test_wearable_webhooks_persist_and_dispatch_event(tmp_path, monkeypatch):
    _reset_runtime_caches()
    with _build_client(tmp_path, monkeypatch) as client:
        from api.webhooks import dispatcher
        from core.db import session_scope
        from core.models import TrainingLog

        with session_scope() as s:
            before_count = s.query(TrainingLog).count()

        strava_resp = client.post(
            "/api/v1/integrations/strava/webhook",
            json={
                "object_type": "activity",
                "object_id": 991337,
                "aspect_type": "create",
                "owner_id": 1,
                "activity": {
                    "name": "Morning Run",
                    "type": "Run",
                    "distance": 10500,
                    "moving_time": 3000,
                    "average_heartrate": 148,
                    "max_heartrate": 168,
                    "start_date_local": date.today().isoformat(),
                },
            },
        )
        assert strava_resp.status_code == 200, strava_resp.text
        assert strava_resp.json()["provider"] == "strava"
        assert strava_resp.json()["event"] == "training_log.created"
        assert strava_resp.json()["status"] == "created"
        assert strava_resp.json()["deduplicated"] is False
        strava_log_id = int(strava_resp.json()["training_log"]["id"])

        strava_duplicate = client.post(
            "/api/v1/integrations/strava/webhook",
            json={
                "object_type": "activity",
                "object_id": 991337,
                "aspect_type": "create",
                "owner_id": 1,
                "activity": {
                    "name": "Morning Run",
                    "type": "Run",
                    "distance": 10500,
                    "moving_time": 3000,
                    "average_heartrate": 148,
                    "max_heartrate": 168,
                    "start_date_local": date.today().isoformat(),
                },
            },
        )
        assert strava_duplicate.status_code == 200, strava_duplicate.text
        assert strava_duplicate.json()["status"] == "duplicate"
        assert strava_duplicate.json()["deduplicated"] is True
        assert int(strava_duplicate.json()["training_log"]["id"]) == strava_log_id
        assert int(strava_duplicate.json()["duplicate_of_training_log_id"]) == strava_log_id

        garmin_resp = client.post(
            "/api/v1/integrations/garmin/webhook",
            json={
                "ownerId": 1,
                "activities": [
                    {
                        "activityId": "abc-123",
                        "activityName": "Evening Tempo",
                        "activityType": "running",
                        "distanceInMeters": 8000,
                        "durationInSeconds": 2400,
                        "averageHeartRateInBeatsPerMinute": 152,
                        "maxHeartRateInBeatsPerMinute": 174,
                        "startTimeLocal": date.today().isoformat(),
                    }
                ],
            },
        )
        assert garmin_resp.status_code == 200, garmin_resp.text
        assert garmin_resp.json()["provider"] == "garmin"

        history = dispatcher.history_snapshot()
        training_events = [item for item in history if item["event"] == "training_log.created"]
        assert len(training_events) >= 2

        with session_scope() as s:
            count = s.query(TrainingLog).count()
            assert count == before_count + 2


def test_wearable_webhook_retries_transient_persist_error(tmp_path, monkeypatch):
    _reset_runtime_caches()
    with _build_client(tmp_path, monkeypatch) as client:
        import api.integrations as integrations_mod

        original = integrations_mod.persist_training_log
        state = {"calls": 0}

        def flaky_persist(db, data):
            state["calls"] += 1
            if state["calls"] == 1:
                raise RuntimeError("transient_write_failure")
            return original(db, data)

        monkeypatch.setattr(integrations_mod, "persist_training_log", flaky_persist)

        resp = client.post(
            "/api/v1/integrations/strava/webhook",
            json={
                "object_type": "activity",
                "object_id": 777001,
                "aspect_type": "create",
                "owner_id": 1,
                "activity": {
                    "name": "Retry Test Run",
                    "type": "Run",
                    "distance": 6000,
                    "moving_time": 1800,
                    "average_heartrate": 146,
                    "max_heartrate": 166,
                    "start_date_local": date.today().isoformat(),
                },
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "created"
        assert state["calls"] >= 2


def test_athlete_today_analytics_predictions_and_coach_portfolio(tmp_path, monkeypatch):
    from core.db import session_scope
    from core.models import CheckIn

    with _build_client(tmp_path, monkeypatch) as client:
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")

        # Regression: /today should tolerate multiple historical check-ins and choose the latest.
        with session_scope() as s:
            s.add(
                CheckIn(
                    athlete_id=1,
                    day=date.today() - timedelta(days=1),
                    sleep=3,
                    energy=3,
                    recovery=3,
                    stress=3,
                    training_today=False,
                )
            )

        today_resp = client.get("/api/v1/athletes/1/today", headers=athlete_headers)
        assert today_resp.status_code == 200, today_resp.text
        today_body = today_resp.json()
        assert today_body["athlete_id"] == 1
        assert today_body["readiness_score"] is not None
        assert "training_load_summary" in today_body
        assert "monotony" in today_body["training_load_summary"]
        assert today_body["adapted_session"]["session"]["blocks"]
        assert "target_pace_range" in today_body["adapted_session"]["session"]["blocks"][0]

        analytics_resp = client.get("/api/v1/athletes/1/analytics", headers=athlete_headers)
        assert analytics_resp.status_code == 200, analytics_resp.text
        analytics_body = analytics_resp.json()
        assert analytics_body["athlete_id"] == 1
        assert analytics_body["available"] is True
        assert analytics_body["fitness_fatigue"] is not None
        assert len(analytics_body["fitness_fatigue"]["series"]) >= 1
        assert analytics_body["vdot_history"] is not None
        assert analytics_body["intensity_distribution"] is not None
        assert analytics_body["weekly_rollups"] is not None

        predictions_resp = client.get("/api/v1/athletes/1/predictions", headers=athlete_headers)
        assert predictions_resp.status_code == 200, predictions_resp.text
        predictions_body = predictions_resp.json()
        assert predictions_body["athlete_id"] == 1
        assert predictions_body["available"] is True
        assert "benchmark" in predictions_body
        assert predictions_body["predictions"]["distances"]["10K"]["predicted_time"]

        plan_status_resp = client.get("/api/v1/athletes/1/plan-status", headers=athlete_headers)
        assert plan_status_resp.status_code == 200, plan_status_resp.text
        plan_status_body = plan_status_resp.json()
        assert plan_status_body["athlete_id"] == 1
        assert isinstance(plan_status_body["has_plan"], bool)
        assert isinstance(plan_status_body["upcoming_sessions"], list)

        portfolio_resp = client.get("/api/v1/coach/portfolio-analytics", headers=coach_headers)
        assert portfolio_resp.status_code == 200, portfolio_resp.text
        portfolio_body = portfolio_resp.json()
        assert portfolio_body["athletes_total"] >= 1
        assert portfolio_body["active_interventions"] >= 1
        assert "weekly_compliance_rate" in portfolio_body

        # athlete cannot access coach-only endpoint
        forbidden_portfolio = client.get("/api/v1/coach/portfolio-analytics", headers=athlete_headers)
        assert forbidden_portfolio.status_code == 403
        assert forbidden_portfolio.json()["detail"]["code"] == "FORBIDDEN_ROLE"


def test_protected_endpoints_require_auth_and_scope(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        unauth = client.get("/api/v1/athletes/1/today")
        assert unauth.status_code == 401
        assert unauth.json()["detail"]["code"] == "AUTH_REQUIRED"

        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")
        wrong_scope = client.get("/api/v1/athletes/2/analytics", headers=athlete_headers)
        assert wrong_scope.status_code == 403
        assert wrong_scope.json()["detail"]["code"] == "FORBIDDEN_ATHLETE_SCOPE"

        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        athletes_list = client.get("/api/v1/athletes", headers=coach_headers)
        assert athletes_list.status_code == 200, athletes_list.text
        assert athletes_list.json()["total"] >= 1
        assert isinstance(athletes_list.json()["items"], list)

        athlete_detail = client.get("/api/v1/athletes/1", headers=coach_headers)
        assert athlete_detail.status_code == 200, athlete_detail.text
        assert athlete_detail.json()["id"] == 1
        assert athlete_detail.json()["email"] == "demo.runner@example.com"

        interventions = client.get("/api/v1/coach/interventions", headers=coach_headers)
        assert interventions.status_code == 200, interventions.text
        assert interventions.json()["total"] >= 1
        first_intervention = interventions.json()["items"][0]
        assert isinstance(first_intervention["why_factors"], list)
        assert isinstance(first_intervention["expected_impact"], dict)

        athlete_forbidden = client.get("/api/v1/athletes", headers=athlete_headers)
        assert athlete_forbidden.status_code == 403
        assert athlete_forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"

        athlete_wrong_scope_detail = client.get("/api/v1/athletes/2", headers=athlete_headers)
        assert athlete_wrong_scope_detail.status_code == 403
        assert athlete_wrong_scope_detail.json()["detail"]["code"] == "FORBIDDEN_ATHLETE_SCOPE"


def test_auth_lockout_and_forced_password_change_flow(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        locked = client.post("/api/v1/auth/token", json={"username": "locked1", "password": "LockedPass!234"})
        assert locked.status_code == 403
        assert locked.json()["detail"]["code"] == "ACCOUNT_LOCKED"

        # invalid password increments failed attempts
        bad_login = client.post("/api/v1/auth/token", json={"username": "athlete1", "password": "wrong"})
        assert bad_login.status_code == 401
        assert bad_login.json()["detail"]["code"] == "INVALID_CREDENTIALS"

        # must-change-password blocks token issuance with specific code
        reset_required = client.post("/api/v1/auth/token", json={"username": "coach1", "password": "CoachPass!234"})
        assert reset_required.status_code == 403
        assert reset_required.json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"

        # change-password clears must_change_password and allows login
        change = client.post(
            "/api/v1/auth/change-password",
            json={
                "username": "coach1",
                "current_password": "CoachPass!234",
                "new_password": "CoachPass!235",
            },
        )
        assert change.status_code == 200, change.text
        assert change.json()["status"] == "ok"

        login = client.post("/api/v1/auth/token", json={"username": "coach1", "password": "CoachPass!235"})
        assert login.status_code == 200, login.text
        assert login.json()["token_type"] == "bearer"
        assert login.json()["access_token"]


def test_events_crud_and_preferences_endpoints(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")

        list_resp = client.get("/api/v1/athletes/1/events", headers=athlete_headers)
        assert list_resp.status_code == 200, list_resp.text
        initial_total = list_resp.json()["total"]
        assert initial_total >= 1

        create_resp = client.post(
            "/api/v1/athletes/1/events",
            json={"name": "Goal Half", "event_date": (date.today() + timedelta(days=70)).isoformat(), "distance": "Half Marathon"},
            headers=athlete_headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        event_id = create_resp.json()["id"]
        assert create_resp.json()["athlete_id"] == 1

        patch_resp = client.patch(
            f"/api/v1/events/{event_id}",
            json={"name": "A Goal Half", "distance": "10K"},
            headers=coach_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        assert patch_resp.json()["name"] == "A Goal Half"
        assert patch_resp.json()["distance"] == "10K"

        wrong_scope = client.get("/api/v1/athletes/2/events", headers=athlete_headers)
        assert wrong_scope.status_code == 403
        assert wrong_scope.json()["detail"]["code"] == "FORBIDDEN_ATHLETE_SCOPE"

        delete_resp = client.delete(f"/api/v1/events/{event_id}", headers=athlete_headers)
        assert delete_resp.status_code == 200, delete_resp.text
        assert delete_resp.json()["status"] == "ok"

        pref_get = client.get("/api/v1/athletes/1/preferences", headers=athlete_headers)
        assert pref_get.status_code == 200, pref_get.text
        pref_body = pref_get.json()
        assert pref_body["athlete_id"] == 1
        assert "preferred_training_days" in pref_body
        assert "preferred_long_run_day" in pref_body

        pref_patch = client.patch(
            "/api/v1/athletes/1/preferences",
            json={
                "preferred_training_days": ["mon", "Wed", "SUN", "Wed"],
                "preferred_long_run_day": "Sunday",
                "reminder_training_days": ["Tue", "Thu"],
                "privacy_ack": True,
            },
            headers=athlete_headers,
        )
        assert pref_patch.status_code == 200, pref_patch.text
        updated = pref_patch.json()
        assert updated["preferred_training_days"] == ["Mon", "Wed", "Sun"]
        assert updated["preferred_long_run_day"] == "Sun"
        assert updated["reminder_training_days"] == ["Tue", "Thu"]
        assert updated["privacy_ack"] is True

        pref_coach = client.get("/api/v1/athletes/1/preferences", headers=coach_headers)
        assert pref_coach.status_code == 200
        assert pref_coach.json()["preferred_long_run_day"] == "Sun"


def test_coach_people_management_create_coach_and_athlete(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        admin_headers = _auth_headers(client, "master", "MasterPass!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        # athlete cannot manage people
        forbidden = client.post(
            "/api/v1/coach/coaches",
            json={"username": "newcoach", "password": "CoachPass!234", "must_change_password": False},
            headers=athlete_headers,
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"

        create_coach = client.post(
            "/api/v1/coach/coaches",
            json={"username": "newcoach", "password": "CoachPass!234", "must_change_password": False},
            headers=admin_headers,
        )
        assert create_coach.status_code == 200, create_coach.text
        assert create_coach.json()["user"]["role"] == "coach"
        assert create_coach.json()["user"]["username"] == "newcoach"

        coaches = client.get("/api/v1/coach/coaches?offset=0&limit=50", headers=admin_headers)
        assert coaches.status_code == 200, coaches.text
        assert any(item["username"] == "newcoach" for item in coaches.json()["items"])

        duplicate_coach = client.post(
            "/api/v1/coach/coaches",
            json={"username": "newcoach", "password": "CoachPass!234"},
            headers=admin_headers,
        )
        assert duplicate_coach.status_code == 409
        assert duplicate_coach.json()["detail"]["code"] == "USERNAME_TAKEN"

        bad_pw = client.post(
            "/api/v1/coach/coaches",
            json={"username": "weakcoach", "password": "weak"},
            headers=admin_headers,
        )
        assert bad_pw.status_code == 400
        assert bad_pw.json()["detail"]["code"] == "PASSWORD_POLICY"

        create_athlete = client.post(
            "/api/v1/coach/athletes",
            json={
                "first_name": "Taylor",
                "last_name": "Runner",
                "email": "taylor.runner@example.com",
                "username": "taylor1",
                "password": "AthletePass!234",
                "max_hr": 188,
                "resting_hr": 52,
                "threshold_pace_sec_per_km": 280,
                "easy_pace_sec_per_km": 345,
            },
            headers=admin_headers,
        )
        assert create_athlete.status_code == 200, create_athlete.text
        athlete_body = create_athlete.json()
        assert athlete_body["athlete"]["email"] == "taylor.runner@example.com"
        assert athlete_body["user"]["role"] == "client"
        assert athlete_body["user"]["athlete_id"] == athlete_body["athlete"]["id"]

        duplicate_email = client.post(
            "/api/v1/coach/athletes",
            json={
                "first_name": "Taylor",
                "last_name": "Runner",
                "email": "taylor.runner@example.com",
                "username": "taylor2",
                "password": "AthletePass!234",
            },
            headers=admin_headers,
        )
        assert duplicate_email.status_code == 409
        assert duplicate_email.json()["detail"]["code"] == "ATHLETE_EMAIL_TAKEN"

        # New accounts can authenticate.
        new_coach_login = client.post("/api/v1/auth/token", json={"username": "newcoach", "password": "CoachPass!234"})
        assert new_coach_login.status_code == 200, new_coach_login.text
        assert new_coach_login.json()["role"] == "coach"

        new_athlete_login = client.post("/api/v1/auth/token", json={"username": "taylor1", "password": "AthletePass!234"})
        assert new_athlete_login.status_code == 200, new_athlete_login.text
        assert new_athlete_login.json()["athlete_id"] == athlete_body["athlete"]["id"]


def test_coach_people_management_user_admin_actions_and_athlete_update(tmp_path, monkeypatch):
    from core.db import session_scope
    from core.models import User

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        admin_headers = _auth_headers(client, "master", "MasterPass!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        create_coach = client.post(
            "/api/v1/coach/coaches",
            json={"username": "opscoach", "password": "CoachPass!234", "must_change_password": False},
            headers=admin_headers,
        )
        assert create_coach.status_code == 200, create_coach.text
        opscoach_id = int(create_coach.json()["user"]["id"])

        create_athlete = client.post(
            "/api/v1/coach/athletes",
            json={
                "first_name": "Morgan",
                "last_name": "Pacer",
                "email": "morgan.pacer@example.com",
                "username": "morgan1",
                "password": "AthletePass!234",
                "max_hr": 186,
                "resting_hr": 49,
            },
            headers=admin_headers,
        )
        assert create_athlete.status_code == 200, create_athlete.text
        athlete_id = int(create_athlete.json()["athlete"]["id"])

        users = client.get("/api/v1/coach/users?offset=0&limit=200", headers=admin_headers)
        assert users.status_code == 200, users.text
        users_body = users.json()
        assert users_body["total"] >= 3
        assert any(item["username"] == "opscoach" for item in users_body["items"])
        assert any(item["username"] == "morgan1" and item["role"] == "client" for item in users_body["items"])

        filter_role = client.get("/api/v1/coach/users?role=athlete", headers=admin_headers)
        assert filter_role.status_code == 200
        assert any(item["username"] == "morgan1" for item in filter_role.json()["items"])
        assert all(item["role"] == "client" for item in filter_role.json()["items"])

        with session_scope() as s:
            locked_user = s.get(User, opscoach_id)
            assert locked_user is not None
            locked_user.failed_attempts = 5
            locked_user.locked_until = datetime.utcnow() + timedelta(minutes=30)

        unlock = client.post(f"/api/v1/coach/users/{opscoach_id}/unlock", headers=admin_headers)
        assert unlock.status_code == 200, unlock.text
        assert unlock.json()["user"]["failed_attempts"] == 0
        assert unlock.json()["user"]["locked_until"] is None

        reset = client.post(
            f"/api/v1/coach/users/{opscoach_id}/reset-password",
            json={"new_password": "NewCoachPass!234", "must_change_password": True},
            headers=admin_headers,
        )
        assert reset.status_code == 200, reset.text
        assert reset.json()["user"]["must_change_password"] is True

        login_requires_change = client.post("/api/v1/auth/token", json={"username": "opscoach", "password": "NewCoachPass!234"})
        assert login_requires_change.status_code == 403
        assert login_requires_change.json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"

        update_athlete = client.patch(
            f"/api/v1/coach/athletes/{athlete_id}",
            json={
                "first_name": "Morgan",
                "last_name": "Pacer-Updated",
                "status": "paused",
                "max_hr": 188,
                "resting_hr": 50,
                "threshold_pace_sec_per_km": 282,
                "easy_pace_sec_per_km": 348,
            },
            headers=coach_headers,
        )
        assert update_athlete.status_code == 200, update_athlete.text
        updated = update_athlete.json()
        assert updated["last_name"] == "Pacer-Updated"
        assert updated["status"] == "paused"
        assert updated["max_hr"] == 188
        assert updated["threshold_pace_sec_per_km"] == 282

        athlete_cannot_manage = client.get("/api/v1/coach/users", headers=athlete_headers)
        assert athlete_cannot_manage.status_code == 403
        assert athlete_cannot_manage.json()["detail"]["code"] == "FORBIDDEN_ROLE"


def test_coach_intervention_actions_and_audit_log(tmp_path, monkeypatch):
    from core.db import session_scope
    from core.models import AppWriteLog

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        listing = client.get("/api/v1/coach/interventions", headers=coach_headers)
        assert listing.status_code == 200, listing.text
        intervention_id = listing.json()["items"][0]["id"]

        forbidden = client.post(
            f"/api/v1/coach/interventions/{intervention_id}/action",
            json={"action": "resolve"},
            headers=athlete_headers,
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"

        snooze = client.post(
            f"/api/v1/coach/interventions/{intervention_id}/action",
            json={"action": "snooze", "cooldown_minutes": 180, "note": "Waiting for athlete reply"},
            headers=coach_headers,
        )
        assert snooze.status_code == 200, snooze.text
        snooze_body = snooze.json()
        assert snooze_body["status"] == "ok"
        assert snooze_body["intervention"]["status"] == "snoozed"
        assert snooze_body["intervention"]["cooldown_until"] is not None

        resolve = client.post(
            f"/api/v1/coach/interventions/{intervention_id}/action",
            json={"action": "resolve"},
            headers=coach_headers,
        )
        assert resolve.status_code == 200, resolve.text
        resolve_body = resolve.json()
        assert resolve_body["intervention"]["status"] == "resolved"
        assert resolve_body["intervention"]["cooldown_until"] is None

        with session_scope() as s:
            logs = s.query(AppWriteLog).filter(AppWriteLog.scope == "coach_intervention_action").all()
            assert len(logs) >= 2
            latest = logs[-1]
            assert latest.actor_user_id == 4
            assert latest.payload["intervention_id"] == intervention_id
            assert latest.payload["action"] == "resolve"

        audit_list = client.get("/api/v1/coach/audit-logs?scope=coach_intervention_action&limit=20", headers=coach_headers)
        assert audit_list.status_code == 200, audit_list.text
        audit_body = audit_list.json()
        assert audit_body["total"] >= 2
        assert audit_body["items"][0]["scope"] == "coach_intervention_action"
        assert "payload" in audit_body["items"][0]

        filtered_audit = client.get(
            f"/api/v1/coach/audit-logs?scope=coach_intervention_action&intervention_id={intervention_id}",
            headers=coach_headers,
        )
        assert filtered_audit.status_code == 200, filtered_audit.text
        assert filtered_audit.json()["total"] >= 2

        today_str = date.today().isoformat()
        dated_audit = client.get(
            f"/api/v1/coach/audit-logs?scope=coach_intervention_action&created_from={today_str}&created_to={today_str}",
            headers=coach_headers,
        )
        assert dated_audit.status_code == 200, dated_audit.text
        assert dated_audit.json()["total"] >= 2

        athlete_forbidden = client.get("/api/v1/coach/audit-logs", headers=athlete_headers)
        assert athlete_forbidden.status_code == 403
        assert athlete_forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"


def test_coach_intervention_auto_apply_low_risk_policy(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        review_queue = client.get("/api/v1/coach/interventions?status=open&review_state=needs_review", headers=coach_headers)
        assert review_queue.status_code == 200, review_queue.text
        assert review_queue.json()["total"] >= 1
        assert review_queue.json()["items"][0]["auto_apply_eligible"] is False
        assert review_queue.json()["items"][0]["review_reason"] == "athlete_policy_missing"

        # Enable athlete automation policy so the seeded low-risk intervention becomes eligible.
        pref_patch = client.patch(
            "/api/v1/athletes/1/preferences",
            json={
                "auto_apply_low_risk": True,
                "auto_apply_confidence_min": 0.75,
                "auto_apply_risk_max": 0.45,
            },
            headers=athlete_headers,
        )
        assert pref_patch.status_code == 200, pref_patch.text

        eligible_queue = client.get("/api/v1/coach/interventions?status=open&review_state=auto_eligible", headers=coach_headers)
        assert eligible_queue.status_code == 200, eligible_queue.text
        assert eligible_queue.json()["total"] >= 1
        assert eligible_queue.json()["items"][0]["auto_apply_eligible"] is True
        assert eligible_queue.json()["items"][0]["review_reason"] == "eligible"

        forbidden = client.post("/api/v1/coach/interventions/auto-apply-low-risk", headers=athlete_headers)
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"

        run = client.post("/api/v1/coach/interventions/auto-apply-low-risk?limit=50", headers=coach_headers)
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["status"] == "ok"
        assert body["scanned_count"] >= 1
        assert body["eligible_count"] >= 1
        assert body["applied_count"] >= 1
        assert any(item["status"] == "approved" for item in body["applied"])

        listing = client.get("/api/v1/coach/interventions?status=approved", headers=coach_headers)
        assert listing.status_code == 200, listing.text
        approved_item = next((item for item in listing.json()["items"] if item["id"] == body["applied"][0]["id"]), None)
        assert approved_item is not None
        assert approved_item["auto_revert_available"] is True
        assert approved_item["auto_revert_block_reason"] in {None, ""}

        audit = client.get("/api/v1/coach/audit-logs?scope=coach_intervention_auto_apply_batch", headers=coach_headers)
        assert audit.status_code == 200, audit.text
        assert audit.json()["total"] >= 1


def test_coach_intervention_revert_auto_apply_approval(tmp_path, monkeypatch):
    from core.db import session_scope
    from core.models import AppWriteLog

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        pref_patch = client.patch(
            "/api/v1/athletes/1/preferences",
            json={
                "auto_apply_low_risk": True,
                "auto_apply_confidence_min": 0.75,
                "auto_apply_risk_max": 0.45,
            },
            headers=athlete_headers,
        )
        assert pref_patch.status_code == 200, pref_patch.text

        run = client.post("/api/v1/coach/interventions/auto-apply-low-risk?limit=50", headers=coach_headers)
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["applied_count"] >= 1
        intervention_id = int(body["applied"][0]["id"])

        listing_approved = client.get("/api/v1/coach/interventions?status=approved", headers=coach_headers)
        assert listing_approved.status_code == 200, listing_approved.text
        approved_item = next((item for item in listing_approved.json()["items"] if int(item["id"]) == intervention_id), None)
        assert approved_item is not None
        assert approved_item["auto_revert_available"] is True

        forbidden = client.post(
            f"/api/v1/coach/interventions/{intervention_id}/revert-auto-approval",
            headers=athlete_headers,
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"

        reverted = client.post(
            f"/api/v1/coach/interventions/{intervention_id}/revert-auto-approval",
            headers=coach_headers,
        )
        assert reverted.status_code == 200, reverted.text
        revert_body = reverted.json()
        assert revert_body["status"] == "ok"
        assert revert_body["intervention"]["status"] == "open"
        assert revert_body["intervention"]["cooldown_until"] is None
        assert revert_body["intervention"]["auto_revert_available"] is False

        double_revert = client.post(
            f"/api/v1/coach/interventions/{intervention_id}/revert-auto-approval",
            headers=coach_headers,
        )
        assert double_revert.status_code == 409, double_revert.text
        assert double_revert.json()["detail"]["code"] in {"AUTO_APPLY_ALREADY_REVERTED", "INTERVENTION_STATE_CHANGED"}

        with session_scope() as s:
            logs = (
                s.query(AppWriteLog)
                .filter(AppWriteLog.scope == "coach_intervention_action")
                .order_by(AppWriteLog.id.desc())
                .all()
            )
            assert any((row.payload or {}).get("action") == "revert_auto_approve" for row in logs)
            latest_revert = next((row for row in logs if (row.payload or {}).get("action") == "revert_auto_approve"), None)
            assert latest_revert is not None
            assert int((latest_revert.payload or {}).get("intervention_id")) == intervention_id
            assert int((latest_revert.payload or {}).get("source_action_log_id")) > 0


def test_coach_intervention_revert_requires_auto_apply_source(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        listing = client.get("/api/v1/coach/interventions", headers=coach_headers)
        assert listing.status_code == 200, listing.text
        intervention_id = int(listing.json()["items"][0]["id"])

        manual = client.post(
            f"/api/v1/coach/interventions/{intervention_id}/action",
            json={"action": "approve"},
            headers=coach_headers,
        )
        assert manual.status_code == 200, manual.text

        approved_listing = client.get("/api/v1/coach/interventions?status=approved", headers=coach_headers)
        assert approved_listing.status_code == 200, approved_listing.text
        approved_item = next((item for item in approved_listing.json()["items"] if int(item["id"]) == intervention_id), None)
        assert approved_item is not None
        assert approved_item["auto_revert_available"] is False
        assert approved_item["auto_revert_block_reason"] == "auto_apply_source_not_found"

        revert = client.post(
            f"/api/v1/coach/interventions/{intervention_id}/revert-auto-approval",
            headers=coach_headers,
        )
        assert revert.status_code == 409, revert.text
        assert revert.json()["detail"]["code"] == "AUTO_APPLY_REVERT_NOT_AVAILABLE"


def test_coach_intervention_review_state_validation(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        invalid = client.get("/api/v1/coach/interventions?review_state=unknown", headers=coach_headers)
        assert invalid.status_code == 400, invalid.text
        assert invalid.json()["detail"]["code"] == "INVALID_REVIEW_STATE_FILTER"


def test_coach_automation_policy_endpoints_and_fallback_auto_apply(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        default_policy = client.get("/api/v1/coach/automation-policy", headers=coach_headers)
        assert default_policy.status_code == 200, default_policy.text
        assert default_policy.json()["source"] == "default"
        assert default_policy.json()["enabled"] is False

        forbidden = client.get("/api/v1/coach/automation-policy", headers=athlete_headers)
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"

        updated_policy = client.patch(
            "/api/v1/coach/automation-policy",
            json={
                "enabled": True,
                "default_auto_apply_low_risk": True,
                "default_auto_apply_confidence_min": 0.7,
                "default_auto_apply_risk_max": 0.5,
                "apply_when_athlete_pref_missing": True,
                "apply_when_athlete_pref_disabled": True,
            },
            headers=coach_headers,
        )
        assert updated_policy.status_code == 200, updated_policy.text
        assert updated_policy.json()["source"] == "saved"
        assert updated_policy.json()["enabled"] is True
        assert updated_policy.json()["default_auto_apply_low_risk"] is True

        # No athlete prefs row exists yet for athlete 1; coach-level fallback should allow auto-apply.
        run = client.post("/api/v1/coach/interventions/auto-apply-low-risk?limit=50", headers=coach_headers)
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["applied_count"] >= 1
        assert any(item["status"] == "approved" for item in body["applied"])

        action_audit = client.get("/api/v1/coach/audit-logs?scope=coach_intervention_action&limit=20", headers=coach_headers)
        assert action_audit.status_code == 200
        assert any((row.get("payload") or {}).get("policy_source") == "coach_default_missing_pref" for row in action_audit.json()["items"])


def test_coach_command_center_endpoint(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        forbidden = client.get("/api/v1/coach/command-center", headers=athlete_headers)
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"

        resp = client.get("/api/v1/coach/command-center?queue_limit=5&recent_decisions_limit=5", headers=coach_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ranking_version"] == "heuristic_v1"
        assert body["ranked_queue_limit"] == 5
        assert "portfolio" in body
        assert "ranked_queue" in body
        assert "recent_decisions" in body
        if body["ranked_queue"]:
            first = body["ranked_queue"][0]
            assert "priority_score" in first
            assert "priority_components" in first
            assert first["ranking_version"] == "heuristic_v1"


def test_coach_planner_ruleset_endpoint(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        forbidden = client.get("/api/v1/coach/planner-ruleset", headers=athlete_headers)
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"

        resp = client.get("/api/v1/coach/planner-ruleset", headers=coach_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "meta" in body
        assert "quality_policy_rules" in body
        assert "token_orchestration_rules" in body
        assert body["meta"]["week_policy_version"].startswith("jd_")
        assert body["meta"]["progression_track_ruleset_version"].startswith("jd_")
        assert body["meta"]["token_orchestration_ruleset_version"].startswith("jd_")
        assert body["meta"]["quality_policy_rule_count"] >= 1
        assert body["meta"]["token_orchestration_rule_count"] >= 1
        assert isinstance(body["token_orchestration_rules"], list)


def test_coach_planner_ruleset_validate_update_and_rollback(tmp_path, monkeypatch):
    ruleset_path = tmp_path / "planner_ruleset.json"
    backup_path = tmp_path / "planner_ruleset.bak.json"
    with _build_client(
        tmp_path,
        monkeypatch,
        env_overrides={"PROGRESSION_TRACK_RULESET_PATH": str(ruleset_path)},
    ) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")

        initial = client.get("/api/v1/coach/planner-ruleset", headers=coach_headers)
        assert initial.status_code == 200, initial.text
        ruleset = initial.json()
        assert ruleset["meta"]["source"].endswith(".json")

        invalid = client.post(
            "/api/v1/coach/planner-ruleset/validate",
            json={"ruleset": {"meta": {}, "quality_policy_rules": {}, "token_orchestration_rules": []}},
            headers=coach_headers,
        )
        assert invalid.status_code == 200, invalid.text
        invalid_body = invalid.json()
        assert invalid_body["valid"] is False
        assert invalid_body["errors"]
        assert isinstance(invalid_body["warnings"], list)
        assert isinstance(invalid_body["diff_preview"], dict)

        mutated = dict(ruleset)
        mutated_meta = dict(mutated["meta"])
        mutated_meta["week_policy_version"] = "jd_week_policy_v1_customtest"
        mutated["meta"] = mutated_meta

        valid = client.post("/api/v1/coach/planner-ruleset/validate", json={"ruleset": mutated}, headers=coach_headers)
        assert valid.status_code == 200, valid.text
        valid_body = valid.json()
        assert valid_body["valid"] is True
        assert isinstance(valid_body["warnings"], list)
        assert isinstance(valid_body["diff_preview"], dict)
        assert bool(valid_body["diff_preview"].get("has_changes")) is True

        mutated_bad = dict(mutated)
        bad_token_rules = list(mutated_bad["token_orchestration_rules"])
        bad_rule = dict(bad_token_rules[0])
        bad_rule["name"] = bad_token_rules[0]["name"]
        bad_rule["phase"] = "invalid_phase"
        bad_rule["race_focuses"] = ["10k", "bad_focus"]
        bad_token_rules.append(bad_rule)
        mutated_bad["token_orchestration_rules"] = bad_token_rules
        semantic_invalid = client.post(
            "/api/v1/coach/planner-ruleset/validate",
            json={"ruleset": mutated_bad},
            headers=coach_headers,
        )
        assert semantic_invalid.status_code == 200, semantic_invalid.text
        semantic_body = semantic_invalid.json()
        assert semantic_body["valid"] is False
        assert any("unsupported value 'invalid_phase'" in err for err in semantic_body["errors"])

        update = client.put("/api/v1/coach/planner-ruleset", json={"ruleset": mutated}, headers=coach_headers)
        assert update.status_code == 200, update.text
        update_body = update.json()
        assert update_body["status"] == "ok"
        assert update_body["ruleset"]["meta"]["week_policy_version"] == "jd_week_policy_v1_customtest"
        assert backup_path.exists()

        rolled = client.post("/api/v1/coach/planner-ruleset/rollback", headers=coach_headers)
        assert rolled.status_code == 200, rolled.text
        rolled_body = rolled.json()
        assert rolled_body["status"] == "ok"
        assert rolled_body["ruleset"]["meta"]["week_policy_version"] != "jd_week_policy_v1_customtest"

        history = client.get("/api/v1/coach/planner-ruleset/history?offset=0&limit=10", headers=coach_headers)
        assert history.status_code == 200, history.text
        history_body = history.json()
        assert history_body["total"] >= 2
        assert "scope_counts" in history_body
        assert history_body["scope_counts"].get("planner_ruleset_update", 0) >= 1
        assert history_body["scope_counts"].get("planner_ruleset_rollback", 0) >= 1
        assert history_body["items"]
        update_item = next((it for it in history_body["items"] if it["scope"] == "planner_ruleset_update"), None)
        assert update_item is not None
        payload = update_item["payload"]
        assert "before_meta" in payload
        assert "after_meta" in payload
        assert "diff_preview" in payload
        assert "latest_backup_snapshot" in payload

        backups = client.get("/api/v1/coach/planner-ruleset/backups?limit=20", headers=coach_headers)
        assert backups.status_code == 200, backups.text
        backups_body = backups.json()
        assert backups_body["total"] >= 1
        assert backups_body["items"]
        assert any(item["kind"] == "latest_backup" for item in backups_body["items"])


def test_session_library_governance_report_endpoint(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        forbidden = client.get("/api/v1/coach/session-library/governance/report", headers=athlete_headers)
        assert forbidden.status_code == 403

        # Seed some governance activity for the report.
        client.post("/api/v1/coach/session-library/gold-standard-pack", headers=coach_headers)
        report = client.get("/api/v1/coach/session-library/governance/report?recent_limit=5", headers=coach_headers)
        assert report.status_code == 200, report.text
        body = report.json()
        assert "template_count" in body
        assert "status_counts" in body
        assert "methodology_counts" in body
        assert "recent_scope_counts" in body
        assert "recent_actions" in body
        assert body["template_count"] >= 1


def test_session_library_crud_and_validate_endpoints(tmp_path, monkeypatch):
    from core.services.session_library import default_progression, default_regression, default_structure, default_targets

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        # coach list + detail
        listing = client.get("/api/v1/coach/session-library?offset=0&limit=20", headers=coach_headers)
        assert listing.status_code == 200, listing.text
        assert listing.json()["total"] >= 1
        assert listing.json()["items"][0]["id"] >= 1

        detail = client.get("/api/v1/coach/session-library/1", headers=coach_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["id"] == 1
        assert "structure_json" in detail.json()

        # athlete cannot access coach-only session library routes
        forbidden = client.get("/api/v1/coach/session-library", headers=athlete_headers)
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "FORBIDDEN_ROLE"

        valid_payload = {
            "name": "VO2 Builder 5x3",
            "category": "Run",
            "intent": "vo2",
            "energy_system": "aerobic_power",
            "tier": "hard",
            "is_treadmill": False,
            "duration_min": 58,
            "structure_json": default_structure(58),
            "targets_json": default_targets(),
            "progression_json": default_progression(),
            "regression_json": default_regression(),
            "prescription": "Structured intervals with full warmup and cooldown.",
            "coaching_notes": "Hold mechanics and stop if pain increases.",
        }

        validate_ok = client.post("/api/v1/coach/session-library/validate", json=valid_payload, headers=coach_headers)
        assert validate_ok.status_code == 200, validate_ok.text
        assert validate_ok.json()["valid"] is True
        assert validate_ok.json()["errors"] == []

        invalid_payload = {**valid_payload, "structure_json": {"version": 2, "blocks": []}}
        validate_bad = client.post("/api/v1/coach/session-library/validate", json=invalid_payload, headers=coach_headers)
        assert validate_bad.status_code == 200, validate_bad.text
        assert validate_bad.json()["valid"] is False
        assert len(validate_bad.json()["errors"]) >= 1

        created = client.post("/api/v1/coach/session-library", json=valid_payload, headers=coach_headers)
        assert created.status_code == 200, created.text
        created_body = created.json()
        created_id = created_body["id"]
        assert created_body["name"] == "VO2 Builder 5x3"

        patched = client.patch(
            f"/api/v1/coach/session-library/{created_id}",
            json={"name": "VO2 Builder 6x3", "tier": "medium"},
            headers=coach_headers,
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["name"] == "VO2 Builder 6x3"
        assert patched.json()["tier"] == "medium"

        bad_patch = client.patch(
            f"/api/v1/coach/session-library/{created_id}",
            json={"structure_json": {"version": 2, "blocks": []}},
            headers=coach_headers,
        )
        assert bad_patch.status_code == 400
        assert bad_patch.json()["detail"]["code"] == "SESSION_TEMPLATE_INVALID"

        deleted = client.delete(f"/api/v1/coach/session-library/{created_id}", headers=coach_headers)
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["status"] == "ok"


def test_session_library_duplicate_audit_endpoint(tmp_path, monkeypatch):
    from core.services.session_library import default_progression, default_regression, default_structure, default_targets

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")

        exact_like_payload = {
            "name": "Tempo Builder Variant A",
            "category": "run",
            "intent": "threshold",
            "energy_system": "lactate_threshold",
            "tier": "medium",
            "is_treadmill": False,
            "duration_min": 50,
            "structure_json": default_structure(50),
            "targets_json": default_targets(),
            "progression_json": default_progression(),
            "regression_json": default_regression(),
            "prescription": "Tempo day",
            "coaching_notes": "Steady threshold effort.",
        }
        create_exact = client.post("/api/v1/coach/session-library", json=exact_like_payload, headers=coach_headers)
        assert create_exact.status_code == 200, create_exact.text

        near_like_payload = {
            **exact_like_payload,
            "name": "Tempo Builder Variant B",
            "duration_min": 52,
            "structure_json": default_structure(52),
        }
        create_near = client.post("/api/v1/coach/session-library", json=near_like_payload, headers=coach_headers)
        assert create_near.status_code == 200, create_near.text

        audit = client.get("/api/v1/coach/session-library/audit/duplicates?limit=20", headers=coach_headers)
        assert audit.status_code == 200, audit.text
        body = audit.json()
        assert "summary" in body
        assert "candidates" in body
        assert body["summary"]["template_count"] >= 3
        assert body["summary"]["candidate_count"] >= 1
        assert isinstance(body["candidates"], list)
        first = body["candidates"][0]
        assert first["kind"] in {"exact", "near"}
        assert "left" in first and "right" in first
        assert "reason_tags" in first


def test_session_library_duplicate_audit_distinguishes_jd_variant_structures(tmp_path, monkeypatch):
    from sqlalchemy import select

    from api.routes import _session_library_duplicate_audit
    from core.db import session_scope
    from core.models import SessionLibrary

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        seed_gold = client.post("/api/v1/coach/session-library/gold-standard-pack", headers=coach_headers)
        assert seed_gold.status_code == 200, seed_gold.text

        with session_scope() as s:
            rows = (
                s.execute(
                    select(SessionLibrary).where(
                        SessionLibrary.name.in_(
                            [
                                "Threshold Cruise Intervals (T) 3x10min",
                                "Threshold Cruise Intervals (T) 5x6min",
                            ]
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 2
            expected_names = {rows[0].name, rows[1].name}

            audit = _session_library_duplicate_audit(rows, limit=10, min_similarity=0.5)
            assert audit.summary.template_count == 2
            assert audit.summary.exact_duplicate_pairs == 0
            assert audit.summary.candidate_count >= 1
            pair = next((c for c in audit.candidates if {c.left.name, c.right.name} == expected_names), None)
            assert pair is not None
            assert pair.kind == "near"


def test_session_library_gold_standard_pack_endpoint(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")

        resp = client.post("/api/v1/coach/session-library/gold-standard-pack", headers=coach_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["template_count"] >= 8
        assert body["created_count"] + body["updated_count"] >= 8

        listing = client.get("/api/v1/coach/session-library?q=Long%20Run%20(E)%2090min&offset=0&limit=5", headers=coach_headers)
        assert listing.status_code == 200, listing.text
        assert any(item["name"] == "Long Run (E) 90min" and item["status"] == "canonical" for item in listing.json()["items"])


def test_session_library_bulk_deprecate_legacy_endpoint(tmp_path, monkeypatch):
    from core.services.session_library import default_progression, default_regression, default_structure, default_targets

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")

        payload = {
            "name": "Legacy Generic Easy Template",
            "category": "run",
            "intent": "easy_aerobic",
            "energy_system": "aerobic_base",
            "tier": "medium",
            "is_treadmill": False,
            "duration_min": 50,
            "structure_json": default_structure(50),
            "targets_json": default_targets(),
            "progression_json": default_progression(),
            "regression_json": default_regression(),
            "prescription": "Generic easy run template.",
            "coaching_notes": "Legacy-style template for migration testing.",
        }
        created = client.post("/api/v1/coach/session-library", json=payload, headers=coach_headers)
        assert created.status_code == 200, created.text
        created_id = created.json()["id"]
        assert created.json()["status"] == "active"

        seed_gold = client.post("/api/v1/coach/session-library/gold-standard-pack", headers=coach_headers)
        assert seed_gold.status_code == 200, seed_gold.text

        preview = client.post(
            "/api/v1/coach/session-library/governance/bulk-deprecate-legacy",
            json={"dry_run": True, "sample_limit": 20},
            headers=coach_headers,
        )
        assert preview.status_code == 200, preview.text
        preview_body = preview.json()
        assert preview_body["status"] == "ok"
        assert preview_body["action"] == "bulk_deprecate_legacy"
        assert preview_body["dry_run"] is True
        assert preview_body["candidate_count"] >= 1

        apply_resp = client.post(
            "/api/v1/coach/session-library/governance/bulk-deprecate-legacy",
            json={"dry_run": False, "sample_limit": 10},
            headers=coach_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        apply_body = apply_resp.json()
        assert apply_body["dry_run"] is False
        assert apply_body["changed_count"] >= 1

        legacy_listing = client.get(
            f"/api/v1/coach/session-library?q=Legacy%20Generic%20Easy%20Template&offset=0&limit=5",
            headers=coach_headers,
        )
        assert legacy_listing.status_code == 200, legacy_listing.text
        legacy_items = legacy_listing.json()["items"]
        assert any(item["id"] == created_id and item["status"] == "deprecated" for item in legacy_items)

        canonical_listing = client.get(
            "/api/v1/coach/session-library?q=Long%20Run%20(E)%2090min&offset=0&limit=5",
            headers=coach_headers,
        )
        assert canonical_listing.status_code == 200, canonical_listing.text
        assert any(item["name"] == "Long Run (E) 90min" and item["status"] == "canonical" for item in canonical_listing.json()["items"])


def test_session_library_bulk_canonicalize_duplicates_endpoint(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")

        seed_gold = client.post("/api/v1/coach/session-library/gold-standard-pack", headers=coach_headers)
        assert seed_gold.status_code == 200, seed_gold.text

        canonical = client.get("/api/v1/coach/session-library?q=Long%20Run%20(E)%2090min&offset=0&limit=5", headers=coach_headers)
        assert canonical.status_code == 200, canonical.text
        canonical_items = canonical.json()["items"]
        canonical_id = next(item["id"] for item in canonical_items if item["name"] == "Long Run (E) 90min")
        canonical_detail = client.get(f"/api/v1/coach/session-library/{canonical_id}", headers=coach_headers)
        assert canonical_detail.status_code == 200, canonical_detail.text
        detail = canonical_detail.json()

        payload = {
            "name": "Long Run (E) 90min Legacy Clone",
            "category": detail["category"],
            "intent": detail["intent"],
            "energy_system": detail["energy_system"],
            "tier": detail["tier"],
            "is_treadmill": detail["is_treadmill"],
            "duration_min": detail["duration_min"],
            "structure_json": detail["structure_json"],
            "targets_json": detail["targets_json"],
            "progression_json": detail["progression_json"],
            "regression_json": detail["regression_json"],
            "prescription": detail["prescription"],
            "coaching_notes": detail["coaching_notes"],
        }
        legacy = client.post("/api/v1/coach/session-library", json=payload, headers=coach_headers)
        assert legacy.status_code == 200, legacy.text
        legacy_id = legacy.json()["id"]
        assert legacy.json()["status"] == "active"

        preview = client.post(
            "/api/v1/coach/session-library/governance/bulk-canonicalize-duplicates",
            json={"dry_run": True, "candidate_limit": 200, "min_similarity": 0.78, "sample_limit": 10},
            headers=coach_headers,
        )
        assert preview.status_code == 200, preview.text
        preview_body = preview.json()
        assert preview_body["status"] == "ok"
        assert preview_body["action"] == "bulk_canonicalize_duplicates"
        assert preview_body["dry_run"] is True
        assert isinstance(preview_body["applied"], list)
        assert preview_body["applied_count"] >= 1

        apply_resp = client.post(
            "/api/v1/coach/session-library/governance/bulk-canonicalize-duplicates",
            json={"dry_run": False, "candidate_limit": 200, "min_similarity": 0.78, "sample_limit": 10},
            headers=coach_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        apply_body = apply_resp.json()
        assert apply_body["dry_run"] is False
        assert apply_body["applied_count"] >= 1

        listing = client.get(
            f"/api/v1/coach/session-library?q=Long%20Run%20(E)%2090min%20Legacy%20Clone&offset=0&limit=5",
            headers=coach_headers,
        )
        assert listing.status_code == 200, listing.text
        items = listing.json()["items"]
        matched = next((item for item in items if item["id"] == legacy_id), None)
        assert matched is not None
        assert matched["status"] == "duplicate"
        assert matched["duplicate_of_template_id"] is not None


def test_session_library_bulk_canonicalize_skips_near_jd_variants(tmp_path, monkeypatch):
    from core.services.session_library import gold_standard_session_templates_v1

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")

        templates = {item["name"]: item for item in gold_standard_session_templates_v1()}
        first = templates["Threshold Cruise Intervals (T) 3x10min"]
        second = templates["Threshold Cruise Intervals (T) 5x6min"]

        create_one = client.post("/api/v1/coach/session-library", json=first, headers=coach_headers)
        assert create_one.status_code == 200, create_one.text
        create_two = client.post("/api/v1/coach/session-library", json=second, headers=coach_headers)
        assert create_two.status_code == 200, create_two.text

        preview = client.post(
            "/api/v1/coach/session-library/governance/bulk-canonicalize-duplicates",
            json={"dry_run": True, "candidate_limit": 50, "min_similarity": 0.5, "sample_limit": 20},
            headers=coach_headers,
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["status"] == "ok"
        assert body["applied_count"] == 0
        assert body["skipped_count"] >= 1
        assert any(item["reason_code"] == "JD_VARIANT_MANUAL_REVIEW" for item in body["skipped"])


def test_session_library_metadata_audit_endpoint(tmp_path, monkeypatch):
    from core.services.session_library import default_progression, default_regression, default_structure, default_targets

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        seed_gold = client.post("/api/v1/coach/session-library/gold-standard-pack", headers=coach_headers)
        assert seed_gold.status_code == 200, seed_gold.text

        payload = {
            "name": "Tempo Audit Candidate",
            "category": "Run",  # non-canonical casing on purpose
            "intent": "threshold",
            "energy_system": "lactate_threshold",
            "tier": "HARD",  # non-canonical casing on purpose
            "is_treadmill": False,
            "duration_min": 50,
            "structure_json": default_structure(50),  # no explicit intensity_code on main_set
            "targets_json": default_targets(),
            "progression_json": default_progression(),
            "regression_json": default_regression(),
            "prescription": "Tempo day with controlled work.",
            "coaching_notes": "Stay smooth through reps.",
        }
        created = client.post("/api/v1/coach/session-library", json=payload, headers=coach_headers)
        assert created.status_code == 200, created.text
        created_id = created.json()["id"]
        assert created.json()["status"] == "active"
        assert created.json()["duplicate_of_template_id"] is None

        audit = client.get("/api/v1/coach/session-library/audit/metadata?limit=50", headers=coach_headers)
        assert audit.status_code == 200, audit.text
        body = audit.json()
        assert "summary" in body and "items" in body
        assert body["summary"]["template_count"] >= 1
        assert body["summary"]["templates_with_issues"] >= 1
        assert isinstance(body["items"], list)

        target_item = next((item for item in body["items"] if item["template"]["id"] == created_id), None)
        assert target_item is not None
        issue_codes = {issue["code"] for issue in target_item["issues"]}
        assert "noncanonical_category_format" in issue_codes
        assert "noncanonical_tier_format" in issue_codes
        assert "missing_intensity_code_main_set" in issue_codes

        normalized = client.post(f"/api/v1/coach/session-library/{created_id}/normalize-metadata", headers=coach_headers)
        assert normalized.status_code == 200, normalized.text
        normalized_body = normalized.json()
        assert normalized_body["status"] == "ok"
        assert normalized_body["template"]["category"] == "run"
        assert normalized_body["template"]["tier"] == "hard"
        assert normalized_body["applied_change_count"] >= 2
        assert any(change["field"] == "category" for change in normalized_body["applied_changes"])
        assert normalized_body["issue_counts_after"]["warnings"] <= normalized_body["issue_counts_before"]["warnings"]

        canonical = client.post(
            f"/api/v1/coach/session-library/{created_id}/governance-action",
            json={"action": "mark_canonical"},
            headers=coach_headers,
        )
        assert canonical.status_code == 200, canonical.text
        assert canonical.json()["template"]["status"] == "canonical"

        dup_payload = {
            "name": "Tempo Audit Candidate Clone",
            "category": "run",
            "intent": "threshold",
            "energy_system": "lactate_threshold",
            "tier": "hard",
            "is_treadmill": False,
            "duration_min": 50,
            "structure_json": default_structure(50),
            "targets_json": default_targets(),
            "progression_json": default_progression(),
            "regression_json": default_regression(),
            "prescription": "Tempo day with controlled work.",
            "coaching_notes": "Stay smooth through reps.",
        }
        dup_created = client.post("/api/v1/coach/session-library", json=dup_payload, headers=coach_headers)
        assert dup_created.status_code == 200, dup_created.text
        dup_id = dup_created.json()["id"]

        mark_dup = client.post(
            f"/api/v1/coach/session-library/{dup_id}/governance-action",
            json={"action": "mark_duplicate", "duplicate_of_template_id": created_id},
            headers=coach_headers,
        )
        assert mark_dup.status_code == 200, mark_dup.text
        assert mark_dup.json()["template"]["status"] == "duplicate"
        assert mark_dup.json()["template"]["duplicate_of_template_id"] == created_id

        deprecate = client.post(
            f"/api/v1/coach/session-library/{dup_id}/governance-action",
            json={"action": "deprecate"},
            headers=coach_headers,
        )
        assert deprecate.status_code == 200, deprecate.text
        assert deprecate.json()["template"]["status"] == "deprecated"


def test_plan_designer_preview_create_detail_and_week_ops(tmp_path, monkeypatch):
    from core.db import session_scope
    from core.models import PlanDaySession

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        seed_gold = client.post("/api/v1/coach/session-library/gold-standard-pack", headers=coach_headers)
        assert seed_gold.status_code == 200, seed_gold.text

        payload = {
            "athlete_id": 1,
            "race_goal": "10K",
            "weeks": 6,
            "start_date": (date.today() + timedelta(days=35)).isoformat(),
            "sessions_per_week": 4,
            "max_session_min": 120,
            "preferred_days": ["Mon", "Wed", "Fri", "Sun"],
            "preferred_long_run_day": "Sun",
        }

        preview = client.post("/api/v1/coach/plans/preview", json=payload, headers=coach_headers)
        assert preview.status_code == 200, preview.text
        preview_body = preview.json()
        assert preview_body["athlete_id"] == 1
        assert len(preview_body["weeks_detail"]) == 6
        assert preview_body["weeks_detail"][0]["assignments"]
        assert isinstance(preview_body["weeks_detail"][0].get("selection_strategy_version"), str)
        assert preview_body["weeks_detail"][0]["planned_long_run_minutes"] is not None
        assert preview_body["weeks_detail"][0]["planned_load_estimate"] is not None
        preview_names = [a["session_name"] for a in preview_body["weeks_detail"][0]["assignments"]]
        assert any(("Long Run (E)" in name) or ("Easy Run (E)" in name) for name in preview_names)
        first_assignment = preview_body["weeks_detail"][0]["assignments"][0]
        assert "planning_token" in first_assignment
        assert "template_selection_reason" in first_assignment
        assert isinstance(first_assignment.get("template_selection_rationale") or [], list)
        if len(preview_body["weeks_detail"]) >= 2:
            week2 = preview_body["weeks_detail"][1]
            week2_names = [a["session_name"] for a in week2["assignments"]]
            assert any("Threshold" in name for name in week2_names), week2_names

        created = client.post("/api/v1/coach/plans", json=payload, headers=coach_headers)
        assert created.status_code == 200, created.text
        plan_id = created.json()["id"]
        assert created.json()["athlete_id"] == 1
        assert isinstance(created.json()["name"], str)
        assert "10K" in created.json()["name"]

        list_resp = client.get("/api/v1/coach/athletes/1/plans", headers=coach_headers)
        assert list_resp.status_code == 200, list_resp.text
        assert list_resp.json()["total"] >= 1

        detail = client.get(f"/api/v1/coach/plans/{plan_id}", headers=coach_headers)
        assert detail.status_code == 200, detail.text
        detail_body = detail.json()
        assert detail_body["plan"]["id"] == plan_id
        assert isinstance(detail_body["plan"]["name"], str)
        assert len(detail_body["weeks"]) == 6
        first_week = detail_body["weeks"][0]
        assert isinstance(first_week["sessions"], list)
        assert first_week["sessions"]
        assert first_week["planned_minutes"] is not None
        assert first_week["planned_minutes"] > len(first_week["sessions"])
        assert first_week["planned_load"] is not None
        assert first_week["planned_load"] > 0
        assert "source_template_id" in first_week["sessions"][0]
        assert "template_selection_reason" in first_week["sessions"][0]
        first_session_id = first_week["sessions"][0]["id"]
        before_minutes = first_week["planned_minutes"]
        before_load = first_week["planned_load"]

        patch_session = client.patch(
            f"/api/v1/coach/plan-day-sessions/{first_session_id}",
            json={"session_name": "Tempo Builder", "source_template_name": "Tempo Builder"},
            headers=coach_headers,
        )
        assert patch_session.status_code == 200, patch_session.text
        assert patch_session.json()["session_name"] == "Tempo Builder"
        assert patch_session.json()["source_template_id"] is not None

        with session_scope() as s:
            stored = s.get(PlanDaySession, first_session_id)
            assert stored is not None
            assert stored.source_template_id is not None
            assert isinstance(stored.compiled_session_json, dict)
            assert stored.compiled_session_json.get("compiler_meta", {}).get("methodology") == "daniels_vdot"
            assert isinstance(stored.compile_context_json, dict)
            assert isinstance((stored.compile_context_json or {}).get("planning"), dict)
            assert stored.compiled_methodology == "daniels_vdot"

        detail_after_patch = client.get(f"/api/v1/coach/plans/{plan_id}", headers=coach_headers)
        assert detail_after_patch.status_code == 200, detail_after_patch.text
        week_after_patch = detail_after_patch.json()["weeks"][0]
        assert week_after_patch["planned_minutes"] is not None
        assert week_after_patch["planned_load"] is not None
        assert (week_after_patch["planned_minutes"] != before_minutes) or (week_after_patch["planned_load"] != before_load)

        lock = client.post(f"/api/v1/coach/plans/{plan_id}/weeks/1/lock", headers=coach_headers)
        assert lock.status_code == 200, lock.text
        assert lock.json()["locked"] is True

        regenerate_locked = client.post(
            f"/api/v1/coach/plans/{plan_id}/weeks/1/regenerate",
            json={"preferred_days": ["Tue", "Thu", "Sat", "Sun"], "preferred_long_run_day": "Sun", "preserve_completed": True},
            headers=coach_headers,
        )
        assert regenerate_locked.status_code == 409
        assert regenerate_locked.json()["detail"]["code"] == "PLAN_WEEK_LOCKED"

        unlock = client.post(f"/api/v1/coach/plans/{plan_id}/weeks/1/unlock", headers=coach_headers)
        assert unlock.status_code == 200, unlock.text
        assert unlock.json()["locked"] is False

        regenerate = client.post(
            f"/api/v1/coach/plans/{plan_id}/weeks/1/regenerate",
            json={"preferred_days": ["Tue", "Thu", "Sat", "Sun"], "preferred_long_run_day": "Sun", "preserve_completed": True},
            headers=coach_headers,
        )
        assert regenerate.status_code == 200, regenerate.text
        assert regenerate.json()["plan"]["id"] == plan_id
        regen_week = regenerate.json()["weeks"][0]
        assert regen_week["planned_minutes"] is not None
        assert regen_week["planned_load"] is not None

        patch_plan = client.patch(f"/api/v1/coach/plans/{plan_id}", json={"status": "draft"}, headers=coach_headers)
        assert patch_plan.status_code == 200, patch_plan.text
        assert patch_plan.json()["status"] == "draft"

        custom_name = "John Smith's New York Plan 2026"
        rename_plan = client.patch(f"/api/v1/coach/plans/{plan_id}", json={"name": custom_name}, headers=coach_headers)
        assert rename_plan.status_code == 200, rename_plan.text
        assert rename_plan.json()["name"] == custom_name

        custom_payload = {
            **payload,
            "start_date": (date.today() + timedelta(days=140)).isoformat(),
            "plan_name": "Demo1 Spring 10K Block",
        }
        created_custom = client.post("/api/v1/coach/plans", json=custom_payload, headers=coach_headers)
        assert created_custom.status_code == 200, created_custom.text
        assert created_custom.json()["name"] == "Demo1 Spring 10K Block"
