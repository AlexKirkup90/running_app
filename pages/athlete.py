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
    Challenge,
    ChallengeEntry,
    CheckIn,
    Event,
    GroupMembership,
    GroupMessage,
    Kudos,
    Plan,
    PlanDaySession,
    PlanWeek,
    SessionLibrary,
    SyncLog,
    TrainingGroup,
    TrainingLog,
    WearableConnection,
)
from core.services.analytics import weekly_summary
from core.services.race_predictor import predict_all_distances
from core.services.readiness import readiness_band, readiness_score
from core.services.session_engine import (
    adapt_session_structure,
    compute_acute_chronic_ratio,
    hr_range_for_label,
    pace_from_sec_per_km,
    pace_range_for_label,
)
from core.services.training_load import compute_session_load, compute_weekly_metrics, overtraining_risk
from core.services.community import (
    compute_challenge_progress,
    compute_leaderboard,
    compute_training_streak,
)
from core.services.vdot import RACE_DISTANCES_M, pace_display
from core.services.wearables.sync import (
    build_training_log_dict,
    default_lookback,
    fetch_all_activities,
    prepare_import_batch,
)

logger = logging.getLogger(__name__)


def _get_today_context(athlete_id: int) -> dict:
    today = date.today()
    with session_scope() as s:
        checkin = s.execute(select(CheckIn.sleep, CheckIn.energy, CheckIn.recovery, CheckIn.stress).where(CheckIn.athlete_id == athlete_id, CheckIn.day == today)).first()
        athlete_profile = s.execute(
            select(Athlete.max_hr, Athlete.resting_hr, Athlete.threshold_pace_sec_per_km, Athlete.easy_pace_sec_per_km, Athlete.vdot_score).where(Athlete.id == athlete_id)
        ).first()
        planned_day_row = s.execute(
            select(PlanDaySession.id, PlanDaySession.session_name, PlanDaySession.status)
            .join(PlanWeek, PlanWeek.id == PlanDaySession.plan_week_id)
            .join(Plan, Plan.id == PlanWeek.plan_id)
            .where(PlanDaySession.athlete_id == athlete_id, PlanDaySession.session_day == today, Plan.status == "active")
            .order_by(PlanDaySession.id.desc())
        ).first()
        week_row = s.execute(
            select(PlanWeek.week_number, PlanWeek.sessions_order, PlanWeek.phase).join(Plan, Plan.id == PlanWeek.plan_id).where(
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
        recent_logs = s.execute(
            select(TrainingLog.load_score, TrainingLog.pain_flag, TrainingLog.duration_min, TrainingLog.rpe, TrainingLog.avg_hr)
            .where(TrainingLog.athlete_id == athlete_id, TrainingLog.date >= (today - timedelta(days=27)))
            .order_by(TrainingLog.date)
        ).all()
        next_event = s.execute(select(Event.event_date).where(Event.athlete_id == athlete_id, Event.event_date >= today).order_by(Event.event_date)).first()

    planned_session_name = None
    planned_day_id = None
    planned_status = None
    current_phase = None
    if planned_day_row:
        planned_day_id, planned_session_name, planned_status = planned_day_row
    if week_row:
        current_phase = week_row[2]
        if not planned_session_name and isinstance(week_row[1], list) and week_row[1]:
            planned_session_name = week_row[1][today.weekday() % len(week_row[1])]

    vdot_score = None
    if athlete_profile and len(athlete_profile) >= 5:
        vdot_score = athlete_profile[4]

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
        "current_phase": current_phase,
        "vdot_score": vdot_score,
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
    current_phase = ctx["current_phase"]
    vdot_score = ctx["vdot_score"]

    st.subheader("1) Check-In")
    readiness = None
    if checkin:
        sleep, energy, recovery, stress = checkin
        readiness = readiness_score(sleep, energy, recovery, stress)
        st.success(f"Readiness: {readiness} ({readiness_band(readiness)})")
    else:
        st.info("Complete your check-in")

    # Training load summary
    if recent_logs:
        daily_loads = []
        for load, _pain, dur, rpe, avg_hr in recent_logs:
            session_load = compute_session_load(int(dur or 0), int(rpe or 5), avg_hr=int(avg_hr) if avg_hr else None)
            daily_loads.append(session_load.trimp)
        if len(daily_loads) >= 7:
            weekly = compute_weekly_metrics(daily_loads)
            risk = overtraining_risk(weekly.monotony, weekly.strain)
            risk_color = {"low": "green", "moderate": "orange", "high": "red"}.get(risk, "grey")
            st.caption(
                f"Training Load — Monotony: {weekly.monotony:.1f} | Strain: {weekly.strain:.0f} | "
                f"Risk: :{risk_color}[{risk}]"
            )

    st.subheader("2) Session Briefing")
    loads_28d = [float(load or 0) for load, _pain, _dur, _rpe, _hr in recent_logs]
    pain_recent = any(bool(pain) for _load, pain, _dur, _rpe, _hr in recent_logs[-3:])
    ratio = compute_acute_chronic_ratio(loads_28d)
    days_to_event = (next_event[0] - today).days if next_event else None
    max_hr = resting_hr = threshold_pace = easy_pace = None
    if athlete_profile:
        max_hr, resting_hr, threshold_pace, easy_pace = athlete_profile[:4]
        vdot_label = f" | VDOT {vdot_score}" if vdot_score else ""
        phase_label = f" | Phase: {current_phase}" if current_phase else ""
        st.caption(
            f"Pace anchors: threshold {pace_from_sec_per_km(threshold_pace)}, easy {pace_from_sec_per_km(easy_pace)} | "
            f"HR: max {max_hr or 'n/a'}, resting {resting_hr or 'n/a'} | A:C ratio {ratio}{vdot_label}{phase_label}"
        )
    session_token = ctx["planned_session_name"]
    if not session_token:
        st.info("No planned session found for this week.")
    else:
        with session_scope() as s:
            session_template = s.execute(
                select(
                    SessionLibrary.name, SessionLibrary.structure_json, SessionLibrary.prescription,
                    SessionLibrary.coaching_notes, SessionLibrary.progression_json, SessionLibrary.regression_json,
                ).where(SessionLibrary.name == session_token)
            ).first()
            if not session_template:
                session_template = s.execute(
                    select(
                        SessionLibrary.name, SessionLibrary.structure_json, SessionLibrary.prescription,
                        SessionLibrary.coaching_notes, SessionLibrary.progression_json, SessionLibrary.regression_json,
                    ).where(SessionLibrary.category == session_token).order_by(SessionLibrary.duration_min)
                ).first()
        if not session_template:
            st.warning(f"No session template found for '{session_token}'.")
        else:
            name, structure_json, prescription, coaching_notes, progression_json, regression_json = session_template
            adapted = adapt_session_structure(
                structure_json, readiness, pain_recent, ratio, days_to_event,
                phase=current_phase, vdot=vdot_score,
            )
            st.write(f"**Planned Session:** {name}")
            st.caption(f"Adaptation: {adapted['action']} | {adapted['reason']}")
            st.write(prescription)
            st.write(coaching_notes)

            blocks = adapted["session"].get("blocks", [])
            is_v3 = adapted["session"].get("version", 2) >= 3
            rows = []
            for block in blocks:
                tgt = block.get("target", {})
                if is_v3:
                    pace_col = tgt.get("pace_display") or tgt.get("pace_label", "")
                    hr_col = ""
                else:
                    pace_label = tgt.get("pace_zone")
                    hr_label = tgt.get("hr_zone")
                    pace_col = pace_range_for_label(pace_label or "", threshold_pace, easy_pace)
                    hr_col = hr_range_for_label(hr_label or "", max_hr, resting_hr)
                rows.append(
                    {
                        "phase": block.get("phase"),
                        "duration_min": block.get("duration_min"),
                        "pace": pace_col,
                        "hr": hr_col,
                        "rpe": str(tgt.get("rpe_range", "")),
                    }
                )
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

            # Expand interval detail for v3 sessions
            interval_rows = []
            for block in blocks:
                intervals = block.get("intervals")
                if isinstance(intervals, list):
                    for ivl in intervals:
                        work_pace_str = ivl.get("work_pace_display") or ivl.get("work_pace", "")
                        recovery_pace_str = ivl.get("recovery_pace_display") or ivl.get("recovery_pace", "")
                        band = ivl.get("work_pace_band")
                        band_str = f"{pace_display(band[0])} - {pace_display(band[1])}" if band else ""
                        interval_rows.append({
                            "reps": ivl.get("reps"),
                            "work": f"{ivl.get('work_duration_min', '')} min",
                            "work_pace": work_pace_str,
                            "pace_band": band_str,
                            "recovery": f"{ivl.get('recovery_duration_min', '')} min",
                            "recovery_pace": recovery_pace_str,
                            "description": ivl.get("description", ""),
                        })
            if interval_rows:
                st.markdown("**Interval Detail**")
                st.dataframe(pd.DataFrame(interval_rows), use_container_width=True)

            # Progression / regression triggers
            prog_rules = progression_json if isinstance(progression_json, dict) else {}
            reg_rules = regression_json if isinstance(regression_json, dict) else {}
            if prog_rules or reg_rules:
                with st.expander("Progression & Regression Rules"):
                    if prog_rules:
                        st.markdown("**Progression**")
                        for key, rule in prog_rules.items():
                            if isinstance(rule, dict):
                                st.caption(f"- {rule.get('trigger', '')} → {rule.get('action', '')}")
                    if reg_rules:
                        st.markdown("**Regression**")
                        for key, rule in reg_rules.items():
                            if isinstance(rule, dict):
                                st.caption(f"- {rule.get('trigger', '')} → {rule.get('action', '')}")

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
        logs = s.execute(
            select(
                TrainingLog.id, TrainingLog.date, TrainingLog.duration_min, TrainingLog.load_score,
                TrainingLog.session_category, TrainingLog.rpe, TrainingLog.avg_pace_sec_per_km,
                TrainingLog.distance_km, TrainingLog.avg_hr, TrainingLog.pain_flag,
            ).where(TrainingLog.athlete_id == athlete_id).order_by(TrainingLog.date)
        ).all()
        events = s.execute(select(Event.event_date).where(Event.athlete_id == athlete_id)).all()
        vdot_score = s.execute(select(Athlete.vdot_score).where(Athlete.id == athlete_id)).scalar()
        # Benchmark/race results for VDOT history
        benchmarks = s.execute(
            select(TrainingLog.date, TrainingLog.distance_km, TrainingLog.duration_min, TrainingLog.session_category)
            .where(
                TrainingLog.athlete_id == athlete_id,
                TrainingLog.distance_km > 0,
                TrainingLog.duration_min > 0,
                TrainingLog.session_category.in_(["Benchmark / Time Trial", "Race Pace Run", "Race Pace"]),
            ).order_by(TrainingLog.date)
        ).all()

    if not logs:
        st.info("No logs yet")
        return

    from core.services.analytics import (
        compute_fitness_fatigue,
        compute_intensity_distribution,
        compute_pace_trends,
        compute_vdot_history,
        compute_volume_distribution,
        race_readiness_score,
        vdot_trend,
    )

    log_dicts = [
        {
            "id": lid, "date": d, "duration_min": dur, "load_score": load,
            "session_category": cat, "rpe": rpe, "avg_pace_sec_per_km": pace,
            "distance_km": dist, "avg_hr": hr, "pain_flag": pain,
        }
        for lid, d, dur, load, cat, rpe, pace, dist, hr, pain in logs
    ]

    # Weekly summary
    df = pd.DataFrame(log_dicts)
    w = weekly_summary(df)
    st.subheader("Weekly Volume")
    st.line_chart(w.set_index("week")[["duration_min", "load_score"]])

    # Fitness / Fatigue (CTL / ATL / TSB)
    st.subheader("Fitness & Fatigue")
    daily_loads = [{"date": log["date"], "load": float(log["load_score"] or 0)} for log in log_dicts]
    ff_points = compute_fitness_fatigue(daily_loads)
    if ff_points:
        ff_df = pd.DataFrame([{"date": p.day, "CTL (Fitness)": p.ctl, "ATL (Fatigue)": p.atl, "TSB (Form)": p.tsb} for p in ff_points])
        st.line_chart(ff_df.set_index("date"))
        latest = ff_points[-1]
        readiness = race_readiness_score(latest.tsb)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fitness (CTL)", f"{latest.ctl:.0f}")
        c2.metric("Fatigue (ATL)", f"{latest.atl:.0f}")
        c3.metric("Form (TSB)", f"{latest.tsb:.0f}")
        c4.metric("Race Readiness", readiness.replace("_", " ").title())

    # VDOT progression
    if benchmarks:
        st.subheader("VDOT Progression")
        bench_dicts = [{"date": d, "distance_km": dist, "duration_min": dur, "source": cat} for d, dist, dur, cat in benchmarks]
        vdot_history = compute_vdot_history(bench_dicts)
        if vdot_history:
            trend_info = vdot_trend(vdot_history)
            st.caption(
                f"Current VDOT: {trend_info['current_vdot']} | "
                f"Peak: {trend_info['peak_vdot']} | "
                f"Trend: {trend_info['trend']} | "
                f"Rate: {trend_info['improvement_per_month']:+.1f}/month"
            )
            vdot_df = pd.DataFrame([{"date": p.event_date, "VDOT": p.vdot} for p in vdot_history])
            st.line_chart(vdot_df.set_index("date"))
    elif vdot_score:
        st.subheader("VDOT")
        st.metric("Current VDOT", vdot_score)
        st.caption("Log benchmark / time trial sessions to track VDOT progression over time.")

    # Intensity distribution (80/20 rule check)
    st.subheader("Intensity Distribution")
    intensity = compute_intensity_distribution(log_dicts)
    if intensity:
        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("Easy (RPE 1-4)", f"{intensity['easy']}%")
        ic2.metric("Moderate (RPE 5-7)", f"{intensity['moderate']}%")
        ic3.metric("Hard (RPE 8-10)", f"{intensity['hard']}%")
        ideal_easy = intensity["easy"] >= 75
        if ideal_easy:
            st.success("Good polarisation — majority of training is easy.")
        elif intensity["easy"] >= 60:
            st.info("Moderate polarisation. Consider increasing easy volume for better recovery.")
        else:
            st.warning("Low easy percentage. Risk of overtraining — increase easy volume.")

    # Volume distribution
    st.subheader("Volume by Session Type")
    vol = compute_volume_distribution(log_dicts)
    if vol:
        st.bar_chart(pd.DataFrame({"category": list(vol.keys()), "percentage": list(vol.values())}).set_index("category"))

    # Pace trends
    pace_df = compute_pace_trends(log_dicts)
    if not pace_df.empty:
        st.subheader("Pace Trends")
        for cat in pace_df["category"].unique():
            cat_data = pace_df[pace_df["category"] == cat][["date", "rolling_avg_pace"]].copy()
            cat_data = cat_data.rename(columns={"rolling_avg_pace": f"{cat} (sec/km)"})
            st.line_chart(cat_data.set_index("date"))

    if events:
        st.write("Next event in days:", min((event_date - date.today()).days for (event_date,) in events))


def athlete_events(athlete_id: int) -> None:
    st.header("Events")
    with session_scope() as s:
        rows = s.execute(select(Event.id, Event.name, Event.event_date, Event.distance).where(Event.athlete_id == athlete_id)).all()
        vdot_score = s.execute(select(Athlete.vdot_score).where(Athlete.id == athlete_id)).scalar()
        # Find best recent race result for predictions
        best_race = s.execute(
            select(TrainingLog.distance_km, TrainingLog.duration_min)
            .where(
                TrainingLog.athlete_id == athlete_id,
                TrainingLog.distance_km > 0,
                TrainingLog.duration_min > 0,
                TrainingLog.session_category.in_(["Benchmark / Time Trial", "Race Pace Run", "Race Pace"]),
            )
            .order_by(TrainingLog.date.desc())
        ).first()

    st.subheader("Upcoming")
    if rows:
        st.dataframe(pd.DataFrame([{"id": event_id, "name": name, "event_date": event_date, "distance": distance} for event_id, name, event_date, distance in rows]), use_container_width=True)
    else:
        st.info("No events added.")

    # Race time predictions
    if best_race and best_race[0] and best_race[1]:
        distance_km = float(best_race[0])
        time_min = float(best_race[1])
        # Find closest standard distance label
        best_label = min(RACE_DISTANCES_M.keys(), key=lambda k: abs(RACE_DISTANCES_M[k] - distance_km * 1000))
        st.subheader("Race Time Predictions")
        st.caption(f"Based on recent result: {distance_km:.1f} km in {time_min:.0f} min (mapped to {best_label})")
        try:
            predictions = predict_all_distances(best_label, time_min * 60)
            pred_rows = []
            for dist_name, preds in predictions.items():
                for pred in preds:
                    pred_rows.append({"distance": dist_name, "predicted_time": pred.predicted_display, "method": pred.method})
            if pred_rows:
                st.dataframe(pd.DataFrame(pred_rows), use_container_width=True)
        except Exception:
            st.caption("Unable to generate predictions from available data.")
    elif vdot_score:
        st.subheader("Race Time Predictions")
        st.caption(f"Based on VDOT {vdot_score} — log a benchmark/time trial for more accurate predictions.")
        try:
            predictions = predict_all_distances("5K", 0, vdot_override=vdot_score)
            pred_rows = []
            for dist_name, preds in predictions.items():
                for pred in preds:
                    pred_rows.append({"distance": dist_name, "predicted_time": pred.predicted_display, "method": pred.method})
            if pred_rows:
                st.dataframe(pd.DataFrame(pred_rows), use_container_width=True)
        except Exception:
            pass

    with st.form("add_event"):
        name = st.text_input("Event name")
        event_date = st.date_input("Event date", value=date.today())
        distance = st.selectbox("Distance", ["800m", "1500m", "Mile", "5K", "10K", "Half Marathon", "Marathon", "Other"])
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

    # ── Wearable Connections ──────────────────────────────────────────────
    st.subheader("Connected Devices")
    with session_scope() as s:
        connections = s.execute(
            select(
                WearableConnection.id, WearableConnection.service,
                WearableConnection.sync_status, WearableConnection.last_sync_at,
                WearableConnection.external_athlete_id,
            ).where(WearableConnection.athlete_id == athlete_id)
        ).all()
    if connections:
        for conn_id, service, sync_status, last_sync, ext_id in connections:
            status_icon = "green" if sync_status == "active" else "orange"
            last_str = last_sync.strftime("%Y-%m-%d %H:%M") if last_sync else "Never"
            st.write(
                f":{status_icon}[{service.title()}] — Status: {sync_status} | "
                f"Last sync: {last_str} | ID: {ext_id or 'n/a'}"
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Sync {service.title()} Now", key=f"sync_{conn_id}"):
                    _trigger_wearable_sync(athlete_id, conn_id, service)
            with col2:
                if st.button(f"Disconnect {service.title()}", key=f"disc_{conn_id}"):
                    with session_scope() as s:
                        wc = s.get(WearableConnection, conn_id)
                        if wc:
                            s.delete(wc)
                    st.success(f"{service.title()} disconnected.")
                    st.rerun()
    else:
        st.info("No wearable devices connected.")
    st.caption("To connect Garmin or Strava, your coach can initiate the connection from Integrations.")

    # Recent sync history
    with session_scope() as s:
        sync_logs = s.execute(
            select(SyncLog.service, SyncLog.status, SyncLog.activities_imported,
                   SyncLog.activities_skipped, SyncLog.started_at)
            .where(SyncLog.athlete_id == athlete_id)
            .order_by(SyncLog.id.desc())
            .limit(5)
        ).all()
    if sync_logs:
        st.caption("Recent Syncs")
        for svc, s_status, imported, skipped, started in sync_logs:
            st.caption(f"{svc.title()} — {s_status} | +{imported} imported, {skipped} skipped | {started:%Y-%m-%d %H:%M}")


def athlete_community(athlete_id: int) -> None:
    """Community page: groups, challenges, leaderboards, activity feed."""
    st.header("Community")

    # ── My Groups ────────────────────────────────────────────────────────
    st.subheader("My Groups")
    with session_scope() as s:
        memberships = s.execute(
            select(TrainingGroup.id, TrainingGroup.name, TrainingGroup.description, GroupMembership.role)
            .join(GroupMembership, GroupMembership.group_id == TrainingGroup.id)
            .where(GroupMembership.athlete_id == athlete_id)
            .order_by(TrainingGroup.name)
        ).all()

    if memberships:
        for gid, gname, gdesc, grole in memberships:
            with st.expander(f"{gname} ({grole})"):
                st.write(gdesc or "No description.")
                _show_group_feed(gid, athlete_id)
                _show_group_leaderboard(gid)
    else:
        st.info("You haven't joined any training groups yet.")

    # ── Active Challenges ────────────────────────────────────────────────
    st.subheader("Active Challenges")
    with session_scope() as s:
        challenges = s.execute(
            select(Challenge.id, Challenge.name, Challenge.challenge_type,
                   Challenge.target_value, Challenge.start_date, Challenge.end_date,
                   ChallengeEntry.progress, ChallengeEntry.completed)
            .join(ChallengeEntry, ChallengeEntry.challenge_id == Challenge.id)
            .where(ChallengeEntry.athlete_id == athlete_id, Challenge.status == "active")
            .order_by(Challenge.end_date)
        ).all()

    if challenges:
        for cid, cname, ctype, target, start, end, progress, completed in challenges:
            prog = compute_challenge_progress(progress, target, end)
            status_icon = "white_check_mark" if completed else "hourglass_flowing_sand"
            st.write(f":{status_icon}: **{cname}** — {ctype}")
            st.progress(min(prog.pct / 100, 1.0), text=f"{prog.current:.1f} / {target:.1f} ({prog.pct:.0f}%)")
            if prog.days_remaining > 0 and not completed:
                st.caption(f"{prog.days_remaining} days remaining")
    else:
        st.info("No active challenges.")

    # ── Training Streak ──────────────────────────────────────────────────
    st.subheader("Training Streak")
    with session_scope() as s:
        log_dates = [
            row[0] for row in s.execute(
                select(TrainingLog.date).where(TrainingLog.athlete_id == athlete_id).order_by(TrainingLog.date.desc()).limit(90)
            ).all()
        ]
    streak = compute_training_streak(log_dates)
    st.metric("Current Streak", f"{streak} day{'s' if streak != 1 else ''}")

    # ── Kudos Received ───────────────────────────────────────────────────
    with session_scope() as s:
        kudos_count = len(s.execute(
            select(Kudos.id).where(Kudos.to_athlete_id == athlete_id)
        ).all())
    st.metric("Kudos Received", kudos_count)


def _show_group_feed(group_id: int, athlete_id: int) -> None:
    """Show recent activity feed for a group."""
    with session_scope() as s:
        messages = s.execute(
            select(GroupMessage.content, GroupMessage.message_type,
                   GroupMessage.created_at, Athlete.first_name, Athlete.last_name)
            .join(Athlete, Athlete.id == GroupMessage.author_athlete_id)
            .where(GroupMessage.group_id == group_id)
            .order_by(GroupMessage.id.desc())
            .limit(10)
        ).all()
    if messages:
        for content, mtype, created, first, last in messages:
            prefix = "" if mtype == "text" else f"[{mtype}] "
            st.caption(f"{first} {last} — {prefix}{content} ({created:%H:%M})")

    # Quick message form
    msg = st.text_input("Post a message", key=f"msg_{group_id}")
    if msg and st.button("Send", key=f"send_{group_id}"):
        with session_scope() as s:
            s.add(GroupMessage(group_id=group_id, author_athlete_id=athlete_id, content=msg))
        st.rerun()


def _show_group_leaderboard(group_id: int) -> None:
    """Show weekly distance leaderboard for a group."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    with session_scope() as s:
        member_ids = [
            row[0] for row in s.execute(
                select(GroupMembership.athlete_id).where(GroupMembership.group_id == group_id)
            ).all()
        ]
        if not member_ids:
            return
        from sqlalchemy import func
        rows = s.execute(
            select(
                TrainingLog.athlete_id,
                func.sum(TrainingLog.distance_km).label("total_km"),
                func.sum(TrainingLog.duration_min).label("total_min"),
                func.count(TrainingLog.id).label("sessions"),
            )
            .where(TrainingLog.athlete_id.in_(member_ids), TrainingLog.date >= week_start)
            .group_by(TrainingLog.athlete_id)
        ).all()
        names = {
            row[0]: f"{row[1]} {row[2]}" for row in s.execute(
                select(Athlete.id, Athlete.first_name, Athlete.last_name)
                .where(Athlete.id.in_(member_ids))
            ).all()
        }
    if rows:
        log_data = [
            {"athlete_id": aid, "name": names.get(aid, "?"), "distance_km": float(km or 0),
             "duration_min": int(mins or 0), "sessions_count": int(ct)}
            for aid, km, mins, ct in rows
        ]
        lb = compute_leaderboard(log_data, metric="distance")
        for entry in lb:
            st.caption(f"#{entry.rank} {entry.name} — {entry.value:.1f} km")


def _trigger_wearable_sync(athlete_id: int, connection_id: int, service: str) -> None:
    """Execute a manual sync for a single wearable connection."""
    from datetime import datetime, timezone
    with session_scope() as s:
        conn = s.get(WearableConnection, connection_id)
        if not conn or conn.sync_status != "active":
            st.error("Connection not active.")
            return
        athlete = s.get(Athlete, athlete_id)
        a_max_hr = athlete.max_hr if athlete else None
        a_resting_hr = athlete.resting_hr if athlete else None

        # Determine adapter
        if service == "garmin":
            from core.services.wearables.garmin import GarminAdapter
            from core.config import get_config
            cfg = get_config()
            adapter = GarminAdapter(
                client_id=getattr(cfg, "garmin_client_id", ""),
                client_secret=getattr(cfg, "garmin_client_secret", ""),
            )
        elif service == "strava":
            from core.services.wearables.strava import StravaAdapter
            from core.config import get_config
            cfg = get_config()
            adapter = StravaAdapter(
                client_id=getattr(cfg, "strava_client_id", ""),
                client_secret=getattr(cfg, "strava_client_secret", ""),
            )
        else:
            st.error(f"Unknown service: {service}")
            return

        # Create sync log
        sync_log = SyncLog(athlete_id=athlete_id, service=service, sync_type="manual")
        s.add(sync_log)
        s.flush()

        try:
            after = default_lookback(conn.last_sync_at)
            activities = fetch_all_activities(adapter, conn.access_token, after=after)
            sync_log.activities_found = len(activities)

            existing_ids = {
                row[0] for row in s.execute(
                    select(TrainingLog.source_id).where(
                        TrainingLog.athlete_id == athlete_id,
                        TrainingLog.source == service,
                        TrainingLog.source_id.isnot(None),
                    )
                ).all()
            }
            existing_dates = {
                row[0] for row in s.execute(
                    select(TrainingLog.date).where(TrainingLog.athlete_id == athlete_id)
                ).all()
            }

            candidates, skipped = prepare_import_batch(
                activities, existing_ids, existing_dates, a_max_hr, a_resting_hr
            )
            sync_log.activities_skipped = skipped

            for cand in candidates:
                log_dict = build_training_log_dict(cand, athlete_id)
                s.add(TrainingLog(**log_dict))
            sync_log.activities_imported = len(candidates)

            conn.last_sync_at = datetime.now(tz=timezone.utc)
            sync_log.status = "completed"
            sync_log.completed_at = datetime.now(tz=timezone.utc)
            st.success(f"Sync complete: {len(candidates)} imported, {skipped} skipped.")
        except Exception as e:
            sync_log.status = "failed"
            sync_log.error_message = str(e)[:500]
            st.error(f"Sync failed: {e}")
