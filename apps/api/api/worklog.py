"""Hourly work log with a rolling 7-day window."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from api.auth import CurrentUser
from api.schemas import WorkLogEntryOut
from sway_core.datetime_utils import utc_now

WINDOW_DAYS = 7
# Timezones span UTC-12..UTC+14, so a client's local date is at most a day off UTC.
MAX_TODAY_SKEW = timedelta(days=1)


def window_start(today: date) -> date:
    return today - timedelta(days=WINDOW_DAYS - 1)


def validate_today(today: date, utc_today: date) -> date:
    if abs(today - utc_today) > MAX_TODAY_SKEW:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid date.")
    return today


def _is_missing_table(exc: APIError) -> bool:
    return bool(exc.args and isinstance(exc.args[0], dict) and exc.args[0].get("code") == "PGRST205")


def _unavailable() -> HTTPException:
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Work log is not configured. Run the latest Supabase schema.",
    )


def _table(user: CurrentUser):
    return user.client.table("work_log_entries")


def _prune(user: CurrentUser, today: date) -> None:
    _table(user).delete().eq("user_id", user.id).lt("entry_date", window_start(today).isoformat()).execute()


def list_entries(user: CurrentUser, today: date) -> list[WorkLogEntryOut]:
    validate_today(today, utc_now().date())
    try:
        _prune(user, today)
        res = (
            _table(user)
            .select("entry_date,hour_slot,note")
            .eq("user_id", user.id)
            .gte("entry_date", window_start(today).isoformat())
            .lte("entry_date", today.isoformat())
            .order("entry_date")
            .order("hour_slot")
            .execute()
        )
    except APIError as exc:
        if _is_missing_table(exc):
            raise _unavailable() from exc
        raise
    return [WorkLogEntryOut(**row) for row in res.data or []]


def put_entry(user: CurrentUser, entry_date: date, hour: int, note: str, today: date) -> WorkLogEntryOut:
    validate_today(today, utc_now().date())
    if not 0 <= hour <= 23:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Hour must be between 0 and 23.")
    if not window_start(today) <= entry_date <= today:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Date is outside the last 7 days.")
    text = note.strip()
    key = {"user_id": user.id, "entry_date": entry_date.isoformat(), "hour_slot": hour}
    try:
        _prune(user, today)
        if text:
            _table(user).upsert({**key, "note": text}, on_conflict="user_id,entry_date,hour_slot").execute()
        else:
            _table(user).delete().match(key).execute()
    except APIError as exc:
        if _is_missing_table(exc):
            raise _unavailable() from exc
        raise
    return WorkLogEntryOut(entry_date=entry_date, hour_slot=hour, note=text)
