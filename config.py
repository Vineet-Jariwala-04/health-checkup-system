"""App-wide configuration."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- Google Sheets live sync -------------------------------------------
# Every time a patient row is created or updated, the whole patient_history
# table is pushed to this sheet so it always mirrors the database instantly.
GOOGLE_SHEETS_ENABLED = True
GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / 'config' / 'google_service_account.json'
GOOGLE_SHEET_URL = (
    'https://docs.google.com/spreadsheets/d/18_2a0fz9vgLACve4vYRcE5mnMbmnbYlbED_WWnuplKw/edit'
)
GOOGLE_SHEET_WORKSHEET_NAME = 'Sheet1'
