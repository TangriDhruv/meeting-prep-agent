"""Google Calendar API v3 wrapper."""

from datetime import datetime, timezone, timedelta
from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


def _normalize_event(item: dict) -> dict:
    """Extract a clean meeting dict from a raw Calendar API event."""
    start_raw = item.get("start", {})
    end_raw = item.get("end", {})

    start = start_raw.get("dateTime") or start_raw.get("date", "")
    end = end_raw.get("dateTime") or end_raw.get("date", "")

    attendees = [
        {
            "email": a.get("email", ""),
            "name": a.get("displayName", ""),
            "response": a.get("responseStatus", ""),
        }
        for a in item.get("attendees", [])
    ]

    return {
        "id": item.get("id", ""),
        "summary": item.get("summary", "(No title)"),
        "start": start,
        "end": end,
        "attendees": attendees,
        "description": item.get("description", ""),
        "location": item.get("location", ""),
        "organizer": item.get("organizer", {}).get("email", ""),
        "html_link": item.get("htmlLink", ""),
    }


def fetch_upcoming_meetings(creds: Credentials, days_ahead: int = 7) -> list[dict]:
    """Return normalized meetings starting from now up to days_ahead days."""
    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days_ahead)).isoformat()

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return [_normalize_event(item) for item in result.get("items", [])]


def fetch_meeting_by_id(creds: Credentials, meeting_id: str) -> dict:
    """Return a single normalized meeting event by its calendar event ID."""
    service = build("calendar", "v3", credentials=creds)
    item = service.events().get(calendarId="primary", eventId=meeting_id).execute()
    return _normalize_event(item)
