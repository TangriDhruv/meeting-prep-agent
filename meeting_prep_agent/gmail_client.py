"""Gmail API v1 wrapper."""

import base64
import re
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Max characters to include per message body to avoid overwhelming Claude's context
_MAX_BODY_CHARS = 2000


def _get_header(headers: list[dict], name: str) -> str:
    """Extract a header value by name (case-insensitive)."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


def _extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from a message payload."""
    mime_type = payload.get("mimeType", "")

    # Direct text/plain part
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # Recurse into multipart parts
    if mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _extract_body(part)
            if text:
                return text

    return ""


def _clean_body(text: str) -> str:
    """Strip quoted replies and excessive whitespace to keep bodies concise."""
    # Remove lines that look like quoted replies ("> ..." or "On ... wrote:")
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if re.match(r"^On .+ wrote:$", stripped):
            break
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    # Collapse 3+ blank lines into 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned[:_MAX_BODY_CHARS]


def _get_thread_summary(service, thread_id: str) -> dict:
    """Fetch full message content for a thread and return a rich summary dict."""
    thread = service.users().threads().get(
        userId="me", id=thread_id, format="full",
    ).execute()

    messages = thread.get("messages", [])
    if not messages:
        return {}

    first_msg = messages[0]
    headers = first_msg.get("payload", {}).get("headers", [])

    # Collect body of each message (most recent last, up to 5 messages)
    message_bodies = []
    for msg in messages[-5:]:
        payload = msg.get("payload", {})
        msg_headers = payload.get("headers", [])
        sender = _get_header(msg_headers, "From")
        date = _get_header(msg_headers, "Date")
        body = _clean_body(_extract_body(payload))
        if body:
            message_bodies.append(f"[{date}] {sender}:\n{body}")

    return {
        "thread_id": thread_id,
        "subject": _get_header(headers, "Subject"),
        "from": _get_header(headers, "From"),
        "to": _get_header(headers, "To"),
        "date": _get_header(headers, "Date"),
        "message_count": len(messages),
        "messages": message_bodies,
    }


def fetch_emails_with_person(
    creds: Credentials, email: str, max_results: int = 10
) -> list[dict]:
    """Return full thread content for emails exchanged with a specific person."""
    query = f"from:{email} OR to:{email}"
    return search_emails(creds, query, max_results)


def search_emails(
    creds: Credentials, query: str, max_results: int = 10
) -> list[dict]:
    """Return full thread content for emails matching an arbitrary Gmail search query."""
    service = build("gmail", "v1", credentials=creds)

    result = (
        service.users()
        .threads()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    threads = result.get("threads", [])
    summaries = []
    for t in threads:
        summary = _get_thread_summary(service, t["id"])
        if summary:
            summaries.append(summary)

    return summaries
