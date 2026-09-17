"""
QR Generator module for Event QR Pass & Scanner Management System.
Generates crisp, high-contrast QR codes and base64 representations for passes.
"""

import qrcode
from io import BytesIO
import base64

def generate_qr_bytes(token: str) -> bytes:
    """Generate raw PNG bytes for a given pass token."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(token)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()

def generate_qr_base64(token: str) -> str:
    """Generate a base64 Data URL for a given pass token."""
    raw_bytes = generate_qr_bytes(token)
    encoded = base64.b64encode(raw_bytes).decode('utf-8')
    return f"data:image/png;base64,{encoded}"

if __name__ == "__main__":
    sample_token = "PASS-BCA1ST-TESTTOKEN123"
    b64 = generate_qr_base64(sample_token)
    print("QR Generator Test: Success! Base64 length:", len(b64))
