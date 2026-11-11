"""Login + Sign-up screen (split layout: hero on the left, form on the right)."""
import base64
import re
from pathlib import Path

import streamlit as st

import api_client as api
from . import icons, styles

ASSETS = Path(__file__).resolve().parent.parent / "assets"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
SIGN_IN, SIGN_UP = "Sign in", "Create account"


def _logo_b64():
    p = ASSETS / "logo-dark.png"          # white lettering -> readable on the dark hero
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def _hero():
    logo = _logo_b64()
    img = f'<img src="data:image/png;base64,{logo}" alt="AHV Hospital">' if logo else ""
    feats = [
        (icons.CPU, "Four AI risk checks", "Heart, diabetes, blood sugar and blood pressure."),
        (icons.FILE, "Downloadable PDF report", "One combined summary you can share with your doctor."),
        (icons.SHIELD, "Your own private account", "Results are saved to your profile only."),
    ]
    feat_html = "".join(
        f'<div class="feat"><div class="ic">{i}</div><div><b>{t}</b><span>{d}</span></div></div>'
        for i, t, d in feats
    )
    st.markdown(
        '<div class="hero"><div class="blob b1"></div><div class="blob b2"></div>'
        f'<div class="hero-top">{img}<h1>Understand your health risks, early.</h1>'
        '<p class="lead">Answer a few simple questions and get an instant, machine-learning based '
        'risk estimate for the conditions that matter most.</p>'
        '<svg class="ecg" viewBox="0 0 400 56" preserveAspectRatio="none" aria-hidden="true">'
        '<path d="M0 30 H110 L125 30 L138 8 L154 50 L168 22 L178 30 H290 L303 30 L314 12 L326 44 L336 30 H400"/></svg></div>'
        f'<div class="hero-bottom">{feat_html}<div class="tagline">Expertise · Compassion · Community</div></div></div>',
        unsafe_allow_html=True,
    )


def _hint(text, kind=""):
    icon = icons.CHECK if kind == "ok" else (icons.ALERT if kind == "bad" else "")
    st.markdown(f'<div class="hint {kind}">{icon}<span>{text}</span></div>', unsafe_allow_html=True)


def _banner(text, kind="info", icon=icons.INFO):
    st.markdown(f'<div class="banner {kind}">{icon}<div>{text}</div></div>', unsafe_allow_html=True)


def _strength(pw):
    score = sum([len(pw) >= 8, bool(re.search(r"[a-z]", pw) and re.search(r"[A-Z]", pw)),
                 bool(re.search(r"\d", pw)), bool(re.search(r"[^A-Za-z0-9]", pw))])
    return score if len(pw) >= 6 else min(score, 1)


def _keep_mode():
    if st.session_state.get("auth_mode") is None:
        st.session_state.auth_mode = st.session_state.get("_auth_last", SIGN_IN)


def _go(mode):
    st.session_state.auth_mode = mode


def _login():
    st.markdown('<div class="form-head"><h2>Welcome back</h2>'
                '<p>Sign in to see your checkups and reports.</p></div>', unsafe_allow_html=True)
    if msg := st.session_state.pop("flash", None):
        _banner(msg, "ok", icons.CHECK)
    with st.form("login_form", border=True):
        email = st.text_input("Email", placeholder="you@example.com", icon=":material/mail:", key="li_email")
        pw = st.text_input("Password", type="password", placeholder="Your password", icon=":material/lock:", key="li_pw")
        go = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if go:
        email = email.strip().lower()
        if not email or not pw:
            _banner("Please enter your email and password.", "bad", icons.ALERT)
        elif not EMAIL_RE.match(email):
            _banner("That email address doesn't look right.", "bad", icons.ALERT)
        else:
            with st.spinner("Signing you in…"):
                res, status = api.login(email, pw)
            if status == 200:
                st.session_state.user_id = res["user_id"]
                st.rerun()
            _banner(res.get("error", "Incorrect email or password."), "bad", icons.ALERT)
    st.markdown('<div class="link-row">New to AHV Hospital?</div>', unsafe_allow_html=True)
    st.button("Create an account", use_container_width=True, on_click=_go, args=(SIGN_UP,), key="to_signup")


def _fresh_otp_state():
    return {"sent_email": None, "verified_email": None, "token": None, "msg": None}


def _reset_otp():
    st.session_state.su_otp = _fresh_otp_state()
    st.session_state.pop("su_otp_code", None)


def _signup():
    st.markdown('<div class="form-head"><h2>Create your account</h2>'
                '<p>It takes less than a minute. No payment details needed.</p></div>', unsafe_allow_html=True)

    if st.session_state.get("pending_msg"):
        st.markdown(f'<div class="card success-card"><div class="badge">{icons.MAIL_CHECK}</div>'
                    f'<h3>Request sent</h3><p>{st.session_state.pending_msg}</p></div>', unsafe_allow_html=True)
        st.button("Back to sign in", use_container_width=True, key="back_si",
                  on_click=lambda: (st.session_state.pop("pending_msg", None), _go(SIGN_IN)))
        return

    role = st.radio("I am a…", ["patient", "admin"], horizontal=True, key="su_role",
                    format_func=lambda r: "Patient" if r == "patient" else "Admin",
                    captions=["Check my own health", "Manage the system"])
    if role == "admin":
        _banner("Admin accounts must be approved by an existing admin before you can sign in "
                "(the very first admin is approved automatically).")

    otp_required = api.signup_config()
    otp = st.session_state.setdefault("su_otp", _fresh_otp_state())

    # 1) name + age
    c1, c2 = st.columns([2, 1])
    with c1:
        name = st.text_input("Full name", placeholder="Your full name", icon=":material/person:", key="su_name")
    with c2:
        age = st.number_input("Age", min_value=1, max_value=129, value=18, step=1, key="su_age")

    # 2) email, with the "Send OTP" button right beside it
    typed = (st.session_state.get("su_email") or "").strip().lower()
    verified = bool(otp_required and otp["token"] and otp["verified_email"] == typed)
    code_sent = bool(otp_required and not verified and otp["sent_email"] == typed and typed)

    ec, bc = st.columns([3, 1], vertical_alignment="bottom")
    with ec:
        email = st.text_input("Email", placeholder="you@example.com", icon=":material/mail:",
                              key="su_email", disabled=verified)
    e = email.strip().lower()
    if otp_required:
        with bc:
            label = "Verified ✓" if verified else ("Resend OTP" if code_sent else "Send OTP")
            send = st.button(label, key="su_send", use_container_width=True, disabled=verified)
        if send:
            if not EMAIL_RE.match(e):
                otp["msg"] = ("bad", "Please enter a valid email address first.")
            else:
                with st.spinner("Sending the code…"):
                    res, status = api.signup_send_otp(e, name.strip())
                if status == 200:
                    otp.update(sent_email=e, verified_email=None, token=None, msg=("ok", res.get("message", "Code sent.")))
                    st.session_state.pop("su_otp_code", None)
                    st.rerun()
                else:
                    otp["msg"] = ("bad", res.get("error", "Could not send the code."))
    if e and not verified and not code_sent:
        _hint("Looks good", "ok") if EMAIL_RE.match(e) else _hint("Enter a valid email like name@example.com", "bad")

    # 3) the OTP check section, directly under the email
    if otp_required:
        if otp["msg"] and not verified:
            _banner(otp["msg"][1], "ok" if otp["msg"][0] == "ok" else "bad",
                    icons.CHECK if otp["msg"][0] == "ok" else icons.ALERT)
        if code_sent:
            oc, vc = st.columns([3, 1], vertical_alignment="bottom")
            with oc:
                code = st.text_input("Enter the 6-digit code from your email", placeholder="123456",
                                     max_chars=6, icon=":material/key:", key="su_otp_code")
            with vc:
                verify = st.button("Verify", key="su_verify", use_container_width=True)
            if verify:
                digits = "".join(ch for ch in code if ch.isdigit())
                if len(digits) != 6:
                    otp["msg"] = ("bad", "Please enter the 6-digit code from your email.")
                    st.rerun()
                with st.spinner("Checking the code…"):
                    res, status = api.signup_verify_otp(e, digits)
                if status == 200:
                    otp.update(verified_email=e, token=res["verify_token"], msg=None)
                else:
                    otp["msg"] = ("bad", res.get("error", "Could not verify the code."))
                st.rerun()
        if verified:
            _banner("Email verified. You can finish creating your account below.", "ok", icons.CHECK)
            if st.button("Use a different email", key="su_change"):
                _reset_otp()
                st.rerun()

    # 4) password
    pw = st.text_input("Password", type="password", placeholder="At least 6 characters",
                       icon=":material/lock:", key="su_pw")
    s = _strength(pw) if pw else 0
    if pw:
        label = ["", "Too weak", "Fair", "Good", "Strong"][s] if len(pw) >= 6 else "Use at least 6 characters"
        st.markdown(f'<div class="meter s{s}"><i></i><i></i><i></i><i></i></div>', unsafe_allow_html=True)
        _hint(label, "ok" if s >= 3 else ("bad" if len(pw) < 6 else ""))
    pw2 = st.text_input("Confirm password", type="password", placeholder="Re-enter your password",
                        icon=":material/lock_reset:", key="su_pw2")
    if pw2:
        _hint("Passwords match", "ok") if pw2 == pw else _hint("Passwords don't match yet", "bad")

    blocked = otp_required and not verified
    if blocked:
        st.caption("Verify your email to enable the button below. Your account is created only after that.")
    if st.button("Create account", type="primary", use_container_width=True, key="su_go", disabled=blocked):
        n = name.strip()
        problem = (
            "Please enter your full name." if not n else
            "Please enter a valid email address." if not EMAIL_RE.match(e) else
            "Password must be at least 6 characters long." if len(pw) < 6 else
            "The two passwords don't match." if pw != pw2 else None
        )
        if problem:
            _banner(problem, "bad", icons.ALERT)
        else:
            with st.spinner("Creating your account…"):
                res, status = api.signup(n, int(age), e, pw, role, otp["token"] if otp_required else None)
            if status != 200:
                _banner(res.get("error", "Could not create the account."), "bad", icons.ALERT)
            elif res.get("status") == "pending_approval":
                _reset_otp()
                st.session_state.pending_msg = res["message"]
                st.rerun()
            else:
                _reset_otp()
                st.session_state.user_id = res["user_id"]
                st.rerun()
    st.markdown('<div class="link-row">Already have an account?</div>', unsafe_allow_html=True)
    st.button("Sign in instead", use_container_width=True, on_click=_go, args=(SIGN_IN,), key="to_signin")
    st.markdown('<div class="fine">This tool gives statistical estimates, not a medical diagnosis.</div>',
                unsafe_allow_html=True)


def render():
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        _hero()
    with right:
        styles.theme_controls()
        st.session_state.setdefault("auth_mode", SIGN_IN)
        picked = st.segmented_control("Mode", [SIGN_IN, SIGN_UP], key="auth_mode",
                                      label_visibility="collapsed", selection_mode="single", width="stretch",
                                      on_change=_keep_mode)
        mode = picked or st.session_state.get("_auth_last", SIGN_IN)
        st.session_state._auth_last = mode
        _signup() if mode == SIGN_UP else _login()
