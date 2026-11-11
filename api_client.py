"""
Thin HTTP client the Streamlit frontend (streamlit_app.py) uses to talk to the Flask
backend (app.py). streamlit_app.py no longer imports database.py or the ML
models directly — every operation goes through one of the functions below,
which just calls the Flask REST API.

Make sure the backend is running first:

    python app.py

before you start Streamlit.
"""

import base64

import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:5000/api"


class ApiError(Exception):
    """Raised when the backend returns an error response."""


def _request(method, path, timeout, **kwargs):
    try:
        resp = requests.request(method, f"{API_BASE_URL}{path}", timeout=timeout, **kwargs)
    except requests.exceptions.ConnectionError:
        st.error(
            "⚠️ Could not reach the Flask backend API at "
            f"{API_BASE_URL}. Please start it first with `python app.py`, "
            "then reload this page."
        )
        st.stop()
    except requests.exceptions.Timeout:
        st.warning(
            "⏳ The backend is taking longer than usual to respond. "
            "Please wait a moment and try again."
        )
        st.stop()
    return resp


def _get(path, **kwargs):
    return _request("get", path, timeout=30, **kwargs)


def _post(path, json=None):
    return _request("post", path, timeout=30, json=json)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def signup_config():
    """Tells the screen whether signup needs the emailed code."""
    try:
        return bool(_get("/signup/config").json().get("otp_required", True))
    except Exception:
        return True


def signup_send_otp(email, name=""):
    """Emails a 6-digit code. Returns (json, status_code)."""
    resp = _post("/signup/send-otp", json={"email": email, "name": name})
    return resp.json(), resp.status_code


def signup_verify_otp(email, code):
    """Checks the code. On success the json has a one-time 'verify_token'."""
    resp = _post("/signup/verify-otp", json={"email": email, "code": code})
    return resp.json(), resp.status_code


def signup(name, age, email, password, role, verify_token=None):
    resp = _post("/signup", json={
        "name": name, "age": age, "email": email, "password": password, "role": role,
        "verify_token": verify_token,
    })
    return resp.json(), resp.status_code


def login(email, password):
    resp = _post("/login", json={"email": email, "password": password})
    return resp.json(), resp.status_code


def logout(user_id, pdf_bytes=None):
    """pdf_bytes (optional) is the freshly built report; the backend saves it
    and attaches it to the logout email."""
    payload = {"user_id": user_id}
    if pdf_bytes:
        payload["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")
    _post("/logout", json=payload)


# ---------------------------------------------------------------------------
# Users / admin
# ---------------------------------------------------------------------------

def get_user(user_id):
    resp = _get(f"/user/{user_id}")
    if resp.status_code != 200:
        return None
    return resp.json()


def get_all_users():
    return _get("/users").json()


def get_pending_admins():
    return _get("/pending-admins").json()


def approve_admin(user_id, approver_id):
    """Returns (json, status_code). Only the first admin is allowed to approve."""
    resp = _post(f"/approve-admin/{user_id}", json={"approver_id": approver_id})
    return resp.json(), resp.status_code


def unlock_user(user_id, approver_id):
    """Admin action. Returns (json, status_code)."""
    resp = _post(f"/unlock/{user_id}", json={"approver_id": approver_id})
    return resp.json(), resp.status_code


# ---------------------------------------------------------------------------
# Checkups / predictions
# ---------------------------------------------------------------------------

def get_checkups(user_id):
    return _get(f"/checkups/{user_id}").json()


def predict_heart(user_id, **fields):
    payload = {"user_id": user_id, **fields}
    return _post("/checkup/heart", json=payload).json()


def predict_diabetes(user_id, **fields):
    payload = {"user_id": user_id, **fields}
    return _post("/checkup/diabetes", json=payload).json()


def predict_sugar(user_id, **fields):
    payload = {"user_id": user_id, **fields}
    return _post("/checkup/sugar", json=payload).json()


def predict_bp(user_id, **fields):
    payload = {"user_id": user_id, **fields}
    return _post("/checkup/bp", json=payload).json()


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def get_history(user_id):
    """Every checkup run of one user (oldest first)."""
    return _get(f"/history/{user_id}").json()


def get_all_history(approver_id):
    """Admin analytics: every run of every user."""
    resp = _get("/history", params={"approver_id": approver_id})
    return resp.json() if resp.status_code == 200 else []


def get_insights(user_id):
    """Explainable results + the AI-generated draft prescription for the latest runs."""
    return _get(f"/insights/{user_id}").json()


def save_report(user_id, pdf_bytes):
    _post(f"/report/{user_id}", json={"pdf_base64": base64.b64encode(pdf_bytes).decode("ascii")})


def get_report(user_id):
    data = _get(f"/report/{user_id}").json()
    if not data:
        return None
    return {
        "pdf_data": base64.b64decode(data["pdf_base64"]),
        "created_at": data["created_at"],
    }
