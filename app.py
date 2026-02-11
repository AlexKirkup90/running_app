from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import select

from core.bootstrap import ensure_demo_seeded
from core.db import session_scope
from core.models import Athlete, AthletePreference, CheckIn, CoachIntervention, Event, ImportRun, Plan, PlanDaySession, PlanWeek, SessionLibrary, TrainingLog, User
from core.observability import system_status
from core.security import account_locked, hash_password, verify_password
from core.services.analytics import weekly_summary
from core.services.planning import assign_week_sessions, default_phase_session_tokens, generate_plan_weeks
from core.services.readiness import readiness_band, readiness_score
from core.services.session_library import (
    default_progression,
    default_regression,
    default_structure,
    default_targets,
    validate_session_payload,
)
from core.services.session_engine import (
    adapt_session_structure,
    compute_acute_chronic_ratio,
    hr_range_for_label,
    pace_from_sec_per_km,
    pace_range_for_label,
)

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


def coach_command_center():
    st.header("Command Center")
    with session_scope() as s:
        rows = s.execute(
            select(
                CoachIntervention.id,
                CoachIntervention.athlete_id,
                CoachIntervention.action_type,
                CoachIntervention.status,
                CoachIntervention.risk_score,
                CoachIntervention.confidence_score,
                CoachIntervention.guardrail_reason,
            ).where(CoachIntervention.status == "open")
        ).all()
    if not rows:
        st.success("No open interventions.")
        return
    df = pd.DataFrame(
        [
            {
                "id": iid,
                "athlete_id": athlete_id,
                "action": action,
                "status": status,
                "risk": risk,
                "confidence": confidence,
                "guardrail_reason": guardrail_reason,
            }
            for iid, athlete_id, action, status, risk, confidence, guardrail_reason in rows
        ]
    )
    st.dataframe(df, use_container_width=True)

    with st.form("resolve_intervention"):
        intervention_id = st.number_input("Intervention ID to close", min_value=1, value=int(df.iloc[0]["id"]))
        submit = st.form_submit_button("Mark Closed")
    if submit:
        with session_scope() as s:
            rec = s.get(CoachIntervention, int(intervention_id))
            if rec is None:
                st.error("Intervention not found.")
            else:
                rec.status = "closed"
                st.success(f"Intervention {intervention_id} closed.")
                st.rerun()


def coach_plan_builder():
    st.header("Plan Builder")
    preview_key = "plan_builder_preview_v2"

    def _load_session_catalog(s):
        session_rows = s.execute(select(SessionLibrary.name, SessionLibrary.category, SessionLibrary.tier, SessionLibrary.duration_min)).all()
        by_cat_tier: dict[tuple[str, str], list[str]] = {}
        by_cat: dict[str, list[str]] = {}
        for name, category, tier, _duration in session_rows:
            by_cat_tier.setdefault((category, tier), []).append(name)
            by_cat.setdefault(category, []).append(name)
        return by_cat_tier, by_cat, sorted({r[0] for r in session_rows})

    def _resolve_session_names(by_cat_tier: dict[tuple[str, str], list[str]], by_cat: dict[str, list[str]], week_number: int, tokens: list[str]) -> list[str]:
        tier = ["short", "medium", "long"][(week_number - 1) % 3]
        names: list[str] = []
        for token in tokens:
            match = by_cat_tier.get((token, tier), [])
            if not match:
                match = by_cat.get(token, [])
            names.append(match[0] if match else token)
        return names

    with session_scope() as s:
        athletes = s.execute(select(Athlete.id, Athlete.first_name, Athlete.last_name)).all()
    if not athletes:
        st.warning("No athletes available yet. Add a client first.")
        return
    athlete_options = {f"{first} {last} (#{athlete_id})": athlete_id for athlete_id, first, last in athletes}
    build_tab, manage_tab = st.tabs(["Build & Publish", "Manage Plan Weeks"])

    with build_tab:
        with st.form("plan_builder_preview"):
            athlete_label = st.selectbox("Athlete", list(athlete_options.keys()))
            race_goal = st.selectbox("Race Goal", ["5K", "10K", "Half Marathon", "Marathon"])
            weeks = st.selectbox("Plan Length (weeks)", [12, 24, 36, 48], index=1)
            sessions_per_week = st.slider("Sessions / week", min_value=3, max_value=6, value=4)
            max_session_min = st.slider("Max session minutes", min_value=60, max_value=240, value=140)
            start_date = st.date_input("Start date", value=date.today())
            submit_preview = st.form_submit_button("Preview Plan")

        if submit_preview:
            athlete_id = athlete_options[athlete_label]
            week_rows = generate_plan_weeks(start_date, weeks, race_goal, sessions_per_week, max_session_min)
            with session_scope() as s:
                by_cat_tier, by_cat, _ = _load_session_catalog(s)
            preview_weeks: list[dict] = []
            preview_days: list[dict] = []
            for row in week_rows:
                resolved = _resolve_session_names(by_cat_tier, by_cat, row["week_number"], row["sessions_order"])
                assignments = assign_week_sessions(row["week_start"], resolved)
                preview_weeks.append(
                    {
                        "week_number": row["week_number"],
                        "phase": row["phase"],
                        "week_start": row["week_start"],
                        "week_end": row["week_end"],
                        "target_load": row["target_load"],
                        "sessions_order": resolved,
                        "assignments": assignments,
                    }
                )
                for a in assignments:
                    preview_days.append(
                        {
                            "week_number": row["week_number"],
                            "session_day": a["session_day"],
                            "session_name": a["session_name"],
                            "phase": row["phase"],
                        }
                    )
            st.session_state[preview_key] = {
                "athlete_id": athlete_id,
                "race_goal": race_goal,
                "weeks": weeks,
                "sessions_per_week": sessions_per_week,
                "max_session_min": max_session_min,
                "start_date": start_date,
                "weeks_preview": preview_weeks,
                "day_preview": preview_days,
            }
            st.rerun()

        preview = st.session_state.get(preview_key)
        if preview:
            st.subheader("Plan Preview")
            st.caption(
                f"Athlete #{preview['athlete_id']} | {preview['race_goal']} | {preview['weeks']} weeks | "
                f"{preview['sessions_per_week']} sessions/week"
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "week": w["week_number"],
                            "phase": w["phase"],
                            "week_start": w["week_start"],
                            "week_end": w["week_end"],
                            "target_load": w["target_load"],
                            "sessions": " | ".join(w["sessions_order"]),
                        }
                        for w in preview["weeks_preview"]
                    ]
                ),
                use_container_width=True,
            )
            st.dataframe(pd.DataFrame(preview["day_preview"]).sort_values(["session_day", "week_number"]), use_container_width=True)
            col_publish, col_clear = st.columns(2)
            if col_publish.button("Publish Plan", type="primary"):
                with session_scope() as s:
                    # Deactivate older active plans for same athlete and remove their future day sessions.
                    active_plans = s.execute(select(Plan).where(Plan.athlete_id == preview["athlete_id"], Plan.status == "active")).scalars().all()
                    for p in active_plans:
                        p.status = "archived"
                    future_rows = s.execute(
                        select(PlanDaySession).where(PlanDaySession.athlete_id == preview["athlete_id"], PlanDaySession.session_day >= preview["start_date"])
                    ).scalars().all()
                    for row in future_rows:
                        s.delete(row)

                    plan = Plan(
                        athlete_id=preview["athlete_id"],
                        race_goal=preview["race_goal"],
                        weeks=preview["weeks"],
                        sessions_per_week=preview["sessions_per_week"],
                        max_session_min=preview["max_session_min"],
                        start_date=preview["start_date"],
                        status="active",
                    )
                    s.add(plan)
                    s.flush()
                    for week in preview["weeks_preview"]:
                        week_obj = PlanWeek(
                            plan_id=plan.id,
                            week_number=week["week_number"],
                            phase=week["phase"],
                            week_start=week["week_start"],
                            week_end=week["week_end"],
                            sessions_order=week["sessions_order"],
                            target_load=week["target_load"],
                            locked=False,
                        )
                        s.add(week_obj)
                        s.flush()
                        for assignment in week["assignments"]:
                            s.add(
                                PlanDaySession(
                                    plan_week_id=week_obj.id,
                                    athlete_id=preview["athlete_id"],
                                    session_day=assignment["session_day"],
                                    session_name=assignment["session_name"],
                                    source_template_name=assignment["session_name"],
                                    status="planned",
                                )
                            )
                st.success("Plan published.")
                st.session_state.pop(preview_key, None)
                st.rerun()
            if col_clear.button("Clear Preview"):
                st.session_state.pop(preview_key, None)
                st.rerun()

    with manage_tab:
        with session_scope() as s:
            plan_rows = s.execute(
                select(
                    Plan.id,
                    Plan.athlete_id,
                    Athlete.first_name,
                    Athlete.last_name,
                    Plan.race_goal,
                    Plan.weeks,
                    Plan.sessions_per_week,
                    Plan.start_date,
                    Plan.status,
                )
                .join(Athlete, Athlete.id == Plan.athlete_id)
                .where(Plan.status == "active")
                .order_by(Plan.id.desc())
            ).all()
            by_cat_tier, by_cat, all_session_names = _load_session_catalog(s)
        if not plan_rows:
            st.info("No active plans to manage.")
            return
        plan_options = {
            f"Plan #{pid} | {first} {last} | {goal} | {start_dt}": {
                "id": pid,
                "athlete_id": athlete_id,
                "weeks": week_count,
                "sessions_per_week": sessions_per_week,
                "status": status,
            }
            for pid, athlete_id, first, last, goal, week_count, sessions_per_week, start_dt, status in plan_rows
        }
        plan_label = st.selectbox("Active Plan", list(plan_options.keys()))
        plan_meta = plan_options[plan_label]
        with session_scope() as s:
            week_rows = s.execute(
                select(PlanWeek.id, PlanWeek.week_number, PlanWeek.phase, PlanWeek.week_start, PlanWeek.week_end, PlanWeek.locked)
                .where(PlanWeek.plan_id == plan_meta["id"])
                .order_by(PlanWeek.week_number)
            ).all()
        if not week_rows:
            st.info("No weeks found for the selected plan.")
            return
        week_options = {f"Week {week_number} | {phase} | {week_start}": (week_id, week_number, phase, week_start, week_end, locked) for week_id, week_number, phase, week_start, week_end, locked in week_rows}
        week_label = st.selectbox("Week", list(week_options.keys()))
        week_id, week_number, phase, week_start, week_end, week_locked = week_options[week_label]
        st.caption(f"Locked: {week_locked}")

        with session_scope() as s:
            day_rows = s.execute(
                select(PlanDaySession.id, PlanDaySession.session_day, PlanDaySession.session_name, PlanDaySession.status)
                .where(PlanDaySession.plan_week_id == week_id)
                .order_by(PlanDaySession.session_day)
            ).all()
        st.dataframe(
            pd.DataFrame([{"id": did, "session_day": day, "session_name": name, "status": status} for did, day, name, status in day_rows]),
            use_container_width=True,
        )
        if not all_session_names:
            st.warning("No session templates available. Add templates in Session Library first.")

        col_a, col_b = st.columns(2)
        with col_a:
            with st.form("swap_day_session"):
                if day_rows and all_session_names:
                    day_options = {str(day): did for did, day, _name, _status in day_rows}
                    day_label = st.selectbox("Day to swap", list(day_options.keys()))
                    replacement = st.selectbox("Replacement session", all_session_names)
                    submit_swap = st.form_submit_button("Swap Session")
                else:
                    day_label = None
                    replacement = None
                    submit_swap = st.form_submit_button("Swap Session", disabled=True)
            if submit_swap:
                if week_locked:
                    st.error("Week is locked. Unlock before swapping.")
                else:
                    day_id = day_options[day_label]
                    with session_scope() as s:
                        row = s.get(PlanDaySession, day_id)
                        if row:
                            row.session_name = replacement
                            row.source_template_name = replacement
                            refreshed = s.execute(
                                select(PlanDaySession.session_name).where(PlanDaySession.plan_week_id == week_id).order_by(PlanDaySession.session_day)
                            ).all()
                            week_obj = s.get(PlanWeek, week_id)
                            week_obj.sessions_order = [name for (name,) in refreshed]
                    st.success("Session swapped.")
                    st.rerun()

        with col_b:
            if st.button("Lock / Unlock Week"):
                with session_scope() as s:
                    week_obj = s.get(PlanWeek, week_id)
                    if week_obj:
                        week_obj.locked = not week_obj.locked
                st.success("Week lock state updated.")
                st.rerun()

            if st.button("Regenerate Week"):
                if week_locked:
                    st.error("Week is locked. Unlock before regenerating.")
                elif not all_session_names:
                    st.error("No session templates available to regenerate this week.")
                else:
                    sessions_tokens = default_phase_session_tokens(phase, int(plan_meta["sessions_per_week"]))
                    resolved = _resolve_session_names(by_cat_tier, by_cat, week_number, sessions_tokens)
                    assignments = assign_week_sessions(week_start, resolved)
                    with session_scope() as s:
                        existing = s.execute(select(PlanDaySession).where(PlanDaySession.plan_week_id == week_id)).scalars().all()
                        for row in existing:
                            s.delete(row)
                        for a in assignments:
                            s.add(
                                PlanDaySession(
                                    plan_week_id=week_id,
                                    athlete_id=plan_meta["athlete_id"],
                                    session_day=a["session_day"],
                                    session_name=a["session_name"],
                                    source_template_name=a["session_name"],
                                    status="planned",
                                )
                            )
                        week_obj = s.get(PlanWeek, week_id)
                        if week_obj:
                            week_obj.sessions_order = [a["session_name"] for a in assignments]
                    st.success("Week regenerated.")
                    st.rerun()


def coach_session_library():
    st.header("Session Library")
    with session_scope() as s:
        rows = s.execute(
            select(
                SessionLibrary.id,
                SessionLibrary.name,
                SessionLibrary.category,
                SessionLibrary.intent,
                SessionLibrary.energy_system,
                SessionLibrary.tier,
                SessionLibrary.is_treadmill,
                SessionLibrary.duration_min,
                SessionLibrary.structure_json,
                SessionLibrary.targets_json,
                SessionLibrary.progression_json,
                SessionLibrary.regression_json,
                SessionLibrary.prescription,
                SessionLibrary.coaching_notes,
            )
        ).all()
    if not rows:
        st.warning("Session library is empty. Add your first template below.")

    full_rows = [
        {
            "id": sid,
            "name": name,
            "category": category,
            "intent": intent,
            "energy_system": energy_system,
            "tier": tier,
            "treadmill": treadmill,
            "duration_min": duration_min,
            "structure_json": structure_json,
            "targets_json": targets_json,
            "progression_json": progression_json,
            "regression_json": regression_json,
            "prescription": prescription,
            "coaching_notes": coaching_notes,
        }
        for (
            sid,
            name,
            category,
            intent,
            energy_system,
            tier,
            treadmill,
            duration_min,
            structure_json,
            targets_json,
            progression_json,
            regression_json,
            prescription,
            coaching_notes,
        ) in rows
    ]
    df = pd.DataFrame(full_rows)

    def _json_or_none(raw: str, label: str, errors: list[str]):
        try:
            return json.loads(raw)
        except Exception as exc:
            errors.append(f"{label} is not valid JSON: {exc}")
            return None

    browse_tab, add_tab, edit_tab, delete_tab = st.tabs(["Browse", "Add", "Edit", "Delete"])

    with browse_tab:
        if df.empty:
            st.info("No templates yet.")
        else:
            categories = sorted(df["category"].unique().tolist())
            intents = sorted(df["intent"].unique().tolist())
            selected_categories = st.multiselect("Category", categories, default=categories)
            selected_intents = st.multiselect("Intent", intents, default=intents)
            treadmill_only = st.checkbox("Treadmill only", value=False)
            min_dur, max_dur = int(df["duration_min"].min()), int(df["duration_min"].max())
            duration_range = st.slider("Duration range (min)", min_value=min_dur, max_value=max_dur, value=(min_dur, max_dur))

            filtered = df[df["category"].isin(selected_categories) & df["intent"].isin(selected_intents)]
            if treadmill_only:
                filtered = filtered[filtered["treadmill"]]
            filtered = filtered[(filtered["duration_min"] >= duration_range[0]) & (filtered["duration_min"] <= duration_range[1])]
            st.caption(f"{len(filtered)} sessions")
            st.dataframe(filtered[["id", "name", "category", "intent", "energy_system", "tier", "treadmill", "duration_min"]].sort_values(["category", "duration_min", "name"]), use_container_width=True)

    with add_tab:
        st.subheader("Add Session Template")
        with st.form("session_add"):
            name = st.text_input("Name")
            category = st.text_input("Category", value="Easy Run")
            intent = st.text_input("Intent", value="easy_aerobic")
            energy_system = st.text_input("Energy System", value="aerobic_base")
            tier = st.selectbox("Tier", ["short", "medium", "long"], index=1)
            is_treadmill = st.checkbox("Treadmill Session", value=False)
            duration_min = st.number_input("Duration (min)", min_value=10, value=45)
            structure_text = st.text_area("Structure JSON", value=json.dumps(default_structure(int(duration_min)), indent=2), height=220)
            targets_text = st.text_area("Targets JSON", value=json.dumps(default_targets(), indent=2), height=180)
            progression_text = st.text_area("Progression JSON", value=json.dumps(default_progression(), indent=2), height=120)
            regression_text = st.text_area("Regression JSON", value=json.dumps(default_regression(), indent=2), height=120)
            prescription = st.text_area("Prescription", value="Detailed running prescription including warmup, main set, and cooldown.")
            coaching_notes = st.text_area("Coaching Notes", value="Adapt using readiness, pain flags, and recent load.")
            submit_add = st.form_submit_button("Create Template")

        if submit_add:
            parse_errors: list[str] = []
            structure_json = _json_or_none(structure_text, "Structure JSON", parse_errors)
            targets_json = _json_or_none(targets_text, "Targets JSON", parse_errors)
            progression_json = _json_or_none(progression_text, "Progression JSON", parse_errors)
            regression_json = _json_or_none(regression_text, "Regression JSON", parse_errors)
            payload = {
                "name": name,
                "category": category,
                "intent": intent,
                "energy_system": energy_system,
                "tier": tier,
                "is_treadmill": is_treadmill,
                "duration_min": int(duration_min),
                "structure_json": structure_json,
                "targets_json": targets_json,
                "progression_json": progression_json,
                "regression_json": regression_json,
                "prescription": prescription,
                "coaching_notes": coaching_notes,
            }
            errors = parse_errors + validate_session_payload(payload)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                with session_scope() as s:
                    dup = s.execute(select(SessionLibrary.id).where(SessionLibrary.name == name.strip())).scalar_one_or_none()
                    if dup:
                        st.error("A session with this name already exists.")
                    else:
                        s.add(
                            SessionLibrary(
                                name=name.strip(),
                                category=category.strip(),
                                intent=intent.strip(),
                                energy_system=energy_system.strip(),
                                tier=tier,
                                is_treadmill=is_treadmill,
                                duration_min=int(duration_min),
                                structure_json=structure_json,
                                targets_json=targets_json,
                                progression_json=progression_json,
                                regression_json=regression_json,
                                prescription=prescription.strip(),
                                coaching_notes=coaching_notes.strip(),
                            )
                        )
                        st.success("Session template created.")
                        st.rerun()

    with edit_tab:
        st.subheader("Edit Session Template")
        if df.empty:
            st.info("No templates available to edit.")
        else:
            options = {f"{row['name']} (#{int(row['id'])})": int(row["id"]) for _, row in df.iterrows()}
            selected_label = st.selectbox("Select template", list(options.keys()))
            selected_id = options[selected_label]
            current = next(row for row in full_rows if row["id"] == selected_id)
            with st.form("session_edit"):
                name = st.text_input("Name", value=current["name"])
                category = st.text_input("Category", value=current["category"])
                intent = st.text_input("Intent", value=current["intent"])
                energy_system = st.text_input("Energy System", value=current["energy_system"])
                tier = st.selectbox("Tier", ["short", "medium", "long"], index=["short", "medium", "long"].index(current["tier"]) if current["tier"] in {"short", "medium", "long"} else 1)
                is_treadmill = st.checkbox("Treadmill Session", value=bool(current["treadmill"]))
                duration_min = st.number_input("Duration (min)", min_value=10, value=int(current["duration_min"]))
                structure_text = st.text_area("Structure JSON", value=json.dumps(current["structure_json"], indent=2), height=220)
                targets_text = st.text_area("Targets JSON", value=json.dumps(current["targets_json"], indent=2), height=180)
                progression_text = st.text_area("Progression JSON", value=json.dumps(current["progression_json"], indent=2), height=120)
                regression_text = st.text_area("Regression JSON", value=json.dumps(current["regression_json"], indent=2), height=120)
                prescription = st.text_area("Prescription", value=current["prescription"])
                coaching_notes = st.text_area("Coaching Notes", value=current["coaching_notes"])
                submit_edit = st.form_submit_button("Save Changes")

            if submit_edit:
                parse_errors: list[str] = []
                structure_json = _json_or_none(structure_text, "Structure JSON", parse_errors)
                targets_json = _json_or_none(targets_text, "Targets JSON", parse_errors)
                progression_json = _json_or_none(progression_text, "Progression JSON", parse_errors)
                regression_json = _json_or_none(regression_text, "Regression JSON", parse_errors)
                payload = {
                    "name": name,
                    "category": category,
                    "intent": intent,
                    "energy_system": energy_system,
                    "tier": tier,
                    "is_treadmill": is_treadmill,
                    "duration_min": int(duration_min),
                    "structure_json": structure_json,
                    "targets_json": targets_json,
                    "progression_json": progression_json,
                    "regression_json": regression_json,
                    "prescription": prescription,
                    "coaching_notes": coaching_notes,
                }
                errors = parse_errors + validate_session_payload(payload)
                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    with session_scope() as s:
                        dup = s.execute(select(SessionLibrary.id).where(SessionLibrary.name == name.strip(), SessionLibrary.id != selected_id)).scalar_one_or_none()
                        if dup:
                            st.error("Another session with this name already exists.")
                        else:
                            session_obj = s.get(SessionLibrary, selected_id)
                            if session_obj is None:
                                st.error("Session not found.")
                            else:
                                session_obj.name = name.strip()
                                session_obj.category = category.strip()
                                session_obj.intent = intent.strip()
                                session_obj.energy_system = energy_system.strip()
                                session_obj.tier = tier
                                session_obj.is_treadmill = is_treadmill
                                session_obj.duration_min = int(duration_min)
                                session_obj.structure_json = structure_json
                                session_obj.targets_json = targets_json
                                session_obj.progression_json = progression_json
                                session_obj.regression_json = regression_json
                                session_obj.prescription = prescription.strip()
                                session_obj.coaching_notes = coaching_notes.strip()
                                st.success("Session template updated.")
                                st.rerun()

    with delete_tab:
        st.subheader("Delete Session Template")
        if df.empty:
            st.info("No templates available to delete.")
        else:
            options = {f"{row['name']} (#{int(row['id'])})": int(row["id"]) for _, row in df.iterrows()}
            selected_label = st.selectbox("Select template to delete", list(options.keys()), key="delete_session_select")
            selected_id = options[selected_label]
            confirm = st.checkbox("I understand this will permanently delete the template.", key="delete_session_confirm")
            if st.button("Delete Template", type="secondary"):
                if not confirm:
                    st.error("Please confirm deletion.")
                else:
                    with session_scope() as s:
                        session_obj = s.get(SessionLibrary, selected_id)
                        if session_obj is None:
                            st.error("Session not found.")
                        else:
                            s.delete(session_obj)
                            st.success("Session template deleted.")
                            st.rerun()


def coach_portfolio_analytics():
    st.header("Portfolio Analytics")
    with session_scope() as s:
        rows = s.execute(select(TrainingLog.athlete_id, TrainingLog.date, TrainingLog.duration_min, TrainingLog.load_score)).all()
    if not rows:
        st.info("No training logs available yet.")
        return
    df = pd.DataFrame([{"athlete_id": athlete_id, "date": d, "duration_min": mins, "load_score": load} for athlete_id, d, mins, load in rows])
    summary = df.groupby("athlete_id", as_index=False).agg(total_sessions=("athlete_id", "count"), total_minutes=("duration_min", "sum"), total_load=("load_score", "sum"))
    st.dataframe(summary.sort_values("total_load", ascending=False), use_container_width=True)


def coach_integrations():
    st.header("Integrations")
    with session_scope() as s:
        runs = s.execute(select(ImportRun.id, ImportRun.adapter_name, ImportRun.status, ImportRun.created_at).order_by(ImportRun.id.desc())).all()
    if not runs:
        st.info("No import runs yet.")
        return
    st.dataframe(
        pd.DataFrame([{"id": rid, "adapter": adapter, "status": status, "created_at": created_at} for rid, adapter, status, created_at in runs]),
        use_container_width=True,
    )


def coach_admin_tools():
    st.header("Admin Tools")
    if st.button("Run Demo Bootstrap", type="primary"):
        try:
            ensure_demo_seeded()
            st.success("Bootstrap completed.")
        except Exception as e:
            st.error(f"Bootstrap failed: {e}")
    with session_scope() as s:
        counts = {
            "athletes": len(s.execute(select(Athlete.id)).all()),
            "users": len(s.execute(select(User.id)).all()),
            "sessions_library": len(s.execute(select(SessionLibrary.id)).all()),
            "plans": len(s.execute(select(Plan.id)).all()),
            "training_logs": len(s.execute(select(TrainingLog.id)).all()),
        }
    st.json(counts)


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


def athlete_dashboard(athlete_id: int):
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
                existing.sleep = sleep
                existing.energy = energy
                existing.recovery = recovery
                existing.stress = stress
                existing.training_today = training_today
                st.success("Check-in updated")
            else:
                s.add(CheckIn(athlete_id=athlete_id, day=date.today(), sleep=sleep, energy=energy, recovery=recovery, stress=stress, training_today=training_today))
                st.success("Saved")
        st.rerun()


def athlete_log(athlete_id: int):
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
            st.success("Session saved for today.")
        st.rerun()


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


def athlete_events(athlete_id: int):
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
        st.success("Event added.")
        st.rerun()


def athlete_profile(athlete_id: int):
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
            if page == "Dashboard":
                coach_dashboard()
            elif page == "Command Center":
                coach_command_center()
            elif page == "Clients":
                coach_clients()
            elif page == "Add Client":
                add_client()
            elif page == "Plan Builder":
                coach_plan_builder()
            elif page == "Session Library":
                coach_session_library()
            elif page == "Portfolio Analytics":
                coach_portfolio_analytics()
            elif page == "Integrations":
                coach_integrations()
            elif page == "Admin Tools":
                coach_admin_tools()
        else:
            page = st.sidebar.radio("Athlete", ["Dashboard", "Log Session", "Check-In", "Events", "Analytics", "Profile"])
            athlete_id = st.session_state.athlete_id
            if page == "Dashboard":
                athlete_dashboard(athlete_id)
            elif page == "Log Session":
                athlete_log(athlete_id)
            elif page == "Check-In":
                athlete_checkin(athlete_id)
            elif page == "Events":
                athlete_events(athlete_id)
            elif page == "Analytics":
                athlete_analytics(athlete_id)
            elif page == "Profile":
                athlete_profile(athlete_id)
    except Exception as e:
        log_runtime_error("main", e)
        st.error("Something went wrong. The issue has been logged.")


if __name__ == "__main__":
    main()
