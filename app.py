"""
Flask backend API for the AI-Based Human Body Prediction System.

This is the ONLY place that touches the SQLite database (database.py) and
the trained ML pipelines (*.pkl). The Streamlit frontend (streamlit_app.py) no longer
imports database.py or loads the models directly — it talks to this API
over HTTP instead, using api_client.py.

Run this BEFORE starting Streamlit:

    python app.py

It listens on http://127.0.0.1:5000 by default. Then, in a second terminal:

    streamlit run streamlit_app.py

All business logic (auth checks, password hashing, predictions, saving
checkup results, PDF storage, admin approval) is unchanged from the
original streamlit_app.py — it has simply moved into this file so it is served
through a real Flask REST API, as required by the project guidelines.
"""

import hashlib
import os
import hmac
import secrets
import sqlite3
import time
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import database as db
import explain
import mailer
import prescription

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Model loading (moved here from streamlit_app.py, unchanged)
# ---------------------------------------------------------------------------

def load_models():
    return {
        "heart": joblib.load(BASE_DIR / "Models" / "heart_disease_rf_model.pkl"),
        "diabetes": joblib.load(BASE_DIR / "Models" / "diabetes_rf_model.pkl"),
        "sugar": joblib.load(BASE_DIR / "Models" / "sugar_level_rf_model.pkl"),
        "bp": joblib.load(BASE_DIR / "Models" / "bp_rf_model.pkl"),
    }


MODELS = load_models()
db.init_db()

# Self-heal the Google Sheet once at startup (in the background, so this
# never delays the server coming up) in case anything was missed while the
# backend was last offline. Normal per-write updates after this use the
# cheap single-row sync in database.py, not this full dump.
db.full_resync_to_sheets()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def row_to_dict(row):
    """sqlite3.Row -> plain dict (JSON serialisable), or None."""
    return dict(row) if row is not None else None


# Columns that must never go into a plain user-list/user-detail JSON
# response: report_pdf is raw binary (not JSON serialisable — this was
# causing a 500 on /api/user/<id> and /api/users for any patient who had
# already generated a report) and password_hash is sensitive and unused by
# the frontend now that auth lives entirely in this backend.
_UNSAFE_USER_FIELDS = ("report_pdf", "password_hash")


def sanitize_user(row):
    """row_to_dict(), minus the fields above. Use this (not row_to_dict)
    for any endpoint that returns a user row or a list of user rows."""
    d = row_to_dict(row)
    if d is not None:
        for field in _UNSAFE_USER_FIELDS:
            d.pop(field, None)
    return d


CHECKUP_LABELS = {
    "heart": "❤️ Heart Disease",
    "diabetes": "🍬 Diabetes",
    "sugar": "🩸 Sugar Level",
    "bp": "🫀 Blood Pressure",
}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Auth: signup / login / logout
# ---------------------------------------------------------------------------

# Signup with email verification (all on the signup form):
#   1. /api/signup/send-otp   emails a 6-digit code to the typed address
#   2. /api/signup/verify-otp checks the code and returns a one-time "verify_token"
#   3. /api/signup            creates the account ONLY if it carries that token
OTP_MINUTES = 10            # how long a code works
OTP_MAX_WRONG = 5           # wrong codes allowed before a new code is needed
OTP_RESEND_SECONDS = 60     # minimum gap between two codes for the same email
OTP_MAX_SENDS = 5           # codes per email per hour
OTP_WINDOW_SECONDS = 3600
VERIFIED_VALID_SECONDS = 1800   # after verifying, 30 minutes to finish the form
GLOBAL_MAX_SENDS_PER_HOUR = 60  # whole app: protects the sending Gmail account from being flooded

_global_hits = []


def signup_otp_enabled():
    """Set SIGNUP_OTP=false in .env to skip the emailed code (not recommended)."""
    return os.environ.get("SIGNUP_OTP", "true").strip().lower() != "false"


def _global_allowed():
    now = time.time()
    _global_hits[:] = [t for t in _global_hits if now - t < 3600]
    if len(_global_hits) >= GLOBAL_MAX_SENDS_PER_HOUR:
        return False
    _global_hits.append(now)
    return True


def _valid_email(email):
    return bool(email) and "@" in email and "." in email.split("@")[-1] and " " not in email


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_matches(email, token):
    """True if `token` is the live proof that this exact email was verified."""
    row = db.get_email_otp(email)
    if not token or row is None or not row["token_hash"] or not row["token_expires"]:
        return False
    if time.time() > row["token_expires"]:
        return False
    return hmac.compare_digest(row["token_hash"], _hash_token(str(token)))


@app.get("/api/signup/config")
def signup_config():
    return jsonify({"otp_required": signup_otp_enabled()})


@app.post("/api/signup/send-otp")
def signup_send_otp():
    if not signup_otp_enabled():
        return jsonify({"error": "Email verification is turned off."}), 400
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    name = str(data.get("name") or "").strip()[:80]
    if not _valid_email(email):
        return jsonify({"error": "Please enter a valid email address first."}), 400
    if db.get_user_by_email(email):
        return jsonify({"error": "An account with this email already exists. Please log in instead."}), 400

    now = time.time()
    existing = db.get_email_otp(email)
    if existing and now - existing["created_at"] >= OTP_WINDOW_SECONDS:
        existing = None  # old record: start counting again
    if existing:
        wait = OTP_RESEND_SECONDS - (now - existing["last_sent_at"])
        if wait > 0:
            return jsonify({"error": f"A code was just sent. Please wait {int(wait) + 1} seconds before asking for another one."}), 429
        if existing["sends"] >= OTP_MAX_SENDS:
            return jsonify({"error": "Too many codes were requested for this email. Please try again in an hour."}), 429
    if not _global_allowed():
        return jsonify({"error": "Too many verification codes were requested. Please try again later."}), 429

    code = f"{secrets.randbelow(10 ** 6):06d}"
    sent, error = mailer.send_otp_email(email, name, code, OTP_MINUTES)
    if not sent:
        return jsonify({"error": error}), 503
    db.save_email_otp(
        email, generate_password_hash(code), expires_at=now + OTP_MINUTES * 60, now=now,
        sends=(existing["sends"] + 1) if existing else 1,
        created_at=existing["created_at"] if existing else now,
    )
    return jsonify({"status": "ok", "message": f"We emailed a 6-digit code to {email}. It is valid for {OTP_MINUTES} minutes."})


@app.post("/api/signup/verify-otp")
def signup_verify_otp():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    code = "".join(ch for ch in str(data.get("code") or "") if ch.isdigit())

    pending = db.get_email_otp(email)
    if pending is None or not pending["code_hash"]:
        return jsonify({"error": "Click \"Send OTP\" first to get a code for this email."}), 400
    if time.time() > pending["expires_at"]:
        return jsonify({"error": "This code has expired. Click \"Resend OTP\" to get a new one."}), 400
    if pending["wrong_tries"] >= OTP_MAX_WRONG:
        return jsonify({"error": "Too many wrong codes. Click \"Resend OTP\" to get a new one."}), 400
    if len(code) != 6 or not check_password_hash(pending["code_hash"], code):
        tries = db.bump_email_otp_wrong(email)
        if tries >= OTP_MAX_WRONG:
            return jsonify({"error": "Too many wrong codes. Click \"Resend OTP\" to get a new one."}), 400
        left = OTP_MAX_WRONG - tries
        return jsonify({"error": f"That code is not correct. {left} attempt{'s' if left != 1 else ''} left."}), 400

    token = secrets.token_urlsafe(32)
    db.mark_email_verified(email, _hash_token(token), time.time() + VERIFIED_VALID_SECONDS)
    return jsonify({"status": "ok", "verify_token": token, "message": "Email verified."})


@app.post("/api/signup")
def signup():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role") or "patient"
    if role not in ("patient", "admin"):
        role = "patient"
    try:
        age = int(data.get("age"))
    except (TypeError, ValueError):
        return jsonify({"error": "Please enter a valid age."}), 400

    if not name or not email or not password:
        return jsonify({"error": "Please fill in every field."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long."}), 400
    if db.get_user_by_email(email):
        return jsonify({"error": "An account with this email already exists. Please log in instead."}), 400
    if signup_otp_enabled() and not _token_matches(email, data.get("verify_token")):
        # The account is NEVER created before the emailed code was verified.
        return jsonify({"error": "Please verify your email with the OTP before signing up."}), 403

    is_first_admin = role == "admin" and not db.any_approved_admin_exists()
    try:
        user_id = db.create_user(name, age, email, generate_password_hash(password), role=role)
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists. Please log in instead."}), 400
    db.delete_email_otp(email)  # the verification is used up

    if role == "admin" and not is_first_admin:
        mailer.send_signup_email(db.get_user_by_id(user_id), pending_approval=True)
        return jsonify({
            "status": "pending_approval",
            "message": "Email verified. Your admin account request was submitted — an existing admin must approve it before you can log in.",
        })

    db.record_login_event(user_id, email, "signup", request.remote_addr)
    mailer.send_signup_email(db.get_user_by_id(user_id))
    return jsonify({"status": "ok", "user_id": user_id})


LOCKED_MESSAGE = (
    "This account is locked after 3 wrong password attempts. "
    "Please contact an admin to unlock it."
)


@app.post("/api/login")
def login():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = db.get_user_by_email(email)
    if user is not None and user["is_locked"]:
        # Locked accounts stay locked even with the right password.
        return jsonify({"error": LOCKED_MESSAGE, "locked": True}), 423
    if user is None or not check_password_hash(user["password_hash"], password):
        if user is None:
            return jsonify({"error": "Incorrect email or password."}), 401
        attempts, just_locked = db.register_failed_login(user["user_id"])
        if just_locked:
            mailer.send_account_locked_email(db.get_user_by_id(user["user_id"]))
            return jsonify({"error": LOCKED_MESSAGE, "locked": True}), 423
        left = max(db.MAX_FAILED_ATTEMPTS - attempts, 0)
        return jsonify({
            "error": f"Incorrect email or password. {left} attempt{'s' if left != 1 else ''} left "
                     "before this account is locked.",
        }), 401
    if user["role"] == "admin" and not user["is_approved"]:
        return jsonify({"error": "Your admin account is still awaiting approval. Please check back later."}), 403

    db.reset_failed_attempts(user["user_id"])
    db.record_login_event(user["user_id"], user["email"], "login", request.remote_addr)
    mailer.send_login_email(db.get_user_by_id(user["user_id"]))
    return jsonify({"status": "ok", "user_id": user["user_id"]})


@app.post("/api/logout")
def logout():
    """Body: {"user_id": 1, "pdf_base64": "..." (optional)}.

    The frontend builds the PDF (reportlab lives there) from the latest
    checkups and sends it along, so the emailed PDF always matches the
    results in the email. If none is sent, the last saved report is used.
    """
    import base64

    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")
    user = db.get_user_by_id(user_id) if user_id else None
    if user:
        db.record_login_event(user["user_id"], user["email"], "logout", request.remote_addr)

        pdf_bytes = None
        if data.get("pdf_base64"):
            try:
                pdf_bytes = base64.b64decode(data["pdf_base64"])
                db.save_report(user["user_id"], pdf_bytes)
            except Exception:  # a bad payload must never block logout
                pdf_bytes = None
        if pdf_bytes is None:
            saved = db.get_report(user["user_id"])
            pdf_bytes = bytes(saved["pdf_data"]) if saved else None

        mailer.send_logout_email(
            db.get_user_by_id(user["user_id"]),
            db.get_checkups(user["user_id"]),
            pdf_bytes,
        )
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.get("/api/user/<int:user_id>")
def get_user(user_id):
    return jsonify(sanitize_user(db.get_user_by_id(user_id)))


@app.get("/api/users")
def get_all_users():
    return jsonify([sanitize_user(r) for r in db.get_all_users()])


@app.get("/api/pending-admins")
def pending_admins():
    return jsonify([sanitize_user(r) for r in db.get_pending_admins()])


@app.post("/api/approve-admin/<int:user_id>")
def approve_admin(user_id):
    """Body: {"approver_id": <id>}. Only the first admin may approve new admins."""
    data = request.get_json(silent=True) or {}
    first = db.get_first_admin()
    if first is None or data.get("approver_id") != first["user_id"]:
        return jsonify({"error": "Only the first admin can approve new admin accounts."}), 403
    db.approve_admin(user_id)
    approved = db.get_user_by_id(user_id)
    if approved and approved["role"] == "admin":
        mailer.send_admin_approved_email(approved)
    return jsonify({"status": "ok"})


@app.post("/api/unlock/<int:user_id>")
def unlock_account(user_id):
    """Body: {"approver_id": <id>}. Any approved, unlocked admin may unlock a
    locked account (patients and admins alike)."""
    data = request.get_json(silent=True) or {}
    approver = db.get_user_by_id(data.get("approver_id")) if data.get("approver_id") else None
    if (approver is None or approver["role"] != "admin" or not approver["is_approved"]
            or approver["is_locked"]):
        return jsonify({"error": "Only an approved admin can unlock accounts."}), 403
    target = db.get_user_by_id(user_id)
    if target is None:
        return jsonify({"error": "That account does not exist."}), 404
    if not target["is_locked"]:
        return jsonify({"error": "That account is not locked."}), 400
    db.unlock_user(user_id)
    mailer.send_account_unlocked_email(db.get_user_by_id(user_id))
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Checkups (predictions)
# ---------------------------------------------------------------------------

@app.get("/api/checkups/<int:user_id>")
def get_checkups(user_id):
    return jsonify(db.get_checkups(user_id))


def _log_run(key, user_id, flag, detail, payload, risk_percent=None):
    """Explains the result, stores this run in the history table, and returns the explanation.
    Never lets an explanation problem break the prediction itself."""
    try:
        info = explain.explain(key, MODELS[key], payload)
    except Exception as exc:  # noqa: BLE001
        print(f"[explain] {key}: {exc}")
        if risk_percent is None:
            try:
                risk_percent = explain.risk_percent(key, MODELS[key], payload)
            except Exception:  # noqa: BLE001
                pass
        info = {"risk_percent": risk_percent, "factors": [], "reason": ""}
    if risk_percent is None:
        risk_percent = info["risk_percent"]
    try:
        db.add_history(user_id, key, CHECKUP_LABELS[key], flag, detail, risk_percent, payload, info["factors"])
    except Exception as exc:  # noqa: BLE001
        print(f"[history] {key}: {exc}")
    reason = info.get("reason") or explain.reason(risk_percent, info["factors"])
    return {"risk_percent": risk_percent, "explanation": info["factors"], "reason": reason}


@app.post("/api/checkup/heart")
def checkup_heart():
    payload = request.get_json(force=True) or {}
    user_id = payload.pop("user_id")

    data = pd.DataFrame([payload])
    prediction = int(MODELS["heart"].predict(data)[0])
    # NOTE: in the training data the label 1 means NO heart disease (see explain.py), so disease = class 0.
    high = prediction == explain.HEART_DISEASE_CLASS
    result = "⚠️ High Risk of Heart Disease" if high else "✅ Low Risk / Normal"
    flag = 2 if high else 0

    db.save_checkup(user_id, "heart", CHECKUP_LABELS["heart"], flag, result)
    return jsonify({"result": result, **_log_run("heart", user_id, flag, result, payload)})


@app.post("/api/checkup/diabetes")
def checkup_diabetes():
    payload = request.get_json(force=True) or {}
    user_id = payload.pop("user_id")

    data = pd.DataFrame([payload])
    prediction = int(MODELS["diabetes"].predict(data)[0])
    result = (
        "⚠️ High Risk of Diabetes (Sugar Disease)"
        if prediction == 1
        else "✅ Low Risk / Normal"
    )
    flag = 2 if prediction == 1 else 0

    db.save_checkup(user_id, "diabetes", CHECKUP_LABELS["diabetes"], flag, result)
    return jsonify({"result": result, **_log_run("diabetes", user_id, flag, result, payload)})


@app.post("/api/checkup/sugar")
def checkup_sugar():
    payload = request.get_json(force=True) or {}
    user_id = payload.pop("user_id")

    data = pd.DataFrame([payload])
    prediction = MODELS["sugar"].predict(data)[0]

    proba = MODELS["sugar"].predict_proba(data)[0]
    classes = list(MODELS["sugar"].classes_)
    disease_rate = 0.0
    if "Diabetic" in classes and "Prediabetic" in classes:
        disease_rate = round(
            (proba[classes.index("Diabetic")] + proba[classes.index("Prediabetic")]) * 100,
            1,
        )

    icons = {
        "Normal": "✅ Normal Sugar Level",
        "Prediabetic": "⚠️ Prediabetic Range",
        "Diabetic": "🚨 Diabetic Range (High Sugar)",
    }
    result = icons.get(prediction, str(prediction))
    flag = {"Normal": 0, "Prediabetic": 1, "Diabetic": 2}.get(prediction, 0)

    detail = f"{result} ({disease_rate}% rate)"
    db.save_checkup(user_id, "sugar", CHECKUP_LABELS["sugar"], flag, detail)
    return jsonify({"result": result, "disease_rate": disease_rate,
                    **_log_run("sugar", user_id, flag, detail, payload, risk_percent=disease_rate)})


@app.post("/api/checkup/bp")
def checkup_bp():
    payload = request.get_json(force=True) or {}
    user_id = payload.pop("user_id")
    systolic = payload["systolic"]
    diastolic = payload["diastolic"]

    data = pd.DataFrame([payload])
    prediction = MODELS["bp"].predict(data)[0]

    icons = {
        "Normal": "✅ Normal Blood Pressure",
        "Elevated": "⚠️ Elevated Blood Pressure",
        "Hypertension Stage 1": "⚠️ Hypertension Stage 1",
        "Hypertension Stage 2": "🚨 Hypertension Stage 2",
        "Hypertensive Crisis": "🚨 Hypertensive Crisis — Seek Care Immediately",
    }
    result = icons.get(prediction, str(prediction))
    reading = f"{systolic}/{diastolic} mm Hg"
    flag = 0 if prediction == "Normal" else (1 if prediction in ("Elevated", "Hypertension Stage 1") else 2)

    detail = f"{result} ({reading})"
    db.save_checkup(user_id, "bp", CHECKUP_LABELS["bp"], flag, detail)
    return jsonify({"result": result, "reading": reading, **_log_run("bp", user_id, flag, detail, payload)})


@app.get("/api/history/<int:user_id>")
def get_history(user_id):
    """Every checkup run of one user (oldest first) - for the history charts."""
    return jsonify([{k: r[k] for k in ("id", "checkup_type", "label", "flag", "detail", "risk_percent", "inputs", "created_at")}
                    for r in db.get_history(user_id)])


@app.get("/api/history")
def get_all_history():
    """Admin analytics. Query: ?approver_id=<id of an approved admin>."""
    approver = db.get_user_by_id(request.args.get("approver_id", type=int)) if request.args.get("approver_id") else None
    if approver is None or approver["role"] != "admin" or not approver["is_approved"]:
        return jsonify({"error": "Only an approved admin can view all history."}), 403
    return jsonify([{k: r[k] for k in ("id", "user_id", "checkup_type", "flag", "risk_percent", "created_at")}
                    for r in db.get_all_history()])


@app.get("/api/insights/<int:user_id>")
def get_insights(user_id):
    """Explainable results + the AI-generated draft prescription, built from the latest run of each checkup."""
    user = db.get_user_by_id(user_id)
    latest = db.get_latest_insights(user_id)
    explanations = {k: {"risk_percent": r["risk_percent"], "factors": r["explanation"], "detail": r["detail"],
                        "created_at": r["created_at"], "reason": explain.reason(r["risk_percent"], r["explanation"])}
                    for k, r in latest.items()}
    rx = prescription.build_prescription(
        {k: {"flag": r["flag"], "detail": r["detail"], "inputs": r["inputs"]} for k, r in latest.items()},
        age=user["age"] if user else None,
    )
    return jsonify({"explanations": explanations, "prescription": rx})


# ---------------------------------------------------------------------------
# Combined PDF report storage
# ---------------------------------------------------------------------------

@app.post("/api/report/<int:user_id>")
def save_report(user_id):
    """Body: {"pdf_base64": "..."}. The PDF bytes themselves are still built
    with reportlab in the Streamlit frontend (that's rendering, not a data
    operation) — this endpoint just persists them, same as db.save_report
    did before."""
    import base64

    data = request.get_json(force=True) or {}
    pdf_bytes = base64.b64decode(data.get("pdf_base64", ""))
    db.save_report(user_id, pdf_bytes)
    return jsonify({"status": "ok"})


@app.get("/api/report/<int:user_id>")
def get_report(user_id):
    import base64

    report = db.get_report(user_id)
    if report is None:
        return jsonify(None)
    return jsonify({
        "pdf_base64": base64.b64encode(report["pdf_data"]).decode("ascii"),
        "created_at": report["created_at"],
    })


if __name__ == "__main__":
    # threaded=True lets the dev server handle more than one request at a
    # time, so one slow request (e.g. a checkup save) can never block an
    # unrelated one (e.g. a login) from being served in parallel.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
