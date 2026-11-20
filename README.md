# AI-Based Human Body Prediction System

A patient checkup platform that predicts risk for **Heart Disease**, **Diabetes**,
**Sugar Level**, and **Blood Pressure** using trained Random Forest models,
stores results per patient in SQLite, generates a combined PDF report, and
optionally mirrors patient data live to a Google Sheet.

The app is split into two processes that talk over HTTP:

| Process | File | Role |
|---|---|---|
| **Backend API** | `app.py` | Flask REST API. Owns the database, the ML models, and Google Sheets sync. |
| **Frontend UI** | `streamlit_app.py` | Streamlit web app. Talks to the backend only through `api_client.py`. |

---

## Table of contents

1. [Project structure](#1-project-structure)
2. [How it works](#2-how-it-works)
3. [Setup](#3-setup)
4. [Running the app](#4-running-the-app)
5. [First-time use](#5-first-time-use)
6. [The prediction pages](#6-the-prediction-pages)
7. [Combined report & PDF](#7-combined-report--pdf)
8. [Admin panel](#8-admin-panel)
9. [Database](#9-database)
10. [Google Sheets sync](#10-google-sheets-sync)
11. [Retraining a model](#11-retraining-a-model)
12. [Resetting the database](#12-resetting-the-database)
13. [Troubleshooting](#13-troubleshooting)
14. [Security notes](#14-security-notes)

---

## 1. Project structure

```text
AIMDD-503-Final-Project-Streamlit/
│
├── app.py                     # Flask backend API — the ONLY thing that touches
│                               #   the database and the .pkl models directly
├── streamlit_app.py           # Streamlit frontend — UI, routing, PDF rendering
├── api_client.py              # HTTP client the frontend uses to call the backend
├── database.py                # SQLite persistence layer (single patient_history table)
├── sheets_sync.py             # Google Sheets sync (background, debounced, retried)
├── config.py                  # Google Sheets configuration
├── reset_database.py          # Wipes and recreates the database
│
├── model.py                   # Heart Disease training script
├── model_diabetes.py          # Diabetes training script
├── model_sugar.py             # Sugar Level training script
├── model_bp.py                # Blood Pressure training script
│
├── Dataset/
│   ├── HeartDisease_Dataset.csv
│   ├── Diabetes_Dataset.csv
│   ├── SugarLevel_Dataset.csv
│   └── BloodPressure_Dataset.csv
│
├── Models/
│   ├── heart_disease_rf_model.pkl
│   ├── diabetes_rf_model.pkl
│   ├── sugar_level_rf_model.pkl
│   └── bp_rf_model.pkl
│
├── assets/
│   ├── logo-light.png
│   └── logo-dark.png
│
├── config/
│   └── google_service_account.json   # credentials — never commit this
│
├── checkup_app.db             # SQLite database (created automatically)
├── start_app.bat              # Windows: launches backend + frontend together
├── requirements.txt
├── Google Sheets.txt
├── .gitignore
└── README.md
```

---

## 2. How it works

```text
Browser
  │
  ▼
Streamlit UI (streamlit_app.py) ── HTTP (api_client.py) ──► Flask API (app.py)
                                                                   │
                                            ┌──────────────────────┼──────────────────────┐
                                            ▼                      ▼                      ▼
                                    Models/*.pkl            checkup_app.db         Google Sheets
                                  (Random Forest             (SQLite, one           (background,
                                   predictions)             row per patient)          debounced)
```

- The frontend **never** imports `database.py` or loads a `.pkl` file directly — every
  action (login, running a checkup, viewing the dashboard, generating a report) is an
  HTTP call to the Flask API.
- The four trained models already include their preprocessing pipeline, so the
  backend just builds a one-row DataFrame with the right feature names and calls
  `.predict_proba()`.
- **You do not need to retrain the models to run the app** — `Models/*.pkl` are
  already trained and committed.

---

## 3. Setup

### Step 1 — Open the project folder

Extract the project and open a terminal inside `AIMDD-503-Final-Project-Streamlit/`.

### Step 2 — Check Python

```bash
python --version
```

Python 3.10+ is recommended.

### Step 3 — Create and activate a virtual environment

```bash
python -m venv venv
```

PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Command Prompt:

```cmd
venv\Scripts\activate
```

macOS / Linux:

```bash
source venv/bin/activate
```

### Step 4 — Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5 — Add your Google service account credentials (optional)

Only needed if you want live Google Sheets sync — the app works fully without it.
Place your key at `config/google_service_account.json` and see
[Google Sheets sync](#10-google-sheets-sync) below.

---

## 4. Running the app

The backend **must** be running before the frontend, since every page depends on it.

### Option A — one click (Windows)

Double-click `start_app.bat`. It opens the Flask backend in its own window, waits
for it to finish loading the models, then starts Streamlit.

### Option B — two terminals (any OS)

```bash
# Terminal 1 — backend, start this FIRST
python app.py

# Terminal 2 — frontend
streamlit run streamlit_app.py
```

Streamlit will print a local address such as `http://localhost:8501` — open that
in your browser. If you open Streamlit before the backend, any button that talks
to the database or a model will show an on-screen error telling you to start
`app.py` first.

---

## 5. First-time use

### A. Create a patient account

1. Open the Streamlit app.
2. Click **Create a new account**.
3. Select `Patient`.
4. Enter name, age, email, and a password of at least 6 characters.
5. Click **Sign Up**.

### B. Create the first admin

If no approved admin exists yet, the very first `Admin` signup is auto-approved,
so there's always a way to bootstrap the admin panel. Every admin signup after
that stays pending until an existing approved admin approves it from **Admin DB**.

### C. Log in

Use the email and password you registered.

---

## 6. The prediction pages

After login, the navigation contains **Dashboard**, **❤️ Heart**, **🍬 Diabetes**,
**🩸 Sugar**, **🫀 Blood Pressure**, **📋 Report**, and (approved admins only)
**🗄️ Admin DB**.

| Page | Inputs |
|---|---|
| **Heart** | Gender, Chest Pain Type, Fasting Blood Sugar, Resting ECG, Exercise Induced Angina, Slope, Fluoroscopy Vessels, Thalassemia, Age, Resting Blood Pressure, Cholesterol, Maximum Heart Rate, ST Depression / Oldpeak |
| **Diabetes** | Gender, Family History, Physical Activity, Age, BMI, Glucose Level, Blood Pressure, Insulin Level, Skin Thickness, Diabetes Pedigree |
| **Sugar** | Test type (Fasting / Random (Postprandial) / HbA1c) — the valid numeric range changes with the selected type; also shows the combined `Prediabetic` + `Diabetic` probability as the estimated rate |
| **Blood Pressure** | Gender, Smoker, Salt Intake, Age, Systolic, Diastolic |

Each result is written straight into the logged-in patient's existing row — the
app keeps **one row per patient**, so re-running a checkup overwrites that
checkup's 4 columns (`..._label`, `..._flag`, `..._detail`, `..._updated_at`)
rather than creating a new entry. The risk flag is `0 = Normal`,
`1 = Borderline / Mild`, `2 = High Risk`.

---

## 7. Combined report & PDF

Open **📋 Report**. It reads the patient's latest saved results and builds a
combined risk summary across all four checkups. Clicking **Generate Fresh PDF
Report** builds a PDF with ReportLab, saves it into the patient's database row,
and offers it as an immediate download; it also stays available later from the
**Dashboard**.

---

## 8. Admin panel

Only an approved admin can open **🗄️ Admin DB**, which shows pending admin
approval requests and every patient's ID, name, role, age, email, login/logout
history, IP, all four checkup results, and PDF report timestamp — all read from
the same single `patient_history` table.

---

## 9. Database

Everything lives in **one SQLite table**, `patient_history`, in `checkup_app.db`.
There's one row per patient; logging in again, running a checkup, or generating
a report never inserts a new row — it always updates that patient's existing row
(e.g. `login_count` increments in place).

---

## 10. Google Sheets sync

The backend can mirror `patient_history` to a live Google Sheet using a service
account (`config/google_service_account.json`, configured in `config.py`).

**How it stays fast:** every write commits to SQLite first; the Sheets push is
queued afterward and runs entirely in a background thread, so it never blocks
a request or causes a timeout. Rapid writes to the same patient (e.g. running
several checkups back-to-back) are **debounced** — collapsed into a single
Sheets call about 1.5 seconds later instead of one call per write. Each push
only touches that **one patient's row** (`sheets_sync.upsert_row`) rather than
re-dumping the whole table, so the cost doesn't grow as your patient list does.
A full-table reconciliation (`sheets_sync.sync_rows`) only runs once, at
backend startup, to self-heal anything missed while it was last offline.
Transient failures (rate limits, brief network hiccups) are retried a few
times with backoff before being logged and skipped — a Sheets problem never
breaks login, checkups, or reports.

**To enable it:**

1. Place your service account key at `config/google_service_account.json`.
2. Share the target Google Sheet with that service account's `client_email` as
   an **Editor**.
3. Set the sheet URL in `config.py` (`GOOGLE_SHEET_URL`).
4. Make sure `GOOGLE_SHEETS_ENABLED = True` in `config.py`.

Set `GOOGLE_SHEETS_ENABLED = False` to turn sync off entirely — the app works
fully without it.

---

## 11. Retraining a model

**Not required to run the app** — `Models/*.pkl` are already trained. Only do
this if you've changed a dataset in `Dataset/`.

```bash
python model.py            # Heart Disease
python model_diabetes.py   # Diabetes
python model_sugar.py      # Sugar Level
python model_bp.py         # Blood Pressure
```

Each script reads its CSV from `Dataset/`, splits features/target, scales
numeric features, one-hot encodes categorical ones, trains a Random Forest,
evaluates it, and saves the pipeline into `Models/`.

---

## 12. Resetting the database

```bash
python reset_database.py
```

**Warning:** this deletes all current `patient_history` data and recreates the
table, so the next signup starts again at `user_id = 1`. Don't run this if you
need to keep existing patient accounts or results.

---

## 13. Troubleshooting

**`streamlit is not recognized`**
Use `python -m streamlit run streamlit_app.py` instead — more reliable on Windows.

**`ModuleNotFoundError`**
Activate your virtual environment, then `pip install -r requirements.txt`.

**Port 8501 already in use**
`streamlit run streamlit_app.py --server.port 8502`

**A page shows "Could not reach the Flask backend API"**
The backend isn't running, or isn't running yet. Start `python app.py` first
and wait for it to finish loading the four models, then reload the page.

**Model loading error on backend startup**
`streamlit_app.py` never loads `.pkl` files — only `app.py` does. Confirm all
four files exist under `Models/` next to `app.py`.

**Google Sheets sync is being skipped / logs a DNS or connection error**
This means your machine can't reach `oauth2.googleapis.com` — check your
internet connection, DNS settings, and any firewall/VPN. The app keeps working
normally either way; only the Sheets mirror is affected. See
[Google Sheets sync](#10-google-sheets-sync).

---

## 14. Security notes

`config/google_service_account.json` is a live credential and is already listed
in `.gitignore` — **never commit it or share it publicly.** If it's ever
exposed (pasted somewhere, uploaded by mistake), rotate it immediately: Google
Cloud Console → IAM & Admin → Service Accounts → the account → **Keys** → add a
new key, then delete the old one.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend API | Flask |
| ML | scikit-learn (Random Forest), pandas |
| Database | SQLite |
| Cloud sync | Google Sheets via `gspread` |
| Reports | ReportLab (PDF) |
| Auth | Werkzeug password hashing + Streamlit session state |


---

## 📧 Gmail notifications

Emails go to the address each user (admin **or** patient) signed up / logged in with:

| Event | Email |
|---|---|
| Sign up | "You have signed up" + name, user ID, account type, email, age, date & time (admins awaiting approval are told so) |
| Admin approved | "Your admin account is approved" |
| Log in | "You have logged in" + the same account details, login time, total logins |
| Log out | "You have logged out" + Heart / Diabetes / Sugar / Blood-pressure results + the **PDF report attached** |

**Setup (one time)**
1. On the sending Gmail account turn on **2-Step Verification**.
2. Create an **App Password**: https://myaccount.google.com/apppasswords
3. Copy `.env.example` to `.env` (same folder as `app.py`) and fill in `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`.
4. Restart the Flask backend (`python app.py`).

Notes: emails send on a background thread, so a Gmail problem never blocks signup/login/logout (failures print in the backend window). Passwords are never emailed. The logout email is sent when the user clicks **Log out** (closing the tab does not trigger it). Set `EMAIL_ENABLED=false` in `.env` to switch emails off.


---

## 🔐 Email verification (OTP) on the signup form + account lock

**Signup form order:** Role → Full name and Age → **Email with a "Send OTP" button beside it** → the code box right under the email → Password → Confirm password → Create account.
1. Type your email and click **Send OTP**. A 6-digit code is emailed (works for 10 minutes).
2. Type the code in the box under the email and click **Verify**.
3. Only after "Email verified" does **Create account** turn on. **No account is created before the email is verified** — the backend checks a one-time proof from the verification, so the rule can't be skipped by calling the API directly.

Details: 5 wrong codes cancel the code (click Resend OTP); a new code can be requested once every 60 seconds (max 5 per hour per email; 60 per hour for the whole app, to protect the sending Gmail account). Changing the email after verifying means verifying again. To switch this off, set `SIGNUP_OTP=false` in `.env` (not recommended).

**3 wrong passwords lock the account.**
- The 3rd wrong password locks the account (the owner gets an email). A locked account cannot log in, even with the right password.
- Only an approved **admin** can unlock it: Admin page → **Locked accounts** → **Unlock**. The owner gets an "unlocked" email.
- A correct login resets the wrong-password counter.
- If the only admin is locked, run on the server PC: `python unlock_account.py admin@example.com`

Existing databases are upgraded automatically the first time `python app.py` starts.


---

## 📈 History charts, explainable results and AI prescription

**History page** (new tab): your estimated risk over time for every checkup, one measurement over time (blood pressure, glucose, cholesterol, HbA1c...), and a table of all runs. Every checkup run is now saved (not just the latest).
**Admins:** Admin → **Analytics** shows how many users are normal / borderline / high risk per checkup, checkups per day, and lets an admin open any person's charts.

**Explainable results:** under each result, ONE short line says why it happened, e.g. "High risk mainly because of Glucose level (240 mg/dL) and BMI (36 kg/m2)." The same one-liners are on the Report page and in the PDF. Method: each input is swapped for a typical healthy value from the training data and the model is asked again (approximate, works with any model).

**AI prescription (draft):** the Report page and the PDF include a draft prescription generated from your latest results: tests, **named medicines with common brand names** you can ask for at a medical shop (e.g. Metformin: Glycomet, Glucophage), follow-up and emergency warning signs. Medicines are marked **Rx only** (the shop will ask for a doctor's prescription). It never gives doses, shows no medicines for under-18s, and always carries the warning: *generated by AI, not a doctor - please consult a doctor and do not trust it blindly.* Brand names are examples and differ by country. Rules live in `prescription.py`.

**Important fix - heart result was inverted:** in `HeartDisease_Dataset.csv` the label `1` means *no* heart disease, but the old code treated `1` as "High Risk". Now disease = class `0` (`HEART_DISEASE_CLASS` in `explain.py`). Heart results already saved in your database are corrected automatically, once, the first time the backend starts. Re-run old heart checkups if you want history/explanations for them.
