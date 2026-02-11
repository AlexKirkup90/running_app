from __future__ import annotations

import datetime as dt
import subprocess

from sqlalchemy import text

from core.auth.security import hash_password
from core.db import db_session
from core.services.planning import generate_plan

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


def run_migrations():
    subprocess.run(["alembic", "upgrade", "head"], check=True)


def session_templates():
    items = []
    variants = [("short", 30), ("medium", 50), ("long", 80)]
    envs = [("outdoor", False), ("treadmill", True)]
    i = 0
    for cat in CATEGORIES:
        for var, dur in variants:
            for env, indoor in envs:
                for step in range(1, 3):
                    i += 1
                    d = dur + step * 5
                    blocks = {
                        "warmup": f"{max(10, d//5)} min easy",
                        "main": f"{d - 15} min {cat.lower()}",
                        "cooldown": "10 min easy",
                        "environment": env,
                    }
                    items.append((f"{cat} {var} {env} v{step}", cat, d, indoor, blocks, f"Run {d} minutes as {cat}."))
    return items[:110]


def seed_data():
    with db_session() as s:
        count = s.execute(text("select count(*) from sessions_library")).scalar_one()
        if count < 100:
            for name, cat, dur, indoor, blocks, pres in session_templates():
                s.execute(
                    text(
                        "insert into sessions_library(name,category,duration_min,indoor_ok,blocks_json,prescription) "
                        "values (:n,:c,:d,:i,:b,:p)"
                    ),
                    {"n": name, "c": cat, "d": dur, "i": indoor, "b": blocks, "p": pres},
                )

        s.execute(
            text(
                "insert into athletes(first_name,last_name,email,status) values "
                "('Demo','Runner','demo.runner@example.com','active') on conflict (email) do nothing"
            )
        )
        athlete_id = s.execute(text("select id from athletes where email='demo.runner@example.com'")) .scalar_one()

        s.execute(
            text(
                "insert into users(username,password_hash,role,athlete_id,must_change_password) "
                "values (:u,:p,'coach',null,false) on conflict (username) do nothing"
            ),
            {"u": "coach_admin", "p": hash_password("CoachStrong!123")},
        )
        s.execute(
            text(
                "insert into users(username,password_hash,role,athlete_id,must_change_password) "
                "values (:u,:p,'client',:aid,true) on conflict (username) do nothing"
            ),
            {"u": "demorunner", "p": hash_password("RunnerStart!123"), "aid": athlete_id},
        )

        s.execute(
            text(
                "insert into athlete_preferences(athlete_id,privacy_ack,automation_mode,auto_apply_low_risk) "
                "values (:aid,true,'assisted',true) on conflict (athlete_id) do nothing"
            ),
            {"aid": athlete_id},
        )

        existing_plan = s.execute(text("select id from plans where athlete_id=:aid"), {"aid": athlete_id}).scalar()
        if not existing_plan:
            start = dt.date.today() - dt.timedelta(days=14)
            s.execute(
                text(
                    "insert into plans(athlete_id,goal_race,weeks,sessions_per_week,max_session_duration,start_date) "
                    "values (:aid,'Half Marathon',24,4,120,:sd)"
                ),
                {"aid": athlete_id, "sd": start},
            )
            plan_id = s.execute(text("select currval(pg_get_serial_sequence('plans','id'))")).scalar_one()
            for w in generate_plan(start, "Half Marathon", 24, 4):
                s.execute(
                    text(
                        "insert into plan_weeks(plan_id,week_index,week_start,phase,focus,target_load,sessions_order) "
                        "values (:pid,:wi,:ws,:ph,:fo,:tl,:so)"
                    ),
                    {
                        "pid": plan_id,
                        "wi": w.week_index,
                        "ws": w.start_date,
                        "ph": w.phase,
                        "fo": w.focus,
                        "tl": w.target_load,
                        "so": w.sessions_order,
                    },
                )
            s.execute(
                text(
                    "insert into events(athlete_id,event_date,race_type,name) values (:aid,:d,'Half Marathon','Goal HM')"
                ),
                {"aid": athlete_id, "d": start + dt.timedelta(days=24 * 7)},
            )

        for d in range(1, 15):
            day = dt.date.today() - dt.timedelta(days=d)
            s.execute(
                text(
                    "insert into checkins(athlete_id,checkin_date,sleep_score,energy_score,recovery_score,stress_score,training_today) "
                    "values (:aid,:d,4,4,3,2,true) on conflict (athlete_id,checkin_date) do nothing"
                ),
                {"aid": athlete_id, "d": day},
            )
            s.execute(
                text(
                    "insert into training_logs(athlete_id,log_date,session_type,duration_min,distance_km,load_score,rpe,pain_flag,notes) "
                    "values (:aid,:d,'Easy Run',45,8.2,52,5,false,'Solid') on conflict do nothing"
                ),
                {"aid": athlete_id, "d": day},
            )


if __name__ == "__main__":
    run_migrations()
    seed_data()
    print("Seed complete")
