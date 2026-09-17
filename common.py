"""
Common utilities, event broadcasting (SSE), and authorization helpers.
"""

import json
import queue
import datetime
from database import get_db_connection

subscribers = []

def broadcast_event(event_type: str, data: dict):
    """Broadcast an event to all connected SSE clients (scanners, dashboards)."""
    payload = json.dumps({"event": event_type, "data": data, "timestamp": datetime.datetime.now().isoformat()})
    dead_subs = []
    for q in subscribers:
        try:
            q.put_nowait(payload)
        except Exception:
            dead_subs.append(q)
    for q in dead_subs:
        if q in subscribers:
            subscribers.remove(q)

def get_event_config():
    conn = get_db_connection()
    cfg = conn.execute("SELECT * FROM event_config ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if cfg:
        return dict(cfg)
    return {
        "event_name": "BCA Freshers Party 2026",
        "event_date": "Saturday, October 10, 2026 | 11:00 AM onwards",
        "venue": "Auditorium & Grand Lawn, Main Campus",
        "creator_email": "frsher.party.2k.26@gmail.com",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": ""
    }

def verify_admin_session(request_obj):
    """Verifies that the request comes from an approved admin (Creator or Scanner)."""
    token = request_obj.headers.get("Authorization", "")
    if token.startswith("Bearer "):
        token = token[7:].strip()
    if not token:
        token = request_obj.args.get("session_token") or request_obj.form.get("session_token")

    if not token:
        return None

    conn = get_db_connection()
    admin = conn.execute("SELECT * FROM admins WHERE session_token = ? AND status = 'approved'", (token,)).fetchone()
    conn.close()
    return dict(admin) if admin else None
