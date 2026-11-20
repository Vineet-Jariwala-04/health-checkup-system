"""The four checkup pages: Heart, Diabetes, Sugar level, Blood pressure.

Every value sent to the backend is exactly what the original app sent; only the
labels the user sees were made friendlier.
"""
import streamlit as st

import api_client as api
from . import icons, shell


# ------------------------------------------------------------------ helpers

def _pick(label, options, key, labels=None, help=None):
    """Card-style radio (great for 2-3 short choices)."""
    return st.radio(label, options, horizontal=True, key=key, help=help,
                    format_func=(lambda v: labels[v]) if labels else str)


def _send(page, fn, spinner="Analysing your details…", **fields):
    with st.spinner(spinner):
        try:
            resp = fn(st.session_state.user_id, **fields)
        except Exception as exc:                       # backend down, timeout, ...
            resp = {"error": f"Could not reach the server ({exc.__class__.__name__}). Is the backend running?"}
    st.session_state.setdefault("results", {})[page] = resp


def _layout(page, label, body, extra=None):
    """Form card on the left, sticky result panel on the right."""
    left, right = st.columns([1.7, 1], gap="large")
    with left:
        with st.container(key="form_card"):
            body()
    with right:
        with st.container(key="result_panel"):
            resp = st.session_state.get("results", {}).get(page)
            if not resp:
                shell.empty_panel(label)
            elif "result" not in resp:
                shell.error_banner(resp.get("error", "Something went wrong. Please try again."))
            else:
                shell.result_card(resp, (extra(resp) if extra else "") + shell.why_block(resp))
    st.markdown('<div class="fine">This tool gives statistical risk estimates only. It is not a medical diagnosis — '
                'please consult a doctor for a proper checkup.</div>', unsafe_allow_html=True)


GENDER = ["Male", "Female"]
YES_NO = ["No", "Yes"]


# --------------------------------------------------------------------- heart

def heart():
    shell.page_header(icons.HEART, "Heart disease risk",
                      "Estimate your risk from chest pain type, ECG results, exercise response and key measurements.",
                      ["13 inputs", "About 1 minute"])

    def body():
        shell.section(icons.USER, "About you")
        c1, c2 = st.columns(2)
        with c1:
            sex = _pick("Gender", GENDER, "h_sex")
        with c2:
            age = st.slider("Age", 18, 100, 52, key="h_age")

        shell.section(icons.STETH, "Symptoms & tests")
        c1, c2 = st.columns(2)
        with c1:
            chest = st.selectbox("Chest pain type", ["Typical angina", "Atypical angina", "Non-anginal pain", "Asymptomatic"], key="h_cp")
            ecg = st.selectbox("Resting ECG", ["Normal", "ST-T wave abnormality", "Left ventricular hypertrophy"], key="h_ecg")
            slope = st.selectbox("ST slope", ["Flat", "Downsloping", "Upsloping"], key="h_slope",
                                 help="Slope of the peak-exercise ST segment on the ECG.")
        with c2:
            fbs = st.selectbox("Fasting blood sugar", ["Lower than 120 mg/ml", "Greater than 120 mg/ml"], key="h_fbs",
                               format_func=lambda v: "Below 120 mg/dL" if v.startswith("Lower") else "Above 120 mg/dL")
            vessels = st.selectbox("Vessels seen on fluoroscopy", ["Zero", "One", "Two", "Three", "Four"], key="h_ves",
                                   help="Number of major vessels coloured by fluoroscopy.")
            thal = st.selectbox("Thalassemia", ["Normal", "Fixed Defect", "Reversable Defect", "No"], key="h_thal")
        angina = _pick("Exercise-induced angina", YES_NO, "h_ang", help="Chest pain brought on by exercise.")

        shell.section(icons.RULER, "Measurements")
        c1, c2 = st.columns(2)
        with c1:
            bp = st.slider("Resting blood pressure (mm Hg)", 80, 220, 125, key="h_bp")
            chol = st.slider("Cholesterol (mg/dL)", 100, 600, 212, key="h_chol")
        with c2:
            hr = st.slider("Max heart rate (bpm)", 60, 220, 168, key="h_hr")
            old = st.slider("ST depression (oldpeak)", 0.0, 10.0, 1.0, 0.1, key="h_old",
                            help="ST depression induced by exercise relative to rest.")

        if st.button("Predict risk", type="primary", use_container_width=True, key="h_go"):
            _send("heart", api.predict_heart, sex=sex, chest_pain_type=chest, fasting_blood_sugar=fbs, rest_ecg=ecg,
                  exercise_induced_angina=angina, slope=slope, vessels_colored_by_flourosopy=vessels, thalassemia=thal,
                  age=age, resting_blood_pressure=bp, cholestoral=chol, Max_heart_rate=hr, oldpeak=old)
            st.rerun()

    _layout("heart", "Predict risk", body)


# ------------------------------------------------------------------ diabetes

def diabetes():
    shell.page_header(icons.DROPLET, "Diabetes risk",
                      "Combine lifestyle, family history and lab values to estimate your chance of diabetes.",
                      ["10 inputs", "About 1 minute"])

    def body():
        shell.section(icons.USER, "About you")
        c1, c2 = st.columns(2)
        with c1:
            gender = _pick("Gender", GENDER, "d_sex")
        with c2:
            age = st.slider("Age", 18, 100, 45, key="d_age")

        shell.section(icons.LEAF, "Lifestyle & family")
        c1, c2 = st.columns(2)
        with c1:
            fam = _pick("Family history of diabetes", YES_NO, "d_fam")
        with c2:
            act = _pick("Physical activity", ["Low", "Moderate", "High"], "d_act")

        shell.section(icons.FLASK, "Lab values")
        c1, c2 = st.columns(2)
        with c1:
            glucose = st.slider("Glucose level (mg/dL)", 70, 300, 110, key="d_glu")
            insulin = st.slider("Insulin level (µU/mL)", 0, 400, 85, key="d_ins")
            bmi = st.slider("BMI", 15.0, 55.0, 25.0, 0.1, key="d_bmi", help="Body mass index (kg/m²).")
        with c2:
            bp = st.slider("Blood pressure (mm Hg)", 80, 200, 120, key="d_bp")
            skin = st.slider("Skin thickness (mm)", 0, 90, 23, key="d_skin")
            ped = st.slider("Diabetes pedigree", 0.05, 2.5, 0.45, 0.01, key="d_ped",
                            help="A score for how strongly diabetes runs in your family.")

        if st.button("Predict risk", type="primary", use_container_width=True, key="d_go"):
            _send("diabetes", api.predict_diabetes, gender=gender, family_history=fam, physical_activity=act, age=age,
                  bmi=bmi, glucose_level=glucose, blood_pressure=bp, insulin_level=insulin, skin_thickness=skin,
                  diabetes_pedigree=ped)
            st.rerun()

    _layout("diabetes", "Predict risk", body)


# --------------------------------------------------------------------- sugar

TEST_LABELS = {"Fasting": "Fasting", "Random (Postprandial)": "Random", "HbA1c": "HbA1c"}


def sugar():
    shell.page_header(icons.ACTIVITY, "Blood sugar level",
                      "Check whether a fasting, random or HbA1c reading falls in the normal, prediabetic or diabetic range.",
                      ["6 inputs", "About 30 seconds"])

    def body():
        shell.section(icons.FLASK, "Your test")
        test = _pick("Test type", list(TEST_LABELS), "s_test", TEST_LABELS)
        if test == "Fasting":
            level = st.slider("Sugar level (mg/dL)", 60, 400, 100, 1, key="s_lvl_f",
                              help="Normal fasting: below 100 · Prediabetic: 100–125 · Diabetic: 126 or more")
        elif test == "Random (Postprandial)":
            level = st.slider("Sugar level (mg/dL)", 70, 450, 140, 1, key="s_lvl_r",
                              help="Normal: below 140 · Prediabetic: 140–199 · Diabetic: 200 or more")
        else:
            level = st.slider("HbA1c level (%)", 4.0, 13.0, 5.7, 0.1, key="s_lvl_a",
                              help="Normal: below 5.7% · Prediabetic: 5.7–6.4% · Diabetic: 6.5% or more")

        shell.section(icons.USER, "About you")
        age = st.slider("Age", 15, 100, 40, key="s_age")

        shell.section(icons.STETH, "Symptoms")
        c1, c2, c3 = st.columns(3)
        with c1:
            urine = _pick("Frequent urination", YES_NO, "s_uri")
        with c2:
            thirst = _pick("Excessive thirst", YES_NO, "s_thi")
        with c3:
            fatigue = _pick("Fatigue", YES_NO, "s_fat")

        if st.button("Check sugar level", type="primary", use_container_width=True, key="s_go"):
            _send("sugar", api.predict_sugar, test_type=test, frequent_urination=urine, excessive_thirst=thirst,
                  fatigue=fatigue, age=age, sugar_level=level)
            st.rerun()

    _layout("sugar", "Check sugar level", body,
            extra=lambda r: shell.bar_fact("Model risk rate (prediabetic or diabetic)", r["disease_rate"])
            if r.get("disease_rate") is not None else "")


# ------------------------------------------------------------ blood pressure

def bp():
    shell.page_header(icons.GAUGE, "Blood pressure",
                      "Enter your reading and daily habits to see which blood pressure category it falls in.",
                      ["6 inputs", "About 30 seconds"])

    def body():
        shell.section(icons.USER, "About you")
        c1, c2 = st.columns(2)
        with c1:
            gender = _pick("Gender", GENDER, "b_sex")
        with c2:
            age = st.slider("Age", 18, 100, 40, key="b_age")

        shell.section(icons.LEAF, "Habits")
        c1, c2 = st.columns([1, 1.7])
        with c1:
            smoker = _pick("Smoker", YES_NO, "b_smk")
        with c2:
            salt = _pick("Salt intake", ["Low", "Moderate", "High"], "b_salt")

        shell.section(icons.GAUGE, "Your reading")
        c1, c2 = st.columns(2)
        with c1:
            sys_ = st.slider("Systolic (top number)", 85, 220, 120, key="b_sys")
        with c2:
            dia = st.slider("Diastolic (bottom number)", 50, 140, 80, key="b_dia")
        st.markdown(f'<div class="live" aria-live="polite"><b>{sys_}/{dia}</b><span>mm Hg</span></div>',
                    unsafe_allow_html=True)

        if st.button("Check blood pressure", type="primary", use_container_width=True, key="b_go"):
            _send("bp", api.predict_bp, gender=gender, smoker=smoker, salt_intake=salt, age=age,
                  systolic=sys_, diastolic=dia)
            st.rerun()

    _layout("bp", "Check blood pressure", body,
            extra=lambda r: shell.value_fact("Your reading", r["reading"]) if r.get("reading") else "")


RENDER = {"heart": heart, "diabetes": diabetes, "sugar": sugar, "bp": bp}
