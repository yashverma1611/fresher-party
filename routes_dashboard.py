"""
Dashboard metrics, Audit trail, and Event Configuration routes.
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection
from common import broadcast_event, get_event_config
from qr_generator import generate_qr_base64

dashboard_bp = Blueprint("dashboard_bp", __name__)

@dashboard_bp.route("/api/stats", methods=["GET"])
def get_stats():
    conn = get_db_connection()

    total_invited = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_checked_in = conn.execute("SELECT COUNT(*) FROM students WHERE status = 'checked_in'").fetchone()[0]
    total_pending = total_invited - total_checked_in
    rate = round((total_checked_in / total_invited * 100), 1) if total_invited > 0 else 0

    # BCA 1st Sem
    bca1_invited = conn.execute("SELECT COUNT(*) FROM students WHERE semester LIKE '%1st%'").fetchone()[0]
    bca1_checked_in = conn.execute("SELECT COUNT(*) FROM students WHERE semester LIKE '%1st%' AND status = 'checked_in'").fetchone()[0]
    bca1_pending = bca1_invited - bca1_checked_in
    bca1_rate = round((bca1_checked_in / bca1_invited * 100), 1) if bca1_invited > 0 else 0

    # BCA 3rd Sem
    bca3_invited = conn.execute("SELECT COUNT(*) FROM students WHERE semester LIKE '%3rd%'").fetchone()[0]
    bca3_checked_in = conn.execute("SELECT COUNT(*) FROM students WHERE semester LIKE '%3rd%' AND status = 'checked_in'").fetchone()[0]
    bca3_pending = bca3_invited - bca3_checked_in
    bca3_rate = round((bca3_checked_in / bca3_invited * 100), 1) if bca3_invited > 0 else 0

    # Recent check-ins
    recent = conn.execute("""
    SELECT roll_no, name, semester, checked_in_at, scanned_by_admin_name, scan_method
    FROM students
    WHERE status = 'checked_in'
    ORDER BY checked_in_at DESC
    LIMIT 10
    """).fetchall()

    # Active approved scanners
    scanners_count = conn.execute("SELECT COUNT(*) FROM admins WHERE role = 'scanner' AND status = 'approved'").fetchone()[0]

    conn.close()

    return jsonify({
        "success": True,
        "stats": {
            "total_invited": total_invited,
            "total_checked_in": total_checked_in,
            "total_pending": total_pending,
            "turnout_rate": rate,
            "bca1": {
                "invited": bca1_invited,
                "checked_in": bca1_checked_in,
                "pending": bca1_pending,
                "rate": bca1_rate
            },
            "bca3": {
                "invited": bca3_invited,
                "checked_in": bca3_checked_in,
                "pending": bca3_pending,
                "rate": bca3_rate
            },
            "active_scanners": scanners_count,
            "recent_checkins": [dict(r) for r in recent]
        }
    })

@dashboard_bp.route("/api/audit-logs", methods=["GET"])
def get_audit_logs():
    search = request.args.get("search", "").strip().lower()
    conn = get_db_connection()
    if search:
        logs = conn.execute("""
        SELECT * FROM audit_logs
        WHERE LOWER(student_name) LIKE ? OR LOWER(roll_no) LIKE ? OR LOWER(admin_name) LIKE ? OR LOWER(action) LIKE ?
        ORDER BY id DESC LIMIT 100
        """, (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        logs = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    return jsonify({"success": True, "logs": [dict(l) for l in logs]})

@dashboard_bp.route("/api/pass-details/<token>", methods=["GET"])
def pass_details(token):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE pass_token = ?", (token,)).fetchone()
    conn.close()
    if not student:
        return jsonify({"success": False, "message": "Pass token not found"}), 404

    qr_b64 = generate_qr_base64(token)
    cfg = get_event_config()
    return jsonify({
        "success": True,
        "student": dict(student),
        "qr_b64": qr_b64,
        "config": cfg
    })

@dashboard_bp.route("/api/config", methods=["GET", "POST"])
def config_route():
    conn = get_db_connection()
    if request.method == "POST":
        data = request.json or {}
        event_name = data.get("event_name")
        event_date = data.get("event_date")
        venue = data.get("venue")
        creator_email = data.get("creator_email")
        smtp_server = data.get("smtp_server")
        smtp_port = int(data.get("smtp_port") or 587)
        smtp_user = data.get("smtp_user", "")
        smtp_password = data.get("smtp_password", "")

        conn.execute("""
        UPDATE event_config
        SET event_name = ?, event_date = ?, venue = ?, creator_email = ?,
            smtp_server = ?, smtp_port = ?, smtp_user = ?, smtp_password = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = (SELECT id FROM event_config ORDER BY id DESC LIMIT 1)
        """, (event_name, event_date, venue, creator_email, smtp_server, smtp_port, smtp_user, smtp_password))
        conn.commit()
        conn.close()
        broadcast_event("config_updated", {"event_name": event_name})
        return jsonify({"success": True, "message": "Event settings updated successfully"})
    else:
        cfg = conn.execute("SELECT * FROM event_config ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        return jsonify({"success": True, "config": dict(cfg) if cfg else {}})
