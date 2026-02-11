from __future__ import annotations

from datetime import date, timedelta

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from core.db import session_scope
from core.models import Athlete, AthletePreference, CheckIn, Event, Plan, PlanWeek, SessionLibrary, TrainingLog, User
from core.security import hash_password
from core.services.planning import generate_plan_weeks

CATEGORIES = [
    "Easy Run",
    "Long Run",
    "Recovery Run",
    "Tempo / Threshold",
    "VO2 Intervals",
    "Hill Repeats",
    "Race Pace",
    "Strides / Neuromuscular",
    "Benchmark / Time Trial",
    "Taper / Openers",
    "Cross-Training Optional",
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
        for cat in CATEGORIES:
            for duration in [25, 35, 45, 55, 65]:
                for variant in ["outdoor", "treadmill"]:
                    for tier in ["short", "medium", "long"]:
                        name = f"{cat} {duration}min {variant} {tier}"
                        blocks = {
                            "warmup_min": max(8, duration // 5),
                            "main": [{"type": cat, "minutes": max(10, duration - 15)}],
                            "cooldown_min": 5,
                        }
                        rows.append(
                            SessionLibrary(
                                name=name,
                                category=cat,
                                tier=tier,
                                is_treadmill=variant == "treadmill",
                                duration_min=duration,
                                structure_json=blocks,
                                prescription=f"{cat} progression with {variant} focus for {tier} tier",
                            )
                        )
        s.add_all(rows[:120])


def seed_users_athletes() -> None:
    with session_scope() as s:
        coach = s.execute(select(User).where(User.username == "coach")).scalar_one_or_none()
        if not coach:
            s.add(User(username="coach", role="coach", password_hash=hash_password("CoachPass!234"), must_change_password=False))

        for idx in range(1, 5):
            email = f"athlete{idx}@demo.run"
            athlete = s.execute(select(Athlete).where(Athlete.email == email)).scalar_one_or_none()
            if not athlete:
                athlete = Athlete(first_name=f"Demo{idx}", last_name="Runner", email=email, dob=date(1990, 1, idx))
                s.add(athlete)
                s.flush()
                s.add(User(username=f"athlete{idx}", role="client", athlete_id=athlete.id, password_hash=hash_password("AthletePass!234"), must_change_password=False))
                s.add(AthletePreference(athlete_id=athlete.id, reminder_training_days=["Mon", "Tue", "Thu", "Sat"], privacy_ack=True, automation_mode="assisted", auto_apply_low_risk=True))

                plan = Plan(athlete_id=athlete.id, race_goal=["5K", "10K", "Half Marathon", "Marathon"][idx - 1], weeks=24, sessions_per_week=4, max_session_min=140, start_date=date.today() - timedelta(days=28))
                s.add(plan)
                s.flush()
                weeks = generate_plan_weeks(plan.start_date, plan.weeks, plan.race_goal, plan.sessions_per_week, plan.max_session_min)
                s.add_all([PlanWeek(plan_id=plan.id, **w) for w in weeks])

                s.add(Event(athlete_id=athlete.id, name=f"Goal {plan.race_goal}", event_date=date.today() + timedelta(days=120), distance=plan.race_goal))
                for d in range(21):
                    log_date = date.today() - timedelta(days=d)
                    s.add(TrainingLog(athlete_id=athlete.id, date=log_date, session_category="Easy Run", duration_min=35 + d % 4 * 5, distance_km=6 + d % 3, rpe=4 + d % 4, load_score=30 + d % 15))
                    if d % 2 == 0:
                        s.add(CheckIn(athlete_id=athlete.id, day=log_date, sleep=3 + d % 2, energy=3, recovery=3, stress=2 + d % 2, training_today=True))


def main() -> None:
    run_migrations()
    seed_sessions()
    seed_users_athletes()
    print("Seeding complete")


if __name__ == "__main__":
    main()
