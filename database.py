"""SQLite database layer for the Body Checkup app.

Everything lives in ONE table: `patient_history`. There is one row per
patient (user_id is the unique key). Logging in again, running a checkup,
or downloading a PDF never inserts a new row — it always UPDATEs that
patient's existing row in place (e.g. login_count goes up by 1 on the same
row instead of a new row being created).
"""

import sqlite3
import threading
from pathlib import Path

import sheets_sync

DB_PATH = Path(__file__).resolve().parent / 'checkup_app.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Remove the old multi-table layout (users / login_history / checkups /
    # reports) — everything now lives in the single patient_history table.
    for old_table in ('users', 'login_history', 'checkups', 'reports'):
        cur.execute(f'DROP TABLE IF EXISTS {old_table}')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS patient_history (
            user_id            INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique per patient
            name               TEXT NOT NULL,
            age                INTEGER NOT NULL,
            email              TEXT NOT NULL UNIQUE,                -- mail id
            password_hash      TEXT NOT NULL,

            -- role & admin-approval workflow
            role               TEXT NOT NULL DEFAULT 'patient',     -- 'patient' or 'admin'
            is_approved        INTEGER NOT NULL DEFAULT 1,          -- patients: always 1. admins: 0 until approved

            -- wrong-password lockout: 3 wrong passwords in a row lock the account
            -- until an approved admin unlocks it
            failed_attempts    INTEGER NOT NULL DEFAULT 0,
            is_locked          INTEGER NOT NULL DEFAULT 0,
            locked_at          TEXT,

            -- security / login tracking (same row updated every time, never a new row)
            login_count        INTEGER NOT NULL DEFAULT 0,          -- how many times logged in
            signup_at          TEXT NOT NULL DEFAULT (datetime('now')),
            last_login_at      TEXT,                                -- sign up / login time
            last_logout_at     TEXT,                                -- log out time
            last_ip_address    TEXT,

            -- heart disease report
            heart_label         TEXT,
            heart_flag          INTEGER,
            heart_detail        TEXT,
            heart_updated_at    TEXT,

            -- diabetes report
            diabetes_label       TEXT,
            diabetes_flag        INTEGER,
            diabetes_detail      TEXT,
            diabetes_updated_at  TEXT,

            -- sugar report
            sugar_label          TEXT,
            sugar_flag           INTEGER,
            sugar_detail         TEXT,
            sugar_updated_at     TEXT,

            -- blood pressure report
            bp_label             TEXT,
            bp_flag              INTEGER,
            bp_detail            TEXT,
            bp_updated_at        TEXT,

            -- his (combined) PDF report
            report_pdf           BLOB,
            report_generated_at  TEXT
        )
    ''')

    # Migration safety net: if patient_history already existed from before
    # this update (e.g. on a live deployment), add any columns it's missing
    # rather than crashing.
    existing_cols = {row[1] for row in cur.execute('PRAGMA table_info(patient_history)')}
    if 'role' not in existing_cols:
        cur.execute("ALTER TABLE patient_history ADD COLUMN role TEXT NOT NULL DEFAULT 'patient'")
    if 'is_approved' not in existing_cols:
        cur.execute('ALTER TABLE patient_history ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 1')
    if 'failed_attempts' not in existing_cols:
        cur.execute('ALTER TABLE patient_history ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0')
    if 'is_locked' not in existing_cols:
        cur.execute('ALTER TABLE patient_history ADD COLUMN is_locked INTEGER NOT NULL DEFAULT 0')
    if 'locked_at' not in existing_cols:
        cur.execute('ALTER TABLE patient_history ADD COLUMN locked_at TEXT')

    # Every checkup run (the patient_history columns only keep the LATEST one). Used for the
    # history charts and the explainable results / prescription in the report.
    cur.execute('''
        CREATE TABLE IF NOT EXISTS checkup_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            checkup_type  TEXT NOT NULL,
            label         TEXT,
            flag          INTEGER NOT NULL DEFAULT 0,
            detail        TEXT,
            risk_percent  REAL,
            inputs        TEXT,          -- JSON of what the user entered
            explanation   TEXT,          -- JSON list of the biggest influences
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_history_user ON checkup_history (user_id, checkup_type, id)')

    # One-time correction: before this fix the app treated heart label 1 as "disease", but in the training
    # data 1 means NO disease, so every stored heart result was inverted. Swap them once.
    cur.execute('CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT)')
    if cur.execute("SELECT 1 FROM app_meta WHERE key = 'heart_result_fix_v1'").fetchone() is None:
        cur.execute("""
            UPDATE patient_history SET
                heart_flag = CASE heart_flag WHEN 2 THEN 0 WHEN 0 THEN 2 ELSE heart_flag END,
                heart_detail = CASE heart_detail
                    WHEN '\u26a0\ufe0f High Risk of Heart Disease' THEN '\u2705 Low Risk / Normal'
                    WHEN '\u2705 Low Risk / Normal' THEN '\u26a0\ufe0f High Risk of Heart Disease'
                    ELSE heart_detail END
            WHERE heart_updated_at IS NOT NULL
        """)
        cur.execute("INSERT INTO app_meta (key, value) VALUES ('heart_result_fix_v1', datetime('now'))")

    # One-time codes that verify an email address on the signup form. Only the
    # HASH of the code is stored. Once the code is entered correctly, a random
    # token (also stored hashed) proves the email was verified; the signup request
    # must carry it. No account exists before that.
    cur.execute('DROP TABLE IF EXISTS signup_otps')  # older design, no longer used
    cur.execute('''
        CREATE TABLE IF NOT EXISTS email_otps (
            email          TEXT PRIMARY KEY,
            code_hash      TEXT NOT NULL,      -- '' once the code has been used
            expires_at     REAL NOT NULL,
            wrong_tries    INTEGER NOT NULL DEFAULT 0,
            sends          INTEGER NOT NULL DEFAULT 1,
            last_sent_at   REAL NOT NULL,
            created_at     REAL NOT NULL,
            token_hash     TEXT,
            token_expires  REAL
        )
    ''')

    conn.commit()
    conn.close()


# --------------------------------------------------------------- patients --

def any_approved_admin_exists():
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT 1 FROM patient_history WHERE role = 'admin' AND is_approved = 1 LIMIT 1"
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def create_user(name, age, email, password_hash, role='patient'):
    """Patients are approved immediately. Admin signups start unapproved —
    is_approved stays 0 until an existing approved admin approves them from
    the admin panel, so they can't log in until then. Exception: if no
    approved admin exists anywhere yet, the very first admin signup is
    auto-approved so there's always a way to bootstrap the admin panel."""
    if role == 'admin':
        is_approved = 0 if any_approved_admin_exists() else 1
    else:
        is_approved = 1
    conn = get_db()
    try:
        cur = conn.execute(
            'INSERT INTO patient_history (name, age, email, password_hash, role, is_approved) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (name, age, email, password_hash, role, is_approved),
        )
        conn.commit()
        user_id = cur.lastrowid
    finally:
        conn.close()
    _sync_to_sheets(user_id)
    return user_id


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            'SELECT * FROM patient_history WHERE email = ?', (email,)
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            'SELECT * FROM patient_history WHERE user_id = ?', (user_id,)
        ).fetchone()
    finally:
        conn.close()


def get_all_users():
    conn = get_db()
    try:
        return conn.execute('SELECT * FROM patient_history ORDER BY user_id').fetchall()
    finally:
        conn.close()


def get_pending_admins():
    """Admin signups still waiting for an approved admin to approve them."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM patient_history WHERE role = 'admin' AND is_approved = 0 "
            'ORDER BY user_id'
        ).fetchall()
    finally:
        conn.close()


def get_first_admin():
    """The first admin ever created (auto-approved at signup). Only this admin
    may approve other admin sign-ups."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM patient_history WHERE role = 'admin' AND is_approved = 1 "
            'ORDER BY user_id LIMIT 1'
        ).fetchone()
    finally:
        conn.close()


def approve_admin(user_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE patient_history SET is_approved = 1 WHERE user_id = ? AND role = 'admin'",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()
    _sync_to_sheets(user_id)


def clear_all_patients():
    """Drops patient_history entirely and recreates it with the exact same
    name/columns via init_db(). A plain DELETE keeps SQLite's internal
    AUTOINCREMENT counter (in sqlite_sequence) at its old high-water mark, so
    the next signup would still get user_id 5, 6, ... instead of 1. Dropping
    and recreating the table clears that counter too, so the next patient
    really does start at user_id = 1."""
    conn = get_db()
    try:
        conn.execute('DROP TABLE IF EXISTS patient_history')
        conn.commit()
    finally:
        conn.close()
    init_db()
    # Every patient row just got wiped/recreated at once — no single
    # user_id to target, so reconcile the whole sheet in one go.
    full_resync_to_sheets()


# ---------------------------------------------------- login / logout (security) --

# ------------------------------------------------- wrong-password lockout --

MAX_FAILED_ATTEMPTS = 3


def register_failed_login(user_id):
    """Counts one more wrong password. At MAX_FAILED_ATTEMPTS the account is
    locked. Returns (attempts_so_far, just_locked)."""
    conn = get_db()
    try:
        conn.execute(
            'UPDATE patient_history SET failed_attempts = failed_attempts + 1 '
            'WHERE user_id = ? AND is_locked = 0',
            (user_id,),
        )
        row = conn.execute(
            'SELECT failed_attempts, is_locked FROM patient_history WHERE user_id = ?', (user_id,)
        ).fetchone()
        attempts = row['failed_attempts'] if row else 0
        just_locked = False
        if row and not row['is_locked'] and attempts >= MAX_FAILED_ATTEMPTS:
            conn.execute(
                "UPDATE patient_history SET is_locked = 1, locked_at = datetime('now') WHERE user_id = ?",
                (user_id,),
            )
            just_locked = True
        conn.commit()
        return attempts, just_locked
    finally:
        conn.close()


def reset_failed_attempts(user_id):
    conn = get_db()
    try:
        conn.execute(
            'UPDATE patient_history SET failed_attempts = 0 WHERE user_id = ? AND failed_attempts != 0',
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def unlock_user(user_id):
    """Admin action: lifts the lock and clears the wrong-password counter."""
    conn = get_db()
    try:
        conn.execute(
            'UPDATE patient_history SET is_locked = 0, failed_attempts = 0, locked_at = NULL '
            'WHERE user_id = ?',
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------ email verification codes --

def get_email_otp(email):
    conn = get_db()
    try:
        return conn.execute('SELECT * FROM email_otps WHERE email = ?', (email,)).fetchone()
    finally:
        conn.close()


def save_email_otp(email, code_hash, expires_at, now, sends=1, created_at=None):
    """Creates or replaces the code for this email (also drops any older token)."""
    conn = get_db()
    try:
        conn.execute(
            'INSERT OR REPLACE INTO email_otps '
            '(email, code_hash, expires_at, wrong_tries, sends, last_sent_at, created_at, token_hash, token_expires) '
            'VALUES (?, ?, ?, 0, ?, ?, ?, NULL, NULL)',
            (email, code_hash, expires_at, sends, now, created_at or now),
        )
        conn.commit()
    finally:
        conn.close()


def bump_email_otp_wrong(email):
    conn = get_db()
    try:
        conn.execute('UPDATE email_otps SET wrong_tries = wrong_tries + 1 WHERE email = ?', (email,))
        conn.commit()
        row = conn.execute('SELECT wrong_tries FROM email_otps WHERE email = ?', (email,)).fetchone()
        return row['wrong_tries'] if row else 0
    finally:
        conn.close()


def mark_email_verified(email, token_hash, token_expires):
    """The code was right: burn it and store the proof-of-verification token."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE email_otps SET code_hash = '', expires_at = 0, token_hash = ?, token_expires = ? WHERE email = ?",
            (token_hash, token_expires, email),
        )
        conn.commit()
    finally:
        conn.close()


def delete_email_otp(email):
    conn = get_db()
    try:
        conn.execute('DELETE FROM email_otps WHERE email = ?', (email,))
        conn.commit()
    finally:
        conn.close()


def record_login_event(user_id, email, action, ip_address=None):
    """Updates the patient's own row in place — no new row is ever created here.

    'signup' and 'login' both bump login_count by 1 and stamp last_login_at.
    'logout' stamps last_logout_at. Either way it's an UPDATE on the same
    user_id, matching the previous entry rather than inserting a fresh one.
    """
    conn = get_db()
    try:
        if action == 'logout':
            conn.execute(
                "UPDATE patient_history "
                "SET last_logout_at = datetime('now'), last_ip_address = ? "
                'WHERE user_id = ?',
                (ip_address, user_id),
            )
        else:  # 'signup' and 'login' both count as a login moment
            conn.execute(
                "UPDATE patient_history "
                "SET login_count = login_count + 1, "
                "    last_login_at = datetime('now'), "
                '    last_ip_address = ? '
                'WHERE user_id = ?',
                (ip_address, user_id),
            )
        conn.commit()
    finally:
        conn.close()
    _sync_to_sheets(user_id)


# ------------------------------------------------------------- checkups --

_CHECKUP_COLUMNS = ('heart', 'diabetes', 'sugar', 'bp')


def save_checkup(user_id, checkup_type, label, flag, detail=''):
    """Updates the 4 columns for this checkup type on the patient's existing
    row (never inserts a new row) — so the latest result simply overwrites
    the previous one."""
    if checkup_type not in _CHECKUP_COLUMNS:
        raise ValueError(f'Unknown checkup type: {checkup_type}')

    conn = get_db()
    try:
        conn.execute(f'''
            UPDATE patient_history
            SET {checkup_type}_label = ?,
                {checkup_type}_flag = ?,
                {checkup_type}_detail = ?,
                {checkup_type}_updated_at = datetime('now')
            WHERE user_id = ?
        ''', (label, flag, detail, user_id))
        conn.commit()
    finally:
        conn.close()
    _sync_to_sheets(user_id)


def add_history(user_id, checkup_type, label, flag, detail, risk_percent, inputs, explanation):
    """Appends one checkup run (never overwrites)."""
    import json
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO checkup_history (user_id, checkup_type, label, flag, detail, risk_percent, inputs, explanation) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (user_id, checkup_type, label, flag, detail, risk_percent,
             json.dumps(inputs, default=str), json.dumps(explanation, default=str)),
        )
        conn.commit()
    finally:
        conn.close()


def _history_row(r):
    import json
    out = dict(r)
    out['inputs'] = json.loads(out['inputs']) if out.get('inputs') else {}
    out['explanation'] = json.loads(out['explanation']) if out.get('explanation') else []
    return out


def get_history(user_id):
    """All runs of one user, oldest first."""
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM checkup_history WHERE user_id = ? ORDER BY id', (user_id,)).fetchall()
    finally:
        conn.close()
    return [_history_row(r) for r in rows]


def get_all_history(limit=20000):
    """Every run of every user (admin analytics), oldest first."""
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM checkup_history ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    finally:
        conn.close()
    return [_history_row(r) for r in reversed(rows)]


def get_latest_insights(user_id):
    """{checkup_type: latest history row} for one user."""
    latest = {}
    for row in get_history(user_id):
        latest[row['checkup_type']] = row
    return latest


def get_checkups(user_id):
    """Rebuilds the old {type: {label, flag, detail, updated_at}} shape from
    the flattened columns, so templates don't need to change."""
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT * FROM patient_history WHERE user_id = ?', (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {}

    checkups = {}
    for checkup_type in _CHECKUP_COLUMNS:
        updated_at = row[f'{checkup_type}_updated_at']
        if updated_at is None:
            continue  # this checkup hasn't been run yet
        checkups[checkup_type] = {
            'label': row[f'{checkup_type}_label'],
            'flag': row[f'{checkup_type}_flag'],
            'detail': row[f'{checkup_type}_detail'],
            'updated_at': updated_at,
        }
    return checkups


def get_all_checkups():
    """All checkup results for every patient, flattened out into one row per
    (patient, checkup type) — used only by the admin DB view for a readable
    list; the underlying storage is still just patient_history."""
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM patient_history ORDER BY user_id').fetchall()
    finally:
        conn.close()

    entries = []
    for row in rows:
        for checkup_type in _CHECKUP_COLUMNS:
            updated_at = row[f'{checkup_type}_updated_at']
            if updated_at is None:
                continue
            entries.append({
                'user_name': row['name'],
                'user_email': row['email'],
                'type': checkup_type,
                'label': row[f'{checkup_type}_label'],
                'flag': row[f'{checkup_type}_flag'],
                'detail': row[f'{checkup_type}_detail'],
                'updated_at': updated_at,
            })
    entries.sort(key=lambda e: e['updated_at'], reverse=True)
    return entries


# -------------------------------------------------------------- reports --

def save_report(user_id, pdf_bytes):
    conn = get_db()
    try:
        conn.execute('''
            UPDATE patient_history
            SET report_pdf = ?, report_generated_at = datetime('now')
            WHERE user_id = ?
        ''', (pdf_bytes, user_id))
        conn.commit()
    finally:
        conn.close()
    _sync_to_sheets(user_id)


def get_report(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT report_pdf AS pdf_data, report_generated_at AS created_at '
            'FROM patient_history WHERE user_id = ?', (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None or row['pdf_data'] is None:
        return None
    return row


# ---------------------------------------------------------- sheets sync --
#
# The rule everywhere above is: commit to SQLite first, queue the Sheets
# push second. Every _sync_to_sheets(user_id) call above happens after
# conn.commit() / conn.close(), so the database is always the source of
# truth and Sheets is always catching up to it, never the other way round.
#
# The push itself only ever touches the one row that changed (via
# sheets_sync.upsert_row) instead of re-dumping the whole table, and it's
# debounced: if the same patient is written to a few times in quick
# succession (e.g. running several checkups back to back), those updates
# collapse into a single Sheets call a moment later instead of one call per
# write. Everything here runs on a background thread/timer, so none of it
# ever makes a request wait on Google.

_pending_lock = threading.Lock()
_pending_rows = {}          # user_id -> latest row dict, waiting to be pushed
_flush_timer = None
_SYNC_DEBOUNCE_SECONDS = 1.5


def _sync_to_sheets(user_id):
    """Reads this one patient's current row and queues it for a Sheets
    push shortly. Called after every write above."""
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT * FROM patient_history WHERE user_id = ?', (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return
    _queue_row_for_sync(dict(row))


def _queue_row_for_sync(row):
    global _flush_timer
    with _pending_lock:
        _pending_rows[row['user_id']] = row
        if _flush_timer is None:
            _flush_timer = threading.Timer(_SYNC_DEBOUNCE_SECONDS, _flush_pending_rows)
            _flush_timer.daemon = True
            _flush_timer.start()


def _flush_pending_rows():
    global _flush_timer
    with _pending_lock:
        rows = list(_pending_rows.values())
        _pending_rows.clear()
        _flush_timer = None
    for row in rows:
        try:
            sheets_sync.upsert_row(row)
        except Exception as exc:  # sheets_sync normally swallows its own errors,
            print(f"[sheets_sync] background sync failed for user {row.get('user_id')}: {exc}")  # final safety net


def full_resync_to_sheets():
    """One-off full dump of every patient row to Google Sheets. Meant to be
    called once at backend startup so the sheet self-heals from anything it
    might have missed (e.g. the app was offline, or Sheets was down for a
    while) — normal per-write updates use the cheaper upsert_row path above.
    Runs in the background so startup never waits on Google."""
    def _worker():
        conn = get_db()
        try:
            rows = conn.execute('SELECT * FROM patient_history ORDER BY user_id').fetchall()
        finally:
            conn.close()
        try:
            sheets_sync.sync_rows([dict(row) for row in rows])
        except Exception as exc:
            print(f"[sheets_sync] startup full resync failed: {exc}")

    threading.Thread(target=_worker, daemon=True).start()
