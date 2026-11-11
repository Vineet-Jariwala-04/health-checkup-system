"""Shared helpers: emoji clean-up, risk summary, labels."""
import html
import re

from . import icons

_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\uFE00-\uFE0F\u200D]+")

# (key, title, icon)
CHECKUPS = [
    ("heart", "Heart disease", icons.HEART),
    ("diabetes", "Diabetes", icons.DROPLET),
    ("sugar", "Blood sugar", icons.ACTIVITY),
    ("bp", "Blood pressure", icons.GAUGE),
]
TITLES = {k: t for k, t, _ in CHECKUPS}
FLAG = {0: ("ok", "Normal"), 1: ("warn", "Borderline"), 2: ("bad", "High risk")}


def clean(text):
    return _EMOJI.sub("", str(text or "")).strip(" -—")


def esc(text):
    return html.escape(str(text if text is not None else ""))


def build_summary(checkups):
    """Same rules as the original app. Returns (level, message) or (None, None)."""
    if not checkups:
        return None, None
    high = sum(1 for c in checkups.values() if c["flag"] == 2)
    mild = sum(1 for c in checkups.values() if c["flag"] == 1)
    if high >= 2:
        return "high", ("Multiple checkups came back high-risk together. This combined pattern is worth "
                        "discussing with a doctor soon rather than waiting.")
    if high == 1 or mild >= 2:
        return "moderate", ("At least one area needs attention, and there are early signs in others too. "
                            "Consider reviewing your diet, activity, sleep, and getting a proper checkup.")
    if mild == 1:
        return "mild", ("Everything is mostly in a healthy range, with one area sitting borderline. "
                        "Worth keeping an eye on with regular checkups.")
    return "low", "All completed checkups came back in the normal range. Keep up the healthy habits!"


LEVELS = {  # level -> (css kind, title)
    "high": ("bad", "High combined risk"),
    "moderate": ("warn", "Moderate risk"),
    "mild": ("warn", "Mild risk"),
    "low": ("ok", "Low overall risk"),
}


def checkups_from_row(row):
    """Rebuild {type: {...}} from a flattened patient_history row (admin views)."""
    out = {}
    for key, _, _ in CHECKUPS:
        if row.get(f"{key}_updated_at"):
            out[key] = {"label": row.get(f"{key}_label"), "flag": row.get(f"{key}_flag") or 0,
                        "detail": row.get(f"{key}_detail"), "updated_at": row.get(f"{key}_updated_at")}
    return out
