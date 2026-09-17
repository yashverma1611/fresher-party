import sys
import unittest
import json
import os
import tempfile

# Point the app at a throwaway test database BEFORE importing it, so tests
# never touch your real event_data.db.
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)
os.environ["EVENT_DB_PATH"] = _test_db_path

from app import app
from database import get_db_connection, init_db
from qr_generator import generate_qr_base64
from excel_manager import create_sample_template, export_attendance_excel

class EventSystemTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        init_db()

        # Seed a couple of throwaway students for this test run only —
        # lives in the temp DB, never in your real event_data.db.
        conn = get_db_connection()
        existing = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        if existing == 0:
            for i in range(5):
                conn.execute("""
                INSERT INTO students (roll_no, name, semester, email, phone, pass_token, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """, (f"TEST1ST{i}", f"Test Student 1st {i}", "BCA 1st",
                      f"test1st{i}@example.com", "+91 9000000000",
                      f"PASS-TEST1ST-{i:04d}"))
            for i in range(5):
                conn.execute("""
                INSERT INTO students (roll_no, name, semester, email, phone, pass_token, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """, (f"TEST3RD{i}", f"Test Student 3rd {i}", "BCA 3rd",
                      f"test3rd{i}@example.com", "+91 9000000000",
                      f"PASS-TEST3RD-{i:04d}"))
            conn.execute("UPDATE admins SET session_token = 'TOKEN-SCANNER-DEMO-GATE1' WHERE email = 'rahul.gate1@college.edu'")
            conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        try:
            os.remove(_test_db_path)
        except OSError:
            pass

    def test_01_database_and_students(self):
        conn = get_db_connection()
        c1 = conn.execute("SELECT COUNT(*) FROM students WHERE semester LIKE '%1st%'").fetchone()[0]
        c3 = conn.execute("SELECT COUNT(*) FROM students WHERE semester LIKE '%3rd%'").fetchone()[0]
        conn.close()
        self.assertGreaterEqual(c1, 5, "BCA 1st Sem students must be present")
        self.assertGreaterEqual(c3, 5, "BCA 3rd Sem students must be present")
        print(f"[TEST 1 PASS] Students seeded: BCA 1st = {c1}, BCA 3rd = {c3}")

    def test_02_qr_generation(self):
        b64 = generate_qr_base64("TEST-TOKEN-12345")
        self.assertTrue(b64.startswith("data:image/png;base64,"))
        self.assertGreater(len(b64), 500)
        print("[TEST 2 PASS] QR code successfully generated as Base64 Data URL")

    def test_03_excel_template_and_export(self):
        template_bytes = create_sample_template()
        self.assertGreater(len(template_bytes), 1000)
        conn = get_db_connection()
        export_bytes = export_attendance_excel(conn)
        conn.close()
        self.assertGreater(len(export_bytes), 1000)
        print(f"[TEST 3 PASS] Multi-sheet Excel template ({len(template_bytes)} bytes) and export ({len(export_bytes)} bytes) OK")

    def test_04_scanner_checkin_and_duplicate_prevention(self):
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE status = 'pending' LIMIT 1").fetchone()
        conn.close()
        self.assertIsNotNone(student, "Need a pending student for test")

        token = student["pass_token"]
        headers = {"Authorization": "Bearer TOKEN-SCANNER-DEMO-GATE1"}

        # First scan -> Must be VERIFIED
        res1 = self.client.post("/api/scan-checkin", headers=headers, json={"pass_token": token, "method": "QR_CAMERA"})
        self.assertEqual(res1.status_code, 200)
        d1 = res1.get_json()
        self.assertTrue(d1["success"])
        self.assertEqual(d1["code"], "VERIFIED")

        # Second scan -> Must be ALREADY_CHECKED_IN (HTTP 409)
        res2 = self.client.post("/api/scan-checkin", headers=headers, json={"pass_token": token, "method": "QR_CAMERA"})
        self.assertEqual(res2.status_code, 409)
        d2 = res2.get_json()
        self.assertFalse(d2["success"])
        self.assertEqual(d2["code"], "ALREADY_CHECKED_IN")
        self.assertIn("ALREADY CHECKED IN", d2["message"])
        print(f"[TEST 4 PASS] Check-in verified on first scan, duplicate scan correctly rejected with 409!")

    def test_05_unauthorized_outsider_blocked(self):
        # No session token -> Must be 401
        res = self.client.post("/api/scan-checkin", json={"pass_token": "FAKE-TOKEN"})
        self.assertEqual(res.status_code, 401)
        print("[TEST 5 PASS] Unauthorized outsider access blocked (401)")

    def test_06_dashboard_stats(self):
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 200)
        d = res.get_json()["stats"]
        self.assertGreater(d["total_invited"], 0)
        self.assertGreater(d["total_checked_in"], 0)
        print(f"[TEST 6 PASS] Live Stats: {d['total_checked_in']}/{d['total_invited']} checked in ({d['turnout_rate']}%)")

    def test_07_audit_trail(self):
        res = self.client.get("/api/audit-logs")
        self.assertEqual(res.status_code, 200)
        logs = res.get_json()["logs"]
        self.assertGreater(len(logs), 0)
        print(f"[TEST 7 PASS] Audit trail has {len(logs)} recorded scan events")

if __name__ == "__main__":
    unittest.main()
