"""Database seeder using Daniels-informed session catalog (v3 structures).

Generates session library entries from the workout catalog with prescriptive
interval blocks, Daniels pace labels, and workout-specific progression/regression
rules — replacing the legacy v2 zone-based templates.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from core.db import session_scope
from core.models import Athlete, AthletePreference, CheckIn, CoachAssignment, Event, OrgMembership, Organization, Plan, PlanDaySession, PlanWeek, SessionLibrary, TrainingLog, User
from core.security import hash_password
from core.services.planning import assign_week_sessions, generate_plan_weeks
from core.services.session_catalog import (
    CATALOG,
    build_prescriptive_progression,
    build_prescriptive_regression,
    build_prescriptive_structure,
    build_prescriptive_targets,
)


def build_session_contract(workout_name: str, duration: int, variant: str, tier: str) -> dict[str, Any]:
    """Build a v3 session contract from the Daniels catalog.

    Uses prescriptive interval blocks, Daniels pace labels, and
    workout-specific progression/regression rules.
    """
    wt = CATALOG[workout_name]
    structure = build_prescriptive_structure(wt, duration, environment=variant)
    targets = build_prescriptive_targets(wt)
    progression = build_prescriptive_progression(wt)
    regression = build_prescriptive_regression(wt)

    # Tier-specific adjustments to main_set duration
    main_block = next((b for b in structure["blocks"] if b["phase"] == "main_set"), None)
    if main_block:
        base_dur = main_block["duration_min"]
        if tier == "short":
            main_block["duration_min"] = max(8, int(base_dur * 0.75))
            progression["tier_rule"] = {"trigger": "2 consecutive successful completions", "action": "Advance to medium tier"}
        elif tier == "long":
            main_block["duration_min"] = int(base_dur * 1.2)
            regression["tier_rule"] = {"trigger": "HR drift early or RPE exceeds target", "action": "Step back to medium tier"}

    return {
        "intent": wt.intent,
        "energy_system": wt.energy_system,
        "structure_json": structure,
        "targets_json": targets,
        "progression_json": progression,
        "regression_json": regression,
        "coaching_notes": wt.coaching_cues or "Adapt daily targets using readiness, pain status, and recent load trends.",
        "prescription": f"{wt.name}: {duration} min with Daniels {wt.daniels_pace}-pace guidance.",
    }


# Core workout types to seed (covers all categories)
SEED_WORKOUT_NAMES = [
    "Easy Run",
    "Recovery Run",
    "Long Run",
    "Long Run with M-Pace Finish",
    "Marathon Pace Run",
    "Tempo Run",
    "Cruise Intervals",
    "Threshold Repeats",
    "VO2max Intervals",
    "VO2max Short Intervals",
    "Repetitions",
    "Hill Repeats",
    "Fartlek",
    "Strides",
    "Race Pace Run",
    "Race Rehearsal",
    "Benchmark / Time Trial",
    "Taper / Openers",
    "Cross-Training",
]


def run_migrations() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


def seed_sessions() -> None:
    with session_scope() as s:
        existing = s.execute(select(SessionLibrary.id)).first()
        if existing:
            return
        rows = []
        for workout_name in SEED_WORKOUT_NAMES:
            for duration in [25, 35, 45, 55, 65]:
                for variant in ["outdoor", "treadmill"]:
                    for tier in ["short", "medium", "long"]:
                        contract = build_session_contract(workout_name, duration, variant, tier)
                        cat = CATALOG[workout_name].category
                        name = f"{workout_name} {duration}min {variant} {tier}"
                        rows.append(
                            SessionLibrary(
                                name=name,
                                category=cat,
                                intent=contract["intent"],
                                energy_system=contract["energy_system"],
                                tier=tier,
                                is_treadmill=variant == "treadmill",
                                duration_min=duration,
                                structure_json=contract["structure_json"],
                                targets_json=contract["targets_json"],
                                progression_json=contract["progression_json"],
                                regression_json=contract["regression_json"],
                                coaching_notes=contract["coaching_notes"],
                                prescription=contract["prescription"],
                            )
                        )
        s.add_all(rows[:120])


# Demo VDOT scores by race goal for seed athletes
_DEMO_VDOT = {"5K": 50, "10K": 48, "Half Marathon": 45, "Marathon": 43}


def seed_users_athletes() -> None:
    with session_scope() as s:
        coach = s.execute(select(User).where(User.username == "coach")).scalar_one_or_none()
        if not coach:
            s.add(User(username="coach", role="coach", password_hash=hash_password("CoachPass!234"), must_change_password=False))

        race_goals = ["5K", "10K", "Half Marathon", "Marathon"]
        for idx in range(1, 5):
            email = f"athlete{idx}@demo.run"
            athlete = s.execute(select(Athlete).where(Athlete.email == email)).scalar_one_or_none()
            if not athlete:
                goal = race_goals[idx - 1]
                vdot = _DEMO_VDOT[goal]
                athlete = Athlete(
                    first_name=f"Demo{idx}",
                    last_name="Runner",
                    email=email,
                    dob=date(1990, 1, idx),
                    max_hr=190 - idx,
                    resting_hr=54 + idx,
                    threshold_pace_sec_per_km=275 + idx * 7,
                    easy_pace_sec_per_km=340 + idx * 8,
                    vdot_score=vdot,
                )
                s.add(athlete)
                s.flush()
                s.add(User(username=f"athlete{idx}", role="client", athlete_id=athlete.id, password_hash=hash_password("AthletePass!234"), must_change_password=False))
                s.add(AthletePreference(athlete_id=athlete.id, reminder_training_days=["Mon", "Tue", "Thu", "Sat"], privacy_ack=True, automation_mode="assisted", auto_apply_low_risk=True))

            # Skip plan creation if athlete already has an active plan
            existing_plan = s.execute(select(Plan.id).where(Plan.athlete_id == athlete.id, Plan.status == "active")).first()
            if existing_plan:
                continue

            goal = race_goals[idx - 1]
            plan = Plan(athlete_id=athlete.id, race_goal=goal, weeks=24, sessions_per_week=4, max_session_min=140, start_date=date.today() - timedelta(days=28))
            s.add(plan)
            s.flush()
            weeks = generate_plan_weeks(plan.start_date, plan.weeks, plan.race_goal, plan.sessions_per_week, plan.max_session_min)
            seen_days: set[tuple[int, date]] = set()
            for w in weeks:
                week = PlanWeek(plan_id=plan.id, **w)
                s.add(week)
                s.flush()
                assignments = assign_week_sessions(week.week_start, week.sessions_order)
                for a in assignments:
                    key = (athlete.id, a["session_day"])
                    if key in seen_days:
                        continue
                    seen_days.add(key)
                    s.add(
                        PlanDaySession(
                            plan_week_id=week.id,
                            athlete_id=athlete.id,
                            session_day=a["session_day"],
                            session_name=a["session_name"],
                            source_template_name=a["session_name"],
                            status="planned",
                        )
                    )

            s.add(Event(athlete_id=athlete.id, name=f"Goal {plan.race_goal}", event_date=date.today() + timedelta(days=120), distance=plan.race_goal))
            for d in range(21):
                log_date = date.today() - timedelta(days=d)
                s.add(TrainingLog(athlete_id=athlete.id, date=log_date, session_category="Easy Run", duration_min=35 + d % 4 * 5, distance_km=6 + d % 3, rpe=4 + d % 4, load_score=30 + d % 15))
                if d % 2 == 0:
                    s.add(CheckIn(athlete_id=athlete.id, day=log_date, sleep=3 + d % 2, energy=3, recovery=3, stress=2 + d % 2, training_today=True))


def seed_organization() -> None:
    """Seed a demo organization with coach membership and athlete assignments."""
    with session_scope() as s:
        existing = s.execute(select(Organization).where(Organization.slug == "run-season-elite")).scalar_one_or_none()
        if existing:
            return

        org = Organization(
            name="Run Season Elite",
            slug="run-season-elite",
            tier="pro",
            max_coaches=5,
            max_athletes=50,
        )
        s.add(org)
        s.flush()

        # Add the coach as owner
        coach = s.execute(select(User).where(User.username == "coach")).scalar_one_or_none()
        if coach:
            s.add(OrgMembership(org_id=org.id, user_id=coach.id, org_role="owner", caseload_cap=30))

            # Add a second coach (assistant) for demo
            assistant = s.execute(select(User).where(User.username == "coach2")).scalar_one_or_none()
            if not assistant:
                assistant = User(username="coach2", role="coach", password_hash=hash_password("CoachPass!234"), must_change_password=False)
                s.add(assistant)
                s.flush()
            s.add(OrgMembership(org_id=org.id, user_id=assistant.id, org_role="coach", caseload_cap=15))

            # Assign athletes to coaches
            athletes = s.execute(select(Athlete)).scalars().all()
            for i, athlete in enumerate(athletes):
                assigned_coach = coach if i < 2 else assistant
                s.add(CoachAssignment(
                    org_id=org.id,
                    coach_user_id=assigned_coach.id,
                    athlete_id=athlete.id,
                    status="active",
                ))


def backfill_plan_day_sessions() -> None:
    with session_scope() as s:
        weeks = s.execute(
            select(PlanWeek.id, PlanWeek.week_start, PlanWeek.sessions_order, Plan.athlete_id).join(Plan, Plan.id == PlanWeek.plan_id)
        ).all()
        for week_id, week_start, sessions_order, athlete_id in weeks:
            existing = s.execute(select(PlanDaySession.id).where(PlanDaySession.plan_week_id == week_id)).first()
            if existing:
                continue
            if not isinstance(sessions_order, list) or not sessions_order:
                continue
            assignments = assign_week_sessions(week_start, sessions_order)
            try:
                nested = s.begin_nested()
                s.add_all(
                    [
                        PlanDaySession(
                            plan_week_id=week_id,
                            athlete_id=athlete_id,
                            session_day=a["session_day"],
                            session_name=a["session_name"],
                            source_template_name=a["session_name"],
                            status="planned",
                        )
                        for a in assignments
                    ]
                )
                s.flush()
                nested.commit()
            except Exception:
                nested.rollback()


def main() -> None:
    run_migrations()
    seed_sessions()
    seed_users_athletes()
    backfill_plan_day_sessions()
    seed_organization()
    print("Seeding complete")


if __name__ == "__main__":
    main()
