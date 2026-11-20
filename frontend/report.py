"""Report page: combined summary + generate / download the PDF."""
from datetime import datetime

import streamlit as st

import api_client as api
from . import dashboard, icons, shell
from .data import CHECKUPS, build_summary, esc
from .pdf_report import build_report_pdf


def _insight_sections(insights):
    """One-line 'why' per checkup + the AI-generated draft prescription (both also in the PDF)."""
    expl = (insights or {}).get("explanations") or {}
    rx = (insights or {}).get("prescription")
    shell.section(icons.STETH, "Why you got these results")
    if not expl:
        st.markdown(f'<div class="banner info">{icons.INFO}<div>Run your checkups again to see why you got each result '
                    'and to get a draft prescription. They are created from new checkups.</div></div>', unsafe_allow_html=True)
    else:
        lines = "".join(f'<p class="whyline"><b>{esc(title)}:</b> {esc(expl[key]["reason"])}</p>'
                        for key, title, _ in CHECKUPS if key in expl and expl[key].get("reason"))
        st.markdown(f'<div class="why">{lines}</div>', unsafe_allow_html=True)
    if rx and expl:
        shell.section(icons.FILE_ICON, "AI prescription (draft)")
        st.markdown(shell.rx_block(rx), unsafe_allow_html=True)


def render(user):
    shell.page_header(icons.FILE, "Health report",
                      "A combined summary of your latest checkups, ready to download as a clean PDF you can share with your doctor.",
                      ["PDF · A4", "Saved to your account"])
    checkups = api.get_checkups(user["user_id"])
    if not checkups:
        st.markdown(f'<div class="empty"><div class="eic">{icons.CLIPBOARD}</div><b>No checkups yet</b>'
                    '<span>Run the Heart, Diabetes, Sugar or Blood pressure checks and your report will appear here.</span></div>',
                    unsafe_allow_html=True)
        return
    level, message = build_summary(checkups)
    dashboard.summary_card(checkups)
    dashboard.tiles(checkups)
    try:
        insights = api.get_insights(user["user_id"])
    except Exception:
        insights = None
    _insight_sections(insights)

    shell.section(icons.FILE_ICON, "PDF report")
    with st.container(key="form_card"):
        if st.button("Generate fresh PDF report", type="primary", icon=":material/description:",
                     use_container_width=True, key="gen_pdf"):
            with st.spinner("Building your report…"):
                pdf = build_report_pdf(user, checkups, level, message, insights)
                try:
                    api.save_report(user["user_id"], pdf)
                except Exception:
                    shell.error_banner("The PDF was built but could not be saved to your account.")
            st.session_state.fresh_pdf = (pdf, datetime.now().strftime("%d %b %Y, %I:%M %p"))

        fresh = st.session_state.get("fresh_pdf")
        if fresh:
            st.markdown(f'<div class="banner ok">{icons.CHECK}<div>Report ready — generated {esc(fresh[1])} and saved to your account.</div></div>',
                        unsafe_allow_html=True)
            st.download_button("Download PDF", data=fresh[0], file_name="health_checkup_report.pdf",
                               mime="application/pdf", icon=":material/download:", use_container_width=True,
                               type="primary", key="dl_fresh")
        prev = api.get_report(user["user_id"])
        if prev and not fresh:
            st.markdown(f'<div class="banner info">{icons.INFO}<div>Your last report was generated on {esc(prev["created_at"])}.</div></div>',
                        unsafe_allow_html=True)
            st.download_button("Download previous PDF", data=prev["pdf_data"], file_name="health_checkup_report.pdf",
                               mime="application/pdf", icon=":material/history:", use_container_width=True, key="dl_prev")
    st.markdown('<div class="fine">This combined summary is a statistical overview only and is not a medical diagnosis. '
                'Please consult a doctor for a full checkup and lab-confirmed results.</div>', unsafe_allow_html=True)
