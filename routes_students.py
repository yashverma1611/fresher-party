"""
Student management, Excel import/export, and Invitation dispatch routes.
"""

from flask import Blueprint, request, jsonify, send_file
from io import BytesIO
import uuid
import datetime
from database import get_db_connection
from common import broadcast_event, get_event_config
from excel_manager import parse_uploaded_excel, create_sample_template, export_attendance_excel
from mailer import send_invitation_email, generate_whatsapp_invitation

students_bp = Blueprint("students_bp", __name__)

@students_bp.route("/api/students", methods=["GET"])
def get_students():
    semester = request.args.get("semester", "all")
    status = request.args.get("status", "all")
    search = request.args.get("search", "").strip().lower()

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if semester != "all":
        query += " AND semester LIKE ?"
        params.append(f"%{semester}%")

    if status != "all":
        query += " AND status = ?"
        params.append(status)

    if search:
        query += " AND (LOWER(roll_no) LIKE ? OR LOWER(name) LIKE ? OR LOWER(phone) LIKE ? OR LOWER(email) LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    query += " ORDER BY semester ASC, roll_no ASC"

    conn = get_db_connection()
    students = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify({"success": True, "students": [dict(s) for s in students]})

@students_bp.route("/api/students", methods=["POST"])
def add_student():
    data = request.json or {}
    roll_no = data.get("roll_no", "").strip().upper()
    name = data.get("name", "").strip()
    semester = data.get("semester", "BCA 1st").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()

    if not roll_no or not name:
        return jsonify({"success": False, "message": "Roll No and Name are required"}), 400

    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM students WHERE roll_no = ?", (roll_no,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "message": f"Student with Roll No {roll_no} already exists"}), 400

    sem_tag = "1ST" if "1st" in semester else "3RD"
    token = f"PASS-BCA{sem_tag}-{uuid.uuid4().hex[:12].upper()}"

    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO students (roll_no, name, semester, email, phone, pass_token, status)
    VALUES (?, ?, ?, ?, ?, ?, 'pending')
    """, (roll_no, name, semester, email, phone, token))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    broadcast_event("student_added", {"id": new_id, "roll_no": roll_no, "name": name, "semester": semester})
    return jsonify({"success": True, "id": new_id, "pass_token": token, "message": "Student added successfully"})

@students_bp.route("/api/students/<int:student_id>", methods=["PUT"])
def update_student(student_id):
    data = request.json or {}
    name = data.get("name", "").strip()
    semester = data.get("semester", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()

    conn = get_db_connection()
    conn.execute("""
    UPDATE students
    SET name = ?, semester = ?, email = ?, phone = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (name, semester, email, phone, student_id))
    conn.commit()
    conn.close()

    broadcast_event("student_updated", {"id": student_id, "name": name, "semester": semester})
    return jsonify({"success": True, "message": "Student details updated"})

@students_bp.route("/api/students/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()

    broadcast_event("student_deleted", {"id": student_id})
    return jsonify({"success": True, "message": "Student deleted"})

@students_bp.route("/api/upload-excel", methods=["POST"])
def upload_excel():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename.endswith((".xlsx", ".xls")):
        return jsonify({"success": False, "message": "Please upload a valid .xlsx file"}), 400

    try:
        file_bytes = file.read()
        extracted = parse_uploaded_excel(file_bytes)
        if not extracted:
            return jsonify({"success": False, "message": "No valid student records found in file"}), 400

        conn = get_db_connection()
        added_count = 0
        updated_count = 0

        for item in extracted:
            existing = conn.execute("SELECT id FROM students WHERE roll_no = ?", (item["roll_no"],)).fetchone()
            if existing:
                conn.execute("""
                UPDATE students
                SET name = ?, semester = ?, email = ?, phone = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (item["name"], item["semester"], item["email"], item["phone"], existing["id"]))
                updated_count += 1
            else:
                sem_tag = "1ST" if "1st" in item["semester"] else "3RD"
                token = f"PASS-BCA{sem_tag}-{uuid.uuid4().hex[:12].upper()}"
                conn.execute("""
                INSERT INTO students (roll_no, name, semester, email, phone, pass_token, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """, (item["roll_no"], item["name"], item["semester"], item["email"], item["phone"], token))
                added_count += 1

        conn.commit()
        conn.close()

        broadcast_event("sheet_imported", {"added": added_count, "updated": updated_count})
        return jsonify({
            "success": True,
            "added": added_count,
            "updated": updated_count,
            "total_parsed": len(extracted),
            "message": f"Successfully processed Excel sheet! Added: {added_count}, Updated: {updated_count}"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error parsing Excel file: {str(e)}"}), 500

@students_bp.route("/api/download-template", methods=["GET"])
def download_template():
    buf = create_sample_template()
    return send_file(
        BytesIO(buf),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="BCA_Event_Pass_Template.xlsx"
    )

@students_bp.route("/api/export-attendance", methods=["GET"])
def export_attendance():
    conn = get_db_connection()
    buf = export_attendance_excel(conn)
    conn.close()
    filename = f"BCA_Freshers_Attendance_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
    return send_file(
        BytesIO(buf),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@students_bp.route("/api/send-email/<int:student_id>", methods=["POST"])
def send_email_invitation(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found"}), 404

    cfg = get_event_config()
    base_url = request.host_url.rstrip("/")
    result = send_invitation_email(dict(student), cfg, base_url)

    conn.execute("""
    INSERT INTO notifications_log (student_id, channel, recipient, subject, content_preview, status)
    VALUES (?, 'email', ?, ?, ?, ?)
    """, (
        student_id,
        student["email"],
        f"Invitation - {cfg['event_name']}",
        result.get("preview_html", result.get("message")),
        result["status"]
    ))
    conn.execute("UPDATE students SET invitation_sent_at = CURRENT_TIMESTAMP, invitation_channel = 'email' WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()

    broadcast_event("invitation_sent", {"student_id": student_id, "channel": "email", "status": result["status"]})
    return jsonify(result)

@students_bp.route("/api/whatsapp-url/<int:student_id>", methods=["GET"])
def get_whatsapp_url(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found"}), 404

    cfg = get_event_config()
    base_url = request.host_url.rstrip("/")
    wa_data = generate_whatsapp_invitation(dict(student), cfg, base_url)

    conn.execute("""
    INSERT INTO notifications_log (student_id, channel, recipient, subject, content_preview, status)
    VALUES (?, 'whatsapp', ?, 'WhatsApp Invitation', ?, 'link_generated')
    """, (student_id, wa_data["phone"], wa_data["text"]))
    conn.commit()
    conn.close()

    return jsonify({"success": True, **wa_data})

@students_bp.route("/api/resend-pass/<int:student_id>", methods=["POST"])
def resend_pass(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found"}), 404

    cfg = get_event_config()
    base_url = request.host_url.rstrip("/")

    email_res = send_invitation_email(dict(student), cfg, base_url)
    wa_data = generate_whatsapp_invitation(dict(student), cfg, base_url)

    conn.execute("""
    INSERT INTO audit_logs (student_id, student_name, roll_no, semester, admin_id, admin_name, method, action, details)
    VALUES (?, ?, ?, ?, 1, 'System / Creator', 'RESEND_DISPATCH', 'PASS_RESENT', 'Resent pass via Email & WhatsApp link')
    """, (student["id"], student["name"], student["roll_no"], student["semester"]))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Pass resent to {student['name']} ({student['email']})",
        "email_status": email_res["status"],
        "whatsapp_url": wa_data["wa_url"]
    })

@students_bp.route("/api/send-bulk-email", methods=["POST"])
def send_bulk_email():
    data = request.json or {}
    semester = data.get("semester", "all")

    conn = get_db_connection()
    query = "SELECT * FROM students WHERE 1=1"
    params = []
    if semester != "all":
        query += " AND semester LIKE ?"
        params.append(f"%{semester}%")

    students = conn.execute(query, params).fetchall()
    cfg = get_event_config()
    base_url = request.host_url.rstrip("/")

    sent_count = 0
    simulated_count = 0
    failed_count = 0

    for s in students:
        res = send_invitation_email(dict(s), cfg, base_url)
        status = res["status"]
        if status == "sent":
            sent_count += 1
        elif status == "simulated":
            simulated_count += 1
        else:
            failed_count += 1

        conn.execute("""
        INSERT INTO notifications_log (student_id, channel, recipient, subject, content_preview, status)
        VALUES (?, 'email', ?, ?, ?, ?)
        """, (s["id"], s["email"], f"Invitation - {cfg['event_name']}", res.get("preview_html", "Sent"), status))

        conn.execute("UPDATE students SET invitation_sent_at = CURRENT_TIMESTAMP, invitation_channel = 'email' WHERE id = ?", (s["id"],))

    conn.commit()
    conn.close()

    broadcast_event("bulk_email_sent", {"sent": sent_count, "simulated": simulated_count, "failed": failed_count})
    return jsonify({
        "success": True,
        "sent": sent_count,
        "simulated": simulated_count,
        "failed": failed_count,
        "total": len(students),
        "message": f"Processed {len(students)} invitation emails (Live: {sent_count}, Simulated/Outbox: {simulated_count})"
    })

@students_bp.route("/api/notifications", methods=["GET"])
def get_notifications():
    conn = get_db_connection()
    logs = conn.execute("""
    SELECT n.*, s.name as student_name, s.roll_no, s.semester
    FROM notifications_log n
    LEFT JOIN students s ON n.student_id = s.id
    ORDER BY n.id DESC LIMIT 50
    """).fetchall()
    conn.close()
    return jsonify({"success": True, "notifications": [dict(l) for l in logs]})
