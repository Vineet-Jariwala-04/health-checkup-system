"""Explainable results: which of your inputs pushed the risk up or down.

Method (works with any scikit-learn model, no extra packages): for every
input we ask the model again with that one input swapped for a typical
HEALTHY value (taken from the training dataset) and measure how much the
estimated risk changes. A big drop means that input was pushing your risk up.
Related inputs (e.g. systolic + diastolic) are swapped together.

This is an approximate, local explanation - not a medical finding.
"""
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
# In HeartDisease_Dataset.csv the label 1 means NO disease (patients labelled 1 have lower ST depression,
# higher max heart rate, no exercise angina, fewer blocked vessels...), so "disease" is class 0.
# The app used to treat 1 as disease, which inverted every heart result. Set to 1 only if you retrain
# the model on data where 1 really means disease.
HEART_DISEASE_CLASS = 0

MIN_EFFECT_POINTS = 1.0     # ignore inputs that move the estimate by less than this
MAX_FACTORS = 5

# key -> (csv file, target column, test for a "healthy" row)
_DATASETS = {
    "heart": ("HeartDisease_Dataset.csv", "target", lambda s: s == 0),
    "diabetes": ("Diabetes_Dataset.csv", "target", lambda s: s == 0),
    "sugar": ("SugarLevel_Dataset.csv", "category", lambda s: s == "Normal"),
    "bp": ("BloodPressure_Dataset.csv", "category", lambda s: s == "Normal"),
}

# friendly names: feature -> (label, unit)
LABELS = {
    "heart": {
        "age": ("Age", "years"), "sex": ("Gender", ""), "chest_pain_type": ("Chest pain type", ""),
        "resting_blood_pressure": ("Resting blood pressure", "mm Hg"), "cholestoral": ("Cholesterol", "mg/dL"),
        "fasting_blood_sugar": ("Fasting blood sugar", ""), "rest_ecg": ("Resting ECG", ""),
        "Max_heart_rate": ("Max heart rate", "bpm"), "exercise_induced_angina": ("Exercise-induced angina", ""),
        "oldpeak": ("ST depression", ""), "slope": ("ST slope", ""),
        "vessels_colored_by_flourosopy": ("Vessels seen on fluoroscopy", ""), "thalassemia": ("Thalassemia", ""),
    },
    "diabetes": {
        "age": ("Age", "years"), "gender": ("Gender", ""), "bmi": ("BMI", "kg/m2"),
        "glucose_level": ("Glucose level", "mg/dL"), "blood_pressure": ("Blood pressure", "mm Hg"),
        "insulin_level": ("Insulin level", "uU/mL"), "skin_thickness": ("Skin thickness", "mm"),
        "diabetes_pedigree": ("Diabetes pedigree", ""), "family_history": ("Family history of diabetes", ""),
        "physical_activity": ("Physical activity", ""),
    },
    "sugar": {
        "age": ("Age", "years"), "sugar_level": ("Sugar level", ""), "frequent_urination": ("Frequent urination", ""),
        "excessive_thirst": ("Excessive thirst", ""), "fatigue": ("Fatigue", ""),
    },
    "bp": {
        "age": ("Age", "years"), "gender": ("Gender", ""), "smoker": ("Smoker", ""),
        "salt_intake": ("Salt intake", ""),
    },
}
# inputs that are swapped together, and inputs that are context only
GROUPS = {"bp": {"Blood pressure reading": ["systolic", "diastolic"]}}
CONTEXT_ONLY = {"sugar": {"test_type"}}      # the test type decides what the sugar number means
_FBS = {"Lower than 120 mg/ml": "Below 120 mg/dL", "Greater than 120 mg/ml": "Above 120 mg/dL"}

_refs_cache = {}


def _reference(key):
    """Typical healthy values: median for numbers, most common for categories."""
    if key in _refs_cache:
        return _refs_cache[key]
    fname, target, is_healthy = _DATASETS[key]
    df = pd.read_csv(BASE_DIR / "Dataset" / fname)
    df.columns = [c.strip() for c in df.columns]
    healthy = df[is_healthy(df[target])].drop(columns=[target])
    ref = {}
    for col in healthy.columns:
        ref[col] = healthy[col].median() if pd.api.types.is_numeric_dtype(healthy[col]) else healthy[col].mode().iloc[0]
    if key == "sugar":   # a "normal" sugar number depends on the test type
        ref["_sugar_by_test"] = healthy.groupby("test_type")["sugar_level"].median().to_dict()
    _refs_cache[key] = ref
    return ref


def _risk(key, model, proba):
    """Probability (0-1) of the 'not healthy' outcome for each row."""
    classes = list(model.classes_)
    if key == "heart":
        return proba[:, classes.index(HEART_DISEASE_CLASS)]
    if key == "diabetes":
        return proba[:, classes.index(1)]
    if key == "sugar":
        return proba[:, classes.index("Diabetic")] + proba[:, classes.index("Prediabetic")]
    return 1 - proba[:, classes.index("Normal")]


def risk_percent(key, model, inputs):
    feats = list(model.feature_names_in_)
    df = pd.DataFrame([{f: inputs[f] for f in feats}])[feats]
    return round(float(_risk(key, model, model.predict_proba(df))[0]) * 100, 1)


def _fmt_num(v):
    v = float(v)
    return f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.1f}"


def _show(key, feature, value, inputs):
    """Human-readable value (with unit)."""
    if feature == "fasting_blood_sugar":
        return _FBS.get(str(value), str(value))
    if key == "sugar" and feature == "sugar_level":
        unit = "%" if inputs.get("test_type") == "HbA1c" else "mg/dL"
        return f"{_fmt_num(value)} {unit}"
    unit = LABELS.get(key, {}).get(feature, ("", ""))[1]
    if isinstance(value, (int, float)) or hasattr(value, "item"):
        return f"{_fmt_num(value)} {unit}".strip()
    return str(value)


def reason(risk_percent, factors):
    """ONE short line saying why the result happened (built from the biggest influences)."""
    if risk_percent is None:
        return ""
    ups = [f for f in factors if f["direction"] == "up"][:2]
    downs = [f for f in factors if f["direction"] == "down"][:2]

    def names(fs):
        return " and ".join(f'{f["label"]} ({f["value"]})' for f in fs)

    if risk_percent >= 50:
        return f"High risk mainly because of {names(ups)}." if ups else "High risk, but no single input stood out."
    if risk_percent >= 20:
        return f"Moderate risk mainly because of {names(ups)}." if ups else "Moderate risk, but no single input stood out."
    if downs:
        return f"Low risk, helped by {names(downs)}."
    if ups:
        return f"Low risk overall; {names(ups[:1])} added a little."
    return "Low risk: your values are close to typical healthy values."


def explain(key, model, inputs):
    """Returns {"risk_percent": float, "factors": [...]} - the biggest influences first."""
    feats = list(model.feature_names_in_)
    ref = dict(_reference(key))
    if key == "sugar":
        ref["sugar_level"] = ref["_sugar_by_test"].get(inputs.get("test_type"), ref["sugar_level"])
    context = CONTEXT_ONLY.get(key, set())

    units = []   # (label, [features])
    grouped = {f for fs in GROUPS.get(key, {}).values() for f in fs}
    for label, fs in GROUPS.get(key, {}).items():
        units.append((label, fs))
    for f in feats:
        if f not in grouped and f not in context:
            units.append((LABELS[key][f][0], [f]))

    base = {f: inputs[f] for f in feats}
    rows = [base]
    for _, fs in units:
        row = dict(base)
        for f in fs:
            row[f] = ref[f]
        rows.append(row)
    probs = _risk(key, model, model.predict_proba(pd.DataFrame(rows)[feats]))
    risk = float(probs[0])

    factors = []
    for (label, fs), p_swapped in zip(units, probs[1:]):
        effect = round((risk - float(p_swapped)) * 100, 1)       # + = pushed risk UP
        if abs(effect) < MIN_EFFECT_POINTS:
            continue
        if len(fs) == 2 and key == "bp":
            value = f"{_fmt_num(inputs['systolic'])}/{_fmt_num(inputs['diastolic'])} mm Hg"
            typical = f"{_fmt_num(ref['systolic'])}/{_fmt_num(ref['diastolic'])} mm Hg"
        else:
            value = _show(key, fs[0], inputs[fs[0]], inputs)
            typical = _show(key, fs[0], ref[fs[0]], inputs)
        up = effect > 0
        factors.append({
            "feature": "+".join(fs), "label": label, "value": value, "typical": typical,
            "effect_points": effect, "direction": "up" if up else "down",
            "sentence": (f"{label} ({value}) {'raised' if up else 'lowered'} your estimated risk by about "
                         f"{abs(effect):g} points compared with a typical healthy value ({typical})."),
        })
    factors.sort(key=lambda f: -abs(f["effect_points"]))
    factors = factors[:MAX_FACTORS]
    return {"risk_percent": round(risk * 100, 1), "factors": factors, "reason": reason(round(risk * 100, 1), factors)}
