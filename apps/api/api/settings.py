"""User settings backed by Supabase."""

from __future__ import annotations

from api.auth import CurrentUser
from api.schemas import SettingsOut, SettingsUpdate
from postgrest.exceptions import APIError
from sway_core.datetime_utils import from_iso, to_iso

DEFAULT_SETTINGS = SettingsOut()


def get_user_settings(user: CurrentUser) -> SettingsOut:
    try:
        res = user.client.table("user_settings").select("*").eq("user_id", user.id).limit(1).execute()
    except APIError as exc:
        if exc.args and isinstance(exc.args[0], dict) and exc.args[0].get("code") == "PGRST205":
            return DEFAULT_SETTINGS
        raise
    if not res.data:
        return DEFAULT_SETTINGS
    row = res.data[0]
    return SettingsOut(
        theme=row.get("theme") or "system",
        reminders_processed_through=from_iso(row.get("reminders_processed_through")),
        browser_notifications_enabled=bool(row.get("browser_notifications_enabled")),
    )


def update_user_settings(user: CurrentUser, payload: SettingsUpdate) -> SettingsOut:
    current = get_user_settings(user)
    merged = current.model_dump()
    for key, value in payload.model_dump(exclude_unset=True).items():
        merged[key] = value
    row = {
        "user_id": user.id,
        "theme": merged["theme"],
        "reminders_processed_through": to_iso(merged["reminders_processed_through"]),
        "browser_notifications_enabled": merged["browser_notifications_enabled"],
    }
    try:
        user.client.table("user_settings").upsert(row).execute()
    except APIError as exc:
        if exc.args and isinstance(exc.args[0], dict) and exc.args[0].get("code") == "PGRST205":
            return SettingsOut(**merged)
        raise
    return get_user_settings(user)
