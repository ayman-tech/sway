"""Google Calendar web OAuth and import."""

from __future__ import annotations

import json
import uuid

from fastapi import HTTPException, status
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from api.auth import CurrentUser, admin_client
from api.config import get_settings
from api.tasks import TaskStore
from sway_core.datetime_utils import utc_now
from sway_core.google import (
    GOOGLE_SCOPES,
    READABLE_CALENDAR_ROLES,
    google_import_window,
    task_from_google_event,
    task_id_for_google_event,
)


def _client_config() -> dict:
    settings = get_settings()
    if not (settings.google_client_id and settings.google_client_secret):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google OAuth is not configured.")
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def _flow() -> Flow:
    flow = Flow.from_client_config(_client_config(), scopes=GOOGLE_SCOPES)
    flow.redirect_uri = get_settings().google_redirect_uri
    return flow


def google_status(user: CurrentUser) -> tuple[bool, str | None]:
    res = admin_client().table("google_calendar_connections").select("*").eq("user_id", user.id).limit(1).execute()
    if not res.data:
        return False, None
    return bool(res.data[0].get("token_json")), res.data[0].get("account_email")


def connect_url(user: CurrentUser) -> str:
    state = str(uuid.uuid4())
    admin_client().table("google_calendar_connections").upsert({
        "user_id": user.id,
        "oauth_state": state,
        "updated_at": utc_now().isoformat(),
    }).execute()
    url, _ = _flow().authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
        include_granted_scopes="true",
    )
    return url


def oauth_callback(code: str, state: str) -> str:
    admin = admin_client()
    res = admin.table("google_calendar_connections").select("*").eq("oauth_state", state).limit(1).execute()
    if not res.data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Google OAuth state.")
    row = res.data[0]
    flow = _flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    account_email = "Google Calendar"
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        account_email = service.calendarList().get(calendarId="primary").execute().get("id", account_email)
    except Exception:  # noqa: BLE001
        pass
    admin.table("google_calendar_connections").upsert({
        "user_id": row["user_id"],
        "token_json": json.loads(creds.to_json()),
        "sync_tokens_json": {},
        "account_email": account_email,
        "oauth_state": None,
        "updated_at": utc_now().isoformat(),
    }).execute()
    return f"{get_settings().web_public_url.rstrip('/')}/dashboard/settings?google=connected"


def disconnect(user: CurrentUser) -> None:
    admin_client().table("google_calendar_connections").delete().eq("user_id", user.id).execute()


def _credentials(row: dict) -> Credentials:
    raw = row.get("token_json")
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google Calendar is not connected.")
    info = raw if isinstance(raw, dict) else json.loads(raw)
    creds = Credentials.from_authorized_user_info(info, GOOGLE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        admin_client().table("google_calendar_connections").update({
            "token_json": json.loads(creds.to_json()),
            "updated_at": utc_now().isoformat(),
        }).eq("user_id", row["user_id"]).execute()
    return creds


def _selected_calendars(service) -> list[str]:
    ids: list[str] = []
    page_token = None
    while True:
        resp = service.calendarList().list(pageToken=page_token).execute()
        for entry in resp.get("items", []):
            if entry.get("selected") and entry.get("accessRole") in READABLE_CALENDAR_ROLES:
                ids.append(entry["id"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            return ids


def _load_tokens(row: dict) -> dict[str, str]:
    raw = row.get("sync_tokens_json") or "{}"
    try:
        return raw if isinstance(raw, dict) else json.loads(raw)
    except ValueError:
        return {}


def sync_google(user: CurrentUser) -> int:
    admin = admin_client()
    res = admin.table("google_calendar_connections").select("*").eq("user_id", user.id).limit(1).execute()
    if not res.data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google Calendar is not connected.")
    row = res.data[0]
    creds = _credentials(row)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    store = TaskStore(user)
    tokens = _load_tokens(row)
    changed = 0

    for calendar_id in _selected_calendars(service):
        sync_token = tokens.get(calendar_id)
        page_token = None
        next_sync_token = None
        while True:
            if sync_token:
                params = {"calendarId": calendar_id, "maxResults": 250, "syncToken": sync_token}
            else:
                time_min, time_max = google_import_window()
                params = {
                    "calendarId": calendar_id,
                    "singleEvents": True,
                    "orderBy": "startTime",
                    "maxResults": 250,
                    "timeMin": time_min,
                    "timeMax": time_max,
                }
            if page_token:
                params["pageToken"] = page_token
            try:
                resp = service.events().list(**params).execute()
            except HttpError as exc:
                if getattr(exc, "resp", None) is not None and exc.resp.status == 410:
                    tokens.pop(calendar_id, None)
                    break
                raise
            for event in resp.get("items", []):
                event_id = event.get("id")
                if not event_id:
                    continue
                existing = None
                try:
                    existing = store.get(task_id_for_google_event(user.id, event_id))
                except HTTPException:
                    existing = None
                if event.get("status") == "cancelled":
                    if existing and existing.deleted_at is None:
                        store.upsert(existing.touched(deleted_at=utc_now()))
                        changed += 1
                    continue
                task = task_from_google_event(event, user.id, existing)
                if task is not None:
                    if (
                        existing is None
                        or existing.title != task.title
                        or existing.description != task.description
                        or existing.due_at != task.due_at
                        or existing.end_at != task.end_at
                        or existing.has_time != task.has_time
                    ):
                        store.upsert(task)
                        changed += 1
            next_sync_token = resp.get("nextSyncToken") or next_sync_token
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        if next_sync_token:
            tokens[calendar_id] = next_sync_token

    admin.table("google_calendar_connections").update({
        "sync_tokens_json": tokens,
        "updated_at": utc_now().isoformat(),
    }).eq("user_id", user.id).execute()
    return changed
