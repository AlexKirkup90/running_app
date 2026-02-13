"""REST API routes for Run Season Command.

All endpoints are prefixed with /api/v1 and require JWT authentication
unless otherwise noted. Coach-only endpoints require role=coach.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from api.auth import (
    TokenData,
    TokenResponse,
    create_access_token,
    get_current_user,
    require_athlete,
    require_coach,
)
from api.schemas import (
    AthleteOut,
    CheckInOut,
    EventOut,
    InterventionOut,
    MessageOut,
    PlanDaySessionOut,
    PlanOut,
    PlanWeekOut,
    RecommendationOut,
    TrainingLogOut,
    WebhookOut,
    WebhookRegister,
)
from api.webhooks import dispatch_event, list_webhooks, register_webhook, unregister_webhook
from core.db import session_scope
from core.models import (
    Athlete,
    CheckIn,
    CoachIntervention,
    Event,
    Plan,
    PlanDaySession,
    PlanWeek,
    TrainingLog,
    User,
)
from core.security import hash_password
from core.services.command_center import collect_athlete_signals, compose_recommendation, sync_interventions_queue
from core.services.readiness import readiness_band, readiness_score
from core.validators import (
    CheckInInput,
    ClientCreateInput,
    EventCreateInput,
    InterventionDecisionInput,
    TrainingLogInput,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


# ── Auth ──────────────────────────────────────────────────────────────────

@router.post("/auth/token", response_model=TokenResponse, tags=["auth"])
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Authenticate and receive a JWT access token."""
    with session_scope() as s:
        user = s.execute(select(User).where(User.username == form_data.username)).scalar_one_or_none()
        if not user or not __import__("core.security", fromlist=["verify_password"]).verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_access_token({"sub": user.username, "user_id": user.id, "role": user.role, "athlete_id": user.athlete_id})
        return TokenResponse(access_token=token, role=user.role, user_id=user.id, athlete_id=user.athlete_id)


@router.get("/auth/me", response_model=TokenData, tags=["auth"])
def me(current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Return the current authenticated user's token data."""
    return current_user


# ── Athletes ──────────────────────────────────────────────────────────────

@router.get("/athletes", response_model=list[AthleteOut], tags=["athletes"])
def list_athletes(
    coach: Annotated[TokenData, Depends(require_coach)],
    status_filter: str = Query("active", alias="status"),
):
    """List athletes, optionally filtered by status. Coach-only."""
    with session_scope() as s:
        q = select(Athlete)
        if status_filter != "all":
            q = q.where(Athlete.status == status_filter)
        rows = s.execute(q.order_by(Athlete.first_name, Athlete.last_name)).scalars().all()
        return [AthleteOut.model_validate(r) for r in rows]


@router.get("/athletes/{athlete_id}", response_model=AthleteOut, tags=["athletes"])
def get_athlete(athlete_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Get a single athlete by ID."""
    if current_user.role == "client" and current_user.athlete_id != athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    with session_scope() as s:
        athlete = s.get(Athlete, athlete_id)
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")
        return AthleteOut.model_validate(athlete)


@router.post("/athletes", response_model=AthleteOut, status_code=201, tags=["athletes"])
async def create_athlete(body: ClientCreateInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Create a new athlete and linked user account. Coach-only."""
    with session_scope() as s:
        existing = s.execute(select(Athlete).where(Athlete.email == body.email)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")
        ath = Athlete(first_name=body.first_name, last_name=body.last_name, email=body.email, dob=body.dob)
        s.add(ath)
        s.flush()
        base = f"{body.first_name}{body.last_name}".lower().replace(" ", "")
        username = base
        i = 1
        while s.execute(select(User).where(User.username == username)).scalar_one_or_none():
            i += 1
            username = f"{base}{i}"
        user = User(username=username, role="client", athlete_id=ath.id, password_hash=hash_password("TempPass!234"), must_change_password=True)
        s.add(user)
        s.flush()
        result = AthleteOut.model_validate(ath)
    await dispatch_event("athlete.created", {"athlete_id": result.id, "email": body.email})
    return result


# ── Check-ins ─────────────────────────────────────────────────────────────

@router.post("/checkins", response_model=CheckInOut, status_code=201, tags=["checkins"])
async def create_checkin(body: CheckInInput, athlete: Annotated[TokenData, Depends(require_athlete)]):
    """Submit a daily check-in. Athlete-only. Upserts for today."""
    today = date.today()
    with session_scope() as s:
        existing = s.execute(select(CheckIn).where(CheckIn.athlete_id == athlete.athlete_id, CheckIn.day == today)).scalar_one_or_none()
        if existing:
            existing.sleep = body.sleep
            existing.energy = body.energy
            existing.recovery = body.recovery
            existing.stress = body.stress
            existing.training_today = body.training_today
            s.flush()
            obj = existing
        else:
            obj = CheckIn(athlete_id=athlete.athlete_id, day=today, sleep=body.sleep, energy=body.energy, recovery=body.recovery, stress=body.stress, training_today=body.training_today)
            s.add(obj)
            s.flush()
        score = readiness_score(obj.sleep, obj.energy, obj.recovery, obj.stress)
        result = CheckInOut.model_validate(obj)
        result.readiness_score = score
        result.readiness_band = readiness_band(score)
    await dispatch_event("checkin.created", {"athlete_id": athlete.athlete_id, "day": str(today), "readiness": score})
    return result


@router.get("/checkins", response_model=list[CheckInOut], tags=["checkins"])
def list_checkins(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    athlete_id: int | None = None,
    limit: int = Query(30, le=200),
):
    """List check-ins. Athletes see their own; coaches can query by athlete_id."""
    target_id = _resolve_athlete_id(current_user, athlete_id)
    with session_scope() as s:
        rows = s.execute(
            select(CheckIn).where(CheckIn.athlete_id == target_id).order_by(CheckIn.day.desc()).limit(limit)
        ).scalars().all()
        results = []
        for r in rows:
            out = CheckInOut.model_validate(r)
            score = readiness_score(r.sleep, r.energy, r.recovery, r.stress)
            out.readiness_score = score
            out.readiness_band = readiness_band(score)
            results.append(out)
        return results


# ── Training Logs ─────────────────────────────────────────────────────────

@router.post("/training-logs", response_model=TrainingLogOut, status_code=201, tags=["training-logs"])
async def create_training_log(body: TrainingLogInput, athlete: Annotated[TokenData, Depends(require_athlete)]):
    """Log a training session. Athlete-only. Upserts for today."""
    today = date.today()
    load = float(body.duration_min) * (body.rpe / 10)
    with session_scope() as s:
        existing = s.execute(select(TrainingLog).where(TrainingLog.athlete_id == athlete.athlete_id, TrainingLog.date == today)).scalar_one_or_none()
        if existing:
            existing.session_category = body.session_category
            existing.duration_min = body.duration_min
            existing.distance_km = body.distance_km
            existing.avg_hr = body.avg_hr
            existing.max_hr = body.max_hr
            existing.avg_pace_sec_per_km = body.avg_pace_sec_per_km
            existing.rpe = body.rpe
            existing.load_score = load
            existing.notes = body.notes
            existing.pain_flag = body.pain_flag
            s.flush()
            obj = existing
        else:
            obj = TrainingLog(
                athlete_id=athlete.athlete_id, date=today, session_category=body.session_category,
                duration_min=body.duration_min, distance_km=body.distance_km, avg_hr=body.avg_hr,
                max_hr=body.max_hr, avg_pace_sec_per_km=body.avg_pace_sec_per_km, rpe=body.rpe,
                load_score=load, notes=body.notes, pain_flag=body.pain_flag,
            )
            s.add(obj)
            s.flush()
        result = TrainingLogOut.model_validate(obj)
    await dispatch_event("training_log.created", {"athlete_id": athlete.athlete_id, "date": str(today), "rpe": body.rpe, "pain": body.pain_flag})
    return result


@router.get("/training-logs", response_model=list[TrainingLogOut], tags=["training-logs"])
def list_training_logs(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    athlete_id: int | None = None,
    limit: int = Query(30, le=200),
):
    """List training logs. Athletes see their own; coaches can query by athlete_id."""
    target_id = _resolve_athlete_id(current_user, athlete_id)
    with session_scope() as s:
        rows = s.execute(
            select(TrainingLog).where(TrainingLog.athlete_id == target_id).order_by(TrainingLog.date.desc()).limit(limit)
        ).scalars().all()
        return [TrainingLogOut.model_validate(r) for r in rows]


# ── Events ────────────────────────────────────────────────────────────────

@router.post("/events", response_model=EventOut, status_code=201, tags=["events"])
def create_event(body: EventCreateInput, athlete: Annotated[TokenData, Depends(require_athlete)]):
    """Create a race event. Athlete-only."""
    with session_scope() as s:
        obj = Event(athlete_id=athlete.athlete_id, name=body.name, event_date=body.event_date, distance=body.distance)
        s.add(obj)
        s.flush()
        return EventOut.model_validate(obj)


@router.get("/events", response_model=list[EventOut], tags=["events"])
def list_events(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    athlete_id: int | None = None,
):
    """List events. Athletes see their own; coaches can query by athlete_id."""
    target_id = _resolve_athlete_id(current_user, athlete_id)
    with session_scope() as s:
        rows = s.execute(
            select(Event).where(Event.athlete_id == target_id).order_by(Event.event_date.asc())
        ).scalars().all()
        return [EventOut.model_validate(r) for r in rows]


# ── Plans ─────────────────────────────────────────────────────────────────

@router.get("/plans", response_model=list[PlanOut], tags=["plans"])
def list_plans(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    athlete_id: int | None = None,
    status_filter: str = Query("active", alias="status"),
):
    """List training plans. Athletes see their own; coaches see all."""
    with session_scope() as s:
        q = select(Plan)
        if current_user.role == "client":
            q = q.where(Plan.athlete_id == current_user.athlete_id)
        elif athlete_id:
            q = q.where(Plan.athlete_id == athlete_id)
        if status_filter != "all":
            q = q.where(Plan.status == status_filter)
        rows = s.execute(q.order_by(Plan.id.desc())).scalars().all()
        return [PlanOut.model_validate(r) for r in rows]


@router.get("/plans/{plan_id}/weeks", response_model=list[PlanWeekOut], tags=["plans"])
def get_plan_weeks(plan_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Get all weeks for a plan."""
    with session_scope() as s:
        plan = s.get(Plan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if current_user.role == "client" and current_user.athlete_id != plan.athlete_id:
            raise HTTPException(status_code=403, detail="Access denied")
        rows = s.execute(select(PlanWeek).where(PlanWeek.plan_id == plan_id).order_by(PlanWeek.week_number)).scalars().all()
        return [PlanWeekOut.model_validate(r) for r in rows]


@router.get("/plans/{plan_id}/sessions", response_model=list[PlanDaySessionOut], tags=["plans"])
def get_plan_sessions(plan_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Get all day sessions for a plan."""
    with session_scope() as s:
        plan = s.get(Plan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if current_user.role == "client" and current_user.athlete_id != plan.athlete_id:
            raise HTTPException(status_code=403, detail="Access denied")
        week_ids = [w.id for w in s.execute(select(PlanWeek).where(PlanWeek.plan_id == plan_id)).scalars().all()]
        if not week_ids:
            return []
        rows = s.execute(
            select(PlanDaySession).where(PlanDaySession.plan_week_id.in_(week_ids)).order_by(PlanDaySession.session_day)
        ).scalars().all()
        return [PlanDaySessionOut.model_validate(r) for r in rows]


# ── Interventions ─────────────────────────────────────────────────────────

@router.get("/interventions", response_model=list[InterventionOut], tags=["interventions"])
def list_interventions(
    coach: Annotated[TokenData, Depends(require_coach)],
    status_filter: str = Query("open", alias="status"),
    athlete_id: int | None = None,
):
    """List interventions. Coach-only."""
    with session_scope() as s:
        q = select(CoachIntervention)
        if status_filter != "all":
            q = q.where(CoachIntervention.status == status_filter)
        if athlete_id:
            q = q.where(CoachIntervention.athlete_id == athlete_id)
        rows = s.execute(q.order_by(CoachIntervention.risk_score.desc())).scalars().all()
        return [InterventionOut.model_validate(r) for r in rows]


@router.post("/interventions/sync", response_model=MessageOut, tags=["interventions"])
def sync_interventions(coach: Annotated[TokenData, Depends(require_coach)]):
    """Refresh the intervention queue across all athletes. Coach-only."""
    result = sync_interventions_queue()
    return MessageOut(message=f"Sync complete: +{result['created']} created, {result['updated']} updated, {result['closed']} closed")


@router.post("/interventions/{intervention_id}/decide", response_model=MessageOut, tags=["interventions"])
def decide_intervention(intervention_id: int, body: InterventionDecisionInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Apply a decision to an intervention. Coach-only."""
    with session_scope() as s:
        rec = s.get(CoachIntervention, intervention_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Intervention not found")
        if rec.status != "open":
            raise HTTPException(status_code=400, detail="Intervention is not open")
        from pages.coach import _apply_intervention_decision
        _apply_intervention_decision(s, rec, body.decision, body.note, body.modified_action, coach.user_id)
    return MessageOut(message=f"Intervention {intervention_id}: {body.decision} applied")


# ── Recommendations ───────────────────────────────────────────────────────

@router.get("/athletes/{athlete_id}/recommendation", response_model=RecommendationOut, tags=["recommendations"])
def get_recommendation(athlete_id: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """Generate a live recommendation for an athlete. Coach-only."""
    with session_scope() as s:
        athlete = s.get(Athlete, athlete_id)
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")
        signals = collect_athlete_signals(s, athlete_id, date.today())
        rec = compose_recommendation(signals)
        return RecommendationOut(
            action=rec.action, risk_score=rec.risk_score, confidence_score=rec.confidence_score,
            expected_impact=rec.expected_impact, why=rec.why,
            guardrail_pass=rec.guardrail_pass, guardrail_reason=rec.guardrail_reason,
        )


# ── Webhooks ──────────────────────────────────────────────────────────────

@router.post("/webhooks", response_model=WebhookOut, status_code=201, tags=["webhooks"])
def create_webhook(body: WebhookRegister, coach: Annotated[TokenData, Depends(require_coach)]):
    """Register a webhook endpoint. Coach-only."""
    try:
        hook = register_webhook(body.url, body.events, body.secret)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return WebhookOut(id=hook["id"], url=hook["url"], events=hook["events"], active=hook["active"])


@router.get("/webhooks", response_model=list[WebhookOut], tags=["webhooks"])
def get_webhooks(coach: Annotated[TokenData, Depends(require_coach)]):
    """List all registered webhooks. Coach-only."""
    return [WebhookOut(id=h["id"], url=h["url"], events=h["events"], active=h["active"]) for h in list_webhooks()]


@router.delete("/webhooks/{hook_id}", response_model=MessageOut, tags=["webhooks"])
def delete_webhook(hook_id: str, coach: Annotated[TokenData, Depends(require_coach)]):
    """Delete a webhook. Coach-only."""
    if not unregister_webhook(hook_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
    return MessageOut(message="Webhook deleted")


# ── Community ─────────────────────────────────────────────────────────────

@router.get("/groups", tags=["community"])
def list_groups(current_user: Annotated[TokenData, Depends(get_current_user)]):
    """List training groups. Athletes see their groups; coaches see all."""
    from core.models import GroupMembership, TrainingGroup
    with session_scope() as s:
        if current_user.role == "client":
            rows = s.execute(
                select(TrainingGroup)
                .join(GroupMembership, GroupMembership.group_id == TrainingGroup.id)
                .where(GroupMembership.athlete_id == current_user.athlete_id)
            ).scalars().all()
        else:
            rows = s.execute(select(TrainingGroup).order_by(TrainingGroup.name)).scalars().all()
        return [
            {"id": g.id, "name": g.name, "description": g.description,
             "privacy": g.privacy, "max_members": g.max_members}
            for g in rows
        ]


@router.get("/challenges", tags=["community"])
def list_challenges(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    status_filter: str = Query("active", alias="status"),
):
    """List challenges. Active by default."""
    from core.models import Challenge
    with session_scope() as s:
        q = select(Challenge)
        if status_filter != "all":
            q = q.where(Challenge.status == status_filter)
        rows = s.execute(q.order_by(Challenge.end_date)).scalars().all()
        return [
            {"id": c.id, "name": c.name, "challenge_type": c.challenge_type,
             "target_value": c.target_value, "start_date": str(c.start_date),
             "end_date": str(c.end_date), "status": c.status}
            for c in rows
        ]


# ── Wearable Connections ──────────────────────────────────────────────────

@router.get("/wearables/connections", tags=["wearables"])
def list_wearable_connections(current_user: Annotated[TokenData, Depends(get_current_user)]):
    """List wearable connections. Athletes see their own; coaches see all."""
    from core.models import WearableConnection
    with session_scope() as s:
        q = select(WearableConnection)
        if current_user.role == "client":
            q = q.where(WearableConnection.athlete_id == current_user.athlete_id)
        rows = s.execute(q.order_by(WearableConnection.id)).scalars().all()
        return [
            {
                "id": r.id, "athlete_id": r.athlete_id, "service": r.service,
                "sync_status": r.sync_status, "last_sync_at": str(r.last_sync_at) if r.last_sync_at else None,
                "external_athlete_id": r.external_athlete_id,
            }
            for r in rows
        ]


@router.delete("/wearables/connections/{connection_id}", response_model=MessageOut, tags=["wearables"])
def delete_wearable_connection(connection_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Disconnect a wearable service."""
    from core.models import WearableConnection
    with session_scope() as s:
        conn = s.get(WearableConnection, connection_id)
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")
        if current_user.role == "client" and conn.athlete_id != current_user.athlete_id:
            raise HTTPException(status_code=403, detail="Access denied")
        s.delete(conn)
    return MessageOut(message="Connection removed")


@router.get("/wearables/sync-logs", tags=["wearables"])
def list_sync_logs(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    athlete_id: int | None = None,
    limit: int = Query(20, le=100),
):
    """List sync logs. Athletes see their own; coaches can filter by athlete_id."""
    from core.models import SyncLog
    target_id = _resolve_athlete_id(current_user, athlete_id)
    with session_scope() as s:
        rows = s.execute(
            select(SyncLog).where(SyncLog.athlete_id == target_id).order_by(SyncLog.id.desc()).limit(limit)
        ).scalars().all()
        return [
            {
                "id": r.id, "service": r.service, "sync_type": r.sync_type,
                "status": r.status, "activities_found": r.activities_found,
                "activities_imported": r.activities_imported, "activities_skipped": r.activities_skipped,
                "started_at": str(r.started_at) if r.started_at else None,
            }
            for r in rows
        ]


# ── Helpers ───────────────────────────────────────────────────────────────

def _resolve_athlete_id(current_user: TokenData, requested_id: int | None) -> int:
    """Resolve the target athlete ID based on role and request."""
    if current_user.role == "client":
        return current_user.athlete_id
    if requested_id:
        return requested_id
    raise HTTPException(status_code=400, detail="athlete_id query parameter required for coaches")
