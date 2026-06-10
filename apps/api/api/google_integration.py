"""Centralized, encrypted Google Calendar OAuth and import."""

from __future__ import annotations

from datetime import timedelta
import json
import threading
import uuid

from fastapi import HTTPException, status
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from api.auth import CurrentUser, admin_client
from api.config import get_settings
from api.schemas import GoogleCredentialsUpdate, GoogleStatusOut, GoogleSyncOut
from api.secret_crypto import decrypt_secret, encrypt_secret, encryption_available
from api.tasks import TaskStore
from sway_core.datetime_utils import from_iso, utc_now
from sway_core.google import (
    GOOGLE_SCOPES,
    READABLE_CALENDAR_ROLES,
    google_import_window,
    task_from_google_event,
    task_id_for_google_event,
)

OAUTH_STATE_LIFETIME = timedelta(minutes=10)
SYNC_COOLDOWN = timedelta(minutes=5)
SYNC_LEASE = timedelta(minutes=5)


def _table():
    return admin_client().table("google_calendar_connections")


def _row_for_user(user_id: str) -> dict | None:
    result = _table().select("*").eq("user_id", user_id).limit(1).execute()
    return result.data[0] if result.data else None


def _client_config(row: dict) -> dict:
    return {
        "web": {
            "client_id": row["oauth_client_id"],
            "client_secret": decrypt_secret(row["oauth_client_secret_ciphertext"]),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [get_settings().google_redirect_uri],
        }
    }


def _flow(row: dict) -> Flow:
    flow = Flow.from_client_config(
        _client_config(row), scopes=GOOGLE_SCOPES, autogenerate_code_verifier=False
    )
    flow.redirect_uri = get_settings().google_redirect_uri
    return flow


def _authorization_url(row: dict) -> str:
    state = str(uuid.uuid4())
    now = utc_now()
    _table().update({
        "oauth_state": state,
        "oauth_state_created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }).eq("user_id", row["user_id"]).execute()
    url, _ = _flow(row).authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return url


def google_status(user: CurrentUser) -> GoogleStatusOut:
    row = _row_for_user(user.id)
    return GoogleStatusOut(
        configured=bool(row and row.get("oauth_client_secret_ciphertext")),
        connected=bool(row and row.get("token_ciphertext")),
        setup_available=encryption_available(),
        client_id=row.get("oauth_client_id") if row else None,
        redirect_uri=get_settings().google_redirect_uri,
        account=row.get("account_email") if row else None,
        last_synced_at=from_iso(row.get("last_synced_at")) if row else None,
        last_sync_error=row.get("last_sync_error") if row else None,
    )


def save_credentials(user: CurrentUser, payload: GoogleCredentialsUpdate) -> str:
    now = utc_now()
    client_id = payload.client_id.strip()
    client_secret = payload.client_secret.strip()
    if not client_id or not client_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Client ID and client secret are required.")
    _table().upsert({
        "user_id": user.id,
        "oauth_client_id": client_id,
        "oauth_client_secret_ciphertext": encrypt_secret(client_secret),
        "token_ciphertext": None,
        "sync_tokens_json": {},
        "account_email": None,
        "oauth_state": None,
        "oauth_state_created_at": None,
        "last_synced_at": None,
        "sync_lease_until": None,
        "last_sync_error": None,
        "updated_at": now.isoformat(),
    }).execute()
    row = _row_for_user(user.id)
    if row is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Unable to save Google credentials.")
    return _authorization_url(row)


def connect_url(user: CurrentUser) -> str:
    row = _row_for_user(user.id)
    if row is None or not row.get("oauth_client_secret_ciphertext"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google OAuth credentials are not configured.")
    return _authorization_url(row)


def oauth_callback(code: str, state: str) -> str:
    admin = admin_client()
    result = admin.table("google_calendar_connections").select("*").eq("oauth_state", state).limit(1).execute()
    if not result.data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Google OAuth state.")
    row = result.data[0]
    state_created_at = from_iso(row.get("oauth_state_created_at"))
    if state_created_at is None or state_created_at < utc_now() - OAUTH_STATE_LIFETIME:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google OAuth state has expired.")

    flow = _flow(row)
    flow.fetch_token(code=code)
    credentials = flow.credentials
    account_email = "Google Calendar"
    try:
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        account_email = service.calendarList().get(calendarId="primary").execute().get("id", account_email)
    except Exception:  # noqa: BLE001 - email is cosmetic
        pass

    now = utc_now()
    admin.table("google_calendar_connections").update({
        "token_ciphertext": encrypt_secret(credentials.to_json()),
        "sync_tokens_json": {},
        "account_email": account_email,
        "oauth_state": None,
        "oauth_state_created_at": None,
        "last_sync_error": None,
        "updated_at": now.isoformat(),
    }).eq("user_id", row["user_id"]).execute()

    user = CurrentUser(id=row["user_id"], email=None, token="", client=admin)
    threading.Thread(target=_background_sync, args=(user,), daemon=True).start()
    return f"{get_settings().web_public_url}/dashboard/settings?gcal=connected"


def _background_sync(user: CurrentUser) -> None:
    try:
        sync_google(user, force=True)
    except Exception:  # noqa: BLE001 - best-effort initial sync
        pass


def disconnect(user: CurrentUser) -> None:
    now = utc_now()
    _table().update({
        "token_ciphertext": None,
        "sync_tokens_json": {},
        "account_email": None,
        "oauth_state": None,
        "oauth_state_created_at": None,
        "last_synced_at": None,
        "sync_lease_until": None,
        "last_sync_error": None,
        "updated_at": now.isoformat(),
    }).eq("user_id", user.id).execute()


def _credentials(row: dict) -> Credentials:
    encrypted = row.get("token_ciphertext")
    if not encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google Calendar is not connected.")
    credentials = Credentials.from_authorized_user_info(
        json.loads(decrypt_secret(encrypted)),
        GOOGLE_SCOPES,
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        _table().update({
            "token_ciphertext": encrypt_secret(credentials.to_json()),
            "updated_at": utc_now().isoformat(),
        }).eq("user_id", row["user_id"]).execute()
    return credentials


def _selected_calendars(service) -> list[str]:
    ids: list[str] = []
    page_token = None
    while True:
        response = service.calendarList().list(pageToken=page_token).execute()
        for entry in response.get("items", []):
            if entry.get("selected") and entry.get("accessRole") in READABLE_CALENDAR_ROLES:
                ids.append(entry["id"])
        page_token = response.get("nextPageToken")
        if not page_token:
            return ids


def _acquire_sync_lease(row: dict, force: bool) -> bool:
    now = utc_now()
    last_synced_at = from_iso(row.get("last_synced_at"))
    if not force and last_synced_at and last_synced_at > now - SYNC_COOLDOWN:
        return False
    result = (
        _table()
        .update({"sync_lease_until": (now + SYNC_LEASE).isoformat()})
        .eq("user_id", row["user_id"])
        .or_(f"sync_lease_until.is.null,sync_lease_until.lt.{now.isoformat()}")
        .execute()
    )
    return bool(result.data)


def sync_google(user: CurrentUser, force: bool = False) -> GoogleSyncOut:
    row = _row_for_user(user.id)
    if row is None or not row.get("token_ciphertext"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google Calendar is not connected.")
    if not _acquire_sync_lease(row, force):
        return GoogleSyncOut(imported=0, skipped=True)

    try:
        changed, tokens = _import_google(user, row)
        now = utc_now()
        _table().update({
            "sync_tokens_json": tokens,
            "last_synced_at": now.isoformat(),
            "sync_lease_until": None,
            "last_sync_error": None,
            "updated_at": now.isoformat(),
        }).eq("user_id", user.id).execute()
        return GoogleSyncOut(imported=changed)
    except Exception as exc:
        _table().update({
            "sync_lease_until": None,
            "last_sync_error": str(exc)[:1000] or "Google Calendar sync failed.",
            "updated_at": utc_now().isoformat(),
        }).eq("user_id", user.id).execute()
        raise


def _import_google(user: CurrentUser, row: dict) -> tuple[int, dict[str, str]]:
    service = build("calendar", "v3", credentials=_credentials(row), cache_discovery=False)
    store = TaskStore(user)
    tokens = row.get("sync_tokens_json") or {}
    if not isinstance(tokens, dict):
        tokens = json.loads(tokens)
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
                response = service.events().list(**params).execute()
            except HttpError as exc:
                if getattr(exc, "resp", None) is not None and exc.resp.status == 410:
                    tokens.pop(calendar_id, None)
                    break
                raise
            for event in response.get("items", []):
                event_id = event.get("id")
                if not event_id:
                    continue
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
                if task is not None and (
                    existing is None
                    or existing.title != task.title
                    or existing.description != task.description
                    or existing.due_at != task.due_at
                    or existing.end_at != task.end_at
                    or existing.due_date != task.due_date
                    or existing.end_date != task.end_date
                ):
                    store.upsert(task)
                    changed += 1
            next_sync_token = response.get("nextSyncToken") or next_sync_token
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        if next_sync_token:
            tokens[calendar_id] = next_sync_token
    return changed, tokens


