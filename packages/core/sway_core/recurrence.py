"""Recurrence helpers built on dateutil RRULE."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr

from sway_core.models import Task

REPEAT_OPTIONS: list[tuple[str, tuple[str, int] | None]] = [
    ("Don't repeat", None),
    ("Daily", ("DAILY", 1)),
    ("Weekly", ("WEEKLY", 1)),
    ("Every 2 weeks", ("WEEKLY", 2)),
    ("Monthly", ("MONTHLY", 1)),
    ("Yearly", ("YEARLY", 1)),
]


def build_rule_string(freq: str, interval: int = 1, until: datetime | date | None = None) -> str:
    parts = [f"FREQ={freq}"]
    if interval and interval > 1:
        parts.append(f"INTERVAL={interval}")
    if isinstance(until, datetime):
        parts.append("UNTIL=" + until.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    elif until is not None:
        parts.append("UNTIL=" + until.strftime("%Y%m%d"))
    return ";".join(parts)


def parse_rule_string(rule: str) -> tuple[str, int, datetime | date | None]:
    freq, interval, until = "DAILY", 1, None
    for part in rule.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.upper()
        if key == "FREQ":
            freq = value.upper()
        elif key == "INTERVAL":
            interval = int(value)
        elif key == "UNTIL":
            until = _parse_until(value)
    return freq, interval, until


def _parse_until(value: str) -> datetime | date:
    value = value.rstrip("Z")
    if "T" not in value:
        return datetime.strptime(value, "%Y%m%d").date()
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def valid_timezone(value: str | None) -> str:
    if not value:
        return "UTC"
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return "UTC"
    return value


def _timed_rule_text(rule: str, zone: ZoneInfo) -> str:
    parts: list[str] = []
    for part in rule.split(";"):
        if part.startswith("UNTIL=") and "T" in part:
            until = _parse_until(part.split("=", 1)[1])
            if isinstance(until, datetime):
                part = "UNTIL=" + until.astimezone(zone).strftime("%Y%m%dT%H%M%S")
        parts.append(part)
    return ";".join(parts)


def timed_occurrences_between(task: Task, start: datetime, end: datetime) -> list[datetime]:
    if not task.recurrence_rule or task.due_at is None or start > end:
        return []
    zone = ZoneInfo(valid_timezone(task.recurrence_timezone))
    local_start = task.due_at.astimezone(zone).replace(tzinfo=None)
    rule = rrulestr(_timed_rule_text(task.recurrence_rule, zone), dtstart=local_start, ignoretz=True)
    lower = start.astimezone(zone).replace(tzinfo=None)
    upper = end.astimezone(zone).replace(tzinfo=None)
    return [
        occurrence.replace(tzinfo=zone).astimezone(timezone.utc)
        for occurrence in rule.between(lower, upper, inc=True)
    ]


def next_timed_occurrence(task: Task, after: datetime) -> datetime | None:
    if not task.recurrence_rule or task.due_at is None:
        return None
    zone = ZoneInfo(valid_timezone(task.recurrence_timezone))
    local_start = task.due_at.astimezone(zone).replace(tzinfo=None)
    rule = rrulestr(_timed_rule_text(task.recurrence_rule, zone), dtstart=local_start, ignoretz=True)
    occurrence = rule.after(after.astimezone(zone).replace(tzinfo=None), inc=False)
    return occurrence.replace(tzinfo=zone).astimezone(timezone.utc) if occurrence else None


def date_occurrences_between(task: Task, start: date, end: date) -> list[date]:
    if not task.recurrence_rule or task.due_date is None or start > end:
        return []
    rule = rrulestr(task.recurrence_rule, dtstart=datetime.combine(task.due_date, time.min), ignoretz=True)
    return [value.date() for value in rule.between(datetime.combine(start, time.min), datetime.combine(end, time.max), inc=True)]


def next_date_occurrence(task: Task, after: date) -> date | None:
    if not task.recurrence_rule or task.due_date is None:
        return None
    rule = rrulestr(task.recurrence_rule, dtstart=datetime.combine(task.due_date, time.min), ignoretz=True)
    occurrence = rule.after(datetime.combine(after, time.min), inc=False)
    return occurrence.date() if occurrence else None


def occurrences_between(task: Task, start: datetime, end: datetime) -> list[datetime]:
    return timed_occurrences_between(task, start, end)


def next_occurrence(task: Task, after: datetime) -> datetime | None:
    return next_timed_occurrence(task, after)
