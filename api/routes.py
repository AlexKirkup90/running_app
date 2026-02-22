"""REST API routes for Run Season Command.

All endpoints are prefixed with /api/v1 and require JWT authentication
unless otherwise noted. Coach-only endpoints require role=coach.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Annotated, Optional

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
    AssignAthleteInput,
    AthleteOut,
    AthleteProfileOut,
    BatchDecisionInput,
    ChallengeCreateInput,
    ChallengeEntryOut,
    ChallengeOut,
    ChangePasswordInput,
    CheckInOut,
    CoachClientRow,
    CoachDashboardOut,
    CoachNoteCreateInput,
    CoachNoteOut,
    CreateOrgInput,
    EventOut,
    FitnessFatigueOut,
    GroupMemberOut,
    GroupMessageCreateInput,
    GroupMessageOut,
    InterventionOut,
    InterventionStatsOut,
    KudosOut,
    LeaderboardEntryOut,
    MessageOut,
    PlanCreateOut,
    PlanDaySessionOut,
    PlanOut,
    PlanPreviewDay,
    PlanPreviewOut,
    PlanPreviewWeek,
    PlanWeekOut,
    RacePredictionOut,
    RecommendationOut,
    SessionBriefingOut,
    SessionLibraryCreateInput,
    SessionLibraryOut,
    TimelineEntry,
    TrainingGroupCreateInput,
    TrainingGroupOut,
    TrainingLoadSummaryOut,
    TrainingLogOut,
    TransferAthleteInput,
    VdotHistoryOut,
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
from core.security import hash_password, validate_password_policy, verify_password
from core.services.command_center import collect_athlete_signals, compose_recommendation, sync_interventions_queue
from core.services.readiness import readiness_band, readiness_score
from core.validators import (
    CheckInInput,
    ClientCreateInput,
    EventCreateInput,
    InterventionDecisionInput,
    PlanCreateInput,
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


@router.post("/auth/change-password", response_model=MessageOut, tags=["auth"])
def change_password(body: ChangePasswordInput, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Change the current user's password."""
    valid, msg = validate_password_policy(body.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)
    with session_scope() as s:
        user = s.get(User, current_user.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not verify_password(body.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.password_hash = hash_password(body.new_password)
        user.must_change_password = False
    return MessageOut(message="Password changed successfully")


# ── Coach Dashboard ──────────────────────────────────────────────────────

@router.get("/coach/dashboard", response_model=CoachDashboardOut, tags=["coach"])
def coach_dashboard(coach: Annotated[TokenData, Depends(require_coach)]):
    """Aggregated coach dashboard: athlete counts, interventions, weekly load."""
    from sqlalchemy import func
    with session_scope() as s:
        total = s.execute(select(func.count(Athlete.id))).scalar() or 0
        active = s.execute(select(func.count(Athlete.id)).where(Athlete.status == "active")).scalar() or 0
        open_intv = s.execute(
            select(func.count(CoachIntervention.id)).where(CoachIntervention.status == "open")
        ).scalar() or 0
        high_risk = s.execute(
            select(func.count(CoachIntervention.id)).where(
                CoachIntervention.status == "open", CoachIntervention.risk_score >= 0.7
            )
        ).scalar() or 0

        # Weekly load for last 8 weeks
        from core.services.analytics import weekly_summary
        import pandas as pd
        cutoff = date.today() - timedelta(weeks=8)
        logs = s.execute(
            select(TrainingLog).where(TrainingLog.date >= cutoff)
        ).scalars().all()
        if logs:
            logs_df = pd.DataFrame([{
                "id": row.id, "date": row.date, "duration_min": row.duration_min, "load_score": row.load_score,
            } for row in logs])
            ws = weekly_summary(logs_df)
            weekly_load = ws.to_dict("records")
        else:
            weekly_load = []

        return CoachDashboardOut(
            total_athletes=total,
            active_athletes=active,
            open_interventions=open_intv,
            high_risk_count=high_risk,
            weekly_load=weekly_load,
        )


@router.get("/coach/clients", response_model=list[CoachClientRow], tags=["coach"])
def coach_clients(coach: Annotated[TokenData, Depends(require_coach)]):
    """List all athletes with intervention counts and latest activity dates."""
    from sqlalchemy import func
    with session_scope() as s:
        athletes = s.execute(
            select(Athlete).where(Athlete.status == "active").order_by(Athlete.first_name, Athlete.last_name)
        ).scalars().all()
        results = []
        for ath in athletes:
            open_count = s.execute(
                select(func.count(CoachIntervention.id)).where(
                    CoachIntervention.athlete_id == ath.id, CoachIntervention.status == "open"
                )
            ).scalar() or 0
            max_risk = s.execute(
                select(func.max(CoachIntervention.risk_score)).where(
                    CoachIntervention.athlete_id == ath.id, CoachIntervention.status == "open"
                )
            ).scalar()
            from core.services.command_center import risk_priority
            risk_label = risk_priority(max_risk) if max_risk is not None else "stable"
            last_ci = s.execute(
                select(func.max(CheckIn.day)).where(CheckIn.athlete_id == ath.id)
            ).scalar()
            last_log = s.execute(
                select(func.max(TrainingLog.date)).where(TrainingLog.athlete_id == ath.id)
            ).scalar()
            results.append(CoachClientRow(
                athlete_id=ath.id,
                first_name=ath.first_name,
                last_name=ath.last_name,
                email=ath.email,
                status=ath.status,
                open_interventions=open_count,
                risk_label=risk_label,
                last_checkin=last_ci,
                last_log=last_log,
            ))
        return results


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
    athlete_id: Optional[int] = None,
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
    athlete_id: Optional[int] = None,
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
    athlete_id: Optional[int] = None,
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
    athlete_id: Optional[int] = None,
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
    athlete_id: Optional[int] = None,
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


# ── Organizations (Phase 6) ───────────────────────────────────────────────

@router.get("/organizations", tags=["organizations"])
def list_organizations(coach: Annotated[TokenData, Depends(require_coach)]):
    """List organizations the coach belongs to, with member counts."""
    from sqlalchemy import func
    from core.models import CoachAssignment, OrgMembership, Organization
    with session_scope() as s:
        rows = s.execute(
            select(Organization, OrgMembership.org_role)
            .join(OrgMembership, OrgMembership.org_id == Organization.id)
            .where(OrgMembership.user_id == coach.user_id)
        ).all()
        result = []
        for org, role in rows:
            coach_count = s.execute(
                select(func.count()).select_from(OrgMembership).where(OrgMembership.org_id == org.id)
            ).scalar() or 0
            athlete_count = s.execute(
                select(func.count()).select_from(CoachAssignment)
                .where(CoachAssignment.org_id == org.id, CoachAssignment.status == "active")
            ).scalar() or 0
            result.append({
                "id": org.id, "name": org.name, "slug": org.slug,
                "tier": org.tier, "role": role,
                "max_coaches": org.max_coaches, "max_athletes": org.max_athletes,
                "coach_count": coach_count, "athlete_count": athlete_count,
            })
        return result


@router.post("/organizations", tags=["organizations"], status_code=201)
def create_organization(
    body: "CreateOrgInput",
    coach: Annotated[TokenData, Depends(require_coach)],
):
    """Create a new organization. The creator becomes owner."""
    from api.schemas import CreateOrgInput as _CI  # noqa: F811
    from core.models import OrgMembership, Organization
    with session_scope() as s:
        org = Organization(name=body.name, slug=body.slug, tier=body.tier)
        s.add(org)
        s.flush()
        s.add(OrgMembership(org_id=org.id, user_id=coach.user_id, org_role="owner", caseload_cap=30))
        s.flush()
        return {"id": org.id, "name": org.name, "slug": org.slug, "tier": org.tier}


@router.get("/organizations/{org_id}/coaches", tags=["organizations"])
def list_org_coaches(org_id: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """List coaches in an organization with assigned athlete counts."""
    from sqlalchemy import func
    from core.models import CoachAssignment, OrgMembership
    with session_scope() as s:
        rows = s.execute(
            select(OrgMembership.user_id, OrgMembership.org_role, OrgMembership.caseload_cap,
                   User.username)
            .join(User, User.id == OrgMembership.user_id)
            .where(OrgMembership.org_id == org_id)
        ).all()
        result = []
        for uid, role, cap, uname in rows:
            assigned = s.execute(
                select(func.count()).select_from(CoachAssignment)
                .where(CoachAssignment.org_id == org_id,
                       CoachAssignment.coach_user_id == uid,
                       CoachAssignment.status == "active")
            ).scalar() or 0
            result.append({
                "user_id": uid, "username": uname, "role": role,
                "caseload_cap": cap, "assigned_athletes": assigned,
            })
        return result


@router.get("/organizations/{org_id}/assignments", tags=["organizations"])
def list_org_assignments(org_id: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """List athlete-coach assignments in an organization."""
    from core.models import CoachAssignment
    with session_scope() as s:
        rows = s.execute(
            select(CoachAssignment.id, CoachAssignment.coach_user_id,
                   CoachAssignment.athlete_id, CoachAssignment.status,
                   Athlete.first_name, Athlete.last_name, User.username)
            .join(Athlete, Athlete.id == CoachAssignment.athlete_id)
            .join(User, User.id == CoachAssignment.coach_user_id)
            .where(CoachAssignment.org_id == org_id)
        ).all()
        return [
            {"id": aid, "coach_user_id": cuid, "coach_username": cuname,
             "athlete_id": atid, "athlete_name": f"{first} {last}",
             "status": st}
            for aid, cuid, atid, st, first, last, cuname in rows
        ]


@router.post("/organizations/{org_id}/assignments", tags=["organizations"], status_code=201)
def create_assignment(
    org_id: int,
    body: "AssignAthleteInput",
    coach: Annotated[TokenData, Depends(require_coach)],
):
    """Assign an athlete to a coach within an organization."""
    from api.schemas import AssignAthleteInput as _AI  # noqa: F811
    from core.models import CoachAssignment
    with session_scope() as s:
        existing = s.execute(
            select(CoachAssignment).where(
                CoachAssignment.org_id == org_id,
                CoachAssignment.athlete_id == body.athlete_id,
                CoachAssignment.status == "active",
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Athlete already assigned in this org")
        assignment = CoachAssignment(
            org_id=org_id, coach_user_id=body.coach_user_id,
            athlete_id=body.athlete_id, status="active",
        )
        s.add(assignment)
        s.flush()
        return {"id": assignment.id, "message": "Athlete assigned"}


@router.put("/organizations/{org_id}/assignments/{assignment_id}/transfer", tags=["organizations"])
def transfer_assignment(
    org_id: int,
    assignment_id: int,
    body: "TransferAthleteInput",
    coach: Annotated[TokenData, Depends(require_coach)],
):
    """Transfer an athlete to a different coach."""
    from api.schemas import TransferAthleteInput as _TI  # noqa: F811
    from core.models import CoachAssignment
    with session_scope() as s:
        assignment = s.execute(
            select(CoachAssignment).where(
                CoachAssignment.id == assignment_id,
                CoachAssignment.org_id == org_id,
            )
        ).scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        assignment.coach_user_id = body.new_coach_user_id
        s.flush()
        return {"message": "Athlete transferred"}


@router.delete("/organizations/{org_id}/assignments/{assignment_id}", tags=["organizations"])
def remove_assignment(
    org_id: int,
    assignment_id: int,
    coach: Annotated[TokenData, Depends(require_coach)],
):
    """Remove an athlete-coach assignment (set to paused)."""
    from core.models import CoachAssignment
    with session_scope() as s:
        assignment = s.execute(
            select(CoachAssignment).where(
                CoachAssignment.id == assignment_id,
                CoachAssignment.org_id == org_id,
            )
        ).scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        assignment.status = "paused"
        s.flush()
        return {"message": "Assignment removed"}


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
    athlete_id: Optional[int] = None,
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


# ── Community & Social (Phase 7) ─────────────────────────────────────────

@router.get("/groups/discover", response_model=list[TrainingGroupOut], tags=["community"])
def discover_groups(athlete: Annotated[TokenData, Depends(require_athlete)]):
    """Discover public groups the athlete is NOT yet a member of."""
    from sqlalchemy import func
    from core.models import GroupMembership, TrainingGroup
    with session_scope() as s:
        my_group_ids = s.execute(
            select(GroupMembership.group_id).where(GroupMembership.athlete_id == athlete.athlete_id)
        ).scalars().all()
        q = select(TrainingGroup).where(TrainingGroup.privacy == "public")
        if my_group_ids:
            q = q.where(TrainingGroup.id.notin_(my_group_ids))
        groups = s.execute(q.order_by(TrainingGroup.name)).scalars().all()
        result = []
        for g in groups:
            count = s.execute(
                select(func.count()).select_from(GroupMembership).where(GroupMembership.group_id == g.id)
            ).scalar() or 0
            if count >= g.max_members:
                continue
            result.append(TrainingGroupOut(
                id=g.id, name=g.name, description=g.description,
                owner_user_id=g.owner_user_id, privacy=g.privacy,
                max_members=g.max_members, member_count=count,
                created_at=g.created_at,
            ))
        return result


@router.post("/groups/{group_id}/join", response_model=MessageOut, status_code=201, tags=["community"])
def join_group(group_id: int, athlete: Annotated[TokenData, Depends(require_athlete)]):
    """Athlete joins a public group."""
    from sqlalchemy import func
    from core.models import GroupMembership, TrainingGroup
    with session_scope() as s:
        group = s.get(TrainingGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        if group.privacy != "public":
            raise HTTPException(status_code=403, detail="Group is not public")
        existing = s.execute(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.athlete_id == athlete.athlete_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Already a member")
        count = s.execute(
            select(func.count()).select_from(GroupMembership).where(GroupMembership.group_id == group_id)
        ).scalar() or 0
        if count >= group.max_members:
            raise HTTPException(status_code=409, detail="Group is full")
        s.add(GroupMembership(group_id=group_id, athlete_id=athlete.athlete_id, role="member"))
    return MessageOut(message="Joined group")


@router.get("/groups", response_model=list[TrainingGroupOut], tags=["community"])
def list_groups(current_user: Annotated[TokenData, Depends(get_current_user)]):
    """List training groups. Athletes see their groups; coaches see all."""
    from sqlalchemy import func
    from core.models import GroupMembership, TrainingGroup
    with session_scope() as s:
        if current_user.role == "client":
            groups = s.execute(
                select(TrainingGroup)
                .join(GroupMembership, GroupMembership.group_id == TrainingGroup.id)
                .where(GroupMembership.athlete_id == current_user.athlete_id)
            ).scalars().all()
        else:
            groups = s.execute(select(TrainingGroup).order_by(TrainingGroup.name)).scalars().all()
        result = []
        for g in groups:
            count = s.execute(
                select(func.count()).select_from(GroupMembership).where(GroupMembership.group_id == g.id)
            ).scalar() or 0
            result.append(TrainingGroupOut(
                id=g.id, name=g.name, description=g.description,
                owner_user_id=g.owner_user_id, privacy=g.privacy,
                max_members=g.max_members, member_count=count,
                created_at=g.created_at,
            ))
        return result


@router.post("/groups", response_model=TrainingGroupOut, status_code=201, tags=["community"])
def create_group(body: TrainingGroupCreateInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Create a training group. Coach-only."""
    from core.models import TrainingGroup
    with session_scope() as s:
        group = TrainingGroup(
            name=body.name, description=body.description,
            owner_user_id=coach.user_id, privacy=body.privacy,
            max_members=body.max_members,
        )
        s.add(group)
        s.flush()
        return TrainingGroupOut(
            id=group.id, name=group.name, description=group.description,
            owner_user_id=group.owner_user_id, privacy=group.privacy,
            max_members=group.max_members, member_count=0,
            created_at=group.created_at,
        )


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberOut], tags=["community"])
def list_group_members(group_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """List members of a training group."""
    from core.models import GroupMembership
    with session_scope() as s:
        rows = s.execute(
            select(GroupMembership, Athlete.first_name, Athlete.last_name)
            .join(Athlete, Athlete.id == GroupMembership.athlete_id)
            .where(GroupMembership.group_id == group_id)
            .order_by(GroupMembership.joined_at)
        ).all()
        return [
            GroupMemberOut(
                id=m.id, group_id=m.group_id, athlete_id=m.athlete_id,
                athlete_name=f"{first} {last}", role=m.role, joined_at=m.joined_at,
            )
            for m, first, last in rows
        ]


@router.post("/groups/{group_id}/members", response_model=MessageOut, status_code=201, tags=["community"])
def add_group_member(group_id: int, athlete_id: int = Query(...), coach: Annotated[TokenData, Depends(require_coach)] = None):
    """Add an athlete to a group. Coach-only."""
    from core.models import GroupMembership
    with session_scope() as s:
        existing = s.execute(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.athlete_id == athlete_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Already a member")
        s.add(GroupMembership(group_id=group_id, athlete_id=athlete_id, role="member"))
    return MessageOut(message="Member added")


@router.delete("/groups/{group_id}/members/{athlete_id}", response_model=MessageOut, tags=["community"])
def remove_group_member(group_id: int, athlete_id: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """Remove an athlete from a group. Coach-only."""
    from core.models import GroupMembership
    with session_scope() as s:
        mem = s.execute(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.athlete_id == athlete_id,
            )
        ).scalar_one_or_none()
        if not mem:
            raise HTTPException(status_code=404, detail="Membership not found")
        s.delete(mem)
    return MessageOut(message="Member removed")


@router.get("/groups/{group_id}/messages", response_model=list[GroupMessageOut], tags=["community"])
def list_group_messages(
    group_id: int,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    limit: int = Query(30, le=100),
):
    """List recent messages in a group."""
    from core.models import GroupMessage
    with session_scope() as s:
        rows = s.execute(
            select(GroupMessage, Athlete.first_name, Athlete.last_name)
            .join(Athlete, Athlete.id == GroupMessage.author_athlete_id)
            .where(GroupMessage.group_id == group_id)
            .order_by(GroupMessage.created_at.desc())
            .limit(limit)
        ).all()
        return [
            GroupMessageOut(
                id=m.id, group_id=m.group_id, author_athlete_id=m.author_athlete_id,
                author_name=f"{first} {last}", content=m.content,
                message_type=m.message_type, created_at=m.created_at,
            )
            for m, first, last in rows
        ]


@router.post("/groups/{group_id}/messages", response_model=GroupMessageOut, status_code=201, tags=["community"])
def post_group_message(
    group_id: int,
    body: GroupMessageCreateInput,
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """Post a message to a group."""
    from core.models import GroupMessage
    if not current_user.athlete_id:
        raise HTTPException(status_code=403, detail="Only athletes can post messages")
    with session_scope() as s:
        athlete = s.get(Athlete, current_user.athlete_id)
        msg = GroupMessage(
            group_id=group_id, author_athlete_id=current_user.athlete_id,
            content=body.content, message_type=body.message_type,
        )
        s.add(msg)
        s.flush()
        return GroupMessageOut(
            id=msg.id, group_id=msg.group_id, author_athlete_id=msg.author_athlete_id,
            author_name=f"{athlete.first_name} {athlete.last_name}",
            content=msg.content, message_type=msg.message_type, created_at=msg.created_at,
        )


@router.get("/groups/{group_id}/leaderboard", response_model=list[LeaderboardEntryOut], tags=["community"])
def group_leaderboard(
    group_id: int,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    metric: str = Query("distance"),
    days: int = Query(7, ge=1, le=90),
):
    """Get a leaderboard for a group over the last N days."""
    from sqlalchemy import func
    from core.models import GroupMembership
    from core.services.community import compute_leaderboard
    cutoff = date.today() - timedelta(days=days)
    with session_scope() as s:
        members = s.execute(
            select(GroupMembership.athlete_id).where(GroupMembership.group_id == group_id)
        ).scalars().all()
        if not members:
            return []
        logs = s.execute(
            select(
                TrainingLog.athlete_id,
                Athlete.first_name, Athlete.last_name,
                func.sum(TrainingLog.distance_km).label("distance_km"),
                func.sum(TrainingLog.duration_min).label("duration_min"),
                func.sum(TrainingLog.load_score).label("load_score"),
                func.count(TrainingLog.id).label("sessions_count"),
            )
            .join(Athlete, Athlete.id == TrainingLog.athlete_id)
            .where(TrainingLog.athlete_id.in_(members), TrainingLog.date >= cutoff)
            .group_by(TrainingLog.athlete_id, Athlete.first_name, Athlete.last_name)
        ).all()
        athlete_logs = [
            {
                "athlete_id": r.athlete_id,
                "name": f"{r.first_name} {r.last_name}",
                "distance_km": float(r.distance_km or 0),
                "duration_min": float(r.duration_min or 0),
                "load_score": float(r.load_score or 0),
                "sessions_count": int(r.sessions_count or 0),
            }
            for r in logs
        ]
        entries = compute_leaderboard(athlete_logs, metric)
        return [LeaderboardEntryOut(athlete_id=e.athlete_id, name=e.name, value=e.value, rank=e.rank) for e in entries]


@router.get("/challenges", response_model=list[ChallengeOut], tags=["community"])
def list_challenges(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    status_filter: str = Query("active", alias="status"),
):
    """List challenges. Active by default."""
    from sqlalchemy import func
    from core.models import Challenge, ChallengeEntry
    with session_scope() as s:
        q = select(Challenge)
        if status_filter != "all":
            q = q.where(Challenge.status == status_filter)
        challenges = s.execute(q.order_by(Challenge.end_date)).scalars().all()
        result = []
        for c in challenges:
            count = s.execute(
                select(func.count()).select_from(ChallengeEntry).where(ChallengeEntry.challenge_id == c.id)
            ).scalar() or 0
            result.append(ChallengeOut(
                id=c.id, group_id=c.group_id, name=c.name,
                challenge_type=c.challenge_type, target_value=c.target_value,
                start_date=c.start_date, end_date=c.end_date, status=c.status,
                created_by=c.created_by, participant_count=count,
                created_at=c.created_at,
            ))
        return result


@router.post("/challenges", response_model=ChallengeOut, status_code=201, tags=["community"])
def create_challenge(body: ChallengeCreateInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Create a challenge. Coach-only."""
    from core.models import Challenge
    with session_scope() as s:
        challenge = Challenge(
            name=body.name, challenge_type=body.challenge_type,
            target_value=body.target_value, start_date=body.start_date,
            end_date=body.end_date, group_id=body.group_id,
            created_by=coach.user_id,
        )
        s.add(challenge)
        s.flush()
        return ChallengeOut(
            id=challenge.id, group_id=challenge.group_id, name=challenge.name,
            challenge_type=challenge.challenge_type, target_value=challenge.target_value,
            start_date=challenge.start_date, end_date=challenge.end_date,
            status=challenge.status, created_by=challenge.created_by,
            participant_count=0, created_at=challenge.created_at,
        )


@router.get("/challenges/{challenge_id}/entries", response_model=list[ChallengeEntryOut], tags=["community"])
def list_challenge_entries(challenge_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """List all entries (participants) for a challenge with progress."""
    from core.models import ChallengeEntry
    with session_scope() as s:
        rows = s.execute(
            select(ChallengeEntry, Athlete.first_name, Athlete.last_name)
            .join(Athlete, Athlete.id == ChallengeEntry.athlete_id)
            .where(ChallengeEntry.challenge_id == challenge_id)
            .order_by(ChallengeEntry.progress.desc())
        ).all()
        return [
            ChallengeEntryOut(
                id=e.id, challenge_id=e.challenge_id, athlete_id=e.athlete_id,
                athlete_name=f"{first} {last}", progress=e.progress,
                completed=e.completed, last_updated=e.last_updated,
            )
            for e, first, last in rows
        ]


@router.post("/challenges/{challenge_id}/join", response_model=MessageOut, status_code=201, tags=["community"])
def join_challenge(challenge_id: int, athlete: Annotated[TokenData, Depends(require_athlete)]):
    """Join a challenge as an athlete."""
    from core.models import ChallengeEntry
    with session_scope() as s:
        existing = s.execute(
            select(ChallengeEntry).where(
                ChallengeEntry.challenge_id == challenge_id,
                ChallengeEntry.athlete_id == athlete.athlete_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Already joined")
        s.add(ChallengeEntry(challenge_id=challenge_id, athlete_id=athlete.athlete_id))
    return MessageOut(message="Joined challenge")


@router.post("/challenges/sync-progress", response_model=MessageOut, tags=["community"])
def sync_challenge_progress(current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Recalculate all active challenge entries from training logs."""
    from core.models import Challenge, ChallengeEntry
    from core.services.community import aggregate_challenge_metric
    with session_scope() as s:
        challenges = s.execute(
            select(Challenge).where(Challenge.status == "active")
        ).scalars().all()
        updated = 0
        for ch in challenges:
            entries = s.execute(
                select(ChallengeEntry).where(ChallengeEntry.challenge_id == ch.id)
            ).scalars().all()
            for entry in entries:
                logs = s.execute(
                    select(TrainingLog).where(
                        TrainingLog.athlete_id == entry.athlete_id,
                        TrainingLog.date >= ch.start_date,
                        TrainingLog.date <= ch.end_date,
                    )
                ).scalars().all()
                log_dicts = [
                    {
                        "distance_km": float(l.distance_km),
                        "duration_min": float(l.duration_min),
                        "date": l.date,
                        "elevation_gain_m": 0,
                    }
                    for l in logs
                ]
                new_progress = aggregate_challenge_metric(log_dicts, ch.challenge_type)
                entry.progress = round(new_progress, 2)
                entry.completed = new_progress >= ch.target_value
                updated += 1
    return MessageOut(message=f"Synced {updated} challenge entries")


@router.get("/kudos", response_model=list[KudosOut], tags=["community"])
def list_kudos(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    athlete_id: Optional[int] = None,
    limit: int = Query(20, le=100),
):
    """List kudos received by an athlete."""
    from sqlalchemy.orm import aliased
    from core.models import Kudos as KudosModel
    target_id = _resolve_athlete_id(current_user, athlete_id)
    FromAthlete = aliased(Athlete)
    ToAthlete = aliased(Athlete)
    with session_scope() as s:
        rows = s.execute(
            select(KudosModel, FromAthlete.first_name, FromAthlete.last_name,
                   ToAthlete.first_name, ToAthlete.last_name)
            .join(FromAthlete, FromAthlete.id == KudosModel.from_athlete_id)
            .join(ToAthlete, ToAthlete.id == KudosModel.to_athlete_id)
            .where(KudosModel.to_athlete_id == target_id)
            .order_by(KudosModel.created_at.desc())
            .limit(limit)
        ).all()
        return [
            KudosOut(
                id=k.id, from_athlete_id=k.from_athlete_id,
                from_name=f"{ff} {fl}", to_athlete_id=k.to_athlete_id,
                to_name=f"{tf} {tl}", training_log_id=k.training_log_id,
                created_at=k.created_at,
            )
            for k, ff, fl, tf, tl in rows
        ]


@router.post("/kudos", response_model=MessageOut, status_code=201, tags=["community"])
def give_kudos(
    to_athlete_id: int = Query(...),
    training_log_id: Optional[int] = Query(None),
    athlete: Annotated[TokenData, Depends(require_athlete)] = None,
):
    """Give kudos to another athlete."""
    from core.models import Kudos as KudosModel
    if athlete.athlete_id == to_athlete_id:
        raise HTTPException(status_code=400, detail="Cannot give kudos to yourself")
    with session_scope() as s:
        existing = s.execute(
            select(KudosModel).where(
                KudosModel.from_athlete_id == athlete.athlete_id,
                KudosModel.to_athlete_id == to_athlete_id,
                KudosModel.training_log_id == training_log_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Already gave kudos")
        s.add(KudosModel(
            from_athlete_id=athlete.athlete_id,
            to_athlete_id=to_athlete_id,
            training_log_id=training_log_id,
        ))
    return MessageOut(message="Kudos sent!")


@router.get("/activity-feed", response_model=list, tags=["community"])
def activity_feed(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    group_id: Optional[int] = None,
    limit: int = Query(20, le=100),
):
    """Get an activity feed of recent training logs from group members or all athletes."""
    from sqlalchemy import func
    from core.models import GroupMembership, Kudos as KudosModel
    from core.services.community import format_activity_summary
    with session_scope() as s:
        q = (
            select(TrainingLog, Athlete.first_name, Athlete.last_name)
            .join(Athlete, Athlete.id == TrainingLog.athlete_id)
        )
        if group_id:
            member_ids = s.execute(
                select(GroupMembership.athlete_id).where(GroupMembership.group_id == group_id)
            ).scalars().all()
            q = q.where(TrainingLog.athlete_id.in_(member_ids))
        q = q.order_by(TrainingLog.date.desc()).limit(limit)
        rows = s.execute(q).all()
        result = []
        for log, first, last in rows:
            kudos_count = s.execute(
                select(func.count()).select_from(KudosModel).where(KudosModel.training_log_id == log.id)
            ).scalar() or 0
            result.append({
                "athlete_id": log.athlete_id,
                "athlete_name": f"{first} {last}",
                "activity_summary": format_activity_summary(log.session_category, log.duration_min, log.distance_km),
                "date": str(log.date),
                "training_log_id": log.id,
                "kudos_count": kudos_count,
            })
        return result


# ── Plan Builder ──────────────────────────────────────────────────────────

@router.post("/plans/preview", response_model=PlanPreviewOut, tags=["plans"])
def preview_plan(body: PlanCreateInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Generate a plan preview without saving. Coach-only."""
    from core.services.planning import assign_week_sessions, generate_plan_weeks
    week_rows = generate_plan_weeks(body.start_date, body.weeks, body.race_goal, body.sessions_per_week, body.max_session_min)
    preview_weeks = []
    preview_days = []
    for wr in week_rows:
        preview_weeks.append(PlanPreviewWeek(
            week_number=wr["week_number"], phase=wr["phase"],
            week_start=wr["week_start"], week_end=wr["week_end"],
            target_load=wr["target_load"], sessions_order=wr["sessions_order"],
        ))
        day_assignments = assign_week_sessions(wr["week_start"], wr["sessions_order"])
        for da in day_assignments:
            preview_days.append(PlanPreviewDay(
                week_number=wr["week_number"], session_day=da["session_day"],
                session_name=da["session_name"], phase=wr["phase"],
            ))
    return PlanPreviewOut(weeks=preview_weeks, days=preview_days)


@router.post("/plans", response_model=PlanCreateOut, status_code=201, tags=["plans"])
def create_plan(body: PlanCreateInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Create and publish a training plan. Archives existing active plans. Coach-only."""
    from core.models import CoachActionLog
    from core.services.planning import assign_week_sessions, generate_plan_weeks
    with session_scope() as s:
        existing_plans = s.execute(
            select(Plan).where(Plan.athlete_id == body.athlete_id, Plan.status == "active")
        ).scalars().all()
        for ep in existing_plans:
            ep.status = "archived"
        future_sessions = s.execute(
            select(PlanDaySession).where(
                PlanDaySession.athlete_id == body.athlete_id,
                PlanDaySession.session_day >= body.start_date,
            )
        ).scalars().all()
        for fs in future_sessions:
            s.delete(fs)
        plan = Plan(
            athlete_id=body.athlete_id, race_goal=body.race_goal,
            weeks=body.weeks, sessions_per_week=body.sessions_per_week,
            max_session_min=body.max_session_min, start_date=body.start_date,
            status="active",
        )
        s.add(plan)
        s.flush()
        week_rows = generate_plan_weeks(body.start_date, body.weeks, body.race_goal, body.sessions_per_week, body.max_session_min)
        for wr in week_rows:
            pw = PlanWeek(
                plan_id=plan.id, week_number=wr["week_number"], phase=wr["phase"],
                week_start=wr["week_start"], week_end=wr["week_end"],
                sessions_order=wr["sessions_order"], target_load=wr["target_load"],
                locked=False,
            )
            s.add(pw)
            s.flush()
            day_assignments = assign_week_sessions(wr["week_start"], wr["sessions_order"])
            for da in day_assignments:
                pds = PlanDaySession(
                    plan_week_id=pw.id, athlete_id=body.athlete_id,
                    session_day=da["session_day"], session_name=da["session_name"],
                    source_template_name=da["session_name"], status="planned",
                )
                s.add(pds)
        s.add(CoachActionLog(
            coach_user_id=coach.user_id, athlete_id=body.athlete_id,
            action="plan_created", payload={"plan_id": plan.id, "race_goal": body.race_goal, "weeks": body.weeks},
        ))
        return PlanCreateOut(plan_id=plan.id, message="Plan created successfully")


@router.put("/plans/{plan_id}/weeks/{week_number}/lock", response_model=MessageOut, tags=["plans"])
def toggle_week_lock(plan_id: int, week_number: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """Toggle the locked status of a plan week. Coach-only."""
    with session_scope() as s:
        pw = s.execute(
            select(PlanWeek).where(PlanWeek.plan_id == plan_id, PlanWeek.week_number == week_number)
        ).scalar_one_or_none()
        if not pw:
            raise HTTPException(status_code=404, detail="Week not found")
        pw.locked = not pw.locked
        s.flush()
        return MessageOut(message=f"Week {week_number} {'locked' if pw.locked else 'unlocked'}")


@router.put("/plans/{plan_id}/weeks/{week_number}/sessions/{session_day}", response_model=MessageOut, tags=["plans"])
def swap_session(
    plan_id: int, week_number: int, session_day: date,
    new_session_name: str = Query(...),
    coach: Annotated[TokenData, Depends(require_coach)] = None,
):
    """Swap a session in a plan week. Blocked if locked. Coach-only."""
    with session_scope() as s:
        pw = s.execute(
            select(PlanWeek).where(PlanWeek.plan_id == plan_id, PlanWeek.week_number == week_number)
        ).scalar_one_or_none()
        if not pw:
            raise HTTPException(status_code=404, detail="Week not found")
        if pw.locked:
            raise HTTPException(status_code=400, detail="Cannot modify a locked week")
        pds = s.execute(
            select(PlanDaySession).where(
                PlanDaySession.plan_week_id == pw.id, PlanDaySession.session_day == session_day,
            )
        ).scalar_one_or_none()
        if not pds:
            raise HTTPException(status_code=404, detail="Day session not found")
        old_name = pds.session_name
        pds.session_name = new_session_name
        pds.source_template_name = new_session_name
        all_day_sessions = s.execute(
            select(PlanDaySession).where(PlanDaySession.plan_week_id == pw.id).order_by(PlanDaySession.session_day)
        ).scalars().all()
        pw.sessions_order = [ds.session_name for ds in all_day_sessions]
        s.flush()
        return MessageOut(message=f"Swapped '{old_name}' -> '{new_session_name}'")


@router.post("/plans/{plan_id}/weeks/{week_number}/regenerate", response_model=MessageOut, tags=["plans"])
def regenerate_week(plan_id: int, week_number: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """Regenerate all sessions for a plan week. Blocked if locked. Coach-only."""
    from core.services.planning import assign_week_sessions, default_phase_session_tokens
    with session_scope() as s:
        plan = s.get(Plan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        pw = s.execute(
            select(PlanWeek).where(PlanWeek.plan_id == plan_id, PlanWeek.week_number == week_number)
        ).scalar_one_or_none()
        if not pw:
            raise HTTPException(status_code=404, detail="Week not found")
        if pw.locked:
            raise HTTPException(status_code=400, detail="Cannot regenerate a locked week")
        existing = s.execute(
            select(PlanDaySession).where(PlanDaySession.plan_week_id == pw.id)
        ).scalars().all()
        for ex in existing:
            s.delete(ex)
        s.flush()
        session_tokens = default_phase_session_tokens(pw.phase, plan.sessions_per_week, race_goal=plan.race_goal)
        day_assignments = assign_week_sessions(pw.week_start, session_tokens)
        for da in day_assignments:
            pds = PlanDaySession(
                plan_week_id=pw.id, athlete_id=plan.athlete_id,
                session_day=da["session_day"], session_name=da["session_name"],
                source_template_name=da["session_name"], status="planned",
            )
            s.add(pds)
        pw.sessions_order = session_tokens
        s.flush()
        return MessageOut(message=f"Week {week_number} regenerated with {len(day_assignments)} sessions")


# ── Session Library ──────────────────────────────────────────────────────

@router.get("/sessions/categories", tags=["sessions"])
def list_session_categories(current_user: Annotated[TokenData, Depends(get_current_user)]):
    """List unique session categories from the library."""
    from core.models import SessionLibrary
    with session_scope() as s:
        rows = s.execute(
            select(SessionLibrary.category).distinct().order_by(SessionLibrary.category)
        ).scalars().all()
        return rows


@router.get("/sessions", response_model=list[SessionLibraryOut], tags=["sessions"])
def list_sessions(
    coach: Annotated[TokenData, Depends(require_coach)],
    category: Optional[str] = None,
    intent: Optional[str] = None,
    is_treadmill: Optional[bool] = None,
):
    """List session library templates. Coach-only."""
    from core.models import SessionLibrary
    with session_scope() as s:
        q = select(SessionLibrary)
        if category:
            q = q.where(SessionLibrary.category == category)
        if intent:
            q = q.where(SessionLibrary.intent == intent)
        if is_treadmill is not None:
            q = q.where(SessionLibrary.is_treadmill == is_treadmill)
        rows = s.execute(q.order_by(SessionLibrary.category, SessionLibrary.name)).scalars().all()
        return [SessionLibraryOut.model_validate(r) for r in rows]


@router.get("/sessions/{session_id}", response_model=SessionLibraryOut, tags=["sessions"])
def get_session(session_id: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """Get a single session template. Coach-only."""
    from core.models import SessionLibrary
    with session_scope() as s:
        session = s.get(SessionLibrary, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionLibraryOut.model_validate(session)


@router.post("/sessions", response_model=SessionLibraryOut, status_code=201, tags=["sessions"])
def create_session_template(body: SessionLibraryCreateInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Create a session template. Coach-only."""
    from core.models import SessionLibrary
    with session_scope() as s:
        existing = s.execute(select(SessionLibrary).where(SessionLibrary.name == body.name)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Session with this name already exists")
        session = SessionLibrary(
            name=body.name, category=body.category, intent=body.intent,
            energy_system=body.energy_system, tier=body.tier, is_treadmill=body.is_treadmill,
            duration_min=body.duration_min, structure_json=body.structure_json,
            targets_json=body.targets_json, progression_json=body.progression_json,
            regression_json=body.regression_json, prescription=body.prescription,
            coaching_notes=body.coaching_notes,
        )
        s.add(session)
        s.flush()
        return SessionLibraryOut.model_validate(session)


@router.put("/sessions/{session_id}", response_model=SessionLibraryOut, tags=["sessions"])
def update_session_template(session_id: int, body: SessionLibraryCreateInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Update a session template. Coach-only."""
    from core.models import SessionLibrary
    with session_scope() as s:
        session = s.get(SessionLibrary, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if body.name != session.name:
            conflict = s.execute(select(SessionLibrary).where(SessionLibrary.name == body.name)).scalar_one_or_none()
            if conflict:
                raise HTTPException(status_code=409, detail="Session with this name already exists")
        session.name = body.name
        session.category = body.category
        session.intent = body.intent
        session.energy_system = body.energy_system
        session.tier = body.tier
        session.is_treadmill = body.is_treadmill
        session.duration_min = body.duration_min
        session.structure_json = body.structure_json
        session.targets_json = body.targets_json
        session.progression_json = body.progression_json
        session.regression_json = body.regression_json
        session.prescription = body.prescription
        session.coaching_notes = body.coaching_notes
        s.flush()
        return SessionLibraryOut.model_validate(session)


@router.delete("/sessions/{session_id}", response_model=MessageOut, tags=["sessions"])
def delete_session_template(session_id: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """Delete a session template. Coach-only."""
    from core.models import SessionLibrary
    with session_scope() as s:
        session = s.get(SessionLibrary, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        s.delete(session)
    return MessageOut(message="Session deleted")


# ── Intervention Stats & Casework ────────────────────────────────────────

@router.get("/interventions/stats", response_model=InterventionStatsOut, tags=["interventions"])
def intervention_stats(coach: Annotated[TokenData, Depends(require_coach)]):
    """Get queue statistics for the command center. Coach-only."""
    now = datetime.utcnow()
    with session_scope() as s:
        open_items = s.execute(
            select(CoachIntervention).where(CoachIntervention.status == "open")
        ).scalars().all()
        open_count = len(open_items)
        high_priority = sum(1 for i in open_items if i.risk_score >= 0.7)
        snoozed = sum(1 for i in open_items if i.cooldown_until and i.cooldown_until > now)
        actionable_now = open_count - snoozed
        ages_hours = []
        for i in open_items:
            if i.created_at:
                age = (now - i.created_at).total_seconds() / 3600
                ages_hours.append(age)
        sla_24 = sum(1 for a in ages_hours if a >= 24)
        sla_72 = sum(1 for a in ages_hours if a >= 72)
        if ages_hours:
            sorted_ages = sorted(ages_hours)
            mid = len(sorted_ages) // 2
            median = sorted_ages[mid] if len(sorted_ages) % 2 else (sorted_ages[mid - 1] + sorted_ages[mid]) / 2
            oldest = max(ages_hours)
        else:
            median = 0.0
            oldest = 0.0
        return InterventionStatsOut(
            open_count=open_count, high_priority=high_priority,
            actionable_now=actionable_now, snoozed=snoozed,
            sla_due_24h=sla_24, sla_due_72h=sla_72,
            median_age_hours=round(median, 1), oldest_age_hours=round(oldest, 1),
        )


@router.post("/interventions/batch-decide", response_model=MessageOut, tags=["interventions"])
def batch_decide_interventions(body: BatchDecisionInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Apply the same decision to multiple interventions. Coach-only."""
    from pages.coach import _apply_intervention_decision
    with session_scope() as s:
        applied = 0
        for iid in body.intervention_ids:
            rec = s.get(CoachIntervention, iid)
            if rec and rec.status == "open":
                _apply_intervention_decision(s, rec, body.decision, body.note, body.modified_action, coach.user_id)
                applied += 1
    return MessageOut(message=f"Applied '{body.decision}' to {applied} interventions")


@router.get("/athletes/{athlete_id}/timeline", response_model=list[TimelineEntry], tags=["casework"])
def get_athlete_timeline(
    athlete_id: int,
    coach: Annotated[TokenData, Depends(require_coach)],
    limit: int = Query(120, le=300),
):
    """Get a unified timeline for an athlete. Coach-only."""
    from core.models import CoachActionLog, CoachNotesTask
    entries: list[dict] = []
    with session_scope() as s:
        actions = s.execute(
            select(CoachActionLog).where(CoachActionLog.athlete_id == athlete_id)
            .order_by(CoachActionLog.created_at.desc()).limit(50)
        ).scalars().all()
        for a in actions:
            entries.append({"when": a.created_at, "source": "coach_action", "title": a.action, "detail": str(a.payload)})
        logs = s.execute(
            select(TrainingLog).where(TrainingLog.athlete_id == athlete_id)
            .order_by(TrainingLog.date.desc()).limit(30)
        ).scalars().all()
        for l in logs:
            pain = " [PAIN]" if l.pain_flag else ""
            entries.append({"when": datetime.combine(l.date, datetime.min.time()), "source": "training_log",
                          "title": l.session_category, "detail": f"{l.duration_min}min RPE:{l.rpe} Load:{l.load_score}{pain}"})
        checkins = s.execute(
            select(CheckIn).where(CheckIn.athlete_id == athlete_id)
            .order_by(CheckIn.day.desc()).limit(30)
        ).scalars().all()
        for c in checkins:
            score = readiness_score(c.sleep, c.energy, c.recovery, c.stress)
            entries.append({"when": datetime.combine(c.day, datetime.min.time()), "source": "checkin",
                          "title": f"Check-in ({readiness_band(score)})", "detail": f"Sleep:{c.sleep} Energy:{c.energy} Recovery:{c.recovery} Stress:{c.stress} -> {score:.1f}"})
        events = s.execute(
            select(Event).where(Event.athlete_id == athlete_id)
        ).scalars().all()
        for e in events:
            entries.append({"when": datetime.combine(e.event_date, datetime.min.time()), "source": "event",
                          "title": e.name, "detail": f"{e.distance}"})
        notes = s.execute(
            select(CoachNotesTask).where(CoachNotesTask.athlete_id == athlete_id)
        ).scalars().all()
        for n in notes:
            when = datetime.combine(n.due_date, datetime.min.time()) if n.due_date else datetime.utcnow()
            entries.append({"when": when, "source": "note", "title": "Coach Note", "detail": n.note})
    entries.sort(key=lambda x: x["when"], reverse=True)
    return [TimelineEntry(**e) for e in entries[:limit]]


@router.get("/athletes/{athlete_id}/notes", response_model=list[CoachNoteOut], tags=["casework"])
def list_athlete_notes(athlete_id: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """List notes/tasks for an athlete. Coach-only."""
    from core.models import CoachNotesTask
    with session_scope() as s:
        rows = s.execute(
            select(CoachNotesTask).where(CoachNotesTask.athlete_id == athlete_id)
            .order_by(CoachNotesTask.id.desc())
        ).scalars().all()
        return [CoachNoteOut.model_validate(r) for r in rows]


@router.post("/athletes/{athlete_id}/notes", response_model=CoachNoteOut, status_code=201, tags=["casework"])
def create_athlete_note(athlete_id: int, body: CoachNoteCreateInput, coach: Annotated[TokenData, Depends(require_coach)]):
    """Create a note/task for an athlete. Coach-only."""
    from core.models import CoachActionLog, CoachNotesTask
    with session_scope() as s:
        note = CoachNotesTask(athlete_id=athlete_id, note=body.note, due_date=body.due_date)
        s.add(note)
        s.add(CoachActionLog(coach_user_id=coach.user_id, athlete_id=athlete_id, action="note_created", payload={"note": body.note}))
        s.flush()
        return CoachNoteOut.model_validate(note)


@router.put("/athletes/{athlete_id}/notes/{note_id}", response_model=CoachNoteOut, tags=["casework"])
def update_athlete_note(
    athlete_id: int, note_id: int,
    completed: Optional[bool] = Query(None),
    coach: Annotated[TokenData, Depends(require_coach)] = None,
):
    """Update a note/task (mark complete/reopen). Coach-only."""
    from core.models import CoachNotesTask
    with session_scope() as s:
        note = s.get(CoachNotesTask, note_id)
        if not note or note.athlete_id != athlete_id:
            raise HTTPException(status_code=404, detail="Note not found")
        if completed is not None:
            note.completed = completed
        s.flush()
        return CoachNoteOut.model_validate(note)


@router.delete("/athletes/{athlete_id}/notes/{note_id}", response_model=MessageOut, tags=["casework"])
def delete_athlete_note(athlete_id: int, note_id: int, coach: Annotated[TokenData, Depends(require_coach)]):
    """Delete a note/task. Coach-only."""
    from core.models import CoachNotesTask
    with session_scope() as s:
        note = s.get(CoachNotesTask, note_id)
        if not note or note.athlete_id != athlete_id:
            raise HTTPException(status_code=404, detail="Note not found")
        s.delete(note)
    return MessageOut(message="Note deleted")


# ── Phase 2: Athlete Intelligence ─────────────────────────────────────────

@router.get("/athletes/{athlete_id}/session-briefing", response_model=SessionBriefingOut, tags=["athlete-intelligence"])
def get_session_briefing(athlete_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Get today's adapted session briefing for an athlete."""
    if current_user.role == "client" and current_user.athlete_id != athlete_id:
        raise HTTPException(status_code=403, detail="Access denied")
    from core.models import SessionLibrary
    from core.services.session_engine import adapt_session_structure, compute_acute_chronic_ratio, pace_from_sec_per_km
    today = date.today()
    with session_scope() as s:
        athlete = s.get(Athlete, athlete_id)
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")

        result = SessionBriefingOut(
            max_hr=athlete.max_hr,
            resting_hr=athlete.resting_hr,
            threshold_pace=pace_from_sec_per_km(athlete.threshold_pace_sec_per_km) if athlete.threshold_pace_sec_per_km else None,
            easy_pace=pace_from_sec_per_km(athlete.easy_pace_sec_per_km) if athlete.easy_pace_sec_per_km else None,
            vdot=getattr(athlete, "vdot_score", None),
        )

        # Today's check-in
        ci = s.execute(select(CheckIn).where(CheckIn.athlete_id == athlete_id, CheckIn.day == today)).scalar_one_or_none()
        if ci:
            score = readiness_score(ci.sleep, ci.energy, ci.recovery, ci.stress)
            result.has_checkin = True
            result.readiness_score = score
            result.readiness_band = readiness_band(score)

        # Today's log
        today_log = s.execute(select(TrainingLog).where(TrainingLog.athlete_id == athlete_id, TrainingLog.date == today)).scalar_one_or_none()
        result.today_logged = today_log is not None

        # A:C ratio from 28 days of loads
        cutoff_28 = today - timedelta(days=28)
        recent_logs = s.execute(
            select(TrainingLog).where(TrainingLog.athlete_id == athlete_id, TrainingLog.date >= cutoff_28).order_by(TrainingLog.date)
        ).scalars().all()
        daily_loads = [float(l.load_score) for l in recent_logs]
        ac_ratio = compute_acute_chronic_ratio(daily_loads)
        result.acute_chronic_ratio = ac_ratio

        # Pain flag (last 3 days)
        cutoff_3 = today - timedelta(days=3)
        pain_recent = any(l.pain_flag for l in recent_logs if l.date >= cutoff_3)

        # Active plan → today's session
        active_plan = s.execute(select(Plan).where(Plan.athlete_id == athlete_id, Plan.status == "active").order_by(Plan.id.desc())).scalar_one_or_none()
        phase = None
        days_to_event = None

        if active_plan:
            pw = s.execute(
                select(PlanWeek).where(PlanWeek.plan_id == active_plan.id, PlanWeek.week_start <= today, PlanWeek.week_end >= today)
            ).scalar_one_or_none()
            if pw:
                phase = pw.phase
                result.phase = phase

            pds = s.execute(
                select(PlanDaySession).where(PlanDaySession.athlete_id == athlete_id, PlanDaySession.session_day == today)
            ).scalar_one_or_none()
            if pds:
                result.planned_session_name = pds.session_name
                result.planned_session_status = pds.status

                # Find template
                tmpl = s.execute(select(SessionLibrary).where(SessionLibrary.name == pds.source_template_name)).scalar_one_or_none()
                if tmpl:
                    result.has_template = True
                    result.prescription = tmpl.prescription
                    result.coaching_notes = tmpl.coaching_notes
                    result.progression_rules = tmpl.progression_json if tmpl.progression_json else None
                    result.regression_rules = tmpl.regression_json if tmpl.regression_json else None

                    # Next event for taper calc
                    next_event = s.execute(
                        select(Event).where(Event.athlete_id == athlete_id, Event.event_date >= today).order_by(Event.event_date)
                    ).scalar_one_or_none()
                    if next_event:
                        days_to_event = (next_event.event_date - today).days

                    # Adapt session
                    adapted = adapt_session_structure(
                        tmpl.structure_json,
                        readiness=result.readiness_score,
                        pain_flag=pain_recent,
                        acute_chronic_ratio=ac_ratio,
                        days_to_event=days_to_event,
                        phase=phase,
                        vdot=result.vdot,
                    )
                    result.adaptation_action = adapted["action"]
                    result.adaptation_reason = adapted["reason"]
                    result.adapted_blocks = adapted["session"].get("blocks", [])

        return result


@router.get("/athletes/{athlete_id}/training-load-summary", response_model=TrainingLoadSummaryOut, tags=["athlete-intelligence"])
def get_training_load_summary(athlete_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Get 30-day training load metrics (monotony, strain, risk)."""
    if current_user.role == "client" and current_user.athlete_id != athlete_id:
        raise HTTPException(status_code=403, detail="Access denied")
    from core.services.training_load import compute_weekly_metrics, overtraining_risk
    today = date.today()
    cutoff = today - timedelta(days=30)
    with session_scope() as s:
        logs = s.execute(
            select(TrainingLog).where(TrainingLog.athlete_id == athlete_id, TrainingLog.date >= cutoff).order_by(TrainingLog.date)
        ).scalars().all()

        if len(logs) < 7:
            return TrainingLoadSummaryOut()

        # Build daily loads for the last 7 days
        last_7_start = today - timedelta(days=6)
        daily = {last_7_start + timedelta(days=i): 0.0 for i in range(7)}
        total_load = 0.0
        for log in logs:
            total_load += log.load_score
            if log.date in daily:
                daily[log.date] += float(log.load_score)

        daily_loads_7 = [daily[last_7_start + timedelta(days=i)] for i in range(7)]
        metrics = compute_weekly_metrics(daily_loads_7)
        risk = overtraining_risk(metrics.monotony, metrics.strain)

        return TrainingLoadSummaryOut(
            has_data=True,
            monotony=metrics.monotony,
            strain=metrics.strain,
            risk_level=risk,
            total_load=round(total_load, 1),
            session_count=len(logs),
            avg_daily_load=metrics.avg_daily_load,
        )


@router.get("/athletes/{athlete_id}/analytics/fitness", response_model=FitnessFatigueOut, tags=["athlete-intelligence"])
def get_fitness_fatigue(athlete_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Get CTL/ATL/TSB time series for fitness & fatigue chart."""
    if current_user.role == "client" and current_user.athlete_id != athlete_id:
        raise HTTPException(status_code=403, detail="Access denied")
    from core.services.analytics import compute_fitness_fatigue, race_readiness_score
    cutoff = date.today() - timedelta(days=120)
    with session_scope() as s:
        logs = s.execute(
            select(TrainingLog).where(TrainingLog.athlete_id == athlete_id, TrainingLog.date >= cutoff).order_by(TrainingLog.date)
        ).scalars().all()

        if not logs:
            return FitnessFatigueOut()

        daily_loads = [{"date": l.date, "load": float(l.load_score)} for l in logs]
        points = compute_fitness_fatigue(daily_loads)

        if not points:
            return FitnessFatigueOut()

        last = points[-1]
        readiness = race_readiness_score(last.tsb)

        return FitnessFatigueOut(
            points=[{"day": str(p.day), "ctl": p.ctl, "atl": p.atl, "tsb": p.tsb, "load": p.daily_load} for p in points],
            current_ctl=last.ctl,
            current_atl=last.atl,
            current_tsb=last.tsb,
            readiness=readiness,
        )


@router.get("/athletes/{athlete_id}/analytics/vdot", response_model=VdotHistoryOut, tags=["athlete-intelligence"])
def get_vdot_history(athlete_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Get VDOT progression from race/benchmark logs."""
    if current_user.role == "client" and current_user.athlete_id != athlete_id:
        raise HTTPException(status_code=403, detail="Access denied")
    from core.services.analytics import compute_vdot_history, vdot_trend
    with session_scope() as s:
        # Get race/benchmark logs (session_category in race, benchmark, time_trial)
        logs = s.execute(
            select(TrainingLog).where(
                TrainingLog.athlete_id == athlete_id,
                TrainingLog.session_category.in_(["race", "benchmark", "time_trial"]),
                TrainingLog.distance_km > 0,
                TrainingLog.duration_min > 0,
            ).order_by(TrainingLog.date)
        ).scalars().all()

        if not logs:
            return VdotHistoryOut()

        race_results = [
            {"date": l.date, "distance_km": float(l.distance_km), "duration_min": float(l.duration_min), "source": l.session_category}
            for l in logs
        ]
        history = compute_vdot_history(race_results)

        if not history:
            return VdotHistoryOut()

        trend = vdot_trend(history)
        return VdotHistoryOut(
            points=[{"date": str(p.event_date), "vdot": p.vdot, "source": p.source, "distance_m": p.distance_m} for p in history],
            current_vdot=trend.get("current_vdot"),
            peak_vdot=trend.get("peak_vdot"),
            trend=trend.get("trend", "insufficient_data"),
            improvement_per_month=trend.get("improvement_per_month", 0.0),
        )


@router.get("/athletes/{athlete_id}/race-predictions", response_model=RacePredictionOut, tags=["athlete-intelligence"])
def get_race_predictions(athlete_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Get race time predictions for all standard distances."""
    if current_user.role == "client" and current_user.athlete_id != athlete_id:
        raise HTTPException(status_code=403, detail="Access denied")
    from core.services.race_predictor import predict_all_distances
    with session_scope() as s:
        athlete = s.get(Athlete, athlete_id)
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")

        # Find best recent race/benchmark
        best_log = s.execute(
            select(TrainingLog).where(
                TrainingLog.athlete_id == athlete_id,
                TrainingLog.session_category.in_(["race", "benchmark", "time_trial"]),
                TrainingLog.distance_km > 0,
                TrainingLog.duration_min > 0,
            ).order_by(TrainingLog.date.desc())
        ).scalars().first()

        vdot_score = getattr(athlete, "vdot_score", None)

        if not best_log and not vdot_score:
            return RacePredictionOut()

        # Determine source
        if best_log:
            dist_km = float(best_log.distance_km)
            # Map to standard distance label
            dist_map = {5.0: "5K", 10.0: "10K", 21.1: "Half Marathon", 42.2: "Marathon"}
            dist_label = None
            for km, label in dist_map.items():
                if abs(dist_km - km) < 0.5:
                    dist_label = label
                    break
            if not dist_label:
                dist_label = "5K"  # fallback

            time_seconds = float(best_log.duration_min) * 60
            predictions_raw = predict_all_distances(dist_label, time_seconds, vdot_override=vdot_score)
            source_event = f"{dist_label} ({best_log.date})"
        else:
            predictions_raw = predict_all_distances("5K", 0, vdot_override=vdot_score)
            source_event = f"VDOT {vdot_score}"

        predictions = {}
        for label, preds in predictions_raw.items():
            predictions[label] = [
                {"distance_label": p.distance_label, "predicted_display": p.predicted_display, "method": p.method, "vdot_used": p.vdot_used}
                for p in preds
            ]

        return RacePredictionOut(
            predictions=predictions,
            source_vdot=vdot_score,
            source_event=source_event,
        )


@router.get("/athletes/{athlete_id}/profile", response_model=AthleteProfileOut, tags=["athlete-intelligence"])
def get_athlete_profile(athlete_id: int, current_user: Annotated[TokenData, Depends(get_current_user)]):
    """Get athlete profile with wearable connections and sync logs."""
    if current_user.role == "client" and current_user.athlete_id != athlete_id:
        raise HTTPException(status_code=403, detail="Access denied")
    from core.models import SyncLog, WearableConnection
    with session_scope() as s:
        athlete = s.get(Athlete, athlete_id)
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")

        connections = s.execute(
            select(WearableConnection).where(WearableConnection.athlete_id == athlete_id)
        ).scalars().all()
        wearables = [
            {"id": c.id, "service": c.service, "sync_status": c.sync_status,
             "last_sync_at": str(c.last_sync_at) if c.last_sync_at else None,
             "external_athlete_id": c.external_athlete_id}
            for c in connections
        ]

        sync_logs = s.execute(
            select(SyncLog).where(SyncLog.athlete_id == athlete_id).order_by(SyncLog.id.desc()).limit(5)
        ).scalars().all()
        logs = [
            {"id": sl.id, "service": sl.service, "status": sl.status,
             "activities_found": sl.activities_found, "activities_imported": sl.activities_imported,
             "started_at": str(sl.started_at) if sl.started_at else None}
            for sl in sync_logs
        ]

        return AthleteProfileOut(
            id=athlete.id, first_name=athlete.first_name, last_name=athlete.last_name,
            email=athlete.email, dob=athlete.dob, max_hr=athlete.max_hr,
            resting_hr=athlete.resting_hr,
            threshold_pace_sec_per_km=athlete.threshold_pace_sec_per_km,
            easy_pace_sec_per_km=athlete.easy_pace_sec_per_km,
            vdot_score=getattr(athlete, "vdot_score", None),
            status=athlete.status,
            wearable_connections=wearables,
            sync_logs=logs,
        )


# ── Helpers ───────────────────────────────────────────────────────────────

def _resolve_athlete_id(current_user: TokenData, requested_id: Optional[int]) -> int:
    """Resolve the target athlete ID based on role and request."""
    if current_user.role == "client":
        return current_user.athlete_id
    if requested_id:
        return requested_id
    raise HTTPException(status_code=400, detail="athlete_id query parameter required for coaches")
