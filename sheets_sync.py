"""Pushes the patient_history table to a Google Sheet, live, on every change.

Uses a Google Cloud service account (config.GOOGLE_SERVICE_ACCOUNT_FILE) to
authenticate — no user's Google login is ever involved. If anything about
the sync fails (no internet, sheet not shared with the service account,
wrong URL, etc.) it's printed as a warning and the app keeps working
normally; a Sheets hiccup should never break checkups, login, or reports.

Two ways to push data:
  - upsert_row(row): updates (or appends) just ONE patient's row. This is
    what gets called after every login/checkup/report — cheap and fast,
    since it never has to read or rewrite the whole sheet.
  - sync_rows(rows): overwrites the whole sheet with a fresh dump. Used only
    for a one-off full reconciliation (e.g. once at backend startup), so the
    sheet self-heals from anything it might have missed while offline.
Both retry a couple of times on transient failures (rate limits, brief
network hiccups) before giving up quietly.
"""

import threading
import time

import config

# Column order shown in the sheet — mirrors patient_history, minus the
# password hash and raw PDF bytes (neither belongs in a spreadsheet).
_COLUMNS = [
    'user_id', 'name', 'age', 'email', 'role', 'is_approved',
    'login_count', 'signup_at', 'last_login_at', 'last_logout_at', 'last_ip_address',
    'heart_label', 'heart_flag', 'heart_detail', 'heart_updated_at',
    'diabetes_label', 'diabetes_flag', 'diabetes_detail', 'diabetes_updated_at',
    'sugar_label', 'sugar_flag', 'sugar_detail', 'sugar_updated_at',
    'bp_label', 'bp_flag', 'bp_detail', 'bp_updated_at',
    'report_generated_at',
]

_lock = threading.Lock()
_client = None
_worksheet = None


def _get_worksheet():
    """Lazily authenticates and opens the worksheet, and caches it for reuse."""
    global _client, _worksheet
    if _worksheet is not None:
        return _worksheet

    import gspread  # imported lazily so the app still runs if it's not installed

    if not config.GOOGLE_SERVICE_ACCOUNT_FILE.exists():
        raise FileNotFoundError(
            f'Service account key not found at {config.GOOGLE_SERVICE_ACCOUNT_FILE}'
        )

    _client = gspread.service_account(filename=str(config.GOOGLE_SERVICE_ACCOUNT_FILE))
    spreadsheet = _client.open_by_url(config.GOOGLE_SHEET_URL)
    try:
        _worksheet = spreadsheet.worksheet(config.GOOGLE_SHEET_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        _worksheet = spreadsheet.sheet1
    return _worksheet


def _call_with_retry(fn, *args, attempts=3, base_delay=0.75, **kwargs):
    """Runs fn(*args, **kwargs), retrying on failure with a short backoff.
    Google Sheets occasionally rate-limits or hiccups on a single call; most
    of the time a 2nd or 3rd try a moment later just works. Re-raises the
    last error if every attempt fails, so the caller can log/ignore it."""
    last_exc = None
    for attempt in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - retried broadly on purpose
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(base_delay * (2 ** attempt))
    raise last_exc


def _row_values(row):
    return ['' if row.get(col) is None else row.get(col) for col in _COLUMNS]


def _col_letter(n):
    """1 -> 'A', 27 -> 'AA', etc."""
    letters = ''
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def upsert_row(row):
    """Updates the sheet row for row['user_id'] in place, or appends a new
    row if that patient isn't in the sheet yet. Never touches any other
    row, so this stays fast no matter how many patients are in the table —
    unlike a full dump, its cost doesn't grow with the size of the app."""
    if not config.GOOGLE_SHEETS_ENABLED:
        return

    values = _row_values(row)
    user_id_str = str(row.get('user_id'))

    def _do_upsert():
        worksheet = _get_worksheet()
        existing_ids = worksheet.col_values(1)  # column A, top to bottom
        if not existing_ids:
            worksheet.append_row(_COLUMNS)
            existing_ids = [_COLUMNS[0]]
        data_ids = existing_ids[1:]  # row 1 is the header
        if user_id_str in data_ids:
            row_number = data_ids.index(user_id_str) + 2  # +1 header, +1 for 1-based rows
            end_col = _col_letter(len(_COLUMNS))
            worksheet.update(f'A{row_number}:{end_col}{row_number}', [values])
        else:
            worksheet.append_row(values)

    with _lock:
        try:
            _call_with_retry(_do_upsert)
        except Exception as exc:  # noqa: BLE001 - a sync failure must never crash the app
            print(f'[sheets_sync] Skipped Google Sheets upsert for user {user_id_str}: {exc}')


def sync_rows(rows):
    """rows: list of dicts (one per patient, straight from patient_history).
    Overwrites the whole sheet with a fresh header + data dump. This is
    comparatively slow (and gets slower as the patient list grows), so it's
    only used for an occasional full reconciliation, not on every write —
    upsert_row() handles normal per-patient updates."""
    if not config.GOOGLE_SHEETS_ENABLED:
        return

    def _do_sync():
        worksheet = _get_worksheet()
        values = [_COLUMNS] + [_row_values(row) for row in rows]
        worksheet.clear()
        worksheet.update(values, 'A1')

    with _lock:
        try:
            _call_with_retry(_do_sync)
        except Exception as exc:  # noqa: BLE001 - a sync failure must never crash the app
            print(f'[sheets_sync] Skipped Google Sheets full sync: {exc}')
