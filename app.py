from __future__ import annotations

from datetime import date, datetime

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import select

from core.bootstrap import ensure_demo_seeded
from core.db import session_scope
from core.models import Athlete, CheckIn, CoachIntervention, Event, TrainingLog, User
from core.observability import system_status
from core.security import account_locked, hash_password, verify_password
from core.services.analytics import weekly_summary
from core.services.readiness import readiness_band, readiness_score

st.set_page_config(page_title="Run Season Command", layout="wide")


def log_runtime_error(page: str, e: Exception):
    # safe fail; table may not exist during bootstrap
    try:
        from core.models import AppRuntimeError

        with session_scope() as s:
            s.add(AppRuntimeError(page=page, error_message=str(e), traceback="hidden"))
    except Exception:
        pass


def auth_panel():
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
                        from datetime import timedelta

                        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                    st.error("Invalid credentials")
                    return
                user.failed_attempts = 0
                user.last_login_at = datetime.utcnow()
                st.session_state.user_id = user.id
                st.session_state.role = user.role
                st.session_state.athlete_id = user.athlete_id
                st.session_state.must_change_password = user.must_change_password
                st.rerun()
        except Exception as e:
            log_runtime_error("login", e)
            st.error("Login unavailable. Please contact your coach.")


def force_password_change(user_id: int):
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
            st.rerun()
        except Exception:
            st.error("Password does not meet policy.")


def coach_dashboard():
    st.header("Coach Dashboard")
    with session_scope() as s:
        athletes = s.execute(select(Athlete.id, Athlete.status)).all()
        logs = s.execute(select(TrainingLog.id, TrainingLog.date, TrainingLog.duration_min, TrainingLog.load_score)).all()
        intervs = s.execute(
            select(CoachIntervention.athlete_id, CoachIntervention.action_type, CoachIntervention.risk_score, CoachIntervention.confidence_score).where(
                CoachIntervention.status == "open"
            )
        ).all()
    active = sum(1 for _, status in athletes if status == "active")
    archived = sum(1 for _, status in athletes if status == "archived")
    deleted = sum(1 for _, status in athletes if status == "deleted")
    a1, a2, a3 = st.columns(3)
    a1.metric("Active", active)
    a2.metric("Archived", archived)
    a3.metric("Deleted", deleted)
    st.subheader("Command Center Queue")
    for athlete_id, action_type, risk_score, confidence_score in intervs[:20]:
        st.write(f"Athlete {athlete_id}: {action_type} | risk {risk_score} | conf {confidence_score}")

    if logs:
        df = pd.DataFrame([{"id": log_id, "date": log_date, "duration_min": duration_min, "load_score": load_score} for log_id, log_date, duration_min, load_score in logs])
        w = weekly_summary(df)
        st.altair_chart(
            alt.Chart(w).mark_line(point=True).encode(x="week:N", y="load_score:Q", tooltip=["week", "load_score", "sessions"]),
            use_container_width=True,
        )


def coach_clients():
    st.header("Clients")
    with session_scope() as s:
        rows = s.execute(select(Athlete.id, Athlete.first_name, Athlete.last_name, Athlete.email, Athlete.status)).all()
    data = [{"id": athlete_id, "name": f"{first_name} {last_name}", "email": email, "status": status} for athlete_id, first_name, last_name, email, status in rows]
    st.dataframe(pd.DataFrame(data), use_container_width=True)


def add_client():
    st.header("Add Client")
    with st.form("add_client"):
        first = st.text_input("First")
        last = st.text_input("Last")
        email = st.text_input("Email")
        dob = st.date_input("DOB", value=date(1990, 1, 1))
        submit = st.form_submit_button("Create")
    if submit:
        with session_scope() as s:
            ath = Athlete(first_name=first, last_name=last, email=email, dob=dob)
            s.add(ath)
            s.flush()
            base = f"{first}{last}".lower().replace(" ", "")
            username = base
            i = 1
            while s.execute(select(User).where(User.username == username)).scalar_one_or_none():
                i += 1
                username = f"{base}{i}"
            user = User(username=username, role="client", athlete_id=ath.id, password_hash=hash_password("TempPass!234"), must_change_password=True)
            s.add(user)
        st.success(f"Created user: {username} / TempPass!234")


def athlete_dashboard(athlete_id: int):
    st.header("Today")
    with session_scope() as s:
        checkin = s.execute(select(CheckIn.sleep, CheckIn.energy, CheckIn.recovery, CheckIn.stress).where(CheckIn.athlete_id == athlete_id, CheckIn.day == date.today())).first()
    st.subheader("1) Check-In")
    if checkin:
        sleep, energy, recovery, stress = checkin
        score = readiness_score(sleep, energy, recovery, stress)
        st.success(f"Readiness: {score} ({readiness_band(score)})")
    else:
        st.info("Complete your check-in")

    st.subheader("2) Session Briefing")
    st.write("Default: next planned session from current week")
    st.subheader("3) Complete Session")
    st.write("Log duration, distance, RPE, optional reflection")


def athlete_checkin(athlete_id: int):
    st.header("Check-In")
    with st.form("checkin"):
        sleep = st.slider("Sleep", 1, 5, 3)
        energy = st.slider("Energy", 1, 5, 3)
        recovery = st.slider("Recovery", 1, 5, 3)
        stress = st.slider("Stress", 1, 5, 3)
        training_today = st.checkbox("Training today", value=True)
        submit = st.form_submit_button("Save Check-In")
    if submit:
        with session_scope() as s:
            existing = s.execute(select(CheckIn).where(CheckIn.athlete_id == athlete_id, CheckIn.day == date.today())).scalar_one_or_none()
            if existing:
                st.warning("Already checked in today")
            else:
                s.add(CheckIn(athlete_id=athlete_id, day=date.today(), sleep=sleep, energy=energy, recovery=recovery, stress=stress, training_today=training_today))
                st.success("Saved")


def athlete_log(athlete_id: int):
    st.header("Log Session")
    with st.form("log"):
        category = st.selectbox("Session Type", ["Easy Run", "Long Run", "Recovery Run", "Tempo / Threshold", "VO2 Intervals", "Hill Repeats", "Race Pace", "Strides / Neuromuscular", "Benchmark / Time Trial", "Taper / Openers", "Cross-Training Optional"])
        duration = st.number_input("Duration (min)", min_value=0, value=45)
        distance = st.number_input("Distance (km)", min_value=0.0, value=8.0)
        rpe = st.slider("RPE", 1, 10, 5)
        notes = st.text_area("Notes")
        pain = st.checkbox("Pain flag", value=False)
        submit = st.form_submit_button("Save")
    if submit:
        with session_scope() as s:
            load = float(duration) * (rpe / 10)
            s.add(TrainingLog(athlete_id=athlete_id, date=date.today(), session_category=category, duration_min=int(duration), distance_km=float(distance), rpe=rpe, load_score=load, notes=notes, pain_flag=pain))
            st.success("Logged")


def athlete_analytics(athlete_id: int):
    st.header("Analytics")
    with session_scope() as s:
        logs = s.execute(select(TrainingLog.id, TrainingLog.date, TrainingLog.duration_min, TrainingLog.load_score).where(TrainingLog.athlete_id == athlete_id)).all()
        events = s.execute(select(Event.event_date).where(Event.athlete_id == athlete_id)).all()
    if not logs:
        st.info("No logs yet")
        return
    df = pd.DataFrame([{"id": log_id, "date": log_date, "duration_min": duration_min, "load_score": load_score} for log_id, log_date, duration_min, load_score in logs])
    w = weekly_summary(df)
    st.line_chart(w.set_index("week")["duration_min"])
    if events:
        st.write("Next event in days:", min((event_date - date.today()).days for (event_date,) in events))


def main():
    # Ensure demo accounts exist in first-run Streamlit deployments.
    try:
        ensure_demo_seeded()
    except Exception:
        pass

    status = system_status(samples=3, slow_queries=0)
    st.caption(f"System Status: {status.status} - {status.message}")

    if "user_id" not in st.session_state:
        auth_panel()
        return

    role = st.session_state.role
    if st.session_state.get("must_change_password"):
        force_password_change(st.session_state.user_id)
        return

    try:
        if role == "coach":
            page = st.sidebar.radio("Coach", ["Dashboard", "Command Center", "Clients", "Add Client", "Plan Builder", "Session Library", "Portfolio Analytics", "Integrations", "Admin Tools"])
            if page in {"Dashboard", "Command Center", "Plan Builder", "Session Library", "Portfolio Analytics", "Integrations", "Admin Tools"}:
                coach_dashboard()
            elif page == "Clients":
                coach_clients()
            elif page == "Add Client":
                add_client()
        else:
            page = st.sidebar.radio("Athlete", ["Dashboard", "Log Session", "Check-In", "Events", "Analytics", "Profile"])
            athlete_id = st.session_state.athlete_id
            if page == "Dashboard":
                athlete_dashboard(athlete_id)
            elif page == "Log Session":
                athlete_log(athlete_id)
            elif page == "Check-In":
                athlete_checkin(athlete_id)
            elif page in {"Events", "Profile"}:
                st.info("Use coach-managed profile/events in this demo")
            elif page == "Analytics":
                athlete_analytics(athlete_id)
    except Exception as e:
        log_runtime_error("main", e)
        st.error("Something went wrong. The issue has been logged.")


if __name__ == "__main__":
    main()
