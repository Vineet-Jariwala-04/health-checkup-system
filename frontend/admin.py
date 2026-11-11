"""Admin-only page: approvals + all-data views (patients, checkups)."""
import csv
import io

import altair as alt
import pandas as pd
import streamlit as st

import api_client as api
from . import history, icons, shell
from .data import CHECKUPS, FLAG, TITLES, checkups_from_row, clean, esc

TABS = {"approvals": "Approvals", "patients": "All users", "checkups": "All checkups", "analytics": "Analytics", "locked": "Locked accounts"}


def _tag(flag):
    if flag is None:
        return '<span class="tag none">—</span>'
    kind, name = FLAG.get(int(flag), FLAG[0])
    return f'<span class="tag {kind}">{name}</span>'


def _table(headers, rows, note=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    st.markdown(f'<div class="tblwrap" tabindex="0"><table class="tbl"><thead><tr>{th}</tr></thead>'
                f'<tbody>{body}</tbody></table></div>' + (f'<div class="fine">{note}</div>' if note else ""),
                unsafe_allow_html=True)


# ------------------------------------------------------------- approvals

def _approvals(user, users, pending):
    first = shell.first_admin(users)
    is_first = bool(first) and first["user_id"] == user["user_id"]
    shell.section(icons.SHIELD, f"Pending admin requests ({len(pending)})")
    if not is_first and first:
        st.markdown(f'<div class="banner info">{icons.INFO}<div>Only the first admin (<b>{esc(first["name"])}</b>) '
                    'can approve new admin accounts. You can see the requests here.</div></div>', unsafe_allow_html=True)
    if not pending:
        st.markdown('<div class="empty"><div class="eic">' + icons.SHIELD + '</div><b>No pending requests</b>'
                    '<span>New admin sign-ups will appear here for approval.</span></div>', unsafe_allow_html=True)
    for p in pending:
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.markdown(f'<div class="card req"><div class="avatar" aria-hidden="true">{esc(p["name"][:1].upper())}</div>'
                    f'<div><b>{esc(p["name"])}</b><span>{esc(p["email"])} · requested {esc(str(p["signup_at"])[:16])}</span></div></div>',
                    unsafe_allow_html=True)
        if is_first:
            if c2.button("Approve", type="primary", icon=":material/check:", key=f"ap_{p['user_id']}",
                         use_container_width=True):
                res, status = api.approve_admin(p["user_id"], user["user_id"])
                if status == 200:
                    st.session_state.flash = f"Approved {p['email']}. They can now sign in as admin."
                else:
                    st.session_state.flash_err = res.get("error", "Could not approve this request.")
                st.rerun()
        else:
            c2.markdown('<span class="tag none">Awaiting first admin</span>', unsafe_allow_html=True)

    shell.section(icons.USER, "Admin team")
    admins = [u for u in users if u["role"] == "admin" and u["is_approved"]]
    rows = [[esc(a["name"]), esc(a["email"]),
             '<span class="tag ok">First admin</span>' if first and a["user_id"] == first["user_id"] else "Admin",
             esc(str(a["signup_at"])[:10]), esc(a["login_count"])] for a in admins]
    _table(["Name", "Email", "Role", "Joined", "Logins"], rows)


# ---------------------------------------------------------------- users

def _users_tab(users):
    shell.section(icons.USER, f"All users ({len(users)})", "Passwords are never shown")
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    q = c1.text_input("Search", placeholder="Search by name or email", icon=":material/search:", key="ad_q",
                      label_visibility="collapsed").strip().lower()
    role = c2.radio("Role", ["All", "Patient", "Admin"], horizontal=True, key="ad_role", label_visibility="collapsed")
    rows_u = [u for u in users if (role == "All" or u["role"] == role.lower())
              and (not q or q in u["name"].lower() or q in u["email"].lower())]
    rows = []
    for u in rows_u:
        r = (u["role"].capitalize() + ("" if u["is_approved"] or u["role"] != "admin" else " (pending)")
             + (" (locked)" if u.get("is_locked") else ""))
        rows.append([esc(u["user_id"]), f"<b>{esc(u['name'])}</b>", r, esc(u["age"]), esc(u["email"]),
                     esc(u["login_count"]), esc(u["last_login_at"] or u["signup_at"]), esc(u["last_logout_at"] or "—"),
                     esc(u["last_ip_address"] or "—"), _tag(u["heart_flag"]), _tag(u["diabetes_flag"]),
                     _tag(u["sugar_flag"]), _tag(u["bp_flag"]), esc(u["report_generated_at"] or "—")])
    if not rows:
        st.markdown('<div class="empty"><b>No users match</b><span>Try a different search or filter.</span></div>',
                    unsafe_allow_html=True)
        return
    _table(["ID", "Name", "Role", "Age", "Email", "Logins", "Last login", "Last logout", "Last IP",
            "Heart", "Diabetes", "Sugar", "BP", "PDF report"], rows, f"Showing {len(rows)} of {len(users)} users.")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "name", "role", "age", "email", "logins", "last_login", "last_logout", "last_ip",
                "heart", "diabetes", "sugar", "blood_pressure", "pdf_report"])
    for u in rows_u:
        def f(k):
            return clean(u.get(f"{k}_detail")) if u.get(f"{k}_flag") is not None else ""
        w.writerow([u["user_id"], u["name"], u["role"], u["age"], u["email"], u["login_count"],
                    u["last_login_at"] or u["signup_at"], u["last_logout_at"] or "", u["last_ip_address"] or "",
                    f("heart"), f("diabetes"), f("sugar"), f("bp"), u["report_generated_at"] or ""])
    st.download_button("Download CSV", buf.getvalue(), "users.csv", "text/csv", icon=":material/download:", key="ad_csv")


# ------------------------------------------------------------- analytics

def _analytics_tab(user, users):
    shell.section(icons.ACTIVITY, "Overview of all users", "Latest result of each checkup")
    rows = []
    for u in users:
        for key, title, _ in CHECKUPS:
            flag = u.get(f"{key}_flag")
            if u.get(f"{key}_updated_at") and flag is not None:
                rows.append({"Checkup": title, "Level": FLAG.get(int(flag), FLAG[0])[1], "User": u["user_id"]})
    try:
        all_runs = history.to_frame(api.get_all_history(user["user_id"]))
    except Exception:
        all_runs = pd.DataFrame()

    people = {r["User"] for r in rows}
    high = {r["User"] for r in rows if r["Level"] == "High risk"}
    c1, c2, c3 = st.columns(3)
    c1.metric("Users with a checkup", len(people))
    c2.metric("Users with a high-risk result", len(high))
    c3.metric("Checkups run (all time)", 0 if all_runs.empty else len(all_runs))
    if not rows:
        st.markdown('<div class="empty"><div class="eic">' + icons.CLIPBOARD + '</div><b>No checkup data yet</b>'
                    '<span>Charts appear after users run checkups.</span></div>', unsafe_allow_html=True)
    else:
        counts = pd.DataFrame(rows).groupby(["Checkup", "Level"]).size().reset_index(name="Users")
        st.altair_chart(alt.Chart(counts).mark_bar().encode(
            x=alt.X("Checkup:N", title=None, sort=[t for _, t, _ in CHECKUPS]),
            y=alt.Y("Users:Q", title="Users", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("Level:N", scale=history.LEVEL_COLORS, title=None),
            tooltip=["Checkup", "Level", "Users"]).properties(height=280), use_container_width=True)
    if not all_runs.empty:
        shell.section(icons.CLIPBOARD, "Checkups run per day")
        per_day = all_runs.assign(Day=all_runs["when"].dt.date).groupby("Day").size().reset_index(name="Checkups")
        per_day["Day"] = pd.to_datetime(per_day["Day"])
        st.altair_chart(alt.Chart(per_day).mark_bar().encode(
            x=alt.X("Day:T", title=None), y=alt.Y("Checkups:Q", axis=alt.Axis(tickMinStep=1)),
            tooltip=["Day:T", "Checkups"]).properties(height=240), use_container_width=True)

    shell.section(icons.USER, "Open one person's charts")
    options = {f'{u["name"]} ({u["email"]})': u for u in users}
    if options:
        pick = st.selectbox("Person", list(options), key="adm_person", label_visibility="collapsed")
        chosen = options[pick]
        try:
            history.charts(api.get_history(chosen["user_id"]), f'adm_{chosen["user_id"]}')
        except Exception:
            shell.error_banner("Could not load that person's history.")


# --------------------------------------------------------------- locked

def _locked_tab(user, users):
    locked = [u for u in users if u.get("is_locked")]
    shell.section(icons.SHIELD, f"Locked accounts ({len(locked)})",
                  "Locked after 3 wrong password attempts. Only an admin can unlock them.")
    if not locked:
        st.markdown('<div class="empty"><div class="eic">' + icons.SHIELD + '</div><b>No locked accounts</b>'
                    '<span>Accounts appear here after 3 wrong password attempts.</span></div>', unsafe_allow_html=True)
        return
    for p in locked:
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.markdown(f'<div class="card req"><div class="avatar" aria-hidden="true">{esc(p["name"][:1].upper())}</div>'
                    f'<div><b>{esc(p["name"])}</b><span>{esc(p["email"])} · {esc(p["role"].capitalize())} · '
                    f'locked {esc(str(p.get("locked_at") or "")[:16])} UTC</span></div></div>', unsafe_allow_html=True)
        if c2.button("Unlock", type="primary", icon=":material/lock_open:", key=f"ul_{p['user_id']}",
                     use_container_width=True):
            res, status = api.unlock_user(p["user_id"], user["user_id"])
            if status == 200:
                st.session_state.flash = f"Unlocked {p['email']}. They can sign in again (an email was sent)."
            else:
                st.session_state.flash_err = res.get("error", "Could not unlock this account.")
            st.rerun()


# ------------------------------------------------------------- checkups

def _checkups_tab(users):
    entries = [(u, k, c) for u in users for k, c in checkups_from_row(u).items()]
    entries.sort(key=lambda t: str(t[2]["updated_at"]), reverse=True)
    shell.section(icons.CLIPBOARD, f"All checkups ({len(entries)})", "Latest result per user and type")
    c1, c2 = st.columns(2)
    ftype = c1.selectbox("Checkup", ["All"] + [k for k, _, _ in CHECKUPS], key="ad_ft",
                         format_func=lambda k: "All checkups" if k == "All" else TITLES[k])
    frisk = c2.selectbox("Result", ["All", 0, 1, 2], key="ad_fr",
                         format_func=lambda v: "All results" if v == "All" else FLAG[v][1])
    sel = [e for e in entries if (ftype == "All" or e[1] == ftype) and (frisk == "All" or e[2]["flag"] == frisk)]
    if not sel:
        st.markdown('<div class="empty"><b>No checkups match</b><span>Change the filters above.</span></div>',
                    unsafe_allow_html=True)
        return
    rows = [[f"<b>{esc(u['name'])}</b>", esc(u["email"]), TITLES[k], esc(clean(c.get("detail"))),
             _tag(c["flag"]), esc(c["updated_at"])] for u, k, c in sel]
    _table(["User", "Email", "Checkup", "Result", "Status", "When"], rows, f"Showing {len(rows)} results.")


# ----------------------------------------------------------------- page

def render(user):
    if user.get("role") != "admin" or not user.get("is_approved"):
        shell.error_banner("You are not authorised to view this page.")
        return
    shell.page_header(icons.SHIELD, "Admin",
                      "Review new admin requests, unlock locked accounts, and browse every user and checkup.",
                      ["Admin only"])
    if msg := st.session_state.pop("flash", None):
        st.markdown(f'<div class="banner ok">{icons.CHECK}<div>{esc(msg)}</div></div>', unsafe_allow_html=True)
    if msg := st.session_state.pop("flash_err", None):
        shell.error_banner(esc(msg))
    try:
        users = api.get_all_users()
        pending = api.get_pending_admins()
    except Exception:
        shell.error_banner("Could not load data. Is the backend running?")
        return

    st.session_state.setdefault("admin_tab", "approvals")
    locked_n = sum(1 for u in users if u.get("is_locked"))
    tabs = dict(TABS)
    if locked_n:
        tabs["locked"] = f"Locked accounts ({locked_n})"
    shell.subnav("admin_tab", tabs, f"Approvals ({len(pending)})" if pending else None)
    tab = st.session_state.get("_admin_tab", "approvals")
    {"approvals": lambda: _approvals(user, users, pending), "patients": lambda: _users_tab(users),
     "checkups": lambda: _checkups_tab(users), "analytics": lambda: _analytics_tab(user, users),
     "locked": lambda: _locked_tab(user, users)}[tab]()
