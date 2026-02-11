from __future__ import annotations

from datetime import date

from sqlalchemy import select

from core.db import session_scope
from core.models import Athlete, SessionLibrary, User
from core.security import hash_password


def ensure_demo_seeded() -> bool:
    """
    Ensure demo auth users/data exist for Streamlit deployments where seed.py
    has not been run manually.
    """
    try:
        with session_scope() as s:
            coach = s.execute(select(User.id).where(User.username == "coach")).scalar_one_or_none()
            has_sessions = s.execute(select(SessionLibrary.id)).first() is not None
            if coach and has_sessions:
                _reconcile_demo_credentials()
                return False
    except Exception:
        # Tables may not exist yet; continue into migration/seed path.
        pass

    from db.seed import run_migrations, seed_sessions, seed_users_athletes

    run_migrations()
    seed_sessions()
    seed_users_athletes()
    _reconcile_demo_credentials()
    return True


def _reconcile_demo_credentials() -> None:
    """
    Ensure default demo login credentials are valid even when the database
    already exists with drifted user records/passwords.
    """
    with session_scope() as s:
        coach = s.execute(select(User).where(User.username == "coach")).scalar_one_or_none()
        if coach is None:
            coach = User(
                username="coach",
                role="coach",
                password_hash=hash_password("CoachPass!234"),
                must_change_password=False,
            )
            s.add(coach)
        else:
            coach.password_hash = hash_password("CoachPass!234")
            coach.must_change_password = False
            coach.failed_attempts = 0
            coach.locked_until = None

        athlete = s.execute(select(Athlete).where(Athlete.email == "athlete1@demo.run")).scalar_one_or_none()
        if athlete is None:
            athlete = Athlete(first_name="Demo1", last_name="Runner", email="athlete1@demo.run", dob=date(1990, 1, 1))
            s.add(athlete)
            s.flush()

        athlete_user = s.execute(select(User).where(User.username == "athlete1")).scalar_one_or_none()
        if athlete_user is None:
            athlete_user = User(
                username="athlete1",
                role="client",
                athlete_id=athlete.id,
                password_hash=hash_password("AthletePass!234"),
                must_change_password=False,
            )
            s.add(athlete_user)
        else:
            athlete_user.athlete_id = athlete.id
            athlete_user.role = "client"
            athlete_user.password_hash = hash_password("AthletePass!234")
            athlete_user.must_change_password = False
            athlete_user.failed_attempts = 0
            athlete_user.locked_until = None
