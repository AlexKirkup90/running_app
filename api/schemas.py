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
