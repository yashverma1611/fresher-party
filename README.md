# BCA Freshers Party 2026 — QR Pass & Scanner System

Flask + SQLite backend with real-time sync (SSE), OTP-based admin approval,
QR entry passes, offline-safe scanning, and Excel import/export.

## What's changed from the version you gave me

- **`database.py`** — no longer auto-seeds 20 demo students. The `students`
  table starts empty; bring in your real guest list via Upload Excel.
- **`app.py`** — `init_db()` now runs at import time, not just inside
  `if __name__ == "__main__"`. This was a real bug: a production server
  like gunicorn *imports* `app.py` rather than executing it directly, so
  the database tables were never being created when deployed that way.
- **`requirements.txt`** — added (Flask, flask-cors, qrcode[pil],
  openpyxl, gunicorn).
- **`.gitignore`** — added, so `event_data.db` and `__pycache__` don't get
  committed.

Still using the demo creator/scanner accounts seeded in `database.py`
(see "Before the real event" below) — replace those when you're ready.

## Running locally

```bash
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000. The database file `event_data.db` is created
automatically next to `app.py` on first run.

On Windows, double-click `start_server.bat` (or run `start_server.ps1` in
PowerShell) instead.

## Bringing in your real guest list

1. Fill in the `BCA_Guest_List_Template.xlsx` template (two sheets: "BCA 1st
   Sem" and "BCA 3rd Sem") with your actual students.
2. In the app, use **Upload Excel** — it detects semester from the sheet
   name and matches columns by header text.

## Deploying to Render (for "from anywhere, anytime" access)

1. Push this whole folder to a GitHub repo. **Don't** commit `event_data.db`
   — Render creates a fresh one on first boot (`.gitignore` already
   excludes it).
2. On [render.com](https://render.com): **New → Web Service** → connect
   your repo.
3. Settings:
   - Environment: **Python 3**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn -w 2 --threads 4 --timeout 120 app:app`
   - Instance type: **Free**
4. Deploy. You'll get a live URL like `https://your-app.onrender.com`.
5. Sign in as creator (`frsher.party.2k.26@gmail.com` / PIN `202600` —
   change this PIN once you're in), upload your real guest sheets, and set
   your Gmail app password in Settings so invitation emails actually send.

### Important: Render's free tier has no persistent disk
A **redeploy** (new git push, or manually redeploying) wipes the SQLite
file, since the container rebuilds from scratch. Ordinary spin-down/wake
cycles from inactivity do **not** wipe it — only a full redeploy does. So:
- Finish all setup and testing *before* the event.
- Don't push new code or manually redeploy once the event has started.
- As a safety net, periodically hit `/api/export-attendance` during the
  event to download a live backup of who's checked in.

## Before the real event
- **Change the creator PIN** (currently the demo `202600`) via the
  creator login flow or directly in the `admins` table.
- **Replace the 3 demo gate scanners** (Rahul, Priya, Amit — fake
  `@college.edu` emails) with your real organizers: have them register via
  the scanner sign-up flow, then approve them from the creator dashboard
  (rejecting or ignoring the demo ones).
- **Set real SMTP credentials** (Gmail address + App Password, generated
  at https://myaccount.google.com/apppasswords) via the Settings/config
  panel — without this, emails are only simulated, not actually sent.

## Running the test suite
```bash
python seed_tokens.py    # needed once — the tests use these demo tokens
python test_system.py
```
