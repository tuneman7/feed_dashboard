#!/usr/bin/env python3
"""
Send a human-friendly multipart (text+HTML) email via Gmail SMTP using OAuth2.
- Reads Google OAuth client + (on first run) writes refresh_token in AWS Secrets Manager.
- Each run exchanges the saved refresh_token for a fresh short-lived access token.
- Reply-To is set equal to From to minimize spam flags.
"""

import base64
import json
import smtplib
from email.utils import formataddr, formatdate, make_msgid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ===================== USER CONFIG =====================
SECRET_NAME  = "/dmtalerts/emailcredentials"   # AWS Secrets Manager path
AWS_REGION   = "us-east-1"                        # region containing the secret

SENDER_EMAIL = "dmtalerts@shift4.com"           # must match the 'email' value stored in the secret
SENDER_NAME  = "DMT Dashboard (Don Irwin)"

RECIPIENTS   = [
# "anol.bhattarai@shift4.com",
# "augustas.grecnas@shift4.com",
# "craig.vanroy@shift4.com",
 #"dgates@shift4.com",
 "don.irwin@shift4.com"
# "dsimeone@shift4.com",
# "elton.zhao@shift4.com",
# "eoga@shift4.com",
# "frank.chukoskie@shift4.com",
# "max.jackson@shift4.com",
# "marthur@shift4.com",
# "monica.kohli@shift4.com",
# "omid.tajalli@shift4.com",
# "Samjhana.Kafle@shift4.com",
# "sanjith.venkatesh@shift4.com",
# "Smitha.Rampure@shift4.com",
#"alexander.savitzky@shift4.com"
]

SUBJECT = "DMT Dashboard — notification path check"

# Plain-text body (readable, multi-paragraph)
TEXT_BODY = """Hi there,

This is Don Irwin. I am validating the DMT Dashboard email path to ensure
messages arrive reliably in corporate mailboxes.

This note mirrors the production format:
- Clear subject line
- Human-readable paragraphs
- Plain-text body with an HTML alternative
- Friendly From name with aligned Reply-To

If you received this, the path is working as expected. If delivery was delayed,
I will follow up with IT for allow-listing and sender reputation improvements.

Thanks,
Don
"""

# HTML alternative (kept simple and clean)
HTML_BODY = """\
<div style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; line-height:1.5; color:#111;">
  <p>Hi there,</p>

  <p>This is <strong>Don Irwin</strong>. I am validating the <em>DMT Dashboard</em> email path to ensure messages arrive reliably in corporate mailboxes.</p>

  <p>This note mirrors the production format:</p>
  <ul>
    <li>Clear subject line</li>
    <li>Human-readable paragraphs</li>
    <li>Plain-text body with an HTML alternative</li>
    <li>Friendly From name with aligned Reply-To</li>
  </ul>

  <p>If you received this, the path is working as expected. If delivery was delayed, I will follow up with IT for allow-listing and sender reputation improvements.</p>

  <p>Thanks,<br/>Don</p>
</div>
"""
# =======================================================

SCOPES      = ["https://mail.google.com/"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT   = 587


def get_secret() -> dict:
    sm = boto3.client("secretsmanager", region_name=AWS_REGION)
    resp = sm.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(resp["SecretString"])


def put_secret(updated: dict) -> None:
    sm = boto3.client("secretsmanager", region_name=AWS_REGION)
    sm.update_secret(SecretId=SECRET_NAME, SecretString=json.dumps(updated))


def ensure_refresh_token(secret: dict):
    """
    Ensure the secret contains a refresh_token. If not, run OAuth to obtain one
    and save it back to Secrets Manager. Uses console flow first for headless.
    """
    if secret.get("refresh_token"):
        return secret, secret["refresh_token"]

    print("No refresh_token found in secret; starting OAuth flow...")
    installed = secret["installed"]
    flow = InstalledAppFlow.from_client_config({"installed": installed}, SCOPES)

    # Prefer console (prints a URL + code). Fallback to local server if unavailable.
    try:
        creds = flow.run_console()
    except AttributeError:
        creds = flow.run_local_server(port=0)

    if not creds.refresh_token:
        raise RuntimeError("OAuth flow did not return a refresh_token.")

    secret["refresh_token"] = creds.refresh_token
    put_secret(secret)
    print("Refresh token saved to Secrets Manager.")
    return secret, creds.refresh_token


def get_access_token(secret: dict, refresh_token: str) -> str:
    """
    Exchange the long-lived refresh token for a short-lived access token.
    Called each run so the access token is always fresh.
    """
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=secret["installed"]["token_uri"],
        client_id=secret["installed"]["client_id"],
        client_secret=secret["installed"]["client_secret"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Failed to obtain access token.")
    return creds.token


def build_xoauth2(user_email: str, access_token: str) -> str:
    """
    Build Gmail's XOAUTH2 auth string.
    """
    raw = f"user={user_email}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def build_message(sender_email: str, sender_name: str, recipients: list,
                  subject: str, text_body: str, html_body: str | None):
    """
    Build a standards-compliant multipart/alternative message.
    Reply-To is set equal to From to keep alignment tight.
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")
    msg["Reply-To"] = sender_email  # aligned with From

    # Always include text; include HTML if provided
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def smtp_send():
    secret = get_secret()

    # Sanity check: the secret's 'email' must match SENDER_EMAIL
    secret_email = secret.get("email")
    if secret_email != SENDER_EMAIL:
        raise ValueError(f"SENDER_EMAIL ({SENDER_EMAIL}) must match secret email ({secret_email}).")

    # Ensure we have a refresh token, then obtain a fresh access token
    secret, refresh_token = ensure_refresh_token(secret)
    access_token = get_access_token(secret, refresh_token)
    xoauth2 = build_xoauth2(SENDER_EMAIL, access_token)

    # Build the message
    msg = build_message(
        SENDER_EMAIL,
        SENDER_NAME,
        RECIPIENTS,
        SUBJECT,
        TEXT_BODY,
        HTML_BODY
    )

    # Send via Gmail SMTP + STARTTLS + XOAUTH2
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        # Uncomment for verbose SMTP session logging:
        # s.set_debuglevel(1)
        s.ehlo()
        s.starttls()
        s.ehlo()
        code, resp = s.docmd("AUTH", "XOAUTH2 " + xoauth2)
        if code != 235:
            raise RuntimeError(f"SMTP AUTH failed: {code} {resp!r}")
        s.sendmail(SENDER_EMAIL, RECIPIENTS, msg.as_string())

    print("Email sent.")


if __name__ == "__main__":
    smtp_send()
