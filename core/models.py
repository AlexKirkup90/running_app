from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Athlete(Base):
    __tablename__ = "athletes"
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    dob: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    athlete_id: Mapped[int | None] = mapped_column(ForeignKey("athletes.id"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class SessionLibrary(Base):
    __tablename__ = "sessions_library"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(60), index=True)
    tier: Mapped[str] = mapped_column(String(20), default="system")
    indoor_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_min: Mapped[int] = mapped_column(Integer)
    blocks_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    prescription: Mapped[str] = mapped_column(Text)


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    goal_race: Mapped[str] = mapped_column(String(20))
    weeks: Mapped[int] = mapped_column(Integer)
    sessions_per_week: Mapped[int] = mapped_column(Integer)
    max_session_duration: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[dt.date] = mapped_column(Date)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class PlanWeek(Base):
    __tablename__ = "plan_weeks"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    week_index: Mapped[int] = mapped_column(Integer)
    week_start: Mapped[dt.date] = mapped_column(Date)
    phase: Mapped[str] = mapped_column(String(30))
    focus: Mapped[str] = mapped_column(String(120))
    target_load: Mapped[float] = mapped_column(Float)
    sessions_order: Mapped[list[str]] = mapped_column(JSON)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)


class PlanWeekMetric(Base):
    __tablename__ = "plan_week_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_week_id: Mapped[int] = mapped_column(ForeignKey("plan_weeks.id"), index=True)
    planned_duration: Mapped[int] = mapped_column(Integer, default=0)
    actual_duration: Mapped[int] = mapped_column(Integer, default=0)
    planned_load: Mapped[float] = mapped_column(Float, default=0)
    actual_load: Mapped[float] = mapped_column(Float, default=0)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    event_date: Mapped[dt.date] = mapped_column(Date)
    race_type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))


class CheckIn(Base):
    __tablename__ = "checkins"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    checkin_date: Mapped[dt.date] = mapped_column(Date)
    sleep_score: Mapped[int] = mapped_column(Integer)
    energy_score: Mapped[int] = mapped_column(Integer)
    recovery_score: Mapped[int] = mapped_column(Integer)
    stress_score: Mapped[int] = mapped_column(Integer)
    training_today: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        UniqueConstraint("athlete_id", "checkin_date", name="uq_checkin_daily"),
        CheckConstraint("sleep_score between 1 and 5"),
        CheckConstraint("energy_score between 1 and 5"),
        CheckConstraint("recovery_score between 1 and 5"),
        CheckConstraint("stress_score between 1 and 5"),
    )


class TrainingLog(Base):
    __tablename__ = "training_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    log_date: Mapped[dt.date] = mapped_column(Date, index=True)
    session_type: Mapped[str] = mapped_column(String(60))
    duration_min: Mapped[int] = mapped_column(Integer)
    distance_km: Mapped[float] = mapped_column(Float, default=0)
    load_score: Mapped[float] = mapped_column(Float)
    rpe: Mapped[int] = mapped_column(Integer)
    pain_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("duration_min >= 0"), CheckConstraint("rpe between 1 and 10"))


class SessionReflection(Base):
    __tablename__ = "session_reflections"
    id: Mapped[int] = mapped_column(primary_key=True)
    training_log_id: Mapped[int] = mapped_column(ForeignKey("training_logs.id"), index=True)
    confidence_score: Mapped[int] = mapped_column(Integer)
    reflection_text: Mapped[str] = mapped_column(Text, default="")


class CoachActionLog(Base):
    __tablename__ = "coach_action_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    coach_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    athlete_id: Mapped[int | None] = mapped_column(ForeignKey("athletes.id"), index=True)
    action: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class CoachNoteTask(Base):
    __tablename__ = "coach_notes_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    note: Mapped[str] = mapped_column(Text)
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open")


class CoachIntervention(Base):
    __tablename__ = "coach_interventions"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="open")
    risk_score: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    expected_impact: Mapped[dict[str, Any]] = mapped_column(JSON)
    factors: Mapped[list[str]] = mapped_column(JSON)
    guardrail_pass: Mapped[bool] = mapped_column(Boolean, default=True)
    guardrail_reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    __table_args__ = (
        Index(
            "uq_intervention_open",
            "athlete_id",
            "action",
            unique=True,
            postgresql_where=(status == "open"),
        ),
    )


class AthletePreference(Base):
    __tablename__ = "athlete_preferences"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), unique=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_training_days: Mapped[list[str]] = mapped_column(JSON, default=["Mon", "Tue", "Thu", "Sat"])
    privacy_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_mode: Mapped[str] = mapped_column(String(20), default="manual")
    auto_apply_low_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_apply_confidence_min: Mapped[float] = mapped_column(Float, default=0.75)
    auto_apply_risk_max: Mapped[float] = mapped_column(Float, default=0.25)


class AppWriteLog(Base):
    __tablename__ = "app_write_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    log_type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class AppRuntimeError(Base):
    __tablename__ = "app_runtime_errors"
    id: Mapped[int] = mapped_column(primary_key=True)
    page: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class ImportRun(Base):
    __tablename__ = "import_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int | None] = mapped_column(ForeignKey("athletes.id"), index=True)
    adapter_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class ImportItem(Base):
    __tablename__ = "import_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="valid")
    message: Mapped[str] = mapped_column(String(255), default="")
