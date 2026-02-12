from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.db import session_scope
from core.models import Athlete, CheckIn, CoachIntervention, Event, PlanDaySession, TrainingLog
from core.services.interventions import Recommendation, generate_recommendation
from core.services.readiness import readiness_score


@dataclass
class AthleteSignals:
    athlete_id: int
    readiness: float
    adherence: float
    days_since_log: int
    days_to_event: int
    pain_recent: bool
    planned_sessions_14d: int
    completed_sessions_14d: int


def risk_priority(risk: float) -> str:
    """Map a numeric risk score (0-1) to a priority label: 'high', 'medium', or 'low'."""
    if risk >= 0.75:
        return "high"
    if risk >= 0.5:
        return "medium"
    return "low"


def derive_adherence(planned_sessions_14d: int, completed_sessions_14d: int, logged_sessions_14d: int) -> float:
    """Compute a 14-day adherence ratio (0.0-1.0) from planned vs completed sessions.

    Falls back to 1.0 if no plan exists but logs are present, or 0.5 if no data.
    """
    if planned_sessions_14d > 0:
        return round(min(1.0, max(0.0, completed_sessions_14d / planned_sessions_14d)), 2)
    if logged_sessions_14d > 0:
        return 1.0
    return 0.5


def compose_recommendation(signals: AthleteSignals) -> Recommendation:
    """Build a coaching Recommendation from athlete signals, adjusting for pain flags.

    Applies a risk uplift and potential action override when recent pain is detected.
    Returns a Recommendation with guardrail checks applied.
    """
    rec = generate_recommendation(
        readiness=signals.readiness,
        adherence=signals.adherence,
        days_since_log=signals.days_since_log,
        days_to_event=signals.days_to_event,
    )

    risk = rec.risk_score
    action = rec.action
    why = list(rec.why)
    if signals.pain_recent:
        if "pain_flag_recent" not in why:
            why.append("pain_flag_recent")
        risk = round(min(1.0, risk + 0.15), 2)
        if action == "monitor":
            action = "recovery_week"

    guardrail_pass = risk <= 0.85
    guardrail_reason = "ok" if guardrail_pass else "risk_too_high"
    return Recommendation(
        action=action,
        risk_score=risk,
        confidence_score=rec.confidence_score,
        expected_impact=rec.expected_impact,
        why=why,
        guardrail_pass=guardrail_pass,
        guardrail_reason=guardrail_reason,
    )


def collect_athlete_signals(s: Session, athlete_id: int, today: date) -> AthleteSignals:
    """Query the database to gather readiness, adherence, and risk signals for one athlete.

    Returns an AthleteSignals dataclass populated from check-ins, logs, events, and plan sessions.
    """
    lookback_14d = today - timedelta(days=13)
    lookback_7d = today - timedelta(days=6)

    latest_checkin = s.execute(
        select(CheckIn.sleep, CheckIn.energy, CheckIn.recovery, CheckIn.stress)
        .where(CheckIn.athlete_id == athlete_id, CheckIn.day <= today)
        .order_by(CheckIn.day.desc())
    ).first()
    readiness = readiness_score(*latest_checkin) if latest_checkin else 3.0

    last_log_date = s.execute(
        select(func.max(TrainingLog.date)).where(TrainingLog.athlete_id == athlete_id)
    ).scalar_one_or_none()
    days_since_log = 999 if not last_log_date else max(0, (today - last_log_date).days)

    pain_recent = bool(
        s.execute(
            select(TrainingLog.id).where(
                TrainingLog.athlete_id == athlete_id,
                TrainingLog.date >= lookback_7d,
                TrainingLog.date <= today,
                TrainingLog.pain_flag.is_(True),
            )
        ).first()
    )

    next_event_day = s.execute(
        select(func.min(Event.event_date)).where(Event.athlete_id == athlete_id, Event.event_date >= today)
    ).scalar_one_or_none()
    days_to_event = 999 if not next_event_day else max(0, (next_event_day - today).days)

    planned_sessions_14d = s.execute(
        select(func.count(PlanDaySession.id)).where(
            PlanDaySession.athlete_id == athlete_id,
            PlanDaySession.session_day >= lookback_14d,
            PlanDaySession.session_day <= today,
        )
    ).scalar_one()
    completed_sessions_14d = s.execute(
        select(func.count(PlanDaySession.id)).where(
            PlanDaySession.athlete_id == athlete_id,
            PlanDaySession.session_day >= lookback_14d,
            PlanDaySession.session_day <= today,
            PlanDaySession.status == "completed",
        )
    ).scalar_one()
    logged_sessions_14d = s.execute(
        select(func.count(TrainingLog.id)).where(
            TrainingLog.athlete_id == athlete_id,
            TrainingLog.date >= lookback_14d,
            TrainingLog.date <= today,
        )
    ).scalar_one()

    adherence = derive_adherence(
        int(planned_sessions_14d or 0),
        int(completed_sessions_14d or 0),
        int(logged_sessions_14d or 0),
    )
    return AthleteSignals(
        athlete_id=athlete_id,
        readiness=readiness,
        adherence=adherence,
        days_since_log=days_since_log,
        days_to_event=days_to_event,
        pain_recent=pain_recent,
        planned_sessions_14d=int(planned_sessions_14d or 0),
        completed_sessions_14d=int(completed_sessions_14d or 0),
    )


def _sync_single_athlete(s: Session, athlete_id: int, today: date) -> dict[str, int]:
    now = datetime.utcnow()
    signals = collect_athlete_signals(s, athlete_id, today)
    rec = compose_recommendation(signals)

    rows = s.execute(
        select(CoachIntervention).where(
            CoachIntervention.athlete_id == athlete_id,
            CoachIntervention.status == "open",
        )
    ).scalars().all()
    open_by_action = {row.action_type: row for row in rows}

    created = updated = closed = 0
    if rec.action == "monitor" and rec.risk_score < 0.35 and not signals.pain_recent:
        for row in rows:
            row.status = "closed"
            row.cooldown_until = None
            closed += 1
        return {"created": created, "updated": updated, "closed": closed}

    current = open_by_action.get(rec.action)
    if current is None:
        current = CoachIntervention(
            athlete_id=athlete_id,
            action_type=rec.action,
            status="open",
            risk_score=rec.risk_score,
            confidence_score=rec.confidence_score,
            expected_impact={
                "impact": rec.expected_impact,
                "signals": {
                    "readiness": signals.readiness,
                    "adherence": signals.adherence,
                    "days_since_log": signals.days_since_log,
                    "days_to_event": signals.days_to_event,
                    "pain_recent": signals.pain_recent,
                },
            },
            why_factors=rec.why,
            guardrail_pass=rec.guardrail_pass,
            guardrail_reason=rec.guardrail_reason,
            cooldown_until=None,
        )
        s.add(current)
        created += 1
    else:
        if current.cooldown_until and current.cooldown_until > now:
            return {"created": created, "updated": updated, "closed": closed}
        current.risk_score = rec.risk_score
        current.confidence_score = rec.confidence_score
        current.expected_impact = {
            "impact": rec.expected_impact,
            "signals": {
                "readiness": signals.readiness,
                "adherence": signals.adherence,
                "days_since_log": signals.days_since_log,
                "days_to_event": signals.days_to_event,
                "pain_recent": signals.pain_recent,
            },
        }
        current.why_factors = rec.why
        current.guardrail_pass = rec.guardrail_pass
        current.guardrail_reason = rec.guardrail_reason
        updated += 1

    for row in rows:
        if row.action_type != rec.action:
            row.status = "closed"
            row.cooldown_until = None
            closed += 1
    return {"created": created, "updated": updated, "closed": closed}


def sync_interventions_queue(today: date | None = None) -> dict[str, int]:
    """Refresh the coach intervention queue for all active athletes.

    Creates, updates, or closes interventions based on current signals.
    Returns a dict with counts: {'created', 'updated', 'closed'}.
    """
    if today is None:
        today = date.today()
    summary = {"created": 0, "updated": 0, "closed": 0}
    with session_scope() as s:
        athlete_ids = s.execute(select(Athlete.id).where(Athlete.status == "active")).scalars().all()
        for athlete_id in athlete_ids:
            result = _sync_single_athlete(s, int(athlete_id), today)
            summary["created"] += result["created"]
            summary["updated"] += result["updated"]
            summary["closed"] += result["closed"]
    return summary
