#!/usr/bin/env python3
"""
Gmail OAuth2 email sender class with configurable defaults.
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


class GmailSender:
    """
    Send emails via Gmail SMTP using OAuth2.
    Manages secrets in AWS Secrets Manager and handles token refresh automatically.
    """
    
    SCOPES = ["https://mail.google.com/"]
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    
    def __init__(
        self,
        secret_name: str = "/dmtalerts/emailcredentials",
        aws_region: str = "us-east-1",
        sender_email: str = "dmtalerts@shift4.com",
        sender_name: str = "DMT Dashboard (Don Irwin)"
    ):
        """
        Initialize the Gmail sender.
        
        Args:
            secret_name: AWS Secrets Manager secret path
            aws_region: AWS region containing the secret
            sender_email: Default sender email address
            sender_name: Default sender display name
        """
        self.secret_name = secret_name
        self.aws_region = aws_region
        self.default_sender_email = sender_email
        self.default_sender_name = sender_name
        
        self._secret = None
        self._access_token = None
    
    def _get_secret(self) -> dict:
        """Retrieve secret from AWS Secrets Manager."""
        if self._secret is None:
            sm = boto3.client("secretsmanager", region_name=self.aws_region)
            resp = sm.get_secret_value(SecretId=self.secret_name)
            self._secret = json.loads(resp["SecretString"])
        return self._secret
    
    def _put_secret(self, updated: dict) -> None:
        """Update secret in AWS Secrets Manager."""
        sm = boto3.client("secretsmanager", region_name=self.aws_region)
        sm.update_secret(SecretId=self.secret_name, SecretString=json.dumps(updated))
        self._secret = updated
    
    def _ensure_refresh_token(self):
        """Ensure the secret contains a refresh_token, running OAuth if needed."""
        secret = self._get_secret()
        
        if secret.get("refresh_token"):
            return secret["refresh_token"]
        
        print("No refresh_token found; starting OAuth flow...")
        installed = secret["installed"]
        flow = InstalledAppFlow.from_client_config({"installed": installed}, self.SCOPES)
        
        try:
            creds = flow.run_console()
        except AttributeError:
            creds = flow.run_local_server(port=0)
        
        if not creds.refresh_token:
            raise RuntimeError("OAuth flow did not return a refresh_token.")
        
        secret["refresh_token"] = creds.refresh_token
        self._put_secret(secret)
        print("Refresh token saved to Secrets Manager.")
        return creds.refresh_token
    
    def _get_access_token(self) -> str:
        """Get a fresh access token using the refresh token."""
        secret = self._get_secret()
        refresh_token = self._ensure_refresh_token()
        
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=secret["installed"]["token_uri"],
            client_id=secret["installed"]["client_id"],
            client_secret=secret["installed"]["client_secret"],
            scopes=self.SCOPES,
        )
        creds.refresh(Request())
        
        if not creds.token:
            raise RuntimeError("Failed to obtain access token.")
        
        return creds.token
    
    def _build_xoauth2(self, user_email: str, access_token: str) -> str:
        """Build Gmail's XOAUTH2 auth string."""
        raw = f"user={user_email}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    
    def _build_message(
        self,
        sender_email: str,
        sender_name: str,
        recipients: list,
        subject: str,
        text_body: str,
        html_body: str | None
    ):
        """Build a multipart/alternative email message."""
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr((sender_name, sender_email))
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="gmail.com")
        msg["Reply-To"] = sender_email
        
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))
        
        return msg
    
    def send_mail(
        self,
        recipients: list[str],
        subject: str,
        text_body: str,
        html_body: str | None = None,
        sender_email: str | None = None,
        sender_name: str | None = None
    ):
        """
        Send an email via Gmail SMTP using OAuth2.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject line
            text_body: Plain text email body
            html_body: Optional HTML email body
            sender_email: Optional override for sender email (defaults to instance default)
            sender_name: Optional override for sender name (defaults to instance default)
        """
        # Use defaults if not overridden
        sender_email = sender_email or self.default_sender_email
        sender_name = sender_name or self.default_sender_name
        
        # Validate sender matches secret
        secret = self._get_secret()
        secret_email = secret.get("email")
        if secret_email != sender_email:
            raise ValueError(
                f"sender_email ({sender_email}) must match secret email ({secret_email})."
            )
        
        # Get fresh access token
        access_token = self._get_access_token()
        xoauth2 = self._build_xoauth2(sender_email, access_token)
        
        # Build message
        msg = self._build_message(
            sender_email,
            sender_name,
            recipients,
            subject,
            text_body,
            html_body
        )
        
        # Send via SMTP
        with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            code, resp = s.docmd("AUTH", "XOAUTH2 " + xoauth2)
            if code != 235:
                raise RuntimeError(f"SMTP AUTH failed: {code} {resp!r}")
            s.sendmail(sender_email, recipients, msg.as_string())
        
        print(f"Email sent to {len(recipients)} recipient(s).")


# Test email content
TEST_TEXT_BODY = """Hi there,

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
Don"""

TEST_HTML_BODY = """\
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
</div>"""


def send_test():
    """Send a test email to validate the email path."""
    sender = GmailSender()
    
    recipients = ["don.irwin@shift4.com"]
    subject = "DMT Dashboard — notification path check"
    
    sender.send_mail(
        recipients=recipients,
        subject=subject,
        text_body=TEST_TEXT_BODY,
        html_body=TEST_HTML_BODY
    )


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "sendtest":
        send_test()
    else:
        print("Usage: python email_sender.py sendtest")
        sys.exit(1)