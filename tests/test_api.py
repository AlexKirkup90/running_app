"""Tests for the FastAPI REST API layer (auth, routes, schemas, webhooks)."""

from __future__ import annotations

from datetime import date

import pytest
from jose import jwt

from api.auth import TokenData, create_access_token, get_current_user, require_coach, require_athlete
from api.schemas import (
    AthleteOut,
    CheckInOut,
    EventOut,
    InterventionOut,
    MessageOut,
    PlanOut,
    RecommendationOut,
    TrainingLogOut,
    WebhookOut,
    WebhookRegister,
)
from api.webhooks import (
    VALID_EVENTS,
    _webhooks,
    dispatch_event,
    list_webhooks,
    register_webhook,
    unregister_webhook,
)


# ── JWT / Auth Tests ──────────────────────────────────────────────────────


def test_create_access_token(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "30")
    token = create_access_token({"sub": "coach1", "user_id": 1, "role": "coach"})
    assert isinstance(token, str)
    payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
    assert payload["sub"] == "coach1"
    assert payload["user_id"] == 1
    assert payload["role"] == "coach"
    assert "exp" in payload


def test_get_current_user_valid_token(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "30")
    token = create_access_token({"sub": "coach1", "user_id": 1, "role": "coach", "athlete_id": None})
    user = get_current_user(token)
    assert isinstance(user, TokenData)
    assert user.username == "coach1"
    assert user.user_id == 1
    assert user.role == "coach"


def test_get_current_user_invalid_token():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_current_user("invalid-token")
    assert exc_info.value.status_code == 401


def test_require_coach_allows_coach():
    user = TokenData(user_id=1, username="coach1", role="coach")
    result = require_coach(user)
    assert result.role == "coach"


def test_require_coach_blocks_athlete():
    from fastapi import HTTPException
    user = TokenData(user_id=2, username="athlete1", role="client", athlete_id=10)
    with pytest.raises(HTTPException) as exc_info:
        require_coach(user)
    assert exc_info.value.status_code == 403


def test_require_athlete_allows_athlete():
    user = TokenData(user_id=2, username="athlete1", role="client", athlete_id=10)
    result = require_athlete(user)
    assert result.athlete_id == 10


def test_require_athlete_blocks_coach():
    from fastapi import HTTPException
    user = TokenData(user_id=1, username="coach1", role="coach")
    with pytest.raises(HTTPException) as exc_info:
        require_athlete(user)
    assert exc_info.value.status_code == 403


# ── Schema Tests ──────────────────────────────────────────────────────────


def test_athlete_out_schema():
    data = AthleteOut(id=1, first_name="Alice", last_name="Smith", email="a@b.com", status="active")
    assert data.id == 1
    assert data.first_name == "Alice"


def test_checkin_out_schema():
    data = CheckInOut(id=1, athlete_id=1, day=date.today(), sleep=4, energy=4, recovery=4, stress=2, training_today=True)
    assert data.sleep == 4


def test_training_log_out_schema():
    data = TrainingLogOut(id=1, athlete_id=1, date=date.today(), session_category="Easy Run", duration_min=45, distance_km=8.0, rpe=5, load_score=22.5)
    assert data.load_score == 22.5


def test_event_out_schema():
    data = EventOut(id=1, athlete_id=1, name="City Marathon", event_date=date(2026, 4, 1), distance="Marathon")
    assert data.distance == "Marathon"


def test_plan_out_schema():
    data = PlanOut(id=1, athlete_id=1, race_goal="10K", weeks=12, sessions_per_week=4, max_session_min=120, start_date=date.today(), status="active")
    assert data.weeks == 12


def test_intervention_out_schema():
    data = InterventionOut(
        id=1, athlete_id=1, action_type="contact_athlete", status="open",
        risk_score=0.6, confidence_score=0.8, expected_impact={"fatigue_delta": -0.2},
        why_factors=["low_adherence"], guardrail_pass=True, guardrail_reason="ok",
    )
    assert data.action_type == "contact_athlete"


def test_recommendation_out_schema():
    data = RecommendationOut(
        action="monitor", risk_score=0.2, confidence_score=0.75,
        expected_impact={"fatigue_delta": 0.0}, why=["stable"],
        guardrail_pass=True, guardrail_reason="ok",
    )
    assert data.action == "monitor"


def test_webhook_register_schema():
    data = WebhookRegister(url="https://example.com/hook", events=["checkin.created"])
    assert data.url == "https://example.com/hook"


def test_webhook_out_schema():
    data = WebhookOut(id="abc123", url="https://example.com/hook", events=["checkin.created"], active=True)
    assert data.active is True


def test_message_out_schema():
    data = MessageOut(message="OK")
    assert data.message == "OK"


# ── Webhook Registry Tests ───────────────────────────────────────────────


def test_register_webhook():
    _webhooks.clear()
    hook = register_webhook("https://example.com/hook", ["checkin.created"])
    assert hook["url"] == "https://example.com/hook"
    assert "checkin.created" in hook["events"]
    assert hook["active"] is True
    assert len(_webhooks) == 1


def test_register_webhook_invalid_event():
    _webhooks.clear()
    with pytest.raises(ValueError, match="Invalid events"):
        register_webhook("https://example.com", ["bogus.event"])


def test_unregister_webhook():
    _webhooks.clear()
    hook = register_webhook("https://example.com/hook", ["checkin.created"])
    assert unregister_webhook(hook["id"]) is True
    assert len(_webhooks) == 0


def test_unregister_missing_webhook():
    _webhooks.clear()
    assert unregister_webhook("nonexistent") is False


def test_list_webhooks():
    _webhooks.clear()
    register_webhook("https://a.com", ["checkin.created"])
    register_webhook("https://b.com", ["training_log.created"])
    hooks = list_webhooks()
    assert len(hooks) == 2


@pytest.mark.asyncio
async def test_dispatch_event_no_subscribers():
    _webhooks.clear()
    count = await dispatch_event("checkin.created", {"athlete_id": 1})
    assert count == 0


def test_valid_events_set():
    assert "checkin.created" in VALID_EVENTS
    assert "training_log.created" in VALID_EVENTS
    assert "intervention.created" in VALID_EVENTS
    assert "intervention.closed" in VALID_EVENTS
    assert "plan.published" in VALID_EVENTS
    assert "athlete.created" in VALID_EVENTS


# ── FastAPI App Tests (integration-light) ────────────────────────────────


def test_fastapi_app_creation():
    from api.main import create_app
    app = create_app()
    assert app.title == "Run Season Command API"
    assert app.version == "2.0.0"
    route_paths = [r.path for r in app.routes]
    assert "/api/v1/auth/token" in route_paths
    assert "/api/v1/athletes" in route_paths
    assert "/api/v1/checkins" in route_paths
    assert "/api/v1/training-logs" in route_paths
    assert "/api/v1/events" in route_paths
    assert "/api/v1/plans" in route_paths
    assert "/api/v1/interventions" in route_paths
    assert "/api/v1/webhooks" in route_paths


def test_openapi_schema_generated():
    from api.main import create_app
    app = create_app()
    schema = app.openapi()
    assert "paths" in schema
    assert "/api/v1/auth/token" in schema["paths"]
    assert "info" in schema
    assert schema["info"]["title"] == "Run Season Command API"
