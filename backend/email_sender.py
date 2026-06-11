"""Gmail SMTP email sender module.

Sends personalised outreach emails via Gmail using smtplib with SSL.
Includes retry logic and explicit comments on Gmail App Password setup.
"""

import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

# ── Gmail SMTP configuration ──────────────────────────────────────────────────
# Gmail App Password setup:
#   1. Enable 2-Step Verification on your Google Account:
#      https://myaccount.google.com/signinoptions/two-step-verification
#   2. Generate a 16-character App Password for "Mail" on your device:
#      https://myaccount.google.com/apppasswords
#   3. Copy the 16-character password (no spaces) into .env as GMAIL_APP_PASS.
#   4. Set GMAIL_USER to your full Gmail address (e.g., yourname@gmail.com).
#   5. Set FROM_NAME to the display name you want in the "From" header.
# Do NOT use your regular Gmail password here — it will be rejected.
# ───────────────────────────────────────────────────────────────────────────────

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS", "")
FROM_NAME = os.getenv("FROM_NAME", "IRUS Business Development")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def send_email(to_email: str, to_name: str, subject: str, body: str) -> bool:
    """Send a single email via Gmail SMTP with one retry on failure.

    Args:
        to_email: Recipient email address.
        to_name: Recipient display name.
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    if not GMAIL_USER or not GMAIL_APP_PASS:
        print("Warning: GMAIL_USER or GMAIL_APP_PASS not set. Skipping send.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{GMAIL_USER}>"
    msg["To"] = f"{to_name} <{to_email}>"

    msg.attach(MIMEText(body, "plain", "utf-8"))

    for attempt in range(2):
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.login(GMAIL_USER, GMAIL_APP_PASS)
                server.sendmail(GMAIL_USER, [to_email], msg.as_string())
            print(f"Email sent successfully to {to_email}")
            return True
        except Exception as exc:
            print(f"Email send error (attempt {attempt + 1}/2) for {to_email}: {exc}")
            if attempt < 1:
                time.sleep(5)

    return False
