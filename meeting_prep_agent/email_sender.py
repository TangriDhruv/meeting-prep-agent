"""Send the meeting prep brief as an HTML email via Gmail API."""

import base64
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from .config import EMAIL_RECIPIENT, EMAIL_SUBJECT_PREFIX


def send_brief_email(creds: Credentials, brief: str) -> None:
    """Convert *brief* (markdown) to HTML and send it to EMAIL_RECIPIENT.

    Args:
        creds: Authorised Google credentials (must include gmail.send scope).
        brief: The meeting prep brief in markdown format.

    Raises:
        ValueError: If EMAIL_RECIPIENT is not configured in the environment.
    """
    if not EMAIL_RECIPIENT:
        raise ValueError(
            "EMAIL_RECIPIENT is not set. Add 'EMAIL_RECIPIENT=you@gmail.com' to your .env file."
        )

    today = datetime.date.today().strftime("%A, %B %-d, %Y")
    subject = f"{EMAIL_SUBJECT_PREFIX} — {today}"

    # Strip any conversational preamble before the markdown content
    for marker in ("---", "#"):
        idx = brief.find(marker)
        if idx != -1:
            brief = brief[idx:]
            break

    html_body = markdown.markdown(brief, extensions=["tables", "fenced_code"])

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = EMAIL_RECIPIENT

    msg.attach(MIMEText(brief, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service = build("gmail", "v1", credentials=creds)
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
