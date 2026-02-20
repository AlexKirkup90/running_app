"""Pydantic response schemas for the REST API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Athletes ---

class AthleteOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    dob: Optional[date] = None
    max_hr: Optional[int] = None
    resting_hr: Optional[int] = None
    threshold_pace_sec_per_km: Optional[int] = None
    easy_pace_sec_per_km: Optional[int] = None
    status: str

    model_config = {"from_attributes": True}


# --- Check-ins ---

class CheckInOut(BaseModel):
    id: int
    athlete_id: int
    day: date
    sleep: int
    energy: int
    recovery: int
    stress: int
    training_today: bool
    readiness_score: Optional[float] = None
    readiness_band: Optional[str] = None

    model_config = {"from_attributes": True}


# --- Training Logs ---

class TrainingLogOut(BaseModel):
    id: int
    athlete_id: int
    date: date
    session_category: str
    duration_min: int
    distance_km: float
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_pace_sec_per_km: Optional[float] = None
    rpe: int
    load_score: float
    notes: str = ""
    pain_flag: bool = False

    model_config = {"from_attributes": True}


# --- Events ---

class EventOut(BaseModel):
    id: int
    athlete_id: int
    name: str
    event_date: date
    distance: str

    model_config = {"from_attributes": True}


# --- Plans ---

class PlanOut(BaseModel):
    id: int
    athlete_id: int
    race_goal: str
    weeks: int
    sessions_per_week: int
    max_session_min: int
    start_date: date
    status: str

    model_config = {"from_attributes": True}


class PlanWeekOut(BaseModel):
    id: int
    plan_id: int
    week_number: int
    phase: str
    week_start: date
    week_end: date
    sessions_order: list
    target_load: float
    locked: bool

    model_config = {"from_attributes": True}


class PlanDaySessionOut(BaseModel):
    id: int
    plan_week_id: int
    athlete_id: int
    session_day: date
    session_name: str
    source_template_name: str
    status: str

    model_config = {"from_attributes": True}


# --- Interventions ---

class InterventionOut(BaseModel):
    id: int
    athlete_id: int
    action_type: str
    status: str
    risk_score: float
    confidence_score: float
    expected_impact: dict
    why_factors: list
    guardrail_pass: bool
    guardrail_reason: str
    cooldown_until: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Recommendations ---

class RecommendationOut(BaseModel):
    action: str
    risk_score: float
    confidence_score: float
    expected_impact: dict
    why: list[str]
    guardrail_pass: bool
    guardrail_reason: str


# --- Webhooks ---

class WebhookRegister(BaseModel):
    url: str = Field(max_length=500)
    events: list[str] = Field(min_length=1)
    secret: Optional[str] = Field(default=None, max_length=200)


class WebhookOut(BaseModel):
    id: str
    url: str
    events: list[str]
    active: bool = True


# --- Generic ---

class MessageOut(BaseModel):
    message: str


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


# --- Auth ---

class ChangePasswordInput(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=10, max_length=128)


# --- Coach Dashboard ---

class CoachDashboardOut(BaseModel):
    total_athletes: int
    active_athletes: int
    open_interventions: int
    high_risk_count: int
    weekly_load: list[dict]


class CoachClientRow(BaseModel):
    athlete_id: int
    first_name: str
    last_name: str
    email: str
    status: str
    open_interventions: int
    risk_label: str
    last_checkin: Optional[date] = None
    last_log: Optional[date] = None

    model_config = {"from_attributes": True}


# --- Organizations (Phase 6) ---

class OrgOut(BaseModel):
    id: int
    name: str
    slug: str
    tier: str
    max_coaches: int
    max_athletes: int
    role: str  # caller's role within org
    coach_count: int = 0
    athlete_count: int = 0

class OrgCoachOut(BaseModel):
    user_id: int
    username: str
    role: str
    caseload_cap: int
    assigned_athletes: int = 0

class OrgAssignmentOut(BaseModel):
    id: int
    coach_user_id: int
    coach_username: str
    athlete_id: int
    athlete_name: str
    status: str

class CreateOrgInput(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=100)
    tier: str = Field(default="free")

class AssignAthleteInput(BaseModel):
    coach_user_id: int
    athlete_id: int

class TransferAthleteInput(BaseModel):
    new_coach_user_id: int


# --- Community & Social (Phase 7) ---

class TrainingGroupOut(BaseModel):
    id: int
    name: str
    description: str
    owner_user_id: int
    privacy: str
    max_members: int
    member_count: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TrainingGroupCreateInput(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    description: str = Field(default="", max_length=1000)
    privacy: str = Field(default="public")
    max_members: int = Field(default=50, ge=2, le=500)


class GroupMemberOut(BaseModel):
    id: int
    group_id: int
    athlete_id: int
    athlete_name: str = ""
    role: str
    joined_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChallengeOut(BaseModel):
    id: int
    group_id: Optional[int] = None
    name: str
    challenge_type: str
    target_value: float
    start_date: date
    end_date: date
    status: str
    created_by: int
    participant_count: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChallengeCreateInput(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    challenge_type: str = Field(default="distance")
    target_value: float = Field(gt=0)
    start_date: date
    end_date: date
    group_id: Optional[int] = None


class ChallengeEntryOut(BaseModel):
    id: int
    challenge_id: int
    athlete_id: int
    athlete_name: str = ""
    progress: float
    completed: bool
    last_updated: Optional[datetime] = None

    model_config = {"from_attributes": True}


class GroupMessageOut(BaseModel):
    id: int
    group_id: int
    author_athlete_id: int
    author_name: str = ""
    content: str
    message_type: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class GroupMessageCreateInput(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    message_type: str = Field(default="text")


class KudosOut(BaseModel):
    id: int
    from_athlete_id: int
    from_name: str = ""
    to_athlete_id: int
    to_name: str = ""
    training_log_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LeaderboardEntryOut(BaseModel):
    athlete_id: int
    name: str
    value: float
    rank: int
