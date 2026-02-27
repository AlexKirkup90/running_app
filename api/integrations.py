from datetime import date, datetime
import hashlib
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.models import AppWriteLog, TrainingLog

from api.deps import get_db
from api.ratelimit import limiter
from api.schemas import ProviderWebhookAccepted, TrainingLogInput, TrainingLogResponse
from api.training_logs import persist_training_log

router = APIRouter(prefix="/integrations", tags=["integrations"])
logger = logging.getLogger(__name__)


def _coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except Exception:
            pass
    return date.today()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None:
            return default
        return int(round(float(value)))
    except Exception:
        return default


def _normalize_activity_type(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_run_activity(value: Any) -> bool:
    normalized = _normalize_activity_type(value)
    return normalized in {"run", "running"}


def _strava_activity_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    event_payload = payload or {}
    details = (
        event_payload.get("activity")
        or event_payload.get("activity_details")
        or event_payload.get("object")
        or event_payload
    )
    return event_payload, (details if isinstance(details, dict) else {})


def _strava_to_training_log(payload: dict[str, Any]) -> TrainingLogInput:
    event_payload, activity = _strava_activity_payload(payload)
    aspect_type = str(event_payload.get("aspect_type") or "create").lower()
    if aspect_type not in {"create", "update"}:
        raise HTTPException(status_code=202, detail={"code": "IGNORED_EVENT", "provider": "strava", "aspect_type": aspect_type})

    athlete = activity.get("athlete") or {}
    sport_type = activity.get("sport_type") or activity.get("type") or event_payload.get("type")
    if not _is_run_activity(sport_type):
        raise HTTPException(
            status_code=202,
            detail={"code": "IGNORED_NON_RUN", "provider": "strava", "activity_type": str(sport_type or "")},
        )

    start_date = activity.get("start_date_local") or activity.get("start_date") or event_payload.get("event_time")
    duration_min = int(round(_safe_float(activity.get("moving_time") or activity.get("elapsed_time"), 0.0) / 60.0))
    distance_km = _safe_float(activity.get("distance"), 0.0) / 1000.0
    avg_hr = _safe_int(activity.get("average_heartrate") or activity.get("avg_hr"))
    max_hr = _safe_int(activity.get("max_heartrate") or activity.get("max_hr"))
    name = str(activity.get("name") or f"Strava activity {event_payload.get('object_id') or ''}").strip()
    session_category = _normalize_activity_type(sport_type) or "run"
    return TrainingLogInput(
        athlete_id=int(
            event_payload.get("athlete_id")
            or activity.get("athlete_id")
            or event_payload.get("owner_id")
            or athlete.get("id")
            or 0
        ),
        date=_coerce_date(start_date),
        session_category=session_category,
        duration_min=max(0, duration_min),
        distance_km=round(max(0.0, distance_km), 3),
        avg_hr=avg_hr,
        max_hr=max_hr,
        rpe=max(1, min(10, _safe_int(activity.get("perceived_exertion") or event_payload.get("perceived_exertion"), 6) or 6)),
        notes=name,
        source=get_settings().strava_provider_name,
        raw_payload=payload,
    )


def _garmin_first_activity(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("activities"), list) and payload["activities"]:
        for item in payload["activities"]:
            if isinstance(item, dict):
                return item
    if isinstance(payload.get("dailies"), list) and payload["dailies"]:
        for daily in payload["dailies"]:
            if not isinstance(daily, dict):
                continue
            if isinstance(daily.get("activities"), list) and daily["activities"]:
                for item in daily["activities"]:
                    if isinstance(item, dict):
                        return item
            return daily
    summary = payload.get("summary") or payload.get("activitySummary") or payload
    return summary if isinstance(summary, dict) else {}


def _garmin_to_training_log(payload: dict[str, Any]) -> TrainingLogInput:
    activity = _garmin_first_activity(payload)
    athlete_id = payload.get("athlete_id") or payload.get("userId") or payload.get("ownerId") or activity.get("userId")
    session_type = (
        activity.get("activityType")
        or activity.get("activityTypeDTO", {}).get("typeKey")
        or activity.get("activityName")
        or payload.get("activity_type")
        or "run"
    )
    if not _is_run_activity(session_type):
        raise HTTPException(
            status_code=202,
            detail={"code": "IGNORED_NON_RUN", "provider": "garmin", "activity_type": str(session_type or "")},
        )
    start_time = activity.get("startTimeLocal") or activity.get("startTimeGMT") or payload.get("start_time")
    duration_sec = activity.get("durationInSeconds") or activity.get("movingDurationInSeconds") or payload.get("duration_sec")
    distance_m = activity.get("distanceInMeters") or payload.get("distance_m")
    avg_hr = (
        activity.get("averageHeartRateInBeatsPerMinute")
        or activity.get("averageHR")
        or payload.get("avg_hr")
    )
    max_hr = activity.get("maxHeartRateInBeatsPerMinute") or activity.get("maxHR") or payload.get("max_hr")
    notes = str(activity.get("activityName") or payload.get("title") or "Garmin activity")
    return TrainingLogInput(
        athlete_id=int(athlete_id or 0),
        date=_coerce_date(start_time),
        session_category=_normalize_activity_type(session_type) or "run",
        duration_min=max(0, int(round(_safe_float(duration_sec, 0.0) / 60.0))),
        distance_km=round(max(0.0, _safe_float(distance_m, 0.0) / 1000.0), 3),
        avg_hr=_safe_int(avg_hr),
        max_hr=_safe_int(max_hr),
        rpe=max(1, min(10, _safe_int(payload.get("rpe"), 5) or 5)),
        notes=notes,
        source=get_settings().garmin_provider_name,
        raw_payload=payload,
    )


def _stable_payload_digest(payload: dict[str, Any]) -> str:
    try:
        canonical = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        canonical = str(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _strava_event_key(payload: dict[str, Any], training_log_input: TrainingLogInput) -> str:
    event_payload, activity = _strava_activity_payload(payload)
    object_id = (
        event_payload.get("object_id")
        or activity.get("id")
        or activity.get("activity_id")
        or event_payload.get("activity_id")
    )
    aspect_type = str(event_payload.get("aspect_type") or "create").strip().lower()
    athlete_id = int(training_log_input.athlete_id or 0)
    if object_id:
        return f"strava:{athlete_id}:{object_id}:{aspect_type}"
    return f"strava:{athlete_id}:payload:{_stable_payload_digest(payload)}"


def _garmin_event_key(payload: dict[str, Any], training_log_input: TrainingLogInput) -> str:
    activity = _garmin_first_activity(payload)
    activity_id = (
        activity.get("activityId")
        or activity.get("activity_id")
        or payload.get("activityId")
        or payload.get("activity_id")
    )
    athlete_id = int(training_log_input.athlete_id or 0)
    if activity_id:
        return f"garmin:{athlete_id}:{activity_id}"
    return f"garmin:{athlete_id}:payload:{_stable_payload_digest(payload)}"


def _provider_event_key(provider: str, payload: dict[str, Any], training_log_input: TrainingLogInput) -> str:
    if provider == "strava":
        return _strava_event_key(payload, training_log_input)
    return _garmin_event_key(payload, training_log_input)


def _webhook_scope(provider: str, event_key: str) -> str:
    digest = hashlib.sha256(event_key.encode("utf-8")).hexdigest()[:20]
    return f"integration_webhook:{provider}:{digest}"


def _deduplicated_webhook_response(
    *,
    provider: str,
    event_key: str,
    scope: str,
    row: TrainingLog,
) -> ProviderWebhookAccepted:
    return ProviderWebhookAccepted(
        provider=provider,
        received_at=datetime.utcnow(),
        event=get_settings().event_training_log_created,
        training_log=TrainingLogResponse.model_validate(row),
        status="duplicate",
        deduplicated=True,
        event_key=event_key,
        ingest_scope=scope,
        duplicate_of_training_log_id=int(row.id),
    )


def _persist_training_log_with_retry(db: Session, training_log_input: TrainingLogInput) -> TrainingLog:
    settings = get_settings()
    attempts = max(1, min(5, int(getattr(settings, "integration_persist_retry_attempts", 1) or 1)))
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return persist_training_log(db, training_log_input)
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
            db.rollback()
            logger.warning(
                "integration_persist_retry",
                extra={
                    "provider": training_log_input.source,
                    "athlete_id": int(training_log_input.athlete_id or 0),
                    "attempt": attempt,
                    "max_attempts": attempts,
                },
            )
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("persist retry loop exited unexpectedly")


def _persist_provider_payload(provider: str, payload: dict[str, Any], db: Session):
    parser = _strava_to_training_log if provider == "strava" else _garmin_to_training_log
    training_log_input = parser(payload)
    event_key = _provider_event_key(provider, payload, training_log_input)
    scope = _webhook_scope(provider, event_key)

    existing_log = db.execute(
        select(AppWriteLog)
        .where(AppWriteLog.scope == scope)
        .order_by(AppWriteLog.created_at.desc(), AppWriteLog.id.desc())
    ).scalars().first()
    if existing_log is not None:
        existing_payload = dict(existing_log.payload or {})
        try:
            existing_training_log_id = int(existing_payload.get("training_log_id"))
        except Exception:
            existing_training_log_id = None
        if existing_training_log_id is not None:
            existing_row = db.execute(select(TrainingLog).where(TrainingLog.id == existing_training_log_id)).scalar_one_or_none()
            if existing_row is not None:
                return _deduplicated_webhook_response(
                    provider=provider,
                    event_key=event_key,
                    scope=scope,
                    row=existing_row,
                )

    row = _persist_training_log_with_retry(db, training_log_input)
    db.add(
        AppWriteLog(
            scope=scope,
            actor_user_id=None,
            payload={
                "provider": provider,
                "event_key": event_key,
                "training_log_id": int(row.id),
                "athlete_id": int(row.athlete_id),
                "deduplicated": False,
            },
        )
    )
    db.flush()
    return ProviderWebhookAccepted(
        provider=provider,
        received_at=datetime.utcnow(),
        event=get_settings().event_training_log_created,
        training_log=TrainingLogResponse.model_validate(row),
        status="created",
        deduplicated=False,
        event_key=event_key,
        ingest_scope=scope,
        duplicate_of_training_log_id=None,
    )


@router.post("/strava/webhook", response_model=ProviderWebhookAccepted)
@limiter.limit(get_settings().webhook_rate_limit)
def strava_webhook(
    request: Request,
    response: Response,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    del request, response
    return _persist_provider_payload("strava", payload, db)


@router.post("/garmin/webhook", response_model=ProviderWebhookAccepted)
@limiter.limit(get_settings().webhook_rate_limit)
def garmin_webhook(
    request: Request,
    response: Response,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    del request, response
    return _persist_provider_payload("garmin", payload, db)
