from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import select

from core.db import session_scope
from core.models import (
    Athlete,
    AthletePreference,
    CheckIn,
    Event,
    Plan,
    PlanDaySession,
    PlanWeek,
    SessionLibrary,
    TrainingLog,
)
from core.services.analytics import weekly_summary
from core.services.readiness import readiness_band, readiness_score
from core.services.session_engine import (
    adapt_session_structure,
    compute_acute_chronic_ratio,
    hr_range_for_label,
    pace_from_sec_per_km,
    pace_range_for_label,
)

logger = logging.getLogger(__name__)


def _get_today_context(athlete_id: int) -> dict:
    today = date.today()
    with session_scope() as s:
        checkin = s.execute(select(CheckIn.sleep, CheckIn.energy, CheckIn.recovery, CheckIn.stress).where(CheckIn.athlete_id == athlete_id, CheckIn.day == today)).first()
        athlete_profile = s.execute(
            select(Athlete.max_hr, Athlete.resting_hr, Athlete.threshold_pace_sec_per_km, Athlete.easy_pace_sec_per_km).where(Athlete.id == athlete_id)
        ).first()
        planned_day_row = s.execute(
            select(PlanDaySession.id, PlanDaySession.session_name, PlanDaySession.status)
            .join(PlanWeek, PlanWeek.id == PlanDaySession.plan_week_id)
            .join(Plan, Plan.id == PlanWeek.plan_id)
            .where(PlanDaySession.athlete_id == athlete_id, PlanDaySession.session_day == today, Plan.status == "active")
            .order_by(PlanDaySession.id.desc())
        ).first()
        week_row = s.execute(
            select(PlanWeek.week_number, PlanWeek.sessions_order).join(Plan, Plan.id == PlanWeek.plan_id).where(
                Plan.athlete_id == athlete_id, Plan.status == "active", PlanWeek.week_start <= today, PlanWeek.week_end >= today
            )
        ).first()
        today_log = s.execute(
            select(
                TrainingLog.id,
                TrainingLog.session_category,
                TrainingLog.duration_min,
                TrainingLog.distance_km,
                TrainingLog.avg_hr,
                TrainingLog.max_hr,
                TrainingLog.avg_pace_sec_per_km,
                TrainingLog.rpe,
                TrainingLog.notes,
                TrainingLog.pain_flag,
            )
            .where(TrainingLog.athlete_id == athlete_id, TrainingLog.date == today)
            .order_by(TrainingLog.id.desc())
        ).first()
        recent_logs = s.execute(select(TrainingLog.load_score, TrainingLog.pain_flag).where(TrainingLog.athlete_id == athlete_id, TrainingLog.date >= (today - timedelta(days=27)))).all()
        next_event = s.execute(select(Event.event_date).where(Event.athlete_id == athlete_id, Event.event_date >= today).order_by(Event.event_date)).first()

    planned_session_name = None
    planned_day_id = None
    planned_status = None
    if planned_day_row:
        planned_day_id, planned_session_name, planned_status = planned_day_row
    elif week_row and isinstance(week_row[1], list) and week_row[1]:
        planned_session_name = week_row[1][today.weekday() % len(week_row[1])]

    return {
        "today": today,
        "checkin": checkin,
        "athlete_profile": athlete_profile,
        "planned_day_id": planned_day_id,
        "planned_session_name": planned_session_name,
        "planned_status": planned_status,
        "today_log": today_log,
        "recent_logs": recent_logs,
        "next_event": next_event,
    }


def athlete_dashboard(athlete_id: int) -> None:
    st.header("Today")
    ctx = _get_today_context(athlete_id)
    today = ctx["today"]
    checkin = ctx["checkin"]
    athlete_profile = ctx["athlete_profile"]
    recent_logs = ctx["recent_logs"]
    next_event = ctx["next_event"]
    today_log = ctx["today_log"]
    st.subheader("1) Check-In")
    readiness = None
    if checkin:
        sleep, energy, recovery, stress = checkin
        readiness = readiness_score(sleep, energy, recovery, stress)
        st.success(f"Readiness: {readiness} ({readiness_band(readiness)})")
    else:
        st.info("Complete your check-in")

    st.subheader("2) Session Briefing")
    loads_28d = [float(load or 0) for load, _ in recent_logs]
    pain_recent = any(bool(pain) for _, pain in recent_logs[-3:])
    ratio = compute_acute_chronic_ratio(loads_28d)
    days_to_event = (next_event[0] - today).days if next_event else None
    max_hr = resting_hr = threshold_pace = easy_pace = None
    if athlete_profile:
        max_hr, resting_hr, threshold_pace, easy_pace = athlete_profile
        st.caption(
            f"Pace anchors: threshold {pace_from_sec_per_km(threshold_pace)}, easy {pace_from_sec_per_km(easy_pace)} | "
            f"HR: max {max_hr or 'n/a'}, resting {resting_hr or 'n/a'} | A:C ratio {ratio}"
        )
    session_token = ctx["planned_session_name"]
    if not session_token:
        st.info("No planned session found for this week.")
    else:
        with session_scope() as s:
            session_template = s.execute(
                select(SessionLibrary.name, SessionLibrary.structure_json, SessionLibrary.prescription, SessionLibrary.coaching_notes).where(
                    SessionLibrary.name == session_token
                )
            ).first()
            if not session_template:
                session_template = s.execute(
                    select(SessionLibrary.name, SessionLibrary.structure_json, SessionLibrary.prescription, SessionLibrary.coaching_notes).where(
                        SessionLibrary.category == session_token
                    ).order_by(SessionLibrary.duration_min)
                ).first()
        if not session_template:
            st.warning(f"No session template found for '{session_token}'.")
        else:
            name, structure_json, prescription, coaching_notes = session_template
            adapted = adapt_session_structure(structure_json, readiness, pain_recent, ratio, days_to_event)
            st.write(f"**Planned Session:** {name}")
            st.caption(f"Adaptation: {adapted['action']} | {adapted['reason']}")
            st.write(prescription)
            st.write(coaching_notes)
            blocks = adapted["session"].get("blocks", [])
            rows = []
            for block in blocks:
                tgt = block.get("target", {})
                pace_label = tgt.get("pace_zone")
                hr_label = tgt.get("hr_zone")
                rows.append(
                    {
                        "phase": block.get("phase"),
                        "duration_min": block.get("duration_min"),
                        "pace_zone": pace_label,
                        "pace_target": pace_range_for_label(pace_label or "", threshold_pace, easy_pace),
                        "hr_zone": hr_label,
                        "hr_target": hr_range_for_label(hr_label or "", max_hr, resting_hr),
                        "rpe_range": tgt.get("rpe_range"),
                        "instructions": block.get("instructions"),
                    }
                )
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
    st.subheader("3) Complete Session")
    if not checkin:
        st.warning("Complete Check-In first, then log your session.")
    elif today_log:
        st.success("Today's session is already logged. You can edit it in Log Session.")
    else:
        st.info("Go to Log Session to complete today's training.")


def athlete_checkin(athlete_id: int) -> None:
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
                existing.sleep = sleep
                existing.energy = energy
                existing.recovery = recovery
                existing.stress = stress
                existing.training_today = training_today
                st.success("Check-in updated")
            else:
                s.add(CheckIn(athlete_id=athlete_id, day=date.today(), sleep=sleep, energy=energy, recovery=recovery, stress=stress, training_today=training_today))
                st.success("Saved")
        logger.info("Check-in saved for athlete_id=%d", athlete_id)
        st.rerun()


def athlete_log(athlete_id: int) -> None:
    st.header("Log Session")
    ctx = _get_today_context(athlete_id)
    if not ctx["checkin"]:
        st.warning("You need to complete today's Check-In before logging a session.")
        return
    planned_session_name = ctx["planned_session_name"]
    today_log = ctx["today_log"]
    today = ctx["today"]

    base_categories = [
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
    options = [planned_session_name] + base_categories if planned_session_name else base_categories
    seen = set()
    category_options = []
    for opt in options:
        if opt and opt not in seen:
            category_options.append(opt)
            seen.add(opt)

    default_category = today_log[1] if today_log else (planned_session_name or category_options[0])
    with st.form("log"):
        category = st.selectbox("Session Type", category_options, index=category_options.index(default_category) if default_category in category_options else 0)
        duration = st.number_input("Duration (min)", min_value=0, value=int(today_log[2]) if today_log else 45)
        distance = st.number_input("Distance (km)", min_value=0.0, value=float(today_log[3]) if today_log else 8.0)
        avg_hr = st.number_input("Avg HR (optional)", min_value=0, value=int(today_log[4]) if today_log and today_log[4] else 0)
        max_hr = st.number_input("Max HR (optional)", min_value=0, value=int(today_log[5]) if today_log and today_log[5] else 0)
        avg_pace = st.number_input("Avg pace sec/km (optional)", min_value=0.0, value=float(today_log[6]) if today_log and today_log[6] else 0.0)
        rpe = st.slider("RPE", 1, 10, int(today_log[7]) if today_log else 5)
        notes = st.text_area("Notes", value=str(today_log[8]) if today_log and today_log[8] else "")
        pain = st.checkbox("Pain flag", value=bool(today_log[9]) if today_log else False)
        submit = st.form_submit_button("Save Session")
    if submit:
        with session_scope() as s:
            load = float(duration) * (rpe / 10)
            existing = s.execute(select(TrainingLog).where(TrainingLog.athlete_id == athlete_id, TrainingLog.date == today)).scalar_one_or_none()
            if existing:
                existing.session_category = category
                existing.duration_min = int(duration)
                existing.distance_km = float(distance)
                existing.avg_hr = int(avg_hr) if avg_hr > 0 else None
                existing.max_hr = int(max_hr) if max_hr > 0 else None
                existing.avg_pace_sec_per_km = float(avg_pace) if avg_pace > 0 else None
                existing.rpe = rpe
                existing.load_score = load
                existing.notes = notes
                existing.pain_flag = pain
            else:
                s.add(
                    TrainingLog(
                        athlete_id=athlete_id,
                        date=today,
                        session_category=category,
                        duration_min=int(duration),
                        distance_km=float(distance),
                        avg_hr=(int(avg_hr) if avg_hr > 0 else None),
                        max_hr=(int(max_hr) if max_hr > 0 else None),
                        avg_pace_sec_per_km=(float(avg_pace) if avg_pace > 0 else None),
                        rpe=rpe,
                        load_score=load,
                        notes=notes,
                        pain_flag=pain,
                    )
                )
            if ctx["planned_day_id"]:
                planned_row = s.get(PlanDaySession, int(ctx["planned_day_id"]))
                if planned_row:
                    planned_row.status = "completed"
            logger.info("Session logged for athlete_id=%d rpe=%d pain=%s", athlete_id, rpe, pain)
            st.success("Session saved for today.")
        st.rerun()


def athlete_analytics(athlete_id: int) -> None:
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


def athlete_events(athlete_id: int) -> None:
    st.header("Events")
    with session_scope() as s:
        rows = s.execute(select(Event.id, Event.name, Event.event_date, Event.distance).where(Event.athlete_id == athlete_id)).all()
    st.subheader("Upcoming")
    if rows:
        st.dataframe(pd.DataFrame([{"id": event_id, "name": name, "event_date": event_date, "distance": distance} for event_id, name, event_date, distance in rows]), use_container_width=True)
    else:
        st.info("No events added.")

    with st.form("add_event"):
        name = st.text_input("Event name")
        event_date = st.date_input("Event date", value=date.today())
        distance = st.selectbox("Distance", ["5K", "10K", "Half Marathon", "Marathon", "Other"])
        submit = st.form_submit_button("Add Event")
    if submit and name.strip():
        with session_scope() as s:
            s.add(Event(athlete_id=athlete_id, name=name.strip(), event_date=event_date, distance=distance))
        logger.info("Event added for athlete_id=%d name=%s", athlete_id, name.strip())
        st.success("Event added.")
        st.rerun()


def athlete_profile(athlete_id: int) -> None:
    st.header("Profile")
    with session_scope() as s:
        athlete = s.execute(select(Athlete.first_name, Athlete.last_name, Athlete.email, Athlete.dob, Athlete.status).where(Athlete.id == athlete_id)).first()
        prefs = s.execute(
            select(AthletePreference.automation_mode, AthletePreference.auto_apply_low_risk, AthletePreference.reminder_training_days).where(
                AthletePreference.athlete_id == athlete_id
            )
        ).first()
    if athlete:
        first, last, email, dob, status = athlete
        st.write(f"Name: {first} {last}")
        st.write(f"Email: {email}")
        st.write(f"DOB: {dob}")
        st.write(f"Status: {status}")
    else:
        st.warning("Athlete profile not found.")
    if prefs:
        mode, low_risk, days = prefs
        st.subheader("Preferences")
        st.write(f"Automation mode: {mode}")
        st.write(f"Auto-apply low risk: {low_risk}")
        st.write(f"Reminder days: {', '.join(days)}")
