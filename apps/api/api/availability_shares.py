"""Expiring public availability snapshots."""

from __future__ import annotations

from datetime import timedelta
import hashlib
import re
import secrets
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from api.auth import CurrentUser, admin_client
from api.config import get_settings
from api.schemas import (
    AvailabilityShareCreate,
    AvailabilityShareCreatedOut,
    AvailabilityShareOut,
    AvailabilitySnapshot,
)
from api.settings import get_user_settings
from sway_core.datetime_utils import from_iso, utc_now

SHARE_LIFETIME = timedelta(days=7)
MAX_ACTIVE_SHARES = 20
TOKEN_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
TOKEN_GROUP_LENGTH = 4
TOKEN_GROUPS = 3
TOKEN_INSERT_ATTEMPTS = 3
TOKEN_PATTERN = re.compile(r"^[abcdefghjkmnpqrstuvwxyz23456789]{4}(?:-[abcdefghjkmnpqrstuvwxyz23456789]{4}){2}$")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_token() -> str:
    groups = [
        "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_GROUP_LENGTH))
        for _ in range(TOKEN_GROUPS)
    ]
    return "-".join(groups)


def _is_token_collision(exc: APIError) -> bool:
    raw_error = getattr(exc, "_raw_error", {})
    detail = raw_error if isinstance(raw_error, dict) else {}
    code = getattr(exc, "code", None) or detail.get("code")
    text = " ".join(
        str(value)
        for value in (
            getattr(exc, "message", None),
            getattr(exc, "details", None),
            detail.get("message"),
            detail.get("details"),
        )
        if value
    ).lower()
    return code == "23505" and "token_hash" in text


def _valid_token(token: str) -> bool:
    return bool(TOKEN_PATTERN.fullmatch(token)) or 32 <= len(token) <= 128


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid creator timezone.") from exc
    return value


def _snapshot_json(snapshot: AvailabilitySnapshot) -> dict:
    selected = sorted(value.isoformat() for value in snapshot.selected_dates)
    return {
        "selected_dates": selected,
        "start_hour": snapshot.start_hour,
        "end_hour": snapshot.end_hour,
        "available_slots": {
            date_iso: sorted(snapshot.available_slots.get(date_iso, []))
            for date_iso in selected
        },
        "busy_slots": {
            date_iso: sorted(snapshot.busy_slots.get(date_iso, []))
            for date_iso in selected
        },
    }


def _table():
    return admin_client().table("availability_shares")


def _cleanup_expired() -> None:
    _table().delete().lte("expires_at", utc_now().isoformat()).execute()


def _service_unavailable(exc: APIError) -> HTTPException:
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Availability sharing is not configured. Run the latest Supabase schema.",
    )


def create_share(user: CurrentUser, payload: AvailabilityShareCreate) -> AvailabilityShareCreatedOut:
    timezone_name = _validate_timezone(payload.creator_timezone)
    first_name = get_user_settings(user).first_name
    now = utc_now()
    expires_at = now + SHARE_LIFETIME
    snapshot = _snapshot_json(payload.snapshot)
    try:
        _cleanup_expired()
        for _attempt in range(TOKEN_INSERT_ATTEMPTS):
            token = _generate_token()
            try:
                _table().insert({
                    "id": str(uuid.uuid4()),
                    "user_id": user.id,
                    "token_hash": _token_hash(token),
                    "snapshot": snapshot,
                    "first_name": first_name,
                    "creator_timezone": timezone_name,
                    "created_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                }).execute()
                break
            except APIError as exc:
                if not _is_token_collision(exc):
                    raise
        else:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Unable to create a unique availability link. Please try again.",
            )
        active = (
            _table()
            .select("id")
            .eq("user_id", user.id)
            .gt("expires_at", now.isoformat())
            .order("created_at", desc=True)
            .execute()
        )
        stale_ids = [row["id"] for row in (active.data or [])[MAX_ACTIVE_SHARES:]]
        if stale_ids:
            _table().delete().in_("id", stale_ids).execute()
    except APIError as exc:
        raise _service_unavailable(exc) from exc
    url = f"{get_settings().web_public_url.rstrip('/')}/availability/share/{token}"
    return AvailabilityShareCreatedOut(url=url, expires_at=expires_at)


def get_share(token: str) -> AvailabilityShareOut:
    if not _valid_token(token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Availability share not found or expired.")
    now = utc_now()
    try:
        _cleanup_expired()
        result = (
            _table()
            .select("snapshot,first_name,creator_timezone,created_at,expires_at")
            .eq("token_hash", _token_hash(token))
            .gt("expires_at", now.isoformat())
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise _service_unavailable(exc) from exc
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Availability share not found or expired.")
    row = result.data[0]
    return AvailabilityShareOut(
        snapshot=AvailabilitySnapshot.model_validate(row["snapshot"]),
        first_name=row.get("first_name"),
        creator_timezone=row["creator_timezone"],
        created_at=from_iso(row["created_at"]),
        expires_at=from_iso(row["expires_at"]),
    )
