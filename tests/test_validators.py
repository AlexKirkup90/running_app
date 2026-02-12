"""Tests for Pydantic input validation models."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from core.validators import (
    CheckInInput,
    ClientCreateInput,
    EventCreateInput,
    InterventionDecisionInput,
    PlanCreateInput,
    TrainingLogInput,
)


# --- CheckInInput ---

def test_checkin_valid():
    ci = CheckInInput(athlete_id=1, sleep=4, energy=3, recovery=5, stress=2)
    assert ci.sleep == 4
    assert ci.training_today is True


def test_checkin_out_of_range_sleep():
    with pytest.raises(ValidationError):
        CheckInInput(athlete_id=1, sleep=0, energy=3, recovery=3, stress=3)


def test_checkin_out_of_range_stress_high():
    with pytest.raises(ValidationError):
        CheckInInput(athlete_id=1, sleep=3, energy=3, recovery=3, stress=6)


def test_checkin_invalid_athlete_id():
    with pytest.raises(ValidationError):
        CheckInInput(athlete_id=0, sleep=3, energy=3, recovery=3, stress=3)


# --- TrainingLogInput ---

def test_training_log_valid():
    tl = TrainingLogInput(
        athlete_id=1, session_category="Easy Run", duration_min=45,
        distance_km=8.0, rpe=5
    )
    assert tl.avg_hr is None
    assert tl.pain_flag is False


def test_training_log_valid_with_hr():
    tl = TrainingLogInput(
        athlete_id=1, session_category="Tempo", duration_min=60,
        distance_km=12.0, avg_hr=150, max_hr=175, rpe=7
    )
    assert tl.avg_hr == 150
    assert tl.max_hr == 175


def test_training_log_max_hr_less_than_avg():
    with pytest.raises(ValidationError, match="max_hr must be >= avg_hr"):
        TrainingLogInput(
            athlete_id=1, session_category="Run", duration_min=30,
            distance_km=5.0, avg_hr=160, max_hr=140, rpe=5
        )


def test_training_log_rpe_out_of_range():
    with pytest.raises(ValidationError):
        TrainingLogInput(
            athlete_id=1, session_category="Run", duration_min=30,
            distance_km=5.0, rpe=11
        )


def test_training_log_negative_distance():
    with pytest.raises(ValidationError):
        TrainingLogInput(
            athlete_id=1, session_category="Run", duration_min=30,
            distance_km=-1.0, rpe=5
        )


# --- PlanCreateInput ---

def test_plan_create_valid():
    p = PlanCreateInput(
        athlete_id=1, race_goal="Marathon", weeks=24,
        sessions_per_week=4, max_session_min=140, start_date=date.today()
    )
    assert p.race_goal == "Marathon"


def test_plan_create_invalid_race_goal():
    with pytest.raises(ValidationError, match="race_goal"):
        PlanCreateInput(
            athlete_id=1, race_goal="Ultra", weeks=12,
            sessions_per_week=4, max_session_min=120, start_date=date.today()
        )


def test_plan_create_weeks_too_low():
    with pytest.raises(ValidationError):
        PlanCreateInput(
            athlete_id=1, race_goal="5K", weeks=2,
            sessions_per_week=3, max_session_min=60, start_date=date.today()
        )


def test_plan_create_sessions_per_week_too_high():
    with pytest.raises(ValidationError):
        PlanCreateInput(
            athlete_id=1, race_goal="10K", weeks=12,
            sessions_per_week=8, max_session_min=120, start_date=date.today()
        )


# --- EventCreateInput ---

def test_event_create_valid():
    e = EventCreateInput(
        athlete_id=1, name="Spring 10K", event_date=date.today() + timedelta(days=30),
        distance="10K"
    )
    assert e.name == "Spring 10K"


def test_event_create_invalid_distance():
    with pytest.raises(ValidationError, match="distance"):
        EventCreateInput(
            athlete_id=1, name="Race", event_date=date.today() + timedelta(days=7),
            distance="100K"
        )


def test_event_create_past_date():
    with pytest.raises(ValidationError, match="event_date"):
        EventCreateInput(
            athlete_id=1, name="Old Race", event_date=date.today() - timedelta(days=1),
            distance="5K"
        )


# --- ClientCreateInput ---

def test_client_create_valid():
    c = ClientCreateInput(
        first_name="Jane", last_name="Doe",
        email="jane@example.com", dob=date(1990, 5, 15)
    )
    assert c.email == "jane@example.com"


def test_client_create_invalid_email():
    with pytest.raises(ValidationError):
        ClientCreateInput(
            first_name="Jane", last_name="Doe",
            email="not-an-email", dob=date(1990, 1, 1)
        )


def test_client_create_future_dob():
    with pytest.raises(ValidationError, match="dob"):
        ClientCreateInput(
            first_name="Jane", last_name="Doe",
            email="jane@example.com", dob=date.today() + timedelta(days=1)
        )


def test_client_create_empty_name():
    with pytest.raises(ValidationError):
        ClientCreateInput(
            first_name="", last_name="Doe",
            email="jane@example.com", dob=date(1990, 1, 1)
        )


# --- InterventionDecisionInput ---

def test_intervention_decision_valid():
    d = InterventionDecisionInput(
        intervention_id=5, decision="accept_and_close", note="Looks good"
    )
    assert d.decision == "accept_and_close"


def test_intervention_decision_invalid():
    with pytest.raises(ValidationError, match="decision"):
        InterventionDecisionInput(intervention_id=5, decision="invalid_choice")


def test_intervention_decision_modify_with_action():
    d = InterventionDecisionInput(
        intervention_id=5, decision="modify_action",
        modified_action="taper_week"
    )
    assert d.modified_action == "taper_week"
