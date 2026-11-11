"""Run this any time you want a completely fresh start on the Patient
History table: it DROPS patient_history and recreates it with the same
name and columns (via database.init_db()), which also resets SQLite's
AUTOINCREMENT counter — so the next signup gets user_id = 1 again instead
of continuing from wherever the old table left off. The now-empty table is
also pushed to Google Sheets.

Usage:
    python3 reset_database.py
"""

import database as db

if __name__ == '__main__':
    db.init_db()
    before = len(db.get_all_users())
    db.clear_all_patients()
    print(f'Dropped and recreated patient_history (had {before} row(s)). '
          f'Next signup will start at user_id = 1.')
