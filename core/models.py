from __future__ import annotations

from datetime import date, datetime
from typing import Optional

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Athlete(Base):
    __tablename__ = "athletes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    dob: Mapped[Optional[date]] = mapped_column(Date)
    max_hr: Mapped[Optional[int]] = mapped_column(Integer)
    resting_hr: Mapped[Optional[int]] = mapped_column(Integer)
    threshold_pace_sec_per_km: Mapped[Optional[int]] = mapped_column(Integer)
    easy_pace_sec_per_km: Mapped[Optional[int]] = mapped_column(Integer)
    vdot_score: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    athlete_id: Mapped[Optional[int]] = mapped_column(ForeignKey("athletes.id"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    athlete = relationship("Athlete")


class SessionLibrary(Base):
    __tablename__ = "sessions_library"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), index=True)
    intent: Mapped[str] = mapped_column(String(40), default="general")
    energy_system: Mapped[str] = mapped_column(String(40), default="aerobic")
    tier: Mapped[str] = mapped_column(String(30), default="medium")
    is_treadmill: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_min: Mapped[int] = mapped_column(Integer)
    structure_json: Mapped[dict] = mapped_column(JSON, default=dict)
    targets_json: Mapped[dict] = mapped_column(JSON, default=dict)
    progression_json: Mapped[dict] = mapped_column(JSON, default=dict)
    regression_json: Mapped[dict] = mapped_column(JSON, default=dict)
    prescription: Mapped[str] = mapped_column(Text, default="")
    coaching_notes: Mapped[str] = mapped_column(Text, default="")


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    race_goal: Mapped[str] = mapped_column(String(30), nullable=False)
    weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    sessions_per_week: Mapped[int] = mapped_column(Integer, default=4)
    max_session_min: Mapped[int] = mapped_column(Integer, default=120)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    locked_until_week: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")


class PlanWeek(Base):
    __tablename__ = "plan_weeks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(30), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    sessions_order: Mapped[list] = mapped_column(JSON, default=list)
    target_load: Mapped[float] = mapped_column(Float, default=0)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("plan_id", "week_number", name="uq_plan_week"),)


class PlanDaySession(Base):
    __tablename__ = "plan_day_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_week_id: Mapped[int] = mapped_column(ForeignKey("plan_weeks.id"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    session_day: Mapped[date] = mapped_column(Date, index=True)
    session_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_template_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), default="planned")
    __table_args__ = (
        UniqueConstraint("athlete_id", "session_day", name="uq_plan_day_session_athlete_day"),
        UniqueConstraint("plan_week_id", "session_day", name="uq_plan_day_session_week_day"),
    )


class PlanWeekMetric(Base):
    __tablename__ = "plan_week_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_week_id: Mapped[int] = mapped_column(ForeignKey("plan_weeks.id"), index=True)
    planned_minutes: Mapped[int] = mapped_column(Integer, default=0)
    planned_load: Mapped[float] = mapped_column(Float, default=0)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    distance: Mapped[str] = mapped_column(String(30), nullable=False)


class CheckIn(Base):
    __tablename__ = "checkins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    sleep: Mapped[int] = mapped_column(Integer, nullable=False)
    energy: Mapped[int] = mapped_column(Integer, nullable=False)
    recovery: Mapped[int] = mapped_column(Integer, nullable=False)
    stress: Mapped[int] = mapped_column(Integer, nullable=False)
    training_today: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        UniqueConstraint("athlete_id", "day", name="uq_checkin_athlete_day"),
        CheckConstraint("sleep between 1 and 5"),
        CheckConstraint("energy between 1 and 5"),
        CheckConstraint("recovery between 1 and 5"),
        CheckConstraint("stress between 1 and 5"),
    )


class TrainingLog(Base):
    __tablename__ = "training_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    session_category: Mapped[str] = mapped_column(String(80))
    duration_min: Mapped[int] = mapped_column(Integer)
    distance_km: Mapped[float] = mapped_column(Float, default=0)
    avg_hr: Mapped[Optional[int]] = mapped_column(Integer)
    max_hr: Mapped[Optional[int]] = mapped_column(Integer)
    avg_pace_sec_per_km: Mapped[Optional[float]] = mapped_column(Float)
    rpe: Mapped[int] = mapped_column(Integer)
    load_score: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    pain_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(40), default="manual")  # manual, garmin, strava
    source_id: Mapped[Optional[str]] = mapped_column(String(120))  # external activity ID
    __table_args__ = (
        CheckConstraint("duration_min >= 0"),
        CheckConstraint("distance_km >= 0"),
        CheckConstraint("rpe between 1 and 10"),
        CheckConstraint("load_score >= 0"),
    )


class SessionReflection(Base):
    __tablename__ = "session_reflections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    training_log_id: Mapped[int] = mapped_column(ForeignKey("training_logs.id"), unique=True)
    confidence: Mapped[int] = mapped_column(Integer, default=3)
    reflection: Mapped[str] = mapped_column(Text, default="")


class CoachActionLog(Base):
    __tablename__ = "coach_action_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoachNotesTask(Base):
    __tablename__ = "coach_notes_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class CoachIntervention(Base):
    __tablename__ = "coach_interventions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open")
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    expected_impact: Mapped[dict] = mapped_column(JSON, default=dict)
    why_factors: Mapped[list] = mapped_column(JSON, default=list)
    guardrail_pass: Mapped[bool] = mapped_column(Boolean, default=True)
    guardrail_reason: Mapped[str] = mapped_column(String(255), default="ok")
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AthletePreference(Base):
    __tablename__ = "athlete_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), unique=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_training_days: Mapped[list] = mapped_column(JSON, default=list)
    privacy_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_mode: Mapped[str] = mapped_column(String(20), default="manual")
    auto_apply_low_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_apply_confidence_min: Mapped[float] = mapped_column(Float, default=0.8)
    auto_apply_risk_max: Mapped[float] = mapped_column(Float, default=0.3)


class AppWriteLog(Base):
    __tablename__ = "app_write_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(80))
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AppRuntimeError(Base):
    __tablename__ = "app_runtime_errors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page: Mapped[str] = mapped_column(String(80))
    error_message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ImportRun(Base):
    __tablename__ = "import_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    adapter_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="started")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ImportItem(Base):
    __tablename__ = "import_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"), index=True)
    athlete_id: Mapped[Optional[int]] = mapped_column(ForeignKey("athletes.id"))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    message: Mapped[str] = mapped_column(String(255), default="")


class WearableConnection(Base):
    __tablename__ = "wearable_connections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    service: Mapped[str] = mapped_column(String(40), nullable=False)  # "garmin", "strava"
    access_token: Mapped[str] = mapped_column(Text, default="")
    refresh_token: Mapped[Optional[str]] = mapped_column(Text)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    external_athlete_id: Mapped[Optional[str]] = mapped_column(String(120))
    scope: Mapped[str] = mapped_column(String(255), default="")
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sync_cursor: Mapped[Optional[str]] = mapped_column(String(255))
    sync_status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("athlete_id", "service", name="uq_wearable_athlete_service"),)


class SyncLog(Base):
    __tablename__ = "sync_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    service: Mapped[str] = mapped_column(String(40), nullable=False)
    sync_type: Mapped[str] = mapped_column(String(20), default="manual")  # manual, scheduled, webhook
    status: Mapped[str] = mapped_column(String(20), default="started")
    activities_found: Mapped[int] = mapped_column(Integer, default=0)
    activities_imported: Mapped[int] = mapped_column(Integer, default=0)
    activities_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


# ── Community & Social ────────────────────────────────────────────────────


class TrainingGroup(Base):
    __tablename__ = "training_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    privacy: Mapped[str] = mapped_column(String(20), default="public")  # public, private, invite_only
    max_members: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("training_groups.id"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="member")  # member, admin
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("group_id", "athlete_id", name="uq_group_member"),)


class Challenge(Base):
    __tablename__ = "challenges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_groups.id"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    challenge_type: Mapped[str] = mapped_column(String(40), nullable=False)  # distance, duration, streak, elevation
    target_value: Mapped[float] = mapped_column(Float, nullable=False)  # km, minutes, days, meters
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, cancelled
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChallengeEntry(Base):
    __tablename__ = "challenge_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    progress: Mapped[float] = mapped_column(Float, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("challenge_id", "athlete_id", name="uq_challenge_entry"),)


class GroupMessage(Base):
    __tablename__ = "group_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("training_groups.id"), index=True)
    author_athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), default="text")  # text, achievement, kudos
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Kudos(Base):
    __tablename__ = "kudos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    to_athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    training_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_logs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("from_athlete_id", "to_athlete_id", "training_log_id", name="uq_kudos"),)


# ── Team & Organization ──────────────────────────────────────────────────


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tier: Mapped[str] = mapped_column(String(30), default="free")  # free, pro, enterprise
    max_coaches: Mapped[int] = mapped_column(Integer, default=1)
    max_athletes: Mapped[int] = mapped_column(Integer, default=20)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrgMembership(Base):
    __tablename__ = "org_memberships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    org_role: Mapped[str] = mapped_column(String(30), nullable=False)  # owner, head_coach, coach, assistant
    caseload_cap: Mapped[int] = mapped_column(Integer, default=20)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_org_user"),)


class CoachAssignment(Base):
    __tablename__ = "coach_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    coach_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused, transferred
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("org_id", "athlete_id", name="uq_org_athlete_assignment"),)


Index("ix_logs_athlete_date", TrainingLog.athlete_id, TrainingLog.date)
Index("ix_intervention_open", CoachIntervention.athlete_id, CoachIntervention.action_type, unique=False, postgresql_where=(CoachIntervention.status == "open"))
