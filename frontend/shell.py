"""Signed-in app shell: top bar, page navigation, page banner, result card."""
import base64
from html import escape as _h_escape
from pathlib import Path

import streamlit as st

import api_client as api
from . import icons, styles

ASSETS = Path(__file__).resolve().parent.parent / "assets"

PAGES = {
    "dashboard": ":material/dashboard: Dashboard",
    "heart": ":material/favorite: Heart",
    "diabetes": ":material/bloodtype: Diabetes",
    "sugar": ":material/water_drop: Sugar",
    "bp": ":material/monitor_heart: Blood pressure",
    "history": ":material/show_chart: History",
    "report": ":material/description: Report",
    "admin": ":material/admin_panel_settings: Admin",
}


def first_admin(users):
    """The first admin = approved admin with the lowest user id."""
    admins = [u for u in users if u["role"] == "admin" and u["is_approved"]]
    return min(admins, key=lambda u: u["user_id"]) if admins else None


def is_first_admin(user, users):
    f = first_admin(users)
    return bool(f) and f["user_id"] == user["user_id"]


def _logo(dark):
    p = ASSETS / ("logo-dark.png" if dark else "logo-light.png")
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def _logout():
    uid = st.session_state.get("user_id")
    if uid:
        # Build a fresh PDF from the latest checkups so the logout email carries
        # the report and matching results. Never let this block logging out.
        pdf = None
        try:
            from .data import build_summary
            from .pdf_report import build_report_pdf
            checkups = api.get_checkups(uid)
            user = api.get_user(uid)
            if checkups and user:
                level, message = build_summary(checkups)
                try:
                    insights = api.get_insights(uid)
                except Exception:
                    insights = None
                pdf = build_report_pdf(user, checkups, level, message, insights)
        except Exception:
            pdf = None
        try:
            api.logout(uid, pdf)
        except Exception:
            pass
    for k in ("user_id", "results", "page", "_page", "fresh_pdf", "admin_tab", "_admin_tab"):
        st.session_state.pop(k, None)


def topbar(user):
    import html as _h
    name = _h.escape(user.get("name", "User"))
    initials = "".join(w[0] for w in user.get("name", "User").split()[:2]).upper() or "U"
    initials = _h.escape(initials)
    logo = _logo(styles.is_dark())
    img = f'<img src="data:image/png;base64,{logo}" alt="AHV Hospital">' if logo else ""
    with st.container(key="topbar"):
        c = st.columns([5, 3, 0.7, 0.7, 1.5], vertical_alignment="center")
        c[0].markdown(f'<div class="brandbar">{img}<div><b>AHV Hospital</b><span>Full body check-up</span></div></div>',
                      unsafe_allow_html=True)
        c[1].markdown(f'<div class="userchip"><div><b>{name}</b><span>{user.get("role", "patient")}</span></div>'
                      f'<div class="avatar" aria-hidden="true">{initials}</div></div>', unsafe_allow_html=True)
        with c[2]:
            styles.theme_button()
        with c[3]:
            styles.text_size_popover()
        with c[4]:
            st.button("Log out", icon=":material/logout:", on_click=_logout, use_container_width=True, key="logout", help="Log out")


def _keep_page():
    if st.session_state.get("page") is None:
        st.session_state.page = st.session_state.get("_page", "dashboard")


def nav(user, pending=0):
    """Segmented page switcher. The Admin tab only exists for approved admins."""
    is_admin = user.get("role") == "admin" and user.get("is_approved")
    keys = [k for k in PAGES if k != "admin" or is_admin]
    labels = dict(PAGES)
    if pending and is_admin:
        labels["admin"] = f"{PAGES['admin']} ({pending})"
    if st.session_state.get("page") not in keys:
        st.session_state.page = "dashboard"
    st.session_state.setdefault("page", "dashboard")
    picked = st.segmented_control("Page", keys, key="page", format_func=labels.get,
                                  label_visibility="collapsed", selection_mode="single",
                                  width="stretch", on_change=_keep_page)
    page = picked or st.session_state.get("_page", "dashboard")
    st.session_state._page = page
    return page


def subnav(key, options, first_label=None):
    """Smaller switcher inside a page (stores the pick in st.session_state._<key>)."""
    labels = dict(options)
    if first_label:
        labels[next(iter(labels))] = first_label

    def keep():
        if st.session_state.get(key) is None:
            st.session_state[key] = st.session_state.get("_" + key, next(iter(options)))
    picked = st.segmented_control(key, list(options), key=key, format_func=labels.get,
                                  label_visibility="collapsed", selection_mode="single", width="stretch",
                                  on_change=keep)
    st.session_state["_" + key] = picked or st.session_state.get("_" + key, next(iter(options)))


def page_header(icon, title, text, chips):
    chip_html = "".join(f"<span>{c}</span>" for c in chips)
    st.markdown(f'<div class="pagehead"><div class="ph-ic">{icon}</div>'
                f'<div class="ph-tx"><h1>{title}</h1><p>{text}</p></div><div class="chips">{chip_html}</div></div>',
                unsafe_allow_html=True)


def section(icon, title, note=""):
    n = f"<small>{note}</small>" if note else ""
    st.markdown(f'<div class="sec"><span class="si">{icon}</span>{title}{n}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- results

_KINDS = {
    "ok": (icons.CHECK_CIRCLE, "Low concern",
           "Nothing worrying shows up in this estimate. Keep up regular activity, balanced meals and routine check-ups."),
    "warn": (icons.TRIANGLE, "Needs attention",
             "This estimate points to some risk. Consider booking a check-up to talk through these numbers with a doctor."),
    "bad": (icons.SIREN, "High concern",
            "This estimate is in a high-risk range. Please speak to a doctor soon, and seek urgent care if you feel unwell."),
}


def _kind(msg):
    return "bad" if "🚨" in msg else ("warn" if "⚠️" in msg else "ok")


def _clean(msg):
    for ch in ("🚨", "⚠️", "✅"):
        msg = msg.replace(ch, "")
    return msg.strip(" -—")


def empty_panel(label):
    st.markdown(f'<div class="empty"><div class="eic">{icons.CLIPBOARD}</div><b>Your result appears here</b>'
                f'<span>Fill in the details and press “{label}”.</span></div>', unsafe_allow_html=True)


def result_card(resp, extra=""):
    """resp = backend JSON. extra = optional HTML 'fact' block."""
    msg = resp.get("result", "")
    kind = _kind(msg)
    icon, pill, advice = _KINDS[kind]
    st.markdown(
        f'<div class="res {kind}" role="status"><div class="top"><div class="badge">{icon}</div>'
        f'<div><span class="pill">{pill}</span><h3>{_h_escape(_clean(msg))}</h3></div></div>{extra}'
        f'<p class="advice">{advice}</p>'
        f'<div class="foot">{icons.INFO}<span>Saved to your profile. A statistical estimate, not a medical diagnosis.</span></div></div>',
        unsafe_allow_html=True)


def why_block(resp):
    """Estimated-risk bar + ONE short line saying why the result happened."""
    out = ""
    risk = resp.get("risk_percent")
    if risk is not None and resp.get("disease_rate") is None:
        out += bar_fact("Estimated risk", risk)
    if resp.get("reason"):
        out += f'<p class="whyline"><b>Why:</b> {_h_escape(resp["reason"])}</p>'
    return out


def rx_block(rx):
    """The AI-generated draft prescription card."""
    tags = {"test": ("none", "Test"), "medicine": ("warn", "Medicine"), "followup": ("ok", "Follow-up"),
            "urgent": ("bad", "Urgent"), "caution": ("none", "Caution")}
    html = (f'<div class="rxcard"><h3>AI-generated prescription (draft)</h3><p class="sum">{_h_escape(rx["summary"])}</p>'
            f'<div class="rxwarn">{icons.TRIANGLE}<span>{_h_escape(rx["disclaimer"])}</span></div>')
    for it in rx["items"]:
        kind, name = tags.get(it["kind"], ("none", it["kind"].title()))
        rx_tag = '<span class="rx-rx">Rx only</span>' if it.get("rx") else ""
        html += (f'<div class="rxitem"><div class="k"><span class="tag {kind}">{name}</span></div>'
                 f'<div class="t"><b>{_h_escape(it["title"])}{rx_tag}</b><span>{_h_escape(it["detail"])}</span></div></div>')
    return html + '</div>'


def bar_fact(label, pct):
    pct = max(0, min(100, float(pct)))
    return (f'<div class="fact"><div class="row"><span>{label}</span><b>{pct:g}%</b></div>'
            f'<div class="bar" role="img" aria-label="{label} {pct:g} percent"><i style="--w:{pct}%"></i></div></div>')


def value_fact(label, value):
    return f'<div class="fact"><div class="row"><span>{label}</span><b>{value}</b></div></div>'


def error_banner(text):
    st.markdown(f'<div class="banner bad">{icons.ALERT}<div>{text}</div></div>', unsafe_allow_html=True)
