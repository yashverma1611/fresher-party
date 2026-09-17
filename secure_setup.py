"""
Freshers Party Check-in System — One-Time Security Setup
============================================================
Run this ONCE on your live server after deploying, to:
  1. Remove the demo/test gate-scanner admin accounts entirely.
  2. Clear every existing session token (forces everyone, including you,
     to log in fresh — kills any leftover/leaked demo sessions).
  3. Set the real creator account details and generate a brand-new,
     random security PIN (replacing the old demo PIN 202600).

Usage:
    python3 secure_setup.py

Safe to re-run: if the demo admins are already gone, it just skips them.
Each run generates a NEW random creator PIN and prints it once — copy it
down immediately, it is not shown again.
"""

import random
from database import get_db_connection, init_db

CREATOR_EMAIL = "frsher.party.2k.26@gmail.com"
CREATOR_NAME = "Creator"
CREATOR_PHONE = "8858655356"

DEMO_ADMIN_EMAILS = [
    "rahul.gate1@college.edu",
    "priya.gate2@college.edu",
    "amit.gate3@college.edu",
]


def main():
    init_db()
    conn = get_db_connection()

    # 1. Remove demo gate-scanner accounts entirely
    removed = 0
    for email in DEMO_ADMIN_EMAILS:
        cur = conn.execute("DELETE FROM admins WHERE email = ?", (email,))
        removed += cur.rowcount
    print(f"Removed {removed} demo scanner account(s).")

    # 2. Clear every remaining session token — forces a fresh login for
    # anyone still holding an old token in their browser.
    conn.execute("UPDATE admins SET session_token = NULL")
    print("Cleared all active session tokens.")

    # 3. Set the real creator account with a fresh random PIN
    new_pin = f"{random.randint(0, 999999):06d}"
    existing = conn.execute(
        "SELECT id FROM admins WHERE email = ? AND role = 'creator'", (CREATOR_EMAIL,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE admins
            SET name = ?, phone = ?, otp = ?, status = 'approved', session_token = NULL
            WHERE id = ?
        """, (CREATOR_NAME, CREATOR_PHONE, new_pin, existing["id"]))
    else:
        conn.execute("""
            INSERT INTO admins (name, email, phone, role, status, otp)
            VALUES (?, ?, ?, 'creator', 'approved', ?)
        """, (CREATOR_NAME, CREATOR_EMAIL, CREATOR_PHONE, new_pin))

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print("  Creator account is ready:")
    print(f"  Email: {CREATOR_EMAIL}")
    print(f"  Name:  {CREATOR_NAME}")
    print(f"  Phone: {CREATOR_PHONE}")
    print(f"  PIN:   {new_pin}   <-- copy this now, it won't be shown again")
    print("=" * 50)


if __name__ == "__main__":
    main()
