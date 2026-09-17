"""
Main Application Entrypoint for Event QR Pass & Scanner System.
BCA 1st & 3rd Sem | Real-Time Sync | Admin OTP | Creator: frsher.party.2k.26@gmail.com
"""

from flask import Flask, render_template, Response
from flask_cors import CORS
import json
import queue
from database import init_db, get_db_connection
from qr_generator import generate_qr_base64
from common import subscribers, get_event_config

from routes_auth import auth_bp
from routes_students import students_bp
from routes_scanner import scanner_bp
from routes_dashboard import dashboard_bp

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Must run at import time (not just under __main__) so production servers
# like gunicorn — which import this module rather than executing it
# directly — still create the database tables before the first request.
init_db()

app.register_blueprint(auth_bp)
app.register_blueprint(students_bp)
app.register_blueprint(scanner_bp)
app.register_blueprint(dashboard_bp)

@app.route("/api/events")
def events_stream():
    """Server-Sent Events stream: real-time updates for all connected devices."""
    def event_generator():
        q = queue.Queue(maxsize=100)
        subscribers.append(q)
        yield f"data: {json.dumps({'event': 'connected', 'message': 'Cloud Sync Active'})}\n\n"
        try:
            while True:
                try:
                    data = q.get(timeout=20.0)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield f": heartbeat\n\n"
        except GeneratorExit:
            if q in subscribers:
                subscribers.remove(q)

    return Response(event_generator(), mimetype="text/event-stream")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/pass/<token>")
def public_pass(token):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE pass_token = ?", (token,)).fetchone()
    conn.close()
    if not student:
        return "<h3>Invalid or Expired Entry Pass Token</h3>", 404

    cfg = get_event_config()
    qr_b64 = generate_qr_base64(token)
    return render_template("pass_view.html", student=dict(student), config=cfg, qr_b64=qr_b64)

if __name__ == "__main__":
    print("=" * 60)
    print("  BCA Freshers Party 2026 - QR Pass & Scanner System Active ")
    print("  Creator: frsher.party.2k.26@gmail.com                     ")
    print("  Real-time Cloud Sync: Active (SSE)                       ")
    print("  Running on: http://127.0.0.1:5000                        ")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
