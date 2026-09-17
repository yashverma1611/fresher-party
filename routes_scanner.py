"""
Scanner check-in, duplicate detection, and offline synchronization routes.
"""

from flask import Blueprint, request, jsonify
import datetime
from database import get_db_connection
from common import broadcast_event, verify_admin_session

scanner_bp = Blueprint("scanner_bp", __name__)

@scanner_bp.route("/api/scan-checkin", methods=["POST"])
def scan_checkin():
    """
    Central Check-In Endpoint.
    Only approved admins can check in passes.
    Validates token, flags duplicate scans immediately with prior check-in info,
    and broadcasts real-time update to all active scanners and live dashboard.
    """
    admin = verify_admin_session(request)
    if not admin:
        return jsonify({
            "success": False,
            "code": "UNAUTHORIZED",
            "message": "Access Denied: Only Creator-Approved Admins with verified OTP can scan passes."
        }), 401

    data = request.json or {}
    pass_token = data.get("pass_token", "").strip()
    student_id = data.get("student_id")
    method = data.get("method", "QR_CAMERA") # 'QR_CAMERA' or 'MANUAL_SEARCH'
    device_info = request.headers.get("User-Agent", "Scanner Device")[:100]

    conn = get_db_connection()
    if pass_token:
        student = conn.execute("SELECT * FROM students WHERE pass_token = ?", (pass_token,)).fetchone()
    elif student_id:
        student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    else:
        conn.close()
        return jsonify({"success": False, "code": "BAD_REQUEST", "message": "Provide either pass_token or student_id"}), 400

    if not student:
        conn.close()
        return jsonify({
            "success": False,
            "code": "INVALID_PASS",
            "message": "INVALID PASS: Token does not match any registered guest in the database."
        }), 404

    # Duplicate check
    if student["status"] == "checked_in":
        conn.execute("""
        INSERT INTO audit_logs (student_id, student_name, roll_no, semester, admin_id, admin_name, method, action, details, device_info)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'DUPLICATE_ATTEMPT', ?, ?)
        """, (
            student["id"], student["name"], student["roll_no"], student["semester"],
            admin["id"], admin["name"], method,
            f"Duplicate entry rejected. Previously checked in at {student['checked_in_at']} by {student['scanned_by_admin_name']}",
            device_info
        ))
        conn.commit()
        conn.close()

        broadcast_event("duplicate_alert", {
            "student_name": student["name"],
            "roll_no": student["roll_no"],
            "semester": student["semester"],
            "scanned_by": admin["name"],
            "original_checkin": student["checked_in_at"]
        })

        return jsonify({
            "success": False,
            "code": "ALREADY_CHECKED_IN",
            "message": f"ALREADY CHECKED IN at {student['checked_in_at']} by {student['scanned_by_admin_name']}!",
            "student": dict(student),
            "checked_in_at": student["checked_in_at"],
            "scanned_by_admin_name": student["scanned_by_admin_name"]
        }), 409

    # Valid entry
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
    UPDATE students
    SET status = 'checked_in',
        checked_in_at = ?,
        scanned_by_admin_id = ?,
        scanned_by_admin_name = ?,
        scan_method = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (now_str, admin["id"], admin["name"], method, student["id"]))

    conn.execute("""
    INSERT INTO audit_logs (student_id, student_name, roll_no, semester, admin_id, admin_name, method, action, details, device_info)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'CHECKED_IN', ?, ?)
    """, (
        student["id"], student["name"], student["roll_no"], student["semester"],
        admin["id"], admin["name"], method,
        f"Verified successfully via {method}",
        device_info
    ))
    conn.commit()

    updated = conn.execute("SELECT * FROM students WHERE id = ?", (student["id"],)).fetchone()
    conn.close()

    broadcast_event("checkin_event", {
        "student": dict(updated),
        "admin_name": admin["name"],
        "checked_in_at": now_str,
        "method": method
    })

    return jsonify({
        "success": True,
        "code": "VERIFIED",
        "message": f"ENTRY APPROVED! Welcome, {student['name']}",
        "student": dict(updated)
    })

@scanner_bp.route("/api/offline-roster", methods=["GET"])
def get_offline_roster():
    """Download student roster for offline caching and verification."""
    conn = get_db_connection()
    students = conn.execute("SELECT id, roll_no, name, semester, pass_token, status, checked_in_at, scanned_by_admin_name FROM students").fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "timestamp": datetime.datetime.now().isoformat(),
        "roster": [dict(s) for s in students]
    })

@scanner_bp.route("/api/sync-offline-scans", methods=["POST"])
def sync_offline_scans():
    """Bulk reconcile scans stored offline when network reconnects."""
    admin = verify_admin_session(request)
    if not admin:
        return jsonify({"success": False, "message": "Admin authorization required"}), 401

    data = request.json or {}
    scans = data.get("scans", [])

    conn = get_db_connection()
    synced = 0
    duplicates = 0

    for item in scans:
        token = item.get("pass_token")
        scan_time = item.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        student = conn.execute("SELECT * FROM students WHERE pass_token = ?", (token,)).fetchone()
        if not student:
            continue

        if student["status"] == "checked_in":
            duplicates += 1
            conn.execute("""
            INSERT INTO audit_logs (student_id, student_name, roll_no, semester, admin_id, admin_name, method, action, details)
            VALUES (?, ?, ?, ?, ?, ?, 'OFFLINE_SYNC', 'DUPLICATE_ATTEMPT', ?)
            """, (
                student["id"], student["name"], student["roll_no"], student["semester"],
                admin["id"], admin["name"], f"Offline duplicate scan rejected. Prior check-in: {student['checked_in_at']}"
            ))
        else:
            conn.execute("""
            UPDATE students
            SET status = 'checked_in',
                checked_in_at = ?,
                scanned_by_admin_id = ?,
                scanned_by_admin_name = ?,
                scan_method = 'OFFLINE_SYNC',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (scan_time, admin["id"], admin["name"], student["id"]))

            conn.execute("""
            INSERT INTO audit_logs (student_id, student_name, roll_no, semester, admin_id, admin_name, method, action, details)
            VALUES (?, ?, ?, ?, ?, ?, 'OFFLINE_SYNC', 'CHECKED_IN', ?)
            """, (
                student["id"], student["name"], student["roll_no"], student["semester"],
                admin["id"], admin["name"], f"Offline scan queued at {scan_time} reconciled"
            ))
            synced += 1

    conn.commit()
    conn.close()

    broadcast_event("offline_synced", {"synced": synced, "duplicates": duplicates, "admin": admin["name"]})
    return jsonify({
        "success": True,
        "synced": synced,
        "duplicates": duplicates,
        "message": f"Sync complete: {synced} entries confirmed, {duplicates} duplicates flagged."
    })
