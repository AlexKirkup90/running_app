from __future__ import annotations

import streamlit as st

from core.bootstrap import ensure_demo_seeded
from core.logging_config import setup_logging
from core.observability import system_status
from pages.auth import auth_panel, force_password_change, log_runtime_error
from pages.coach import (
    add_client,
    coach_admin_tools,
    coach_clients,
    coach_command_center,
    coach_community,
    coach_dashboard,
    coach_integrations,
    coach_org_management,
    coach_plan_builder,
    coach_portfolio_analytics,
    coach_session_library,
    coach_vdot_calculator,
)
from pages.athlete import (
    athlete_analytics,
    athlete_checkin,
    athlete_community,
    athlete_dashboard,
    athlete_events,
    athlete_log,
    athlete_profile,
)

setup_logging()

st.set_page_config(page_title="Run Season Command", layout="wide")


def main():
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
            page = st.sidebar.radio("Coach", ["Dashboard", "Command Center", "Clients", "Add Client", "Plan Builder", "Session Library", "VDOT Calculator", "Portfolio Analytics", "Integrations", "Community", "Organization", "Admin Tools"])
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
            elif page == "VDOT Calculator":
                coach_vdot_calculator()
            elif page == "Portfolio Analytics":
                coach_portfolio_analytics()
            elif page == "Integrations":
                coach_integrations()
            elif page == "Community":
                coach_community()
            elif page == "Organization":
                coach_org_management()
            elif page == "Admin Tools":
                coach_admin_tools()
        else:
            page = st.sidebar.radio("Athlete", ["Dashboard", "Log Session", "Check-In", "Events", "Analytics", "Community", "Profile"])
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
            elif page == "Community":
                athlete_community(athlete_id)
            elif page == "Profile":
                athlete_profile(athlete_id)
    except Exception as e:
        log_runtime_error("main", e)
        st.error("Something went wrong. The issue has been logged.")


if __name__ == "__main__":
    main()
