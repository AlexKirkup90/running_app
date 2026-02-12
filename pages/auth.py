from __future__ import annotations

import logging
from datetime import datetime, timedelta

import streamlit as st
from sqlalchemy import select

from core.bootstrap import ensure_demo_seeded
from core.db import session_scope
from core.models import AppRuntimeError, User
from core.security import account_locked, hash_password, verify_password

logger = logging.getLogger(__name__)


def log_runtime_error(page: str, e: Exception) -> None:
    """Log error to DB and structured logger. Safe to call even if DB is unavailable."""
    logger.error("Runtime error on page=%s: %s", page, e, exc_info=True)
    try:
        with session_scope() as s:
            s.add(AppRuntimeError(page=page, error_message=str(e), traceback="hidden"))
    except Exception:
        pass


def auth_panel() -> None:
    st.title("Run Season Command")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        try:
            username = u.strip().lower()
            if username == "athlete":
                username = "athlete1"

            def _get_user_id() -> int | None:
                with session_scope() as s:
                    return s.execute(select(User.id).where(User.username == username)).scalar_one_or_none()

            try:
                user_id = _get_user_id()
            except Exception:
                user_id = None

            if not user_id:
                try:
                    ensure_demo_seeded()
                    user_id = _get_user_id()
                except Exception:
                    user_id = None

            if not user_id:
                st.error("Invalid credentials")
                return

            with session_scope() as s:
                user = s.get(User, user_id)
                if account_locked(user.locked_until):
                    st.error("Account locked")
                    return
                if not verify_password(p, user.password_hash):
                    user.failed_attempts += 1
                    if user.failed_attempts >= 5:
                        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                    st.error("Invalid credentials")
                    return
                user.failed_attempts = 0
                user.last_login_at = datetime.utcnow()
                st.session_state.user_id = user.id
                st.session_state.role = user.role
                st.session_state.athlete_id = user.athlete_id
                st.session_state.must_change_password = user.must_change_password
                logger.info("User logged in: user_id=%d role=%s", user.id, user.role)
                st.rerun()
        except Exception as e:
            log_runtime_error("login", e)
            st.error("Login unavailable. Please contact your coach.")


def force_password_change(user_id: int) -> None:
    st.warning("You must change password before continuing.")
    with st.form("pw_change"):
        np = st.text_input("New password", type="password")
        submit = st.form_submit_button("Update password")
    if submit:
        try:
            with session_scope() as s:
                user = s.get(User, user_id)
                user.password_hash = hash_password(np)
                user.must_change_password = False
            st.success("Password updated")
            logger.info("Password changed for user_id=%d", user_id)
            st.rerun()
        except Exception:
            st.error("Password does not meet policy.")
