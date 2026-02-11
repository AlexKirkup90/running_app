from __future__ import annotations

import datetime as dt
import traceback

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import text

from core.db import db_session, get_query_stats
from core.services.analytics import weekly_summary
from core.services.interventions import make_recommendation
from core.services.readiness import readiness_score

st.set_page_config(page_title="Run Season Command", layout="wide")


def safe_error(page: str, exc: Exception):
    with db_session() as s:
        s.execute(
            text(
                "insert into app_runtime_errors(page,message,traceback,created_at) "
                "values (:p,:m,:t,now())"
            ),
            {"p": page, "m": str(exc), "t": traceback.format_exc()},
        )
    st.error("Something went wrong. The issue has been logged.")


def auth_screen():
    st.title("Run Season Command")
    st.caption("Coach and athlete command platform")
    username = st.text_input("Username")
    role = st.selectbox("Role (demo)", ["coach", "client"])
    if st.button("Sign in"):
        st.session_state["user"] = {"username": username or "demo", "role": role, "athlete_id": 1}
        st.rerun()


def coach_dashboard():
    st.subheader("Dashboard")
    stats = get_query_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Query p50", f"{stats.p50_ms} ms")
    c2.metric("Query p95", f"{stats.p95_ms} ms")
    c3.metric("Slow queries", stats.slow)

    st.markdown("### Command Center Snapshot")
    recommendation = make_recommendation(-1.2, 0.58, 3, 20)
    st.json(recommendation.__dict__)


def coach_clients():
    st.subheader("Clients")
    with db_session() as s:
        rows = s.execute(text("select id,first_name,last_name,status,email from athletes order by id")).mappings().all()
    st.dataframe(pd.DataFrame(rows))


def athlete_dashboard():
    st.subheader("Today")
    st.write("1) Check-In  2) Session Briefing  3) Complete Session")
    with st.form("checkin"):
        sleep = st.slider("Sleep", 1, 5, 3)
        energy = st.slider("Energy", 1, 5, 3)
        recovery = st.slider("Recovery", 1, 5, 3)
        stress = st.slider("Stress", 1, 5, 3)
        training_today = st.toggle("Training today", True)
        submitted = st.form_submit_button("Save Check-In")
    if submitted:
        score = readiness_score(sleep, energy, recovery, stress)
        st.success(f"Readiness score: {score}")
        with db_session() as s:
            s.execute(
                text(
                    "insert into checkins(athlete_id,checkin_date,sleep_score,energy_score,recovery_score,stress_score,training_today) "
                    "values (:aid,:d,:sl,:en,:re,:st,:tt) on conflict (athlete_id,checkin_date) do update "
                    "set sleep_score=:sl,energy_score=:en,recovery_score=:re,stress_score=:st,training_today=:tt"
                ),
                {
                    "aid": st.session_state["user"].get("athlete_id", 1),
                    "d": dt.date.today(),
                    "sl": sleep,
                    "en": energy,
                    "re": recovery,
                    "st": stress,
                    "tt": training_today,
                },
            )


def analytics_page(user_role: str):
    st.subheader("Analytics")
    with db_session() as s:
        logs = s.execute(text("select log_date,duration_min,load_score from training_logs order by log_date")).mappings().all()
    df = pd.DataFrame(logs)
    summary = weekly_summary(df)
    if summary.empty:
        st.info("No data yet")
        return
    chart = (
        alt.Chart(summary)
        .mark_line(point=True)
        .encode(x="week", y="load_score", tooltip=["duration_min", "sessions"])
    )
    st.altair_chart(chart, use_container_width=True)


if "user" not in st.session_state:
    auth_screen()
else:
    try:
        role = st.session_state["user"]["role"]
        if role == "coach":
            page = st.sidebar.radio(
                "Coach Admin",
                [
                    "Dashboard",
                    "Command Center",
                    "Clients",
                    "Add Client",
                    "Plan Builder",
                    "Session Library",
                    "Portfolio Analytics",
                    "Integrations",
                    "Admin Tools",
                ],
            )
            if page in {"Dashboard", "Command Center"}:
                coach_dashboard()
            elif page == "Clients":
                coach_clients()
            else:
                st.info(f"{page} is available with progressive controls in this build.")
        else:
            page = st.sidebar.radio("Athlete", ["Dashboard", "Log Session", "Check-In", "Events", "Analytics", "Profile"])
            if page in {"Dashboard", "Check-In"}:
                athlete_dashboard()
            elif page == "Analytics":
                analytics_page(role)
            else:
                st.info("Simplified, today-first workflow active.")
    except Exception as exc:
        safe_error("app", exc)
