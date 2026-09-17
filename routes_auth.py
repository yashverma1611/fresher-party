"""
Authentication and Admin management routes.
"""

from flask import Blueprint, request, jsonify
import uuid
from database import get_db_connection
from common import broadcast_event

auth_bp = Blueprint("auth_bp", __name__)

@auth_bp.route("/api/auth/creator-login", methods=["POST"])
def creator_login():
    data = request.json or {}
    email = data.get("email", "").strip()
    pin = data.get("pin", "").strip()

    conn = get_db_connection()
    admin = conn.execute("SELECT * FROM admins WHERE email = ? AND role = 'creator'", (email,)).fetchone()

    if not admin or admin["otp"] != pin:
        conn.close()
        return jsonify({"success": False, "message": "Invalid Creator email or security PIN"}), 401

    session_token = f"TOKEN-CREATOR-{uuid.uuid4().hex}"
    conn.execute("UPDATE admins SET session_token = ?, last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (session_token, admin["id"]))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "session_token": session_token,
        "admin": {
            "id": admin["id"],
            "name": admin["name"],
            "email": admin["email"],
            "role": "creator"
        }
    })

@auth_bp.route("/api/auth/scanner-register", methods=["POST"])
def scanner_register():
    data = request.json or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()

    if not name or not email:
        return jsonify({"success": False, "message": "Name and Email are required"}), 400

    conn = get_db_connection()
    existing = conn.execute("SELECT * FROM admins WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "message": "Account with this email already exists"}), 400

    otp = str(uuid.uuid4().int)[:6]
    conn.execute("""
    INSERT INTO admins (name, email, phone, role, status, otp)
    VALUES (?, ?, ?, 'scanner', 'pending', ?)
    """, (name, email, phone, otp))
    conn.commit()
    conn.close()

    broadcast_event("admin_registered", {"name": name, "email": email})
    return jsonify({"success": True, "message": "Registration submitted! Awaiting Creator approval."})

@auth_bp.route("/api/auth/scanner-login", methods=["POST"])
def scanner_login():
    data = request.json or {}
    email = data.get("email", "").strip()
    otp = data.get("otp", "").strip()

    conn = get_db_connection()
    admin = conn.execute("SELECT * FROM admins WHERE email = ? AND role = 'scanner'", (email,)).fetchone()

    if not admin:
        conn.close()
        return jsonify({"success": False, "message": "Scanner account not found"}), 404

    if admin["status"] != "approved":
        conn.close()
        return jsonify({"success": False, "message": "Account not yet approved by Creator"}), 403

    if admin["otp"] != otp:
        conn.close()
        return jsonify({"success": False, "message": "Invalid 6-digit OTP passcode"}), 401

    session_token = f"TOKEN-SCANNER-{uuid.uuid4().hex}"
    conn.execute("UPDATE admins SET session_token = ?, last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (session_token, admin["id"]))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "session_token": session_token,
        "admin": {
            "id": admin["id"],
            "name": admin["name"],
            "email": admin["email"],
            "role": "scanner"
        }
    })

@auth_bp.route("/api/auth/admins", methods=["GET"])
def list_admins():
    conn = get_db_connection()
    rows = conn.execute("SELECT id, name, email, phone, role, status, otp, created_at, last_login_at FROM admins ORDER BY id ASC").fetchall()
    conn.close()
    return jsonify({"success": True, "admins": [dict(r) for r in rows]})

@auth_bp.route("/api/auth/approve-admin", methods=["POST"])
def approve_admin():
    admin_id = request.json.get("admin_id")
    new_otp = str(uuid.uuid4().int)[:6]
    conn = get_db_connection()
    conn.execute("UPDATE admins SET status = 'approved', otp = ? WHERE id = ?", (new_otp, admin_id))
    conn.commit()
    conn.close()

    broadcast_event("admin_approved", {"admin_id": admin_id, "otp": new_otp})
    return jsonify({"success": True, "otp": new_otp, "message": "Admin approved and OTP generated"})

@auth_bp.route("/api/auth/reject-admin", methods=["POST"])
def reject_admin():
    admin_id = request.json.get("admin_id")
    conn = get_db_connection()
    conn.execute("UPDATE admins SET status = 'rejected', session_token = NULL WHERE id = ?", (admin_id,))
    conn.commit()
    conn.close()

    broadcast_event("admin_rejected", {"admin_id": admin_id})
    return jsonify({"success": True, "message": "Admin status updated to rejected"})

@auth_bp.route("/api/auth/regenerate-otp", methods=["POST"])
def regenerate_otp():
    admin_id = request.json.get("admin_id")
    new_otp = str(uuid.uuid4().int)[:6]
    conn = get_db_connection()
    conn.execute("UPDATE admins SET otp = ? WHERE id = ?", (new_otp, admin_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "otp": new_otp, "message": "New OTP generated"})
