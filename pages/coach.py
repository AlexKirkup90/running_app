from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from core.db import session_scope
from core.models import (
    Athlete,
    Challenge,
    ChallengeEntry,
    CheckIn,
    CoachActionLog,
    CoachAssignment,
    CoachIntervention,
    CoachNotesTask,
    Event,
    GroupMembership,
    ImportRun,
    OrgMembership,
    Organization,
    Plan,
    PlanDaySession,
    PlanWeek,
    SessionLibrary,
    SyncLog,
    TrainingGroup,
    TrainingLog,
    User,
    WearableConnection,
)
from core.security import hash_password
from core.services.analytics import weekly_summary
from core.services.case_management import build_case_timeline
from core.services.command_center import risk_priority, sync_interventions_queue
from core.services.planning import assign_week_sessions, default_phase_session_tokens, generate_plan_weeks
from core.services.session_library import (
    default_progression,
    default_regression,
    default_structure,
    default_targets,
    validate_session_payload,
)
from core.services.plan_adjuster import assess_adherence_trend, detect_pain_cluster, recommend_adjustments
from core.services.training_load import compute_session_load, compute_weekly_metrics, overtraining_risk
from core.services.workload import queue_snapshot

logger = logging.getLogger(__name__)


def coach_dashboard() -> None:
    st.header("Coach Dashboard")
    try:
        sync_interventions_queue()
    except Exception:
        pass
    with session_scope() as s:
        athletes = s.execute(select(Athlete.id, Athlete.status)).all()
        logs = s.execute(select(TrainingLog.id, TrainingLog.date, TrainingLog.duration_min, TrainingLog.load_score)).all()
        intervs = s.execute(
            select(Athlete.first_name, Athlete.last_name, CoachIntervention.action_type, CoachIntervention.risk_score, CoachIntervention.confidence_score)
            .join(Athlete, Athlete.id == CoachIntervention.athlete_id)
            .where(CoachIntervention.status == "open")
            .order_by(CoachIntervention.risk_score.desc(), CoachIntervention.id.desc())
        ).all()
    active = sum(1 for _, status in athletes if status == "active")
    archived = sum(1 for _, status in athletes if status == "archived")
    deleted = sum(1 for _, status in athletes if status == "deleted")
    a1, a2, a3 = st.columns(3)
    a1.metric("Active", active)
    a2.metric("Archived", archived)
    a3.metric("Deleted", deleted)
    st.subheader("Command Center Queue")
    for first_name, last_name, action_type, risk_score, confidence_score in intervs[:20]:
        st.write(
            f"{first_name} {last_name}: {action_type} | "
            f"priority {risk_priority(float(risk_score or 0))} | "
            f"risk {risk_score} | conf {confidence_score}"
        )

    if logs:
        df = pd.DataFrame([{"id": log_id, "date": log_date, "duration_min": duration_min, "load_score": load_score} for log_id, log_date, duration_min, load_score in logs])
        w = weekly_summary(df)
        st.altair_chart(
            alt.Chart(w).mark_line(point=True).encode(x="week:N", y="load_score:Q", tooltip=["week", "load_score", "sessions"]),
            use_container_width=True,
        )


def coach_clients() -> None:
    st.header("Clients")
    with session_scope() as s:
        rows = s.execute(select(Athlete.id, Athlete.first_name, Athlete.last_name, Athlete.email, Athlete.status)).all()
        open_interventions = {
            athlete_id: (count_open, max_risk)
            for athlete_id, count_open, max_risk in s.execute(
                select(
                    CoachIntervention.athlete_id,
                    func.count(CoachIntervention.id),
                    func.max(CoachIntervention.risk_score),
                ).where(CoachIntervention.status == "open").group_by(CoachIntervention.athlete_id)
            ).all()
        }
        last_checkin = {
            athlete_id: day
            for athlete_id, day in s.execute(select(CheckIn.athlete_id, func.max(CheckIn.day)).group_by(CheckIn.athlete_id)).all()
        }
        last_log = {
            athlete_id: day
            for athlete_id, day in s.execute(select(TrainingLog.athlete_id, func.max(TrainingLog.date)).group_by(TrainingLog.athlete_id)).all()
        }
    data = []
    for athlete_id, first_name, last_name, email, status in rows:
        open_count, max_risk = open_interventions.get(athlete_id, (0, 0.0))
        data.append(
            {
                "id": athlete_id,
                "name": f"{first_name} {last_name}",
                "email": email,
                "status": status,
                "open_interventions": int(open_count or 0),
                "highest_risk": float(max_risk or 0),
                "risk_priority": risk_priority(float(max_risk or 0)) if open_count else "none",
                "last_checkin": last_checkin.get(athlete_id),
                "last_log": last_log.get(athlete_id),
            }
        )
    st.dataframe(pd.DataFrame(data), use_container_width=True)


def _apply_intervention_decision(
    s,
    rec: CoachIntervention,
    decision: str,
    note: str,
    modified_action: str | None,
    actor_user_id: int,
) -> None:
    note_fragment = note.strip() if note.strip() else "no_note"
    if decision == "accept_and_close":
        rec.status = "closed"
        rec.cooldown_until = None
        rec.why_factors = list(rec.why_factors or []) + [f"decision:accepted:{note_fragment}"]
    elif decision == "defer_24h":
        rec.cooldown_until = datetime.utcnow() + timedelta(hours=24)
        rec.why_factors = list(rec.why_factors or []) + [f"decision:defer_24h:{note_fragment}"]
    elif decision == "defer_72h":
        rec.cooldown_until = datetime.utcnow() + timedelta(hours=72)
        rec.why_factors = list(rec.why_factors or []) + [f"decision:defer_72h:{note_fragment}"]
    elif decision == "modify_action":
        rec.action_type = modified_action or rec.action_type
        rec.cooldown_until = None
        rec.why_factors = list(rec.why_factors or []) + [f"decision:modified:{note_fragment}"]
    else:
        rec.status = "closed"
        rec.cooldown_until = None
        rec.why_factors = list(rec.why_factors or []) + [f"decision:dismissed:{note_fragment}"]

    s.add(
        CoachActionLog(
            coach_user_id=actor_user_id,
            athlete_id=int(rec.athlete_id),
            action=f"intervention_{decision}",
            payload={
                "intervention_id": int(rec.id),
                "action_type": rec.action_type,
                "note": note.strip(),
            },
        )
    )
    logger.info("Intervention %d: decision=%s by user=%d", rec.id, decision, actor_user_id)


def coach_command_center() -> None:
    st.header("Command Center")
    queue_tab, case_tab = st.tabs(["Queue", "Casework"])

    with queue_tab:
        with st.expander("Queue Refresh", expanded=True):
            if st.button("Refresh Queue", type="primary"):
                try:
                    result = sync_interventions_queue()
                    st.success(f"Queue refreshed: +{result['created']} created, {result['updated']} updated, {result['closed']} closed.")
                except Exception as e:
                    st.error(f"Queue refresh failed: {e}")

        try:
            sync_interventions_queue()
        except Exception:
            pass

        with session_scope() as s:
            rows = s.execute(
                select(
                    CoachIntervention.id,
                    CoachIntervention.athlete_id,
                    Athlete.first_name,
                    Athlete.last_name,
                    CoachIntervention.action_type,
                    CoachIntervention.status,
                    CoachIntervention.risk_score,
                    CoachIntervention.confidence_score,
                    CoachIntervention.guardrail_reason,
                    CoachIntervention.why_factors,
                    CoachIntervention.expected_impact,
                    CoachIntervention.cooldown_until,
                    CoachIntervention.created_at,
                )
                .join(Athlete, Athlete.id == CoachIntervention.athlete_id)
                .where(CoachIntervention.status == "open")
                .order_by(CoachIntervention.risk_score.desc(), CoachIntervention.id.desc())
            ).all()
        if not rows:
            st.success("No open interventions.")
        else:
            now = datetime.utcnow()
            df = pd.DataFrame(
                [
                    {
                        "id": iid,
                        "athlete_id": athlete_id,
                        "athlete": f"{first_name} {last_name}",
                        "action": action,
                        "status": status,
                        "risk": risk,
                        "priority": risk_priority(float(risk or 0)),
                        "confidence": confidence,
                        "guardrail_reason": guardrail_reason,
                        "why_factors": ", ".join(why_factors or []),
                        "signals": (expected_impact or {}).get("signals", {}),
                        "cooldown_until": cooldown_until,
                        "created_at": created_at,
                        "age_hours": round(max(0.0, (now - created_at).total_seconds() / 3600.0), 1) if created_at else None,
                        "is_snoozed": bool(cooldown_until and cooldown_until > now),
                    }
                    for (
                        iid,
                        athlete_id,
                        first_name,
                        last_name,
                        action,
                        status,
                        risk,
                        confidence,
                        guardrail_reason,
                        why_factors,
                        expected_impact,
                        cooldown_until,
                        created_at,
                    ) in rows
                ]
            )
            snapshot = queue_snapshot(df.to_dict(orient="records"), now)

            if "case_athlete_id" not in st.session_state:
                st.session_state.case_athlete_id = int(df.iloc[0]["athlete_id"])

            actionable_df = df[~df["is_snoozed"]]
            snoozed_df = df[df["is_snoozed"]]

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Open", snapshot.open_count)
            c2.metric("High Priority", snapshot.high_priority)
            c3.metric("Actionable Now", snapshot.actionable_now)
            c4.metric("Snoozed", snapshot.snoozed)
            c5.metric("SLA Due 24h", snapshot.sla_due_24h)
            c6.metric("SLA Due 72h", snapshot.sla_due_72h)
            st.caption(f"Median queue age: {snapshot.median_age_hours}h | Oldest: {snapshot.oldest_age_hours}h")

            st.subheader("Actionable Queue")
            if actionable_df.empty:
                st.info("No actionable interventions right now.")
            else:
                st.dataframe(actionable_df.drop(columns=["is_snoozed"]), use_container_width=True)
            if not snoozed_df.empty:
                st.subheader("Snoozed")
                st.dataframe(snoozed_df.drop(columns=["is_snoozed"]), use_container_width=True)

            athlete_labels = {}
            for _, row in df.iterrows():
                aid = int(row["athlete_id"])
                athlete_labels[f"{row['athlete']} (#{aid})"] = aid
            focus_label = st.selectbox("Open Athlete in Casework", list(athlete_labels.keys()))
            if st.button("Focus Athlete"):
                st.session_state.case_athlete_id = athlete_labels[focus_label]
                st.success("Athlete focused for Casework tab.")

            action_options = ["recovery_week", "taper_week", "contact_athlete", "monitor"]
            intervention_lookup = {str(int(row["id"])): int(row["id"]) for _, row in df.iterrows()}
            st.subheader("Batch Queue Actions")
            batch_label_map = {
                f"{int(row['id'])} | {row['athlete']} | {row['action']} | risk {row['risk']}": int(row["id"])
                for _, row in actionable_df.iterrows()
            }
            with st.form("batch_resolve_interventions"):
                selected_batch_labels = st.multiselect("Interventions", list(batch_label_map.keys()), key="batch_intervention_ids")
                batch_decision = st.selectbox(
                    "Batch Decision",
                    ["accept_and_close", "defer_24h", "defer_72h", "modify_action", "dismiss"],
                    key="batch_decision",
                )
                batch_modified_action = None
                if batch_decision == "modify_action":
                    batch_modified_action = st.selectbox("Batch Modified action", action_options, index=0, key="batch_modified_action")
                batch_note = st.text_input("Batch Note", value="", key="batch_note")
                batch_submit = st.form_submit_button("Apply Batch Action")
            if batch_submit:
                if not selected_batch_labels:
                    st.error("Select at least one intervention for batch action.")
                else:
                    selected_ids = [batch_label_map[label] for label in selected_batch_labels]
                    applied = 0
                    with session_scope() as s:
                        for intervention_id in selected_ids:
                            rec = s.get(CoachIntervention, int(intervention_id))
                            if rec is None or rec.status != "open":
                                continue
                            _apply_intervention_decision(
                                s,
                                rec,
                                batch_decision,
                                batch_note,
                                batch_modified_action,
                                int(st.session_state.user_id),
                            )
                            applied += 1
                    st.success(f"Batch action applied to {applied} intervention(s).")
                    st.rerun()

            st.subheader("Single Intervention Action")
            with st.form("resolve_intervention"):
                intervention_id_label = st.selectbox("Intervention ID", list(intervention_lookup.keys()), key="single_intervention_id")
                decision = st.selectbox("Decision", ["accept_and_close", "defer_24h", "defer_72h", "modify_action", "dismiss"], key="single_decision")
                modified_action = None
                if decision == "modify_action":
                    modified_action = st.selectbox("Modified action", action_options, index=0, key="single_modified_action")
                note = st.text_input("Note", value="", key="single_note")
                submit = st.form_submit_button("Apply Decision")
            if submit:
                intervention_id = intervention_lookup[intervention_id_label]
                with session_scope() as s:
                    rec = s.get(CoachIntervention, int(intervention_id))
                    if rec is None:
                        st.error("Intervention not found.")
                    else:
                        _apply_intervention_decision(
                            s,
                            rec,
                            decision,
                            note,
                            modified_action,
                            int(st.session_state.user_id),
                        )
                        st.success(f"Intervention {intervention_id} updated.")
                        st.rerun()

    with case_tab:
        with session_scope() as s:
            athlete_rows = s.execute(
                select(
                    Athlete.id,
                    Athlete.first_name,
                    Athlete.last_name,
                    func.count(CoachIntervention.id),
                    func.max(CoachIntervention.risk_score),
                )
                .outerjoin(CoachIntervention, (CoachIntervention.athlete_id == Athlete.id) & (CoachIntervention.status == "open"))
                .where(Athlete.status == "active")
                .group_by(Athlete.id, Athlete.first_name, Athlete.last_name)
                .order_by(Athlete.first_name, Athlete.last_name)
            ).all()
        if not athlete_rows:
            st.info("No active athletes available.")
            return

        athlete_options: dict[str, int] = {}
        athlete_ids: list[int] = []
        for athlete_id, first_name, last_name, open_count, max_risk in athlete_rows:
            label = (
                f"{first_name} {last_name} (#{athlete_id}) | "
                f"open={int(open_count or 0)} | priority={risk_priority(float(max_risk or 0)) if open_count else 'none'}"
            )
            athlete_options[label] = int(athlete_id)
            athlete_ids.append(int(athlete_id))

        current_case_athlete = int(st.session_state.get("case_athlete_id", athlete_ids[0]))
        if current_case_athlete not in athlete_ids:
            current_case_athlete = athlete_ids[0]
        default_idx = athlete_ids.index(current_case_athlete)
        case_label = st.selectbox("Athlete Case", list(athlete_options.keys()), index=default_idx)
        athlete_id = athlete_options[case_label]
        st.session_state.case_athlete_id = athlete_id

        with session_scope() as s:
            open_interventions = s.execute(
                select(
                    CoachIntervention.id,
                    CoachIntervention.action_type,
                    CoachIntervention.risk_score,
                    CoachIntervention.confidence_score,
                    CoachIntervention.guardrail_reason,
                    CoachIntervention.why_factors,
                    CoachIntervention.cooldown_until,
                    CoachIntervention.created_at,
                )
                .where(CoachIntervention.athlete_id == athlete_id, CoachIntervention.status == "open")
                .order_by(CoachIntervention.risk_score.desc(), CoachIntervention.id.desc())
            ).all()
            action_logs = s.execute(
                select(CoachActionLog.action, CoachActionLog.payload, CoachActionLog.created_at)
                .where(CoachActionLog.athlete_id == athlete_id)
                .order_by(CoachActionLog.created_at.desc())
                .limit(120)
            ).all()
            notes_tasks = s.execute(
                select(CoachNotesTask.id, CoachNotesTask.note, CoachNotesTask.due_date, CoachNotesTask.completed)
                .where(CoachNotesTask.athlete_id == athlete_id)
                .order_by(CoachNotesTask.completed.asc(), CoachNotesTask.due_date.asc(), CoachNotesTask.id.desc())
                .limit(120)
            ).all()
            recent_logs = s.execute(
                select(TrainingLog.date, TrainingLog.session_category, TrainingLog.duration_min, TrainingLog.rpe, TrainingLog.pain_flag, TrainingLog.load_score)
                .where(TrainingLog.athlete_id == athlete_id)
                .order_by(TrainingLog.date.desc())
                .limit(30)
            ).all()
            recent_checkins = s.execute(
                select(CheckIn.day, CheckIn.sleep, CheckIn.energy, CheckIn.recovery, CheckIn.stress)
                .where(CheckIn.athlete_id == athlete_id)
                .order_by(CheckIn.day.desc())
                .limit(30)
            ).all()
            upcoming_events = s.execute(
                select(Event.event_date, Event.name, Event.distance)
                .where(Event.athlete_id == athlete_id, Event.event_date >= date.today())
                .order_by(Event.event_date.asc())
                .limit(10)
            ).all()

        open_tasks = sum(1 for _id, _note, _due, completed in notes_tasks if not completed)
        last_log_day = recent_logs[0][0] if recent_logs else None
        days_since_log = (date.today() - last_log_day).days if last_log_day else None
        m1, m2, m3 = st.columns(3)
        m1.metric("Open Interventions", len(open_interventions))
        m2.metric("Open Notes/Tasks", open_tasks)
        m3.metric("Days Since Last Log", days_since_log if days_since_log is not None else "n/a")

        if open_interventions:
            st.subheader("Open Interventions")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "id": iid,
                            "action": action,
                            "risk": risk,
                            "priority": risk_priority(float(risk or 0)),
                            "confidence": confidence,
                            "guardrail_reason": guardrail_reason,
                            "why_factors": ", ".join(why_factors or []),
                            "cooldown_until": cooldown_until,
                            "created_at": created_at,
                            "age_hours": round(max(0.0, (datetime.utcnow() - created_at).total_seconds() / 3600.0), 1) if created_at else None,
                        }
                        for iid, action, risk, confidence, guardrail_reason, why_factors, cooldown_until, created_at in open_interventions
                    ]
                ),
                use_container_width=True,
            )

        notes_tab, timeline_tab, context_tab = st.tabs(["Notes & Tasks", "Timeline", "Recent Context"])

        with notes_tab:
            with st.form("add_case_task"):
                note = st.text_area("Coach note / task")
                set_due = st.checkbox("Set due date", value=True)
                due = st.date_input("Due date", value=date.today() + timedelta(days=2))
                submit_note = st.form_submit_button("Add Task")
            if submit_note:
                if not note.strip():
                    st.error("Note/task text is required.")
                else:
                    with session_scope() as s:
                        due_date = due if set_due else None
                        task = CoachNotesTask(athlete_id=athlete_id, note=note.strip(), due_date=due_date, completed=False)
                        s.add(task)
                        s.add(
                            CoachActionLog(
                                coach_user_id=int(st.session_state.user_id),
                                athlete_id=athlete_id,
                                action="note_task_added",
                                payload={"note": note.strip(), "due_date": str(due_date) if due_date else None},
                            )
                        )
                    st.success("Task added.")
                    st.rerun()

            if notes_tasks:
                tasks_df = pd.DataFrame(
                    [
                        {"id": tid, "note": note, "due_date": due_date, "completed": completed}
                        for tid, note, due_date, completed in notes_tasks
                    ]
                )
                st.dataframe(tasks_df, use_container_width=True)

                task_lookup = {
                    f"#{tid} | {'done' if completed else 'open'} | due={due_date} | {note[:40]}": tid
                    for tid, note, due_date, completed in notes_tasks
                }
                with st.form("update_case_task"):
                    task_label = st.selectbox("Task", list(task_lookup.keys()))
                    task_action = st.selectbox("Update", ["mark_completed", "reopen", "delete"])
                    task_submit = st.form_submit_button("Apply Task Update")
                if task_submit:
                    task_id = int(task_lookup[task_label])
                    with session_scope() as s:
                        task = s.get(CoachNotesTask, task_id)
                        if not task:
                            st.error("Task not found.")
                        else:
                            if task_action == "mark_completed":
                                task.completed = True
                            elif task_action == "reopen":
                                task.completed = False
                            else:
                                s.delete(task)
                            s.add(
                                CoachActionLog(
                                    coach_user_id=int(st.session_state.user_id),
                                    athlete_id=athlete_id,
                                    action=f"note_task_{task_action}",
                                    payload={"task_id": task_id},
                                )
                            )
                            st.success("Task updated.")
                            st.rerun()
            else:
                st.info("No notes/tasks yet for this athlete.")

        with timeline_tab:
            timeline = build_case_timeline(
                coach_actions=[{"action": action, "payload": payload, "created_at": created_at} for action, payload, created_at in action_logs],
                training_logs=[
                    {"date": d, "session_category": category, "rpe": rpe, "pain_flag": pain_flag}
                    for d, category, _duration, rpe, pain_flag, _load in recent_logs
                ],
                checkins=[
                    {"day": day, "sleep": sleep, "energy": energy, "recovery": recovery, "stress": stress}
                    for day, sleep, energy, recovery, stress in recent_checkins
                ],
                events=[{"event_date": event_date, "name": name, "distance": distance} for event_date, name, distance in upcoming_events],
                notes_tasks=[{"id": tid, "note": note, "due_date": due_date, "completed": completed} for tid, note, due_date, completed in notes_tasks],
            )
            if not timeline:
                st.info("No timeline entries yet.")
            else:
                timeline_df = pd.DataFrame(
                    [
                        {
                            "when": item["when"].strftime("%Y-%m-%d %H:%M"),
                            "source": item["source"],
                            "title": item["title"],
                            "detail": item["detail"],
                        }
                        for item in timeline[:120]
                    ]
                )
                st.dataframe(timeline_df, use_container_width=True)

        with context_tab:
            # Training load analysis
            if recent_logs:
                st.subheader("Training Load Analysis")
                daily_loads = []
                for d, category, duration, rpe, pain_flag, load_score in recent_logs:
                    sl = compute_session_load(int(duration or 0), int(rpe or 5))
                    daily_loads.append(sl.trimp)
                if len(daily_loads) >= 7:
                    weekly = compute_weekly_metrics(daily_loads)
                    risk = overtraining_risk(weekly.monotony, weekly.strain)
                    lc1, lc2, lc3 = st.columns(3)
                    lc1.metric("Monotony", f"{weekly.monotony:.2f}")
                    lc2.metric("Strain", f"{weekly.strain:.0f}")
                    lc3.metric("Overtraining Risk", risk.upper())

                st.subheader("Recent Training Logs")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "date": d,
                                "session_category": category,
                                "duration_min": duration,
                                "rpe": rpe,
                                "pain_flag": pain_flag,
                                "load_score": load_score,
                            }
                            for d, category, duration, rpe, pain_flag, load_score in recent_logs
                        ]
                    ),
                    use_container_width=True,
                )
            else:
                st.info("No recent training logs.")

            # Plan adjuster recommendations
            if recent_logs:
                st.subheader("Plan Adjustment Recommendations")
                log_dicts = [
                    {"date": d, "duration_min": duration, "rpe": rpe, "pain_flag": pain_flag, "load_score": load_score}
                    for d, category, duration, rpe, pain_flag, load_score in recent_logs
                ]
                with session_scope() as s:
                    plan_weeks = s.execute(
                        select(PlanWeek.week_number, PlanWeek.target_load, PlanWeek.week_start, PlanWeek.week_end)
                        .join(Plan, Plan.id == PlanWeek.plan_id)
                        .where(Plan.athlete_id == athlete_id, Plan.status == "active")
                        .order_by(PlanWeek.week_number)
                    ).all()
                if plan_weeks:
                    plan_week_dicts = [
                        {"week_number": wn, "target_load": tl, "week_start": ws, "week_end": we}
                        for wn, tl, ws, we in plan_weeks
                    ]
                    adherence = assess_adherence_trend(log_dicts, plan_week_dicts)
                    pain_cluster = detect_pain_cluster(log_dicts)
                    recommendations = recommend_adjustments(adherence, pain_cluster)
                    if recommendations:
                        for rec in recommendations:
                            st.warning(f"**{rec['action']}**: {rec['reason']}")
                    else:
                        st.success("No plan adjustments recommended. Athlete is on track.")
                else:
                    st.info("No active plan to analyse.")

            if recent_checkins:
                st.subheader("Recent Check-Ins")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"day": day, "sleep": sleep, "energy": energy, "recovery": recovery, "stress": stress}
                            for day, sleep, energy, recovery, stress in recent_checkins
                        ]
                    ),
                    use_container_width=True,
                )
            else:
                st.info("No recent check-ins.")

            if upcoming_events:
                st.subheader("Upcoming Events")
                st.dataframe(
                    pd.DataFrame([{"event_date": event_date, "name": name, "distance": distance} for event_date, name, distance in upcoming_events]),
                    use_container_width=True,
                )
            else:
                st.info("No upcoming events.")


def coach_plan_builder() -> None:
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

    def _resolve_session_names(by_cat_tier, by_cat, week_number, tokens):
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
                logger.info("Plan published for athlete_id=%d goal=%s weeks=%d", preview["athlete_id"], preview["race_goal"], preview["weeks"])
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
                "race_goal": goal,
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
                    sessions_tokens = default_phase_session_tokens(phase, int(plan_meta["sessions_per_week"]), race_goal=plan_meta.get("race_goal"))
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


def _render_session_detail(detail: dict) -> None:
    """Render a rich Daniels-style session detail view."""
    st.markdown(f"### {detail['name']}")
    st.caption(
        f"**Category:** {detail['category']} | **Intent:** {detail['intent']} | "
        f"**Energy System:** {detail['energy_system']} | **Tier:** {detail['tier']} | "
        f"**Duration:** {detail['duration_min']} min"
    )
    if detail.get("prescription"):
        st.markdown(f"**Prescription:** {detail['prescription']}")
    if detail.get("coaching_notes"):
        st.markdown(f"**Coaching Notes:** {detail['coaching_notes']}")

    structure = detail.get("structure_json")
    if isinstance(structure, dict):
        is_v3 = structure.get("version", 2) >= 3
        blocks = structure.get("blocks", [])

        # Show version badge
        if is_v3:
            st.markdown("**Session Design:** Daniels Running Formula (v3 prescriptive)")
        else:
            st.markdown("**Session Design:** Zone-based (v2)")

        # Render blocks
        if blocks:
            block_rows = []
            for block in blocks:
                tgt = block.get("target", {})
                if is_v3:
                    pace_col = tgt.get("pace_label", "")
                    hr_col = ""
                else:
                    pace_col = tgt.get("pace_zone", "")
                    hr_col = tgt.get("hr_zone", "")
                block_rows.append({
                    "Phase": block.get("phase", ""),
                    "Duration (min)": block.get("duration_min", ""),
                    "Daniels Pace": pace_col if is_v3 else "",
                    "Pace Zone": pace_col if not is_v3 else "",
                    "HR Zone": hr_col,
                    "RPE Range": str(tgt.get("rpe_range", "")),
                })
            # Remove empty columns
            block_df = pd.DataFrame(block_rows)
            block_df = block_df.loc[:, (block_df != "").any()]
            st.markdown("**Workout Blocks**")
            st.dataframe(block_df, use_container_width=True)

            # Render interval detail for v3 sessions
            interval_rows = []
            for block in blocks:
                intervals = block.get("intervals")
                if isinstance(intervals, list):
                    for ivl in intervals:
                        work_pace = ivl.get("work_pace", "")
                        recovery_pace = ivl.get("recovery_pace", "")
                        interval_rows.append({
                            "Reps": ivl.get("reps", ""),
                            "Work Duration": f"{ivl.get('work_duration_min', '')} min",
                            "Work Pace": work_pace,
                            "Recovery Duration": f"{ivl.get('recovery_duration_min', '')} min",
                            "Recovery Pace": recovery_pace,
                            "Description": ivl.get("description", ""),
                        })
            if interval_rows:
                st.markdown("**Interval Prescription**")
                st.dataframe(pd.DataFrame(interval_rows), use_container_width=True)

    # Progression & Regression rules
    prog = detail.get("progression_json")
    reg = detail.get("regression_json")
    if (isinstance(prog, dict) and prog) or (isinstance(reg, dict) and reg):
        with st.expander("Progression & Regression Rules"):
            if isinstance(prog, dict) and prog:
                st.markdown("**Progression Rules**")
                for key, rule in prog.items():
                    if isinstance(rule, dict):
                        st.write(f"- **{key}**: {rule.get('trigger', '')} → {rule.get('action', '')}")
            if isinstance(reg, dict) and reg:
                st.markdown("**Regression Rules**")
                for key, rule in reg.items():
                    if isinstance(rule, dict):
                        st.write(f"- **{key}**: {rule.get('trigger', '')} → {rule.get('action', '')}")

    # Targets
    targets = detail.get("targets_json")
    if isinstance(targets, dict) and targets:
        with st.expander("Session Targets"):
            for key, val in targets.items():
                st.write(f"- **{key}**: {val}")


def coach_session_library() -> None:
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

            # ── Daniels Session Detail View ──────────────────────────
            if not filtered.empty:
                detail_opts = {f"{row['name']} ({row['category']} / {row['tier']})": int(row["id"]) for _, row in filtered.iterrows()}
                detail_label = st.selectbox("Inspect Session", list(detail_opts.keys()), key="browse_detail")
                detail_id = detail_opts[detail_label]
                detail = next(r for r in full_rows if r["id"] == detail_id)
                _render_session_detail(detail)

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


def coach_portfolio_analytics() -> None:
    st.header("Portfolio Analytics")
    from core.services.analytics import compute_fitness_fatigue, compute_intensity_distribution, race_readiness_score

    with session_scope() as s:
        rows = s.execute(
            select(TrainingLog.athlete_id, TrainingLog.date, TrainingLog.duration_min, TrainingLog.load_score, TrainingLog.rpe)
        ).all()
        athletes = {aid: f"{first} {last}" for aid, first, last in s.execute(select(Athlete.id, Athlete.first_name, Athlete.last_name)).all()}
    if not rows:
        st.info("No training logs available yet.")
        return

    df = pd.DataFrame([{"athlete_id": aid, "date": d, "duration_min": mins, "load_score": load, "rpe": rpe} for aid, d, mins, load, rpe in rows])

    # Portfolio summary
    summary = df.groupby("athlete_id", as_index=False).agg(
        total_sessions=("athlete_id", "count"),
        total_minutes=("duration_min", "sum"),
        total_load=("load_score", "sum"),
    )
    summary["athlete"] = summary["athlete_id"].map(athletes)
    st.dataframe(summary[["athlete", "athlete_id", "total_sessions", "total_minutes", "total_load"]].sort_values("total_load", ascending=False), use_container_width=True)

    # Per-athlete fitness/fatigue overview
    st.subheader("Athlete Fitness Overview")
    overview_rows = []
    for aid in df["athlete_id"].unique():
        athlete_df = df[df["athlete_id"] == aid].sort_values("date")
        daily_loads = [{"date": row["date"], "load": float(row["load_score"] or 0)} for _, row in athlete_df.iterrows()]
        ff = compute_fitness_fatigue(daily_loads)
        if ff:
            latest = ff[-1]
            readiness = race_readiness_score(latest.tsb)
            log_dicts = [{"duration_min": row["duration_min"], "rpe": row["rpe"]} for _, row in athlete_df.iterrows()]
            intensity = compute_intensity_distribution(log_dicts)
            overview_rows.append({
                "athlete": athletes.get(aid, f"#{aid}"),
                "CTL": latest.ctl,
                "ATL": latest.atl,
                "TSB": latest.tsb,
                "readiness": readiness.replace("_", " ").title(),
                "easy_%": intensity.get("easy", 0),
                "hard_%": intensity.get("hard", 0),
            })
    if overview_rows:
        st.dataframe(pd.DataFrame(overview_rows), use_container_width=True)


def coach_integrations() -> None:
    st.header("Integrations")

    # ── Wearable Connections Overview ─────────────────────────────────────
    st.subheader("Wearable Connections")
    with session_scope() as s:
        connections = s.execute(
            select(
                WearableConnection.id, WearableConnection.athlete_id,
                WearableConnection.service, WearableConnection.sync_status,
                WearableConnection.last_sync_at, WearableConnection.external_athlete_id,
                Athlete.first_name, Athlete.last_name,
            ).join(Athlete, Athlete.id == WearableConnection.athlete_id)
            .order_by(WearableConnection.service, Athlete.last_name)
        ).all()
    if connections:
        conn_rows = []
        for cid, aid, svc, status, last_sync, ext_id, first, last in connections:
            conn_rows.append({
                "Athlete": f"{first} {last}",
                "Service": svc.title(),
                "Status": status,
                "Last Sync": last_sync.strftime("%Y-%m-%d %H:%M") if last_sync else "Never",
                "External ID": ext_id or "",
            })
        st.dataframe(pd.DataFrame(conn_rows), use_container_width=True)
    else:
        st.info("No wearable connections yet.")

    # ── Add Connection (demo/manual) ─────────────────────────────────────
    st.subheader("Add Wearable Connection")
    with session_scope() as s:
        athletes = s.execute(
            select(Athlete.id, Athlete.first_name, Athlete.last_name)
            .where(Athlete.status == "active")
            .order_by(Athlete.first_name)
        ).all()
    athlete_opts = {f"{first} {last}": aid for aid, first, last in athletes}
    with st.form("add_connection"):
        sel_name = st.selectbox("Athlete", list(athlete_opts.keys()) if athlete_opts else ["No athletes"])
        sel_service = st.selectbox("Service", ["garmin", "strava"])
        sel_token = st.text_input("Access Token (from OAuth callback)", type="password")
        sel_refresh = st.text_input("Refresh Token (optional)", type="password")
        sel_ext_id = st.text_input("External Athlete ID")
        add_submit = st.form_submit_button("Connect")
    if add_submit and sel_name in athlete_opts and sel_token:
        sel_athlete_id = athlete_opts[sel_name]
        with session_scope() as s:
            existing = s.execute(
                select(WearableConnection.id).where(
                    WearableConnection.athlete_id == sel_athlete_id,
                    WearableConnection.service == sel_service,
                )
            ).first()
            if existing:
                st.warning(f"{sel_name} already has a {sel_service} connection.")
            else:
                s.add(WearableConnection(
                    athlete_id=sel_athlete_id,
                    service=sel_service,
                    access_token=sel_token,
                    refresh_token=sel_refresh or None,
                    external_athlete_id=sel_ext_id or None,
                    sync_status="active",
                ))
                st.success(f"Connected {sel_service.title()} for {sel_name}.")
                st.rerun()

    # ── Sync Logs ────────────────────────────────────────────────────────
    st.subheader("Sync History")
    with session_scope() as s:
        sync_logs = s.execute(
            select(
                SyncLog.id, SyncLog.service, SyncLog.sync_type, SyncLog.status,
                SyncLog.activities_found, SyncLog.activities_imported,
                SyncLog.activities_skipped, SyncLog.started_at,
                Athlete.first_name, Athlete.last_name,
            ).join(Athlete, Athlete.id == SyncLog.athlete_id)
            .order_by(SyncLog.id.desc())
            .limit(20)
        ).all()
    if sync_logs:
        log_rows = []
        for sid, svc, stype, status, found, imported, skipped, started, first, last in sync_logs:
            log_rows.append({
                "Athlete": f"{first} {last}",
                "Service": svc.title(),
                "Type": stype,
                "Status": status,
                "Found": found,
                "Imported": imported,
                "Skipped": skipped,
                "Started": started.strftime("%Y-%m-%d %H:%M") if started else "",
            })
        st.dataframe(pd.DataFrame(log_rows), use_container_width=True)
    else:
        st.info("No sync logs yet.")

    # ── Legacy Import Runs ───────────────────────────────────────────────
    st.subheader("CSV Import Runs")
    with session_scope() as s:
        runs = s.execute(select(ImportRun.id, ImportRun.adapter_name, ImportRun.status, ImportRun.created_at).order_by(ImportRun.id.desc())).all()
    if runs:
        st.dataframe(
            pd.DataFrame([{"id": rid, "adapter": adapter, "status": status, "created_at": created_at} for rid, adapter, status, created_at in runs]),
            use_container_width=True,
        )
    else:
        st.info("No CSV import runs yet.")


def coach_community() -> None:
    """Community management: create groups, challenges, view leaderboards."""
    st.header("Community Management")

    # ── Training Groups ──────────────────────────────────────────────────
    st.subheader("Training Groups")
    with session_scope() as s:
        groups = s.execute(
            select(TrainingGroup.id, TrainingGroup.name, TrainingGroup.privacy,
                   TrainingGroup.max_members, TrainingGroup.created_at)
            .order_by(TrainingGroup.name)
        ).all()
    if groups:
        group_rows = []
        for gid, gname, privacy, max_m, created in groups:
            with session_scope() as s:
                member_count = len(s.execute(
                    select(GroupMembership.id).where(GroupMembership.group_id == gid)
                ).all())
            group_rows.append({
                "Group": gname, "Privacy": privacy,
                "Members": f"{member_count}/{max_m}",
                "Created": created.strftime("%Y-%m-%d") if created else "",
            })
        st.dataframe(pd.DataFrame(group_rows), use_container_width=True)
    else:
        st.info("No training groups created yet.")

    # Create group form
    with st.form("create_group"):
        st.write("**Create Training Group**")
        g_name = st.text_input("Group Name")
        g_desc = st.text_area("Description", max_chars=500)
        g_privacy = st.selectbox("Privacy", ["public", "private", "invite_only"])
        g_max = st.number_input("Max Members", min_value=2, max_value=200, value=50)
        g_submit = st.form_submit_button("Create Group")
    if g_submit and g_name.strip():
        coach_user_id = st.session_state.get("user_id", 1)
        with session_scope() as s:
            s.add(TrainingGroup(
                name=g_name.strip(), description=g_desc, owner_user_id=coach_user_id,
                privacy=g_privacy, max_members=g_max,
            ))
        st.success(f"Group '{g_name}' created.")
        st.rerun()

    # ── Add Members ──────────────────────────────────────────────────────
    if groups:
        st.subheader("Manage Memberships")
        group_opts = {gname: gid for gid, gname, *_ in groups}
        with session_scope() as s:
            athletes = s.execute(
                select(Athlete.id, Athlete.first_name, Athlete.last_name)
                .where(Athlete.status == "active")
                .order_by(Athlete.first_name)
            ).all()
        athlete_opts = {f"{first} {last}": aid for aid, first, last in athletes}

        with st.form("add_member"):
            sel_group = st.selectbox("Group", list(group_opts.keys()))
            sel_athlete = st.selectbox("Athlete", list(athlete_opts.keys()) if athlete_opts else ["No athletes"])
            sel_role = st.selectbox("Role", ["member", "admin"])
            mem_submit = st.form_submit_button("Add to Group")
        if mem_submit and sel_group in group_opts and sel_athlete in athlete_opts:
            with session_scope() as s:
                existing = s.execute(
                    select(GroupMembership.id).where(
                        GroupMembership.group_id == group_opts[sel_group],
                        GroupMembership.athlete_id == athlete_opts[sel_athlete],
                    )
                ).first()
                if existing:
                    st.warning(f"{sel_athlete} is already in {sel_group}.")
                else:
                    s.add(GroupMembership(
                        group_id=group_opts[sel_group],
                        athlete_id=athlete_opts[sel_athlete],
                        role=sel_role,
                    ))
                    st.success(f"Added {sel_athlete} to {sel_group}.")
                    st.rerun()

    # ── Challenges ───────────────────────────────────────────────────────
    st.subheader("Challenges")
    with session_scope() as s:
        challenges = s.execute(
            select(Challenge.id, Challenge.name, Challenge.challenge_type,
                   Challenge.target_value, Challenge.start_date, Challenge.end_date, Challenge.status)
            .order_by(Challenge.end_date.desc())
        ).all()
    if challenges:
        ch_rows = []
        for cid, cname, ctype, target, start, end, cstatus in challenges:
            with session_scope() as s:
                entry_count = len(s.execute(
                    select(ChallengeEntry.id).where(ChallengeEntry.challenge_id == cid)
                ).all())
            ch_rows.append({
                "Challenge": cname, "Type": ctype, "Target": target,
                "Period": f"{start} → {end}", "Status": cstatus,
                "Participants": entry_count,
            })
        st.dataframe(pd.DataFrame(ch_rows), use_container_width=True)
    else:
        st.info("No challenges created yet.")

    # Create challenge form
    with st.form("create_challenge"):
        st.write("**Create Challenge**")
        c_name = st.text_input("Challenge Name")
        c_type = st.selectbox("Type", ["distance", "duration", "streak", "elevation"])
        c_target = st.number_input("Target Value", min_value=1.0, value=50.0)
        c_start = st.date_input("Start Date", value=date.today())
        c_end = st.date_input("End Date", value=date.today() + timedelta(days=30))
        c_group = st.selectbox(
            "Group (optional)",
            ["None"] + (list(group_opts.keys()) if groups else []),
        ) if groups else "None"
        c_submit = st.form_submit_button("Create Challenge")
    if c_submit and c_name.strip():
        coach_user_id = st.session_state.get("user_id", 1)
        group_id = group_opts.get(c_group) if c_group != "None" else None
        with session_scope() as s:
            s.add(Challenge(
                name=c_name.strip(), challenge_type=c_type, target_value=c_target,
                start_date=c_start, end_date=c_end, created_by=coach_user_id,
                group_id=group_id,
            ))
        st.success(f"Challenge '{c_name}' created.")
        st.rerun()


def coach_org_management() -> None:
    """Organization and team management page."""
    from core.services.team import TIER_LIMITS

    st.header("Organization & Team")
    coach_user_id = st.session_state.get("user_id", 1)

    # ── My Organizations ─────────────────────────────────────────────────
    st.subheader("Organizations")
    with session_scope() as s:
        my_orgs = s.execute(
            select(Organization.id, Organization.name, Organization.tier,
                   Organization.max_coaches, Organization.max_athletes,
                   OrgMembership.org_role)
            .join(OrgMembership, OrgMembership.org_id == Organization.id)
            .where(OrgMembership.user_id == coach_user_id)
            .order_by(Organization.name)
        ).all()

    if my_orgs:
        for org_id, org_name, tier, max_c, max_a, my_role in my_orgs:
            with st.expander(f"{org_name} ({tier}) — Your role: {my_role}"):
                _show_org_detail(org_id, org_name, tier, max_c, max_a, my_role, coach_user_id)
    else:
        st.info("You are not a member of any organization.")

    # ── Create Organization ──────────────────────────────────────────────
    st.subheader("Create Organization")
    with st.form("create_org"):
        org_name = st.text_input("Organization Name")
        org_tier = st.selectbox("Tier", list(TIER_LIMITS.keys()))
        org_submit = st.form_submit_button("Create")
    if org_submit and org_name.strip():
        slug = org_name.strip().lower().replace(" ", "-")
        with session_scope() as s:
            existing = s.execute(select(Organization.id).where(Organization.slug == slug)).first()
            if existing:
                st.warning("An organization with that name already exists.")
            else:
                org = Organization(
                    name=org_name.strip(), slug=slug, tier=org_tier,
                    max_coaches=TIER_LIMITS[org_tier]["max_coaches"],
                    max_athletes=TIER_LIMITS[org_tier]["max_athletes"],
                )
                s.add(org)
                s.flush()
                s.add(OrgMembership(org_id=org.id, user_id=coach_user_id, org_role="owner"))
                st.success(f"Organization '{org_name}' created. You are the owner.")
                st.rerun()


def _show_org_detail(org_id, org_name, tier, max_c, max_a, my_role, coach_user_id):
    """Show details for a single organization."""
    from core.services.team import (
        check_tier_limit,
        compute_coach_capacity,
        compute_org_summary,
        suggest_rebalance,
    )

    with session_scope() as s:
        # Get all coaches in org
        coaches = s.execute(
            select(OrgMembership.user_id, OrgMembership.org_role, OrgMembership.caseload_cap,
                   User.username)
            .join(User, User.id == OrgMembership.user_id)
            .where(OrgMembership.org_id == org_id)
            .order_by(OrgMembership.org_role.desc())
        ).all()

        # Get athlete assignments
        assignments = s.execute(
            select(CoachAssignment.coach_user_id, CoachAssignment.athlete_id,
                   Athlete.first_name, Athlete.last_name)
            .join(Athlete, Athlete.id == CoachAssignment.athlete_id)
            .where(CoachAssignment.org_id == org_id, CoachAssignment.status == "active")
        ).all()

    # Build capacity info
    assignment_counts: dict[int, int] = {}
    for a_coach_id, *_ in assignments:
        assignment_counts[a_coach_id] = assignment_counts.get(a_coach_id, 0) + 1

    capacities = []
    coach_rows = []
    for uid, role, cap, username in coaches:
        count = assignment_counts.get(uid, 0)
        cc = compute_coach_capacity(uid, username, role, count, cap)
        capacities.append(cc)
        coach_rows.append({
            "Coach": username, "Role": role,
            "Athletes": f"{count}/{cap}",
            "Utilization": f"{cc.utilization_pct:.0f}%",
        })

    if coach_rows:
        st.write("**Team**")
        st.dataframe(pd.DataFrame(coach_rows), use_container_width=True)

    # Org summary
    total_athletes = len({a_id for _, a_id, *_ in assignments})
    summary = compute_org_summary(org_id, org_name, tier, max_c, max_a, capacities, total_athletes)
    st.caption(
        f"Coaches: {summary.total_coaches}/{max_c} | "
        f"Athletes: {summary.total_athletes}/{max_a} | "
        f"Avg utilization: {summary.avg_utilization_pct:.0f}%"
    )

    # Rebalance suggestions
    suggestions = suggest_rebalance(capacities)
    if suggestions:
        st.write("**Rebalance Suggestions**")
        for sug in suggestions:
            st.caption(f"Transfer: {sug['reason']}")

    # ── Add Coach ────────────────────────────────────────────────────────
    if my_role in ("owner", "head_coach"):
        with st.form(f"add_coach_{org_id}"):
            st.write("**Add Coach to Organization**")
            with session_scope() as s:
                available_coaches = s.execute(
                    select(User.id, User.username).where(User.role == "coach").order_by(User.username)
                ).all()
            coach_opts = {uname: uid for uid, uname in available_coaches}
            sel_coach = st.selectbox("Coach", list(coach_opts.keys()) if coach_opts else ["No coaches available"])
            sel_role = st.selectbox("Role", ["assistant", "coach", "head_coach"])
            sel_cap = st.number_input("Caseload Cap", min_value=1, max_value=100, value=20)
            ac_submit = st.form_submit_button("Add Coach")
        if ac_submit and sel_coach in coach_opts:
            if not check_tier_limit(tier, len(coaches), "max_coaches"):
                st.warning(f"Coach limit reached for {tier} tier ({max_c} max).")
            else:
                with session_scope() as s:
                    existing = s.execute(
                        select(OrgMembership.id).where(
                            OrgMembership.org_id == org_id,
                            OrgMembership.user_id == coach_opts[sel_coach],
                        )
                    ).first()
                    if existing:
                        st.warning(f"{sel_coach} is already in this organization.")
                    else:
                        s.add(OrgMembership(
                            org_id=org_id, user_id=coach_opts[sel_coach],
                            org_role=sel_role, caseload_cap=sel_cap,
                        ))
                        st.success(f"Added {sel_coach} as {sel_role}.")
                        st.rerun()

    # ── Assign Athlete ───────────────────────────────────────────────────
    if my_role in ("owner", "head_coach"):
        with st.form(f"assign_athlete_{org_id}"):
            st.write("**Assign Athlete to Coach**")
            coach_map = {uname: uid for uid, _, _, uname in coaches}
            with session_scope() as s:
                all_athletes = s.execute(
                    select(Athlete.id, Athlete.first_name, Athlete.last_name)
                    .where(Athlete.status == "active")
                    .order_by(Athlete.first_name)
                ).all()
            ath_opts = {f"{first} {last}": aid for aid, first, last in all_athletes}
            sel_ath = st.selectbox("Athlete", list(ath_opts.keys()) if ath_opts else ["No athletes"])
            sel_to_coach = st.selectbox("Assign to Coach", list(coach_map.keys()))
            assign_submit = st.form_submit_button("Assign")
        if assign_submit and sel_ath in ath_opts and sel_to_coach in coach_map:
            with session_scope() as s:
                existing = s.execute(
                    select(CoachAssignment.id).where(
                        CoachAssignment.org_id == org_id,
                        CoachAssignment.athlete_id == ath_opts[sel_ath],
                    )
                ).first()
                if existing:
                    st.warning(f"{sel_ath} is already assigned in this organization.")
                else:
                    s.add(CoachAssignment(
                        org_id=org_id, coach_user_id=coach_map[sel_to_coach],
                        athlete_id=ath_opts[sel_ath],
                    ))
                    st.success(f"Assigned {sel_ath} to {sel_to_coach}.")
                    st.rerun()


def coach_vdot_calculator() -> None:
    """VDOT pace calculator using Jack Daniels' Running Formula."""
    from core.services.vdot import (
        RACE_DISTANCES_M,
        estimate_vdot,
        get_paces,
        pace_display,
        pace_range_display,
        daniels_pace_band,
    )

    st.header("VDOT Pace Calculator")
    st.caption("Based on Jack Daniels' Running Formula — calculates five training paces from VDOT or a race result.")

    calc_tab, table_tab = st.tabs(["Calculator", "Pace Table"])

    with calc_tab:
        method = st.radio("Input Method", ["Enter VDOT directly", "Estimate from race result"], horizontal=True)

        vdot_val = None
        if method == "Enter VDOT directly":
            vdot_val = st.number_input("VDOT Score", min_value=30.0, max_value=85.0, value=45.0, step=0.5)
        else:
            race_dist = st.selectbox("Race Distance", list(RACE_DISTANCES_M.keys()))
            col_h, col_m, col_s = st.columns(3)
            with col_h:
                hours = st.number_input("Hours", min_value=0, max_value=6, value=0)
            with col_m:
                minutes = st.number_input("Minutes", min_value=0, max_value=59, value=22)
            with col_s:
                seconds = st.number_input("Seconds", min_value=0, max_value=59, value=0)
            total_seconds = hours * 3600 + minutes * 60 + seconds
            if total_seconds > 0:
                distance_m = RACE_DISTANCES_M[race_dist]
                vdot_val = estimate_vdot(distance_m, total_seconds)
                st.success(f"Estimated VDOT: **{vdot_val:.1f}**")

        if vdot_val:
            paces = get_paces(vdot_val)
            st.subheader(f"Training Paces for VDOT {vdot_val:.1f}")

            pace_data = [
                {"Pace Type": "E (Easy)", "Label": "E", "Pace": pace_display(paces.E),
                 "Band": pace_range_display(*daniels_pace_band("E", vdot_val)),
                 "Purpose": "Aerobic development, recovery. Most daily running."},
                {"Pace Type": "M (Marathon)", "Label": "M", "Pace": pace_display(paces.M),
                 "Band": pace_range_display(*daniels_pace_band("M", vdot_val)),
                 "Purpose": "Marathon-specific endurance. Long run segments."},
                {"Pace Type": "T (Threshold)", "Label": "T", "Pace": pace_display(paces.T),
                 "Band": pace_range_display(*daniels_pace_band("T", vdot_val)),
                 "Purpose": "Lactate clearance. Tempo runs, cruise intervals."},
                {"Pace Type": "I (Interval)", "Label": "I", "Pace": pace_display(paces.I),
                 "Band": pace_range_display(*daniels_pace_band("I", vdot_val)),
                 "Purpose": "VO2max stimulus. 3-5 min work intervals."},
                {"Pace Type": "R (Repetition)", "Label": "R", "Pace": pace_display(paces.R),
                 "Band": pace_range_display(*daniels_pace_band("R", vdot_val)),
                 "Purpose": "Speed & running economy. Short, fast reps."},
            ]
            st.dataframe(pd.DataFrame(pace_data)[["Pace Type", "Pace", "Band", "Purpose"]], use_container_width=True, hide_index=True)

            # Quick reference per-km and per-mile
            st.subheader("Pace Reference")
            ref_cols = st.columns(5)
            labels = ["E", "M", "T", "I", "R"]
            sec_values = [paces.E, paces.M, paces.T, paces.I, paces.R]
            for col, label, sec_km in zip(ref_cols, labels, sec_values):
                mile_sec = sec_km * 1.60934
                col.metric(label, pace_display(sec_km), delta=f"{pace_display(mile_sec)} /mi")

    with table_tab:
        st.subheader("VDOT Pace Lookup Table")
        st.caption("All five Daniels paces for VDOT 30 to 85.")
        table_rows = []
        for v in range(30, 86):
            p = get_paces(float(v))
            table_rows.append({
                "VDOT": v,
                "Easy": pace_display(p.E),
                "Marathon": pace_display(p.M),
                "Threshold": pace_display(p.T),
                "Interval": pace_display(p.I),
                "Repetition": pace_display(p.R),
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True, height=600)


def coach_admin_tools() -> None:
    from core.bootstrap import ensure_demo_seeded

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


def add_client() -> None:
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
        logger.info("Client created: username=%s", username)
        st.success(f"Created user: {username} / TempPass!234")
