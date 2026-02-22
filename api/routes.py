from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select

from api.auth import (
    TokenData,
    TokenResponse,
    create_access_token,
    get_current_user,
    require_athlete,
    require_coach,
)
from api.rate_limit import enforce_rate_limit
from api.realtime import manager
from api.schemas import (
    AthleteOut,
    CheckInOut,
    EventOut,
    InterventionOut,
    MessageOut,
    PaginatedResponse,
    PlanDaySessionOut,
    PlanOut,
    PlanWeekOut,
    RecommendationOut,
    TrainingLogOut,
    WebhookOut,
    WebhookRegister,
)
from api.webhooks import dispatch_event, list_webhooks, register_webhook, unregister_webhook
from core.config import get_settings
from core.db import session_scope
from core.models import Athlete, CheckIn, CoachIntervention, Event, Plan, PlanWeek, PlanDaySession, TrainingLog, User
from core.security import hash_password
from core.services.command_center import collect_athlete_signals, compose_recommendation, sync_interventions_queue
from core.services.intervention_actions import apply_intervention_decision
from core.services.readiness import readiness_band, readiness_score
from core.validators import CheckInInput, ClientCreateInput, EventCreateInput, InterventionDecisionInput, TrainingLogInput

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1")


@router.post("/auth/token", response_model=TokenResponse, tags=["auth"])
def login(request: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    enforce_rate_limit(request, key="auth_token", max_requests=5, window_seconds=60)
    with session_scope() as s:
        user = s.execute(select(User).where(User.username == form_data.username)).scalar_one_or_none()
        if not user or not __import__("core.security", fromlist=["verify_password"]).verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_access_token({"sub": user.username, "user_id": user.id, "role": user.role, "athlete_id": user.athlete_id})
        return TokenResponse(access_token=token, role=user.role, user_id=user.id, athlete_id=user.athlete_id)


@router.get("/auth/me", response_model=TokenData, tags=["auth"])
def me(current_user: Annotated[TokenData, Depends(get_current_user)]):
    return current_user


@router.websocket("/ws/coach")
async def coach_ws(websocket: WebSocket):
    await manager.connect("coach", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("coach", websocket)


@router.get("/athletes", response_model=PaginatedResponse[AthleteOut], tags=["athletes"])
def list_athletes(
    coach: Annotated[TokenData, Depends(require_coach)],
    status_filter: str = Query("active", alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
):
    with session_scope() as s:
        q = select(Athlete)
        c = select(func.count()).select_from(Athlete)
        if status_filter != "all":
            q = q.where(Athlete.status == status_filter)
            c = c.where(Athlete.status == status_filter)
        rows = s.execute(q.order_by(Athlete.first_name, Athlete.last_name).offset(offset).limit(limit)).scalars().all()
        total = s.execute(c).scalar_one()
        return PaginatedResponse[AthleteOut](items=[AthleteOut.model_validate(r) for r in rows], total=total, offset=offset, limit=limit)


@router.get("/athletes/{athlete_id}", response_model=AthleteOut, tags=["athletes"])
def get_athlete(athlete_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    if current_user.role == "client" and current_user.athlete_id != athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    with session_scope() as s:
        athlete = s.get(Athlete, athlete_id)
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")
        return AthleteOut.model_validate(athlete)


@router.post("/athletes", response_model=AthleteOut, status_code=201, tags=["athletes"])
async def create_athlete(body: ClientCreateInput, coach: Annotated[TokenData, Depends(require_coach)]):
    with session_scope() as s:
        existing = s.execute(select(Athlete).where(Athlete.email == body.email)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")
        ath = Athlete(first_name=body.first_name, last_name=body.last_name, email=body.email, dob=body.dob)
        s.add(ath)
        s.flush()
        base_username = f"{body.first_name.lower()}.{body.last_name.lower()}"
        username = base_username
        suffix = 1
        while s.execute(select(User).where(User.username == username)).scalar_one_or_none():
            suffix += 1
            username = f"{base_username}{suffix}"
        user = User(username=username, password_hash=hash_password(body.temp_password), role="client", athlete_id=ath.id)
        s.add(user)
        s.flush()
        result = AthleteOut.model_validate(ath)
    await dispatch_event("athlete.created", {"athlete_id": result.id, "email": result.email})
    return result


@router.post("/checkins", response_model=CheckInOut, status_code=201, tags=["checkins"])
async def create_checkin(body: CheckInInput, athlete: Annotated[TokenData, Depends(require_athlete)]):
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
    payload = {"athlete_id": athlete.athlete_id, "day": str(today), "readiness": score}
    await dispatch_event("checkin.created", payload)
    await manager.broadcast("coach", "checkin.created", payload)
    return result


@router.get("/checkins", response_model=PaginatedResponse[CheckInOut], tags=["checkins"])
def list_checkins(current_user: Annotated[TokenData, Depends(get_current_user)], athlete_id: int | None = None, offset: int = Query(0, ge=0), limit: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size)):
    target_id = _resolve_athlete_id(current_user, athlete_id)
    with session_scope() as s:
        rows = s.execute(select(CheckIn).where(CheckIn.athlete_id == target_id).order_by(CheckIn.day.desc()).offset(offset).limit(limit)).scalars().all()
        total = s.execute(select(func.count()).select_from(CheckIn).where(CheckIn.athlete_id == target_id)).scalar_one()
        items: list[CheckInOut] = []
        for r in rows:
            out = CheckInOut.model_validate(r)
            score = readiness_score(r.sleep, r.energy, r.recovery, r.stress)
            out.readiness_score = score
            out.readiness_band = readiness_band(score)
            items.append(out)
        return PaginatedResponse[CheckInOut](items=items, total=total, offset=offset, limit=limit)


@router.post("/training-logs", response_model=TrainingLogOut, status_code=201, tags=["training-logs"])
async def create_training_log(body: TrainingLogInput, athlete: Annotated[TokenData, Depends(require_athlete)]):
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
            obj = TrainingLog(athlete_id=athlete.athlete_id, date=today, session_category=body.session_category, duration_min=body.duration_min, distance_km=body.distance_km, avg_hr=body.avg_hr, max_hr=body.max_hr, avg_pace_sec_per_km=body.avg_pace_sec_per_km, rpe=body.rpe, load_score=load, notes=body.notes, pain_flag=body.pain_flag)
            s.add(obj)
            s.flush()
        result = TrainingLogOut.model_validate(obj)
    payload = {"athlete_id": athlete.athlete_id, "date": str(today), "rpe": body.rpe, "pain": body.pain_flag}
    await dispatch_event("training_log.created", payload)
    await manager.broadcast("coach", "training_log.created", payload)
    return result


@router.get("/training-logs", response_model=PaginatedResponse[TrainingLogOut], tags=["training-logs"])
def list_training_logs(current_user: Annotated[TokenData, Depends(get_current_user)], athlete_id: int | None = None, offset: int = Query(0, ge=0), limit: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size)):
    target_id = _resolve_athlete_id(current_user, athlete_id)
    with session_scope() as s:
        rows = s.execute(select(TrainingLog).where(TrainingLog.athlete_id == target_id).order_by(TrainingLog.date.desc()).offset(offset).limit(limit)).scalars().all()
        total = s.execute(select(func.count()).select_from(TrainingLog).where(TrainingLog.athlete_id == target_id)).scalar_one()
        return PaginatedResponse[TrainingLogOut](items=[TrainingLogOut.model_validate(r) for r in rows], total=total, offset=offset, limit=limit)


@router.post("/events", response_model=EventOut, status_code=201, tags=["events"])
def create_event(body: EventCreateInput, athlete: Annotated[TokenData, Depends(require_athlete)]):
    with session_scope() as s:
        obj = Event(athlete_id=athlete.athlete_id, name=body.name, event_date=body.event_date, distance=body.distance)
        s.add(obj)
        s.flush()
        return EventOut.model_validate(obj)


@router.get("/events", response_model=list[EventOut], tags=["events"])
def list_events(current_user: Annotated[TokenData, Depends(get_current_user)], athlete_id: int | None = None):
    target_id = _resolve_athlete_id(current_user, athlete_id)
    with session_scope() as s:
        rows = s.execute(select(Event).where(Event.athlete_id == target_id).order_by(Event.event_date.asc())).scalars().all()
        return [EventOut.model_validate(r) for r in rows]


@router.get("/plans", response_model=list[PlanOut], tags=["plans"])
def list_plans(current_user: Annotated[TokenData, Depends(get_current_user)], athlete_id: int | None = None, status_filter: str = Query("active", alias="status")):
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
    with session_scope() as s:
        plan = s.get(Plan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if current_user.role == "client" and current_user.athlete_id != plan.athlete_id:
            raise HTTPException(status_code=403, detail="Access denied")
        week_ids = [w.id for w in s.execute(select(PlanWeek).where(PlanWeek.plan_id == plan_id)).scalars().all()]
        if not week_ids:
            return []
        rows = s.execute(select(PlanDaySession).where(PlanDaySession.plan_week_id.in_(week_ids)).order_by(PlanDaySession.session_day)).scalars().all()
        return [PlanDaySessionOut.model_validate(r) for r in rows]


@router.get("/interventions", response_model=list[InterventionOut], tags=["interventions"])
def list_interventions(coach: Annotated[TokenData, Depends(require_coach)], status_filter: str = Query("open", alias="status"), athlete_id: int | None = None):
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
    result = sync_interventions_queue()
    return MessageOut(message=f"Sync complete: +{result['created']} created, {result['updated']} updated, {result['closed']} closed")


@router.post("/interventions/{intervention_id}/decide", response_model=MessageOut, tags=["interventions"])
def decide_intervention(intervention_id: int, body: InterventionDecisionInput, coach: Annotated[TokenData, Depends(require_coach)]):
    with session_scope() as s:
        rec = s.get(CoachIntervention, intervention_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Intervention not found")
        if rec.status != "open":
            raise HTTPException(status_code=400, detail="Intervention is not open")
        apply_intervention_decision(s, rec, body.decision, body.note, body.modified_action, coach.user_id)
    return MessageOut(message=f"Intervention {intervention_id}: {body.decision} applied")


@router.get("/athletes/{athlete_id}/recommendation", response_model=RecommendationOut, tags=["recommendations"])
def get_recommendation(athlete_id: int, coach: Annotated[TokenData, Depends(require_coach)]):
    with session_scope() as s:
        athlete = s.get(Athlete, athlete_id)
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")
        signals = collect_athlete_signals(s, athlete_id, date.today())
        rec = compose_recommendation(signals)
        return RecommendationOut(action=rec.action, risk_score=rec.risk_score, confidence_score=rec.confidence_score, expected_impact=rec.expected_impact, why=rec.why, guardrail_pass=rec.guardrail_pass, guardrail_reason=rec.guardrail_reason)


@router.post("/webhooks", response_model=WebhookOut, status_code=201, tags=["webhooks"])
def create_webhook(body: WebhookRegister, coach: Annotated[TokenData, Depends(require_coach)]):
    try:
        hook = register_webhook(body.url, body.events, body.secret)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return WebhookOut(id=hook["id"], url=hook["url"], events=hook["events"], active=hook["active"])


@router.get("/webhooks", response_model=list[WebhookOut], tags=["webhooks"])
def get_webhooks(coach: Annotated[TokenData, Depends(require_coach)]):
    return [WebhookOut(id=h["id"], url=h["url"], events=h["events"], active=h["active"]) for h in list_webhooks()]


@router.delete("/webhooks/{hook_id}", response_model=MessageOut, tags=["webhooks"])
def delete_webhook(hook_id: str, coach: Annotated[TokenData, Depends(require_coach)]):
    if not unregister_webhook(hook_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
    return MessageOut(message="Webhook deleted")


def _resolve_athlete_id(current_user: TokenData, requested_id: int | None) -> int:
    if current_user.role == "client":
        return current_user.athlete_id
    if requested_id:
        return requested_id
    raise HTTPException(status_code=400, detail="athlete_id query parameter required for coaches")
