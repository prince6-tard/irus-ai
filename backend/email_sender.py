"""Generic SMTP email sender module.

Sends personalised outreach emails via SMTP (GoDaddy SecureServer) using smtplib with SSL.
Includes retry logic and anti-spam deliverability headers.
"""

import os
import imaplib
import smtplib
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

from dotenv import load_dotenv
from config import CC_EMAIL

load_dotenv()

# ── SMTP configuration ────────────────────────────────────────────────────────
# Environment variables (with fallbacks):
#   SMTP_SERVER  — SMTP host (default: sg2plzcpnl506221.prod.sin2.secureserver.net)
#   SMTP_PORT    — SMTP port (default: 465)
#   SMTP_USER    — SMTP username / envelope sender (default: "")
#   SMTP_PASS    — SMTP password (default: "")
#   FROM_NAME    — Display name in the From header (default: "IRUS Business Development")
#   FROM_EMAIL   — Email address in the From header (default: SMTP_USER for SPF alignment)
# ───────────────────────────────────────────────────────────────────────────────

SMTP_HOST = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_NAME = os.getenv("FROM_NAME", "IRUS Business Development")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)


def send_email(to_email: str, to_name: str, subject: str, body: str) -> bool:
    """Send a single email via SMTP with one retry on failure.

    Args:
        to_email: Recipient email address.
        to_name: Recipient display name.
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    if not SMTP_USER or not SMTP_PASS:
        print("Warning: SMTP_USER or SMTP_PASS not set. Skipping send.")
        return False

    from_header = f"{FROM_NAME} <{FROM_EMAIL}>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = f"{to_name} <{to_email}>"
    msg["Reply-To"] = from_header
    if CC_EMAIL:
        msg["Cc"] = CC_EMAIL

    # Anti-spam deliverability headers
    msg["Message-ID"] = f"<{uuid.uuid4()}@o2i.tech>"
    msg["Date"] = formatdate(localtime=True)
    msg["Precedence"] = "bulk"
    msg["List-Unsubscribe"] = "<mailto:ab1@o2i.tech?subject=unsubscribe>"
    msg["X-Mailer"] = "IRUS-Outreach/1.0"

    msg.attach(MIMEText(body, "plain", "utf-8"))

    for attempt in range(2):
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.login(SMTP_USER, SMTP_PASS)
                recipients = [to_email]
                if CC_EMAIL:
                    recipients.append(CC_EMAIL)
                server.sendmail(FROM_EMAIL, recipients, msg.as_string())
            # Save a copy to the IMAP Sent folder so it appears in cPanel webmail
            try:
                with imaplib.IMAP4_SSL(SMTP_HOST, 993) as imap:
                    imap.login(SMTP_USER, SMTP_PASS)
                    imap.append("INBOX.Sent", "\\Seen", imaplib.Time2Internaldate(time.time()), msg.as_string().encode("utf-8"))
                    imap.logout()
            except Exception as exc:
                print(f"IMAP Sent-folder save warning: {exc}")
            print(f"Email sent successfully to {to_email}")
            return True
        except Exception as exc:
            print(f"Email send error (attempt {attempt + 1}/2) for {to_email}: {exc}")
            if attempt < 1:
                time.sleep(5)

    return False
