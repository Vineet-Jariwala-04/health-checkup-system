"""
AHV Hospital - Streamlit frontend (rebuilt).
Step 1: login + sign-up   Step 2: checkup pages   Step 3: dashboard, PDF report, admin

Run the backend first (python app.py), then:  streamlit run streamlit_app.py
"""
import streamlit as st

import api_client as api
from frontend import admin, auth, checkups, dashboard, history, report, shell, styles

st.set_page_config(page_title="AHV Hospital · Health Checkup", page_icon=":material/monitor_heart:", layout="wide")

styles.init()
styles.inject()

uid = st.session_state.get("user_id")
user = api.get_user(uid) if uid else None

if user:
    shell.topbar(user)
    pending = 0
    if user.get("role") == "admin" and user.get("is_approved"):
        try:
            pending = len(api.get_pending_admins())
        except Exception:
            pass
    page = shell.nav(user, pending)
    if page == "dashboard":
        dashboard.render(user)
    elif page == "history":
        history.render(user)
    elif page == "report":
        report.render(user)
    elif page == "admin":
        admin.render(user)
    else:
        checkups.RENDER[page]()
else:
    if uid:                       # stale id (e.g. database was reset)
        st.session_state.user_id = None
    auth.render()
