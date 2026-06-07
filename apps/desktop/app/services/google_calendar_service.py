"""One-way Google Calendar → Sway import (client-side).

Connect runs a desktop OAuth flow (read-only calendar scope). Import uses Google's
incremental sync (syncToken) so anything added/changed/removed while the app was off is
caught up on the next run. Imported events become read-only, Google-sourced tasks; they
flow to the cloud and other devices via the normal Tier-1 sync.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import date, datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.cloud.config import is_google_configured, load_google_config
from app.constants import Source, TaskStatus
from app.models.task import Task
from app.repositories.settings_repo import SettingsRepository
from app.repositories.sqlite_repo import TaskRepository
from app.utils.datetime_utils import from_iso, utc_now

_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
_TOKEN_KEY = "google_token"
_SYNC_TOKENS_KEY = "google_sync_tokens"  # JSON map: calendarId -> syncToken
# Calendar list roles we can read events from (freeBusyReader can't).
_READABLE_ROLES = {"owner", "writer", "reader"}
# Stable namespace so the same Google event maps to the same task id on every device.
_NS = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


class GoogleCalendarError(Exception):
    """User-facing Google Calendar failure."""


def _client_config(client_id: str, client_secret: str) -> dict:
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def _task_id_for(user_id: str, event_id: str) -> str:
    # Include the Sway account id so the same person's devices dedup, while two
    # different accounts can never derive the same row id (defense-in-depth on top of RLS).
    return str(uuid.uuid5(_NS, f"gcal:{user_id}:{event_id}"))


def _meet_link(event: dict) -> str | None:
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    for entry in event.get("conferenceData", {}).get("entryPoints", []):
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return entry["uri"]
    return None


def _build_description(event: dict) -> str | None:
    """Meet link first, then location, then the event's own description."""
    header: list[str] = []
    meet = _meet_link(event)
    if meet:
        header.append(f"🔗 Meet: {meet}")
    location = event.get("location")
    if location:
        header.append(f"📍 {location}")
    sections: list[str] = []
    if header:
        sections.append("\n".join(header))
    body = event.get("description")
    if body:
        sections.append(body.strip())
    return "\n\n".join(sections) or None


def _parse_when(event: dict) -> tuple[datetime | None, date | None, datetime | None, date | None] | None:
    """Return timestamp or date-only scheduling fields from a Google event."""
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


class GoogleCalendarService:
    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings = settings_repo
        self._lock = threading.Lock()  # guards this service's own settings connection

    @staticmethod
    def is_configured() -> bool:
        return is_google_configured()

    def is_connected(self) -> bool:
        with self._lock:
            return bool(self._settings.get(_TOKEN_KEY))

    def connect(self) -> str:
        """Run the OAuth consent flow (opens a browser). Returns the account email. Blocking."""
        cfg = load_google_config()
        if cfg is None:
            raise GoogleCalendarError("Google Calendar isn’t configured.")
        flow = InstalledAppFlow.from_client_config(
            _client_config(cfg.client_id, cfg.client_secret), _SCOPES
        )
        # offline + consent → reliably returns a refresh token so the link persists.
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        with self._lock:
            self._settings.set(_TOKEN_KEY, creds.to_json())
            self._settings.set(_SYNC_TOKENS_KEY, "")  # force a fresh full import
        try:
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            return service.calendarList().get(calendarId="primary").execute().get("id", "Google")
        except Exception:  # noqa: BLE001 (email is cosmetic)
            return "Google Calendar"

    def disconnect(self) -> None:
        with self._lock:
            self._settings.set(_TOKEN_KEY, "")
            self._settings.set(_SYNC_TOKENS_KEY, "")

    def _credentials(self) -> Credentials | None:
        raw = self._settings.get(_TOKEN_KEY)
        if not raw:
            return None
        creds = Credentials.from_authorized_user_info(json.loads(raw), _SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._settings.set(_TOKEN_KEY, creds.to_json())
        return creds

    def import_into(self, task_repo: TaskRepository, user_id: str) -> int:
        """Pull changes from every selected calendar into `task_repo`. Returns changes."""
        with self._lock:
            creds = self._credentials()
            if creds is None:
                return 0
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            tokens = self._load_tokens()
            changed = 0
            for calendar_id in self._selected_calendars(service):
                try:
                    count, new_token = self._sync_calendar(
                        service, task_repo, user_id, calendar_id, tokens.get(calendar_id)
                    )
                except HttpError as exc:
                    if getattr(exc, "resp", None) is not None and exc.resp.status == 410:
                        # This calendar's sync token expired → full resync of it.
                        count, new_token = self._sync_calendar(
                            service, task_repo, user_id, calendar_id, None
                        )
                    else:
                        continue  # one bad calendar shouldn't stop the others
                changed += count
                if new_token:
                    tokens[calendar_id] = new_token
            self._save_tokens(tokens)
            self._prune_past(task_repo)
            return changed

    def _selected_calendars(self, service) -> list[str]:
        """Calendar ids the user has visible (selected) and can read events from."""
        ids: list[str] = []
        page_token = None
        while True:
            resp = service.calendarList().list(pageToken=page_token).execute()
            for entry in resp.get("items", []):
                if entry.get("selected") and entry.get("accessRole") in _READABLE_ROLES:
                    ids.append(entry["id"])
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return ids

    def _sync_calendar(
        self, service, task_repo: TaskRepository, user_id: str, calendar_id: str,
        sync_token: str | None,
    ) -> tuple[int, str | None]:
        changed = 0
        page_token = None
        next_sync_token = None
        while True:
            if sync_token:
                params = {"calendarId": calendar_id, "maxResults": 250, "syncToken": sync_token}
            else:
                params = {
                    "calendarId": calendar_id,
                    "singleEvents": True,
                    "orderBy": "startTime",
                    "maxResults": 250,
                    "timeMin": (utc_now() - timedelta(days=1)).isoformat(),
                    "timeMax": (utc_now() + timedelta(days=120)).isoformat(),
                }
            if page_token:
                params["pageToken"] = page_token
            resp = service.events().list(**params).execute()
            for event in resp.get("items", []):
                if self._apply_event(task_repo, event, user_id):
                    changed += 1
            next_sync_token = resp.get("nextSyncToken") or next_sync_token
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return changed, next_sync_token

    def _load_tokens(self) -> dict[str, str]:
        raw = self._settings.get(_SYNC_TOKENS_KEY)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def _save_tokens(self, tokens: dict[str, str]) -> None:
        self._settings.set(_SYNC_TOKENS_KEY, json.dumps(tokens))

    def _apply_event(self, task_repo: TaskRepository, event: dict, user_id: str) -> bool:
        event_id = event.get("id")
        if not event_id:
            return False
        task_id = _task_id_for(user_id, event_id)
        existing = task_repo.get(task_id)

        if event.get("status") == "cancelled":
            if existing is not None and existing.deleted_at is None:
                task_repo.upsert(existing.touched(deleted_at=utc_now()))
                return True
            return False

        when = _parse_when(event)
        if when is None:
            return False
        due_at, due_date, end_at, end_date = when
        title = event.get("summary") or "(No title)"
        description = _build_description(event)
        # Skip if nothing meaningful changed (avoids re-pushing on full syncs).
        if (
            existing is not None
            and existing.deleted_at is None
            and existing.title == title
            and existing.description == description
            and existing.due_at == due_at
            and existing.end_at == end_at
            and existing.due_date == due_date
            and existing.end_date == end_date
        ):
            return False

        task = Task(
            id=task_id,
            title=title,
            description=description,
            due_at=due_at,
            due_date=due_date,
            end_at=end_at,
            end_date=end_date,
            source=Source.GOOGLE,
            google_event_id=event_id,
            status=TaskStatus.PENDING,
            # Preserve the user's locally-added reminder across calendar changes.
            reminder_minutes_before=existing.reminder_minutes_before if existing and due_at is not None else None,
            created_at=existing.created_at if existing else utc_now(),
        )
        task_repo.upsert(task)
        return True

    def _prune_past(self, task_repo: TaskRepository) -> None:
        """Drop *pending* Google events that finished over a day ago, to keep lists clean.

        Completed ones are kept as history (the user checked them off in Sway).
        """
        cutoff = utc_now() - timedelta(days=1)
        for task in task_repo.list_all():
            if task.source != Source.GOOGLE or not task.is_dated or task.is_completed:
                continue
            timed_past = task.due_at is not None and (task.end_at or task.due_at) < cutoff
            dated_past = task.due_date is not None and (task.end_date or task.due_date) < cutoff.astimezone().date()
            if timed_past or dated_past:
                task_repo.upsert(task.touched(deleted_at=utc_now()))
