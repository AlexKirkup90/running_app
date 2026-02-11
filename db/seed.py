from __future__ import annotations

from datetime import date, timedelta
from typing import Any

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

INTENT_MAP = {
    "Easy Run": ("easy_aerobic", "aerobic_base"),
    "Long Run": ("long_run", "aerobic_durability"),
    "Recovery Run": ("recovery", "active_recovery"),
    "Tempo / Threshold": ("threshold", "lactate_threshold"),
    "VO2 Intervals": ("vo2", "vo2max"),
    "Hill Repeats": ("hill_strength", "neuromuscular_strength"),
    "Race Pace": ("race_specific", "race_specific"),
    "Strides / Neuromuscular": ("strides", "neuromuscular_speed"),
    "Benchmark / Time Trial": ("benchmark", "assessment"),
    "Taper / Openers": ("taper_opener", "race_priming"),
    "Cross-Training Optional": ("cross_train", "aerobic_support"),
}


def build_session_contract(category: str, duration: int, variant: str, tier: str) -> dict[str, Any]:
    warmup = max(10, duration // 5)
    cooldown = 8 if duration >= 45 else 6
    main_duration = max(12, duration - warmup - cooldown)
    intent, energy_system = INTENT_MAP[category]
    base_targets: dict[str, Any] = {
        "primary": {"pace_zone": "Z2", "hr_zone": "Z2", "rpe_range": [3, 4]},
        "secondary": {"cadence_spm": [168, 182], "terrain": "flat_or_rolling"},
    }
    blocks = [
        {
            "phase": "warmup",
            "duration_min": warmup,
            "instructions": "Easy jog, include mobility and two drills.",
            "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]},
        },
        {
            "phase": "main_set",
            "duration_min": main_duration,
            "instructions": f"{category} specific set adjusted to {tier} tier.",
            "target": base_targets["primary"],
        },
        {
            "phase": "cooldown",
            "duration_min": cooldown,
            "instructions": "Relaxed jog, then light mobility work.",
            "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]},
        },
    ]

    if category == "Tempo / Threshold":
        base_targets["primary"] = {"pace_zone": "Z3-Z4", "hr_zone": "Z3-Z4", "rpe_range": [6, 7]}
        blocks[1]["instructions"] = "2-4 repeats at threshold with controlled float recoveries."
        blocks[1]["target"] = base_targets["primary"]
    elif category == "VO2 Intervals":
        base_targets["primary"] = {"pace_zone": "Z5", "hr_zone": "Z4-Z5", "rpe_range": [8, 9]}
        blocks[1]["instructions"] = "Hard interval reps with equal or slightly shorter recoveries."
        blocks[1]["target"] = base_targets["primary"]
    elif category == "Hill Repeats":
        base_targets["primary"] = {"pace_zone": "Hill Effort", "hr_zone": "Z4", "rpe_range": [7, 8]}
        blocks[1]["instructions"] = "Short hill repeats with jog-back recovery and stable form."
        blocks[1]["target"] = base_targets["primary"]
    elif category == "Race Pace":
        base_targets["primary"] = {"pace_zone": "Race Pace", "hr_zone": "Z3-Z4", "rpe_range": [6, 8]}
        blocks[1]["instructions"] = "Race-pace blocks with pacing discipline and steady cadence."
        blocks[1]["target"] = base_targets["primary"]
    elif category == "Strides / Neuromuscular":
        base_targets["primary"] = {"pace_zone": "Strides", "hr_zone": "Z2-Z4", "rpe_range": [5, 7]}
        blocks[1]["instructions"] = "6-10 strides with full recovery and smooth mechanics."
        blocks[1]["target"] = base_targets["primary"]
    elif category == "Benchmark / Time Trial":
        base_targets["primary"] = {"pace_zone": "Benchmark", "hr_zone": "Z4-Z5", "rpe_range": [8, 9]}
        blocks[1]["instructions"] = "Controlled time trial effort to benchmark current fitness."
        blocks[1]["target"] = base_targets["primary"]
    elif category == "Taper / Openers":
        base_targets["primary"] = {"pace_zone": "Z2-Z4", "hr_zone": "Z2-Z4", "rpe_range": [4, 6]}
        blocks[1]["instructions"] = "Short openers to prime neuromuscular system without excess fatigue."
        blocks[1]["target"] = base_targets["primary"]
    elif category == "Cross-Training Optional":
        base_targets["primary"] = {"pace_zone": "N/A", "hr_zone": "Z1-Z2", "rpe_range": [2, 4]}
        blocks[1]["instructions"] = "Low-impact aerobic cross-training session."
        blocks[1]["target"] = base_targets["primary"]

    progression = {
        "increase_one": "Add 5-10 min total duration next week if readiness >= 3.5 and no pain flags.",
        "increase_two": "Add one quality rep or 2-3 min at target pace in main set.",
    }
    regression = {
        "reduce_one": "Trim 15-20% main-set volume when readiness < 3.0 or soreness elevated.",
        "reduce_two": "Swap to easy aerobic run when pain flag is true.",
    }
    if tier == "short":
        progression["tier_rule"] = "Advance to medium when two consecutive completions are successful."
    elif tier == "medium":
        progression["tier_rule"] = "Advance to long when quality and recovery remain stable."
    else:
        regression["tier_rule"] = "Step back to medium tier if HR drifts early or RPE exceeds target."

    return {
        "intent": intent,
        "energy_system": energy_system,
        "structure_json": {
            "version": 2,
            "environment": variant,
            "blocks": blocks,
            "fueling_hint": "Hydrate pre-session; add carbs for sessions >60 min.",
            "success_criteria": "Hit target zones with stable mechanics and controlled effort.",
        },
        "targets_json": base_targets,
        "progression_json": progression,
        "regression_json": regression,
        "coaching_notes": "Adapt daily targets using readiness, pain status, and recent load trends.",
        "prescription": f"{category}: {main_duration} min main set with explicit pace/HR/RPE guidance.",
    }


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
                        contract = build_session_contract(cat, duration, variant, tier)
                        name = f"{cat} {duration}min {variant} {tier}"
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


def seed_users_athletes() -> None:
    with session_scope() as s:
        coach = s.execute(select(User).where(User.username == "coach")).scalar_one_or_none()
        if not coach:
            s.add(User(username="coach", role="coach", password_hash=hash_password("CoachPass!234"), must_change_password=False))

        for idx in range(1, 5):
            email = f"athlete{idx}@demo.run"
            athlete = s.execute(select(Athlete).where(Athlete.email == email)).scalar_one_or_none()
            if not athlete:
                athlete = Athlete(
                    first_name=f"Demo{idx}",
                    last_name="Runner",
                    email=email,
                    dob=date(1990, 1, idx),
                    max_hr=190 - idx,
                    resting_hr=54 + idx,
                    threshold_pace_sec_per_km=275 + idx * 7,
                    easy_pace_sec_per_km=340 + idx * 8,
                )
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
