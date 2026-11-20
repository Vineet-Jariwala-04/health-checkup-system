"""Emergency unlock, run on the computer that hosts the database.

Normally an approved admin unlocks accounts from the Admin page
("Locked accounts" tab). Use this only if NO admin can log in (for example
the only admin locked themselves out).

Usage:
    python unlock_account.py admin@example.com
"""
import sys

import database as db


def main(email):
    user = db.get_user_by_email(email.strip().lower())
    if user is None:
        return f"No account found for {email}."
    if not user["is_locked"]:
        return f"{user['email']} is not locked."
    db.unlock_user(user["user_id"])
    return f"Unlocked {user['email']}. They can log in again."


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python unlock_account.py <email>")
    print(main(sys.argv[1]))
