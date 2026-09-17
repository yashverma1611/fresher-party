"""
Database module for Event QR Pass & Scanner Management System.
Uses SQLite with WAL mode for concurrency across multiple scanners.
"""

import sqlite3
import os
import uuid
import datetime

DB_PATH = os.environ.get(
    "EVENT_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "event_data.db")
)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=25.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 25000")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Event config
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT NOT NULL,
        event_date TEXT NOT NULL,
        venue TEXT NOT NULL,
        creator_email TEXT NOT NULL,
        smtp_server TEXT DEFAULT 'smtp.gmail.com',
        smtp_port INTEGER DEFAULT 587,
        smtp_user TEXT DEFAULT '',
        smtp_password TEXT DEFAULT '',
        email_subject TEXT DEFAULT 'Official Invitation & Entry Pass - BCA Freshers Party 2026',
        email_template TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Admins
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        role TEXT NOT NULL DEFAULT 'scanner',
        status TEXT NOT NULL DEFAULT 'pending',
        otp TEXT,
        otp_expires_at DATETIME,
        session_token TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_login_at DATETIME
    )
    """)

    # 3. Students
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        semester TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        pass_token TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        checked_in_at DATETIME,
        scanned_by_admin_id INTEGER,
        scanned_by_admin_name TEXT,
        scan_method TEXT,
        invitation_sent_at DATETIME,
        invitation_channel TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (scanned_by_admin_id) REFERENCES admins (id)
    )
    """)

    # 4. Audit logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        student_id INTEGER,
        student_name TEXT NOT NULL,
        roll_no TEXT NOT NULL,
        semester TEXT NOT NULL,
        admin_id INTEGER,
        admin_name TEXT NOT NULL,
        method TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        device_info TEXT,
        FOREIGN KEY (student_id) REFERENCES students (id),
        FOREIGN KEY (admin_id) REFERENCES admins (id)
    )
    """)

    # 5. Notifications log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        channel TEXT NOT NULL,
        recipient TEXT NOT NULL,
        subject TEXT,
        content_preview TEXT,
        status TEXT NOT NULL,
        error_message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

    # Seed config
    cursor.execute("SELECT COUNT(*) FROM event_config")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO event_config (event_name, event_date, venue, creator_email, email_template)
        VALUES (?, ?, ?, ?, ?)
        """, (
            "BCA Freshers Party 2026",
            "Saturday, October 10, 2026 | 11:00 AM onwards",
            "Auditorium & Grand Lawn, Main Campus",
            "frsher.party.2k.26@gmail.com",
            """Dear {name},

You are warmly invited to the BCA Freshers Party 2026!
Join us for an extraordinary day of music, games, lunch, and celebration.

EVENT DETAILS:
- Event: BCA Freshers Party 2026
- Date & Time: {date}
- Venue: {venue}
- Guest: {name} (Roll No: {roll_no})
- Batch: {semester} Semester

ENTRY GUIDELINES:
1. Show your unique QR entry pass at Gate 1 or Gate 2.
2. Each pass is unique and can be checked in only once.
3. Keep this pass accessible on your mobile phone or printed copy.

Organizing Committee: BCA Freshers 2026
Contact: frsher.party.2k.26@gmail.com"""
        ))
        conn.commit()

    # Seed creator and sample scanner admins
    cursor.execute("SELECT COUNT(*) FROM admins WHERE email = ?", ("frsher.party.2k.26@gmail.com",))
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO admins (name, email, phone, role, status, otp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "Event Creator",
            "frsher.party.2k.26@gmail.com",
            "+91 9876543210",
            "creator",
            "approved",
            "202600"
        ))

        cursor.execute("""
        INSERT INTO admins (name, email, phone, role, status, otp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("Gate 1 - Rahul Sharma", "rahul.gate1@college.edu", "+91 9811122233", "scanner", "approved", "112233"))

        cursor.execute("""
        INSERT INTO admins (name, email, phone, role, status, otp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("Gate 2 - Priya Patel", "priya.gate2@college.edu", "+91 9822233344", "scanner", "approved", "223344"))

        cursor.execute("""
        INSERT INTO admins (name, email, phone, role, status, otp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("Gate 3 - Amit Verma", "amit.gate3@college.edu", "+91 9833344455", "scanner", "pending", "334455"))

        conn.commit()

    # Students table starts empty — use the Excel template + Upload Excel
    # feature (or the Add Student form) to bring in your real guest list.

    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
