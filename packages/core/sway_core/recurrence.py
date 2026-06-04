"""Recurrence helpers built on dateutil RRULE."""

from __future__ import annotations

from datetime import datetime, timezone

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


def build_rule_string(freq: str, interval: int = 1, until: datetime | None = None) -> str:
    parts = [f"FREQ={freq}"]
    if interval and interval > 1:
        parts.append(f"INTERVAL={interval}")
    if until is not None:
        parts.append("UNTIL=" + until.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    return ";".join(parts)


def parse_rule_string(rule: str) -> tuple[str, int, datetime | None]:
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


def _parse_until(value: str) -> datetime:
    value = value.rstrip("Z")
    fmt = "%Y%m%dT%H%M%S" if "T" in value else "%Y%m%d"
    return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)


def _rule(task: Task):
    return rrulestr(task.recurrence_rule, dtstart=task.due_at)


def occurrences_between(task: Task, start: datetime, end: datetime) -> list[datetime]:
    if not task.recurrence_rule or task.due_at is None or start > end:
        return []
    return list(_rule(task).between(start, end, inc=True))


def next_occurrence(task: Task, after: datetime) -> datetime | None:
    if not task.recurrence_rule or task.due_at is None:
        return None
    return _rule(task).after(after, inc=False)
