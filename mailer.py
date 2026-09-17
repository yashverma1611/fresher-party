"""
Mailer & WhatsApp Generator module for Event QR Pass & Scanner Management System.
Handles formal invitation emails (HTML + inline QR) via SMTP with graceful simulation fallback,
and instant WhatsApp deep-link generation.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import urllib.parse
import re
import datetime
from qr_generator import generate_qr_bytes, generate_qr_base64

def clean_phone_number(phone: str) -> str:
    """Normalize phone number to international format without spaces/plus for WhatsApp links."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        # Default to Indian country code +91 if 10 digits
        return f"91{digits}"
    return digits

def build_formal_email_html(student, config, base_url: str = "http://localhost:5000") -> str:
    """Generate professional, formal HTML invitation email."""
    pass_url = f"{base_url}/pass/{student['pass_token']}"
    qr_b64 = generate_qr_base64(student['pass_token'])

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Official Invitation - {config['event_name']}</title>
</head>
<body style="margin:0; padding:0; background-color:#f1f5f9; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color:#1e293b;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#f1f5f9; padding:24px 0;">
        <tr>
            <td align="center">
                <table border="0" cellpadding="0" cellspacing="0" width="600" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1);">
                    <!-- Header Banner -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding:32px 24px; text-align:center; color:#ffffff;">
                            <div style="font-size:13px; text-transform:uppercase; letter-spacing:2px; opacity:0.85; margin-bottom:8px;">Bachelor of Computer Applications</div>
                            <h1 style="margin:0; font-size:26px; font-weight:800; letter-spacing:-0.5px;">{config['event_name']}</h1>
                            <p style="margin:8px 0 0 0; font-size:15px; opacity:0.9;">Official Invitation &amp; Entry Pass</p>
                        </td>
                    </tr>

                    <!-- Main Body -->
                    <tr>
                        <td style="padding:32px 28px;">
                            <p style="font-size:16px; line-height:1.6; margin:0 0 16px 0;">
                                Dear <strong>{student['name']}</strong>,
                            </p>
                            <p style="font-size:15px; line-height:1.6; color:#475569; margin:0 0 24px 0;">
                                You are cordially invited to celebrate the <strong>{config['event_name']}</strong>! Join us for an exhilarating day of music, games, cultural showcases, and a special lunch banquet.
                            </p>

                            <!-- Event Details Card -->
                            <div style="background-color:#f8fafc; border-left:4px solid #2563eb; border-radius:6px; padding:18px; margin-bottom:24px;">
                                <table border="0" cellpadding="4" cellspacing="0" width="100%">
                                    <tr>
                                        <td width="30%" style="font-size:13px; font-weight:600; color:#64748b;">GUEST NAME:</td>
                                        <td style="font-size:14px; font-weight:700; color:#0f172a;">{student['name']}</td>
                                    </tr>
                                    <tr>
                                        <td style="font-size:13px; font-weight:600; color:#64748b;">ROLL NUMBER:</td>
                                        <td style="font-size:14px; font-weight:700; color:#2563eb;">{student['roll_no']}</td>
                                    </tr>
                                    <tr>
                                        <td style="font-size:13px; font-weight:600; color:#64748b;">SEMESTER / BATCH:</td>
                                        <td style="font-size:14px; font-weight:600; color:#0f172a;">{student['semester']} Semester</td>
                                    </tr>
                                    <tr>
                                        <td style="font-size:13px; font-weight:600; color:#64748b;">DATE &amp; TIME:</td>
                                        <td style="font-size:14px; font-weight:600; color:#0f172a;">{config['event_date']}</td>
                                    </tr>
                                    <tr>
                                        <td style="font-size:13px; font-weight:600; color:#64748b;">VENUE:</td>
                                        <td style="font-size:14px; font-weight:600; color:#0f172a;">{config['venue']}</td>
                                    </tr>
                                </table>
                            </div>

                            <!-- QR Pass Box -->
                            <div style="border:2px dashed #cbd5e1; border-radius:12px; padding:24px; text-align:center; background-color:#ffffff; margin-bottom:24px;">
                                <div style="font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:#64748b; margin-bottom:12px;">Official Entry QR Code</div>
                                <img src="{qr_b64}" alt="QR Entry Pass" width="190" height="190" style="display:block; margin:0 auto; border-radius:8px;" />
                                <div style="font-size:13px; font-family:monospace; color:#334155; margin-top:12px; font-weight:600;">
                                    Token: {student['pass_token']}
                                </div>
                                <div style="margin-top:18px;">
                                    <a href="{pass_url}" target="_blank" style="display:inline-block; background-color:#2563eb; color:#ffffff; font-weight:600; font-size:14px; text-decoration:none; padding:10px 24px; border-radius:6px;">
                                        Open Digital Ticket / Download Pass
                                    </a>
                                </div>
                            </div>

                            <!-- Entry Instructions -->
                            <div style="background-color:#eff6ff; border-radius:8px; padding:16px; font-size:13px; color:#1e40af; line-height:1.5; margin-bottom:20px;">
                                <strong>?? Important Security Guidelines:</strong>
                                <ul style="margin:6px 0 0 0; padding-left:20px;">
                                    <li>Present this QR code on your smartphone at Gate 1 or Gate 2.</li>
                                    <li>This pass is strictly personal and non-transferable.</li>
                                    <li>Once verified by an entry scanner, this QR code will be permanently deactivated.</li>
                                </ul>
                            </div>

                            <p style="font-size:14px; line-height:1.5; color:#64748b; margin:0;">
                                If you have any inquiries, contact the Organizing Committee at <a href="mailto:{config['creator_email']}" style="color:#2563eb;">{config['creator_email']}</a>.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#f8fafc; border-top:1px solid #e2e8f0; padding:18px 24px; text-align:center; font-size:12px; color:#94a3b8;">
                            &copy; 2026 BCA Organizing Committee &bull; Fresher's Party 2026 &bull; All Rights Reserved
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    return html

def send_invitation_email(student, config, base_url: str = "http://localhost:5000") -> dict:
    """
    Dispatches invitation email.
    If SMTP credentials are provided, attempts real TLS connection.
    Otherwise, logs as simulated delivery for zero-friction testing.
    """
    subject = f"Official Invitation & Entry Pass - {student['name']} ({config['event_name']})"
    html_content = build_formal_email_html(student, config, base_url)

    smtp_server = config.get("smtp_server")
    smtp_port = int(config.get("smtp_port") or 587)
    smtp_user = config.get("smtp_user")
    smtp_password = config.get("smtp_password")

    if smtp_user and smtp_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{config['event_name']} <{smtp_user}>"
            msg["To"] = student["email"]

            part_html = MIMEText(html_content, "html")
            msg.attach(part_html)

            # Attach inline QR code
            qr_raw = generate_qr_bytes(student["pass_token"])
            img_part = MIMEImage(qr_raw, "png")
            img_part.add_header("Content-Disposition", "attachment", filename=f"Pass-{student['roll_no']}.png")
            msg.attach(img_part)

            with smtplib.SMTP(smtp_server, smtp_port, timeout=12) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

            return {
                "success": True,
                "status": "sent",
                "recipient": student["email"],
                "message": "Email sent successfully via SMTP"
            }
        except Exception as e:
            return {
                "success": False,
                "status": "failed",
                "recipient": student["email"],
                "message": f"SMTP Error: {str(e)}"
            }
    else:
        # Simulation mode: Perfect for immediate local demonstration
        return {
            "success": True,
            "status": "simulated",
            "recipient": student["email"],
            "subject": subject,
            "preview_html": html_content,
            "message": "Invitation simulated and recorded in Outbox (Configure SMTP in Settings for live sending)"
        }

def generate_whatsapp_invitation(student, config, base_url: str = "http://localhost:5000") -> dict:
    """Generate WhatsApp text and direct wa.me / api.whatsapp.com URL."""
    clean_phone = clean_phone_number(student["phone"])
    pass_url = f"{base_url}/pass/{student['pass_token']}"

    message = (
        f"?? *INVITATION: {config['event_name'].upper()}* ??\n\n"
        f"Dear *{student['name']}* (Roll: *{student['roll_no']}*, *{student['semester']}*),\n"
        f"You are cordially invited to the {config['event_name']}!\n\n"
        f"?? *Date & Time:* {config['event_date']}\n"
        f"?? *Venue:* {config['venue']}\n\n"
        f"??? *Your Digital QR Entry Pass:* {pass_url}\n"
        f"Pass ID: `{student['pass_token']}`\n\n"
        f"?? *Guidelines:* Present your QR pass at Gate 1 or Gate 2. It is valid for a single check-in only.\n\n"
        f"Organizing Committee &bull; Contact: {config['creator_email']}"
    )

    encoded_text = urllib.parse.quote(message)
    wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"

    return {
        "phone": clean_phone,
        "raw_phone": student["phone"],
        "text": message,
        "wa_url": wa_url
    }

if __name__ == "__main__":
    sample_student = {
        "name": "Aarav Sharma",
        "roll_no": "26BCA101",
        "semester": "BCA 1st",
        "email": "aarav.bca26@gmail.com",
        "phone": "+91 9123456701",
        "pass_token": "PASS-BCA1ST-ABC123XYZ"
    }
    sample_cfg = {
        "event_name": "BCA Freshers Party 2026",
        "event_date": "Saturday, October 10, 2026 | 11:00 AM onwards",
        "venue": "Auditorium Hall, Main Campus",
        "creator_email": "frsher.party.2k.26@gmail.com"
    }

    res_email = send_invitation_email(sample_student, sample_cfg)
    print("Email Test:", res_email["status"], "-", res_email["message"])

    res_wa = generate_whatsapp_invitation(sample_student, sample_cfg)
    print("WhatsApp Link Test:", res_wa["wa_url"][:60], "...")
