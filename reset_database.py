"""Run this any time you want a completely fresh start.

It DROPS all four tables - patient_history, checkup_history, email_otps and
app_meta - and recreates them with the same names and columns (via
database.init_db()). Dropping (instead of DELETE) also resets SQLite's
AUTOINCREMENT counters, so the next signup gets user_id = 1 and the next
checkup record starts at id = 1 again. The now-empty patient table is also
pushed to Google Sheets.

Usage:
    python3 reset_database.py
"""

import database as db

TABLES = ('patient_history', 'checkup_history', 'email_otps', 'app_meta')

if __name__ == '__main__':
    db.init_db()
    conn = db.get_db()
    try:
        before = {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in TABLES}
        for t in TABLES:
            conn.execute(f'DROP TABLE IF EXISTS {t}')
        # clear any leftover auto-increment counters for these tables
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN (%s)" % ','.join('?' * len(TABLES)), TABLES)
        conn.commit()
    finally:
        conn.close()

    db.init_db()               # recreates all four tables, empty
    db.full_resync_to_sheets()  # keep the Google Sheet in step (skipped quietly if offline)

    print('Database reset. Removed:')
    for t in TABLES:
        print(f'  {t}: {before[t]} row(s)')
    print('Next signup will start at user_id = 1.')
