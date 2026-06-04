"""Datetime helpers.

Rule (from the plan): all datetimes are stored in UTC as ISO-8601 strings, and are
only converted to local time in the UI layer.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def to_iso(dt: datetime | None) -> str | None:
    """Serialize a datetime to a UTC ISO-8601 string. Naive datetimes are assumed UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def from_iso(value: str | None) -> datetime | None:
    """Parse a stored ISO-8601 string back into a timezone-aware UTC datetime."""
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime | None) -> datetime | None:
    """Convert a UTC datetime to the system local timezone (for display only)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()
