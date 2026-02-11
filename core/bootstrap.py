from __future__ import annotations

from sqlalchemy import select

from core.db import session_scope
from core.models import User


def ensure_demo_seeded() -> bool:
    """
    Ensure demo auth users/data exist for Streamlit deployments where seed.py
    has not been run manually.
    """
    try:
        with session_scope() as s:
            coach = s.execute(select(User.id).where(User.username == "coach")).scalar_one_or_none()
            if coach:
                return False
    except Exception:
        # Tables may not exist yet; continue into migration/seed path.
        pass

    from db.seed import run_migrations, seed_sessions, seed_users_athletes

    run_migrations()
    seed_sessions()
    seed_users_athletes()
    return True
