"""Shared reminder event calculation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sway_core.models import Task
from sway_core.recurrence import occurrences_between


@dataclass(frozen=True)
class ReminderEvent:
    fire_at: datetime
    occurrence: datetime
    task: Task
    kind: str


def reminder_events_between(tasks: list[Task], start: datetime, end: datetime) -> list[ReminderEvent]:
    events: list[ReminderEvent] = []
    for task in tasks:
        if task.due_at is None or task.deleted_at is not None or task.status != "pending":
            continue
        is_google = task.is_read_only
        if is_google and task.reminder_minutes_before is None:
            continue
        offsets: list[tuple[str, int]] = [] if is_google else [("due", 0)]
        if task.reminder_minutes_before is not None and (is_google or task.reminder_minutes_before != 0):
            offsets.append(("extra", task.reminder_minutes_before))
        for kind, minutes in offsets:
            offset = timedelta(minutes=minutes)
            lower, upper = start + offset, end + offset
            occurrences = occurrences_between(task, lower, upper) if task.is_recurring else (
                [task.due_at] if lower <= task.due_at <= upper else []
            )
            for occurrence in occurrences:
                events.append(ReminderEvent(occurrence - offset, occurrence, task, kind))
    return events
