from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from core.config import get_settings
from core.models import TrainingLog

from api.schemas import TrainingLogInput
from api.webhooks import dispatcher

logger = logging.getLogger(__name__)


def persist_training_log(db: Session, data: TrainingLogInput) -> TrainingLog:
    row = TrainingLog(
        athlete_id=data.athlete_id,
        date=data.date,
        session_category=data.session_category,
        duration_min=data.duration_min,
        distance_km=data.distance_km,
        avg_hr=data.avg_hr,
        max_hr=data.max_hr,
        avg_pace_sec_per_km=data.avg_pace_sec_per_km,
        rpe=data.rpe,
        load_score=float(data.load_score or 0),
        notes=data.notes,
        pain_flag=data.pain_flag,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    logger.info(
        "training_log_persisted",
        extra={
            "training_log_id": row.id,
            "athlete_id": row.athlete_id,
            "session_category": row.session_category,
            "source": data.source,
        },
    )
    dispatch_training_log_created(row, source=data.source, raw_payload=data.raw_payload)
    return row


def dispatch_training_log_created(row: TrainingLog, source: str, raw_payload: dict[str, Any] | None = None) -> None:
    settings = get_settings()
    dispatcher.dispatch(
        settings.event_training_log_created,
        {
            "training_log_id": row.id,
            "athlete_id": row.athlete_id,
            "date": row.date.isoformat(),
            "session_category": row.session_category,
            "duration_min": row.duration_min,
            "distance_km": float(row.distance_km or 0),
            "avg_hr": row.avg_hr,
            "max_hr": row.max_hr,
            "rpe": row.rpe,
            "load_score": float(row.load_score or 0),
            "pain_flag": bool(row.pain_flag),
            "source": source,
            "raw_payload": raw_payload or {},
        },
    )
