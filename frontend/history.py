"""History page: charts of every checkup you have run (and the same charts for the admin's patient view)."""
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

import api_client as api
from . import icons, shell
from .data import CHECKUPS, FLAG, TITLES, clean

# label shown in the picker -> (checkup type, input key, test_type filter or None)
MEASURES = {
    "Blood pressure: systolic (mm Hg)": ("bp", "systolic", None),
    "Blood pressure: diastolic (mm Hg)": ("bp", "diastolic", None),
    "Glucose level, diabetes check (mg/dL)": ("diabetes", "glucose_level", None),
    "BMI (kg/m2)": ("diabetes", "bmi", None),
    "Cholesterol (mg/dL)": ("heart", "cholestoral", None),
    "Resting blood pressure, heart check (mm Hg)": ("heart", "resting_blood_pressure", None),
    "Max heart rate (bpm)": ("heart", "Max_heart_rate", None),
    "Fasting sugar (mg/dL)": ("sugar", "sugar_level", "Fasting"),
    "Random sugar (mg/dL)": ("sugar", "sugar_level", "Random (Postprandial)"),
    "HbA1c (%)": ("sugar", "sugar_level", "HbA1c"),
}
LEVEL_COLORS = alt.Scale(domain=["Normal", "Borderline", "High risk"], range=["#16a34a", "#d97706", "#dc2626"])


def to_frame(rows):
    """List of history rows -> DataFrame with local timestamps and readable columns."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    local = datetime.now().astimezone().tzinfo
    df["when"] = pd.to_datetime(df["created_at"], utc=True).dt.tz_convert(local).dt.tz_localize(None)
    df["Checkup"] = df["checkup_type"].map(TITLES)
    df["Level"] = df["flag"].map(lambda f: FLAG.get(int(f), FLAG[0])[1])
    return df


def _line(df, field, color=None, y_title="", domain=None, extra_tooltips=()):
    """Line + points chart. Uses explicit field names so labels containing ':' or '(' are safe."""
    scale = alt.Scale(domain=domain) if domain else alt.Undefined
    enc = dict(
        x=alt.X(field="when", type="temporal", title="Date and time"),
        y=alt.Y(field=field, type="quantitative", title=y_title, scale=scale),
        tooltip=[alt.Tooltip(field="when", type="temporal", title="When"),
                 alt.Tooltip(field=field, type="quantitative", title=y_title), *extra_tooltips],
    )
    if color:
        enc["color"] = alt.Color(field=color, type="nominal", title=None)
    st.altair_chart(alt.Chart(df).mark_line(point=alt.OverlayMarkDef(size=80)).encode(**enc).properties(height=300),
                    use_container_width=True)


def charts(rows, key):
    """The patient charts for one user's history rows. `key` keeps widget keys unique."""
    df = to_frame(rows)
    if df.empty:
        st.markdown(f'<div class="empty"><div class="eic">{icons.CLIPBOARD}</div><b>No checkups yet</b>'
                    '<span>Run the Heart, Diabetes, Sugar or Blood pressure checks and your history will appear here.</span></div>',
                    unsafe_allow_html=True)
        return

    shell.section(icons.ACTIVITY, "Estimated risk over time", "Higher = more at risk")
    risk = df.dropna(subset=["risk_percent"])
    _line(risk, "risk_percent", color="Checkup", y_title="Estimated risk (%)", domain=[0, 100],
          extra_tooltips=[alt.Tooltip(field="Checkup", type="nominal"), alt.Tooltip(field="Level", type="nominal")])
    if len(df) == 1:
        st.caption("Run a checkup again later to see a trend.")

    # one measurement over time (only measurements you actually have data for)
    series = {}
    for label, (ctype, field, test) in MEASURES.items():
        part = df[df["checkup_type"] == ctype]
        if test:
            part = part[part["inputs"].map(lambda i: i.get("test_type") == test)]
        vals = part["inputs"].map(lambda i: i.get(field))
        part = part.assign(value=pd.to_numeric(vals, errors="coerce")).dropna(subset=["value"])
        if not part.empty:
            series[label] = part
    if series:
        shell.section(icons.GAUGE, "Your measurements over time")
        pick = st.selectbox("Measurement", list(series), key=f"{key}_measure", label_visibility="collapsed")
        _line(series[pick], "value", y_title=pick,
              extra_tooltips=[alt.Tooltip(field="Level", type="nominal", title="Result")])

    shell.section(icons.FILE_ICON, "All runs")
    table = df.sort_values("when", ascending=False)
    st.dataframe(
        pd.DataFrame({
            "When": table["when"].dt.strftime("%d %b %Y, %I:%M %p"),
            "Checkup": table["Checkup"],
            "Result": table["detail"].map(clean),
            "Level": table["Level"],
            "Estimated risk (%)": table["risk_percent"],
        }),
        hide_index=True, use_container_width=True)


def render(user):
    shell.page_header(icons.ACTIVITY, "History",
                      "See how your results change over time. Every checkup you run is saved here.",
                      ["Your trends", "Saved automatically"])
    try:
        rows = api.get_history(user["user_id"])
    except Exception:
        shell.error_banner("Could not load your history. Is the backend running?")
        return
    charts(rows, "hist")
    st.markdown('<div class="fine">Estimates only - not a medical diagnosis. Please consult a doctor for lab-confirmed results.</div>',
                unsafe_allow_html=True)
