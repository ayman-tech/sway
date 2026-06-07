"""Google Calendar event mapping shared by desktop and API."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sway_core.constants import Source, TaskStatus
from sway_core.datetime_utils import from_iso, utc_now
from sway_core.models import Task

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
READABLE_CALENDAR_ROLES = {"owner", "writer", "reader"}
GOOGLE_EVENT_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def task_id_for_google_event(user_id: str, event_id: str) -> str:
    return str(uuid.uuid5(GOOGLE_EVENT_NAMESPACE, f"gcal:{user_id}:{event_id}"))


def meet_link(event: dict) -> str | None:
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    for entry in event.get("conferenceData", {}).get("entryPoints", []):
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return entry["uri"]
    return None


def build_description(event: dict) -> str | None:
    header: list[str] = []
    meet = meet_link(event)
    if meet:
        header.append(f"Meet: {meet}")
    location = event.get("location")
    if location:
        header.append(f"Location: {location}")
    sections: list[str] = []
    if header:
        sections.append("\n".join(header))
    body = event.get("description")
    if body:
        sections.append(body.strip())
    return "\n\n".join(sections) or None


def parse_event_when(event: dict) -> tuple[datetime | None, date | None, datetime | None, date | None] | None:
    start, end = event.get("start", {}), event.get("end", {})
    if "dateTime" in start:
        due_at = from_iso(start["dateTime"])
        end_at = from_iso(end["dateTime"]) if end.get("dateTime") else None
        return due_at, None, end_at, None
    if "date" in start:
        due_date = date.fromisoformat(start["date"])
        end_date = date.fromisoformat(end["date"]) if end.get("date") else due_date + timedelta(days=1)
        return None, due_date, None, end_date
    return None


def task_from_google_event(event: dict, user_id: str, existing: Task | None = None) -> Task | None:
    event_id = event.get("id")
    if not event_id:
        return None
    when = parse_event_when(event)
    if when is None:
        return None
    due_at, due_date, end_at, end_date = when
    return Task(
        id=task_id_for_google_event(user_id, event_id),
        title=event.get("summary") or "(No title)",
        description=build_description(event),
        due_at=due_at,
        due_date=due_date,
        end_at=end_at,
        end_date=end_date,
        source=Source.GOOGLE,
        google_event_id=event_id,
        status=TaskStatus.PENDING,
        reminder_minutes_before=existing.reminder_minutes_before if existing and due_at is not None else None,
        created_at=existing.created_at if existing else utc_now(),
    )


def google_import_window() -> tuple[str, str]:
    return (
        (utc_now() - timedelta(days=1)).isoformat(),
        (utc_now() + timedelta(days=120)).isoformat(),
    )
