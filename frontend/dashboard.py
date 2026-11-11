"""Dashboard (patients and admins) + shared checkup tiles."""
import streamlit as st

import api_client as api
from . import icons, shell
from .data import CHECKUPS, FLAG, LEVELS, TITLES, build_summary, checkups_from_row, clean, esc


def _go(page):
    st.session_state.page = page


def tiles(checkups):
    """2x2 grid of the four checkup results (HTML)."""
    out = []
    for key, title, icon in CHECKUPS:
        c = checkups.get(key)
        if c:
            kind, name = FLAG.get(c["flag"], FLAG[0])
            out.append(f'<div class="tile {kind}"><div class="tic">{icon}</div><div class="tbody">'
                       f'<div class="tt">{title}</div><div class="tr">{esc(clean(c.get("detail")))}</div>'
                       f'<div class="td">{esc(c.get("updated_at"))}</div></div><span class="tag {kind}">{name}</span></div>')
        else:
            out.append(f'<div class="tile none"><div class="tic">{icon}</div><div class="tbody">'
                       f'<div class="tt">{title}</div><div class="tr">Not checked yet</div></div>'
                       f'<span class="tag none">Pending</span></div>')
    st.markdown(f'<div class="tiles">{"".join(out)}</div>', unsafe_allow_html=True)


def summary_card(checkups):
    done = len(checkups)
    level, message = build_summary(checkups)
    if level is None:
        st.markdown(f'<div class="banner info">{icons.INFO}<div>No checkups yet. Run any of the four checks to '
                    'see your combined summary here.</div></div>', unsafe_allow_html=True)
        return
    kind, title = LEVELS[level]
    pct = done / 4 * 100
    st.markdown(
        f'<div class="res {kind} summary"><div class="top"><div class="badge">{icons.CHECK_CIRCLE if kind == "ok" else icons.TRIANGLE}</div>'
        f'<div><span class="pill">{done} of 4 checkups done</span><h3>{title}</h3></div></div>'
        f'<p class="advice">{esc(message)}</p>'
        f'<div class="bar" role="img" aria-label="{done} of 4 checkups completed"><i style="--w:{pct}%"></i></div></div>',
        unsafe_allow_html=True)


def _cta_row(checkups):
    missing = [(k, t) for k, t, _ in CHECKUPS if k not in checkups]
    if not missing:
        return
    st.caption("Complete your profile — run the remaining checkups:")
    cols = st.columns(len(missing))
    for col, (k, t) in zip(cols, missing):
        col.button(f"{t}", icon=":material/arrow_forward:", key=f"cta_{k}", on_click=_go, args=(k,),
                   use_container_width=True)


def _profile(user):
    name = user.get("name", "User")
    ini = "".join(w[0] for w in name.split()[:2]).upper() or "U"
    role = user.get("role", "patient")
    chips = [f"Age {esc(user.get('age'))}", f"Member since {esc(str(user.get('signup_at', ''))[:10])}",
             f"{esc(user.get('login_count', 0))} logins"]
    chip_html = "".join(f"<span>{c}</span>" for c in chips)
    st.markdown(
        f'<div class="pagehead"><div class="bigavatar" aria-hidden="true">{ini}</div><div class="ph-tx">'
        f'<h1>Welcome back, {esc(name)}</h1><p>{esc(user.get("email"))} · {role.capitalize()} account</p></div>'
        f'<div class="chips">{chip_html}</div></div>', unsafe_allow_html=True)


def _kpis(items):
    html = "".join(f'<div class="kpi"><div class="kv">{v}</div><div class="kl">{l}</div></div>' for v, l in items)
    st.markdown(f'<div class="kpis">{html}</div>', unsafe_allow_html=True)


def _admin_overview(user):
    try:
        users = api.get_all_users()
        pending = api.get_pending_admins()
    except Exception:
        shell.error_banner("Could not load system data. Is the backend running?")
        return
    patients = [u for u in users if u["role"] == "patient"]
    admins = [u for u in users if u["role"] == "admin" and u["is_approved"]]
    all_c = [(u, k, c) for u in users for k, c in checkups_from_row(u).items()]
    high = sum(1 for _, _, c in all_c if c["flag"] == 2)

    shell.section(icons.STETH, "System overview", "Admin only")
    _kpis([(len(patients), "Patients"), (len(admins), "Admins"), (len(all_c), "Checkups completed"),
           (high, "High-risk results")])
    if pending:
        who = "You" if shell.is_first_admin(user, users) else "The first admin"
        st.markdown(f'<div class="banner warn">{icons.ALERT}<div><b>{len(pending)} admin request'
                    f'{"s" if len(pending) != 1 else ""} waiting for approval.</b> {who} can review '
                    'them on the Admin page.</div></div>', unsafe_allow_html=True)
        st.button("Review requests", icon=":material/arrow_forward:", key="go_admin", on_click=_go, args=("admin",))

    recent = sorted(all_c, key=lambda t: str(t[2]["updated_at"]), reverse=True)[:6]
    shell.section(icons.CLIPBOARD, "Recent activity", "Latest checkups across all users")
    if not recent:
        st.markdown('<div class="empty"><b>No checkups yet</b><span>Results will show here once users run checkups.</span></div>',
                    unsafe_allow_html=True)
    else:
        rows = "".join(
            f'<div class="act"><div><b>{esc(u["name"])}</b><span>{TITLES[k]} · {esc(clean(c.get("detail")))}</span></div>'
            f'<div class="acr"><span class="tag {FLAG[c["flag"]][0]}">{FLAG[c["flag"]][1]}</span>'
            f'<small>{esc(c["updated_at"])}</small></div></div>' for u, k, c in recent)
        st.markdown(f'<div class="card actlist">{rows}</div>', unsafe_allow_html=True)


def render(user):
    _profile(user)
    if user.get("role") == "admin":
        _admin_overview(user)
    shell.section(icons.HEART, "Your health" if user.get("role") == "admin" else "Your latest results")
    checkups = api.get_checkups(user["user_id"])
    summary_card(checkups)
    tiles(checkups)
    _cta_row(checkups)

    shell.section(icons.FILE_ICON, "Your PDF report")
    report = api.get_report(user["user_id"])
    if report:
        c1, c2 = st.columns([2, 1], vertical_alignment="center")
        c1.markdown(f'<div class="banner ok">{icons.CHECK}<div>Last report generated on <b>{esc(report["created_at"])}</b>. '
                    'Run new checkups and visit Report to refresh it.</div></div>', unsafe_allow_html=True)
        c2.download_button("Download PDF", data=report["pdf_data"], file_name="health_checkup_report.pdf",
                           mime="application/pdf", icon=":material/download:", use_container_width=True,
                           type="primary", key="dash_dl")
    else:
        c1, c2 = st.columns([2, 1], vertical_alignment="center")
        c1.markdown(f'<div class="banner info">{icons.INFO}<div>You haven\'t generated a PDF report yet.</div></div>',
                    unsafe_allow_html=True)
        c2.button("Create report", icon=":material/description:", on_click=_go, args=("report",),
                  use_container_width=True, key="dash_mk")
    st.markdown('<div class="fine">This tool gives statistical risk estimates only. It is not a medical diagnosis — '
                'please consult a doctor for a proper checkup.</div>', unsafe_allow_html=True)
