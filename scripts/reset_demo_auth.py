from __future__ import annotations

from sqlalchemy import select

from core.bootstrap import ensure_demo_seeded
from core.db import session_scope
from core.models import User
from core.security import verify_password


def main() -> int:
    ensure_demo_seeded()
    with session_scope() as s:
        coach = s.execute(select(User).where(User.username == "coach")).scalar_one_or_none()
        athlete = s.execute(select(User).where(User.username == "athlete1")).scalar_one_or_none()

    coach_ok = bool(coach and verify_password("CoachPass!234", coach.password_hash))
    athlete_ok = bool(athlete and verify_password("AthletePass!234", athlete.password_hash))

    print(f"coach_exists={bool(coach)} coach_password_ok={coach_ok}")
    print(f"athlete1_exists={bool(athlete)} athlete1_password_ok={athlete_ok}")
    print("alias_note=use username 'athlete' or 'athlete1'")

    return 0 if (coach_ok and athlete_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
