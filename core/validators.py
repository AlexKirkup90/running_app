"""Pydantic validation models for all user-facing data entry points."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class CheckInInput(BaseModel):
    athlete_id: int = Field(gt=0)
    sleep: int = Field(ge=1, le=5)
    energy: int = Field(ge=1, le=5)
    recovery: int = Field(ge=1, le=5)
    stress: int = Field(ge=1, le=5)
    training_today: bool = True


class TrainingLogInput(BaseModel):
    athlete_id: int = Field(gt=0)
    session_category: str = Field(min_length=1, max_length=80)
    duration_min: int = Field(ge=0)
    distance_km: float = Field(ge=0.0)
    avg_hr: Optional[int] = Field(default=None, ge=30, le=250)
    max_hr: Optional[int] = Field(default=None, ge=30, le=250)
    avg_pace_sec_per_km: Optional[float] = Field(default=None, ge=0)
    rpe: int = Field(ge=1, le=10)
    notes: str = Field(default="", max_length=2000)
    pain_flag: bool = False

    @field_validator("max_hr")
    @classmethod
    def max_hr_gte_avg(cls, v, info):
        avg = info.data.get("avg_hr")
        if v is not None and avg is not None and v < avg:
            raise ValueError("max_hr must be >= avg_hr")
        return v


class PlanCreateInput(BaseModel):
    athlete_id: int = Field(gt=0)
    race_goal: str
    weeks: int = Field(ge=4, le=52)
    sessions_per_week: int = Field(ge=2, le=7)
    max_session_min: int = Field(ge=30, le=300)
    start_date: date

    @field_validator("race_goal")
    @classmethod
    def valid_race_goal(cls, v):
        allowed = {"5K", "10K", "Half Marathon", "Marathon"}
        if v not in allowed:
            raise ValueError(f"race_goal must be one of {allowed}")
        return v


class EventCreateInput(BaseModel):
    athlete_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=140)
    event_date: date
    distance: str

    @field_validator("distance")
    @classmethod
    def valid_distance(cls, v):
        allowed = {"5K", "10K", "Half Marathon", "Marathon", "Other"}
        if v not in allowed:
            raise ValueError(f"distance must be one of {allowed}")
        return v

    @field_validator("event_date")
    @classmethod
    def future_date(cls, v):
        if v < date.today():
            raise ValueError("event_date must not be in the past")
        return v


class ClientCreateInput(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    dob: date

    @field_validator("dob")
    @classmethod
    def reasonable_dob(cls, v):
        if v > date.today():
            raise ValueError("dob must be in the past")
        min_date = date(1900, 1, 1)
        if v < min_date:
            raise ValueError("dob must be after 1900")
        return v


class InterventionDecisionInput(BaseModel):
    intervention_id: int = Field(gt=0)
    decision: str
    note: str = Field(default="", max_length=1000)
    modified_action: Optional[str] = None

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, v):
        allowed = {"accept_and_close", "defer_24h", "defer_72h", "modify_action", "dismiss"}
        if v not in allowed:
            raise ValueError(f"decision must be one of {allowed}")
        return v
