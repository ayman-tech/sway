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
        if task.due_at is None:
            continue
        is_google = task.is_read_only
        if is_google and task.reminder_minutes_before is None:
            continue
        if task.is_recurring:
            occurrences = occurrences_between(task, start, end)
        else:
            occurrences = [task.due_at] if start <= task.due_at <= end else []
        for occurrence in occurrences:
            if not is_google:
                events.append(ReminderEvent(occurrence, occurrence, task, "due"))
            if task.reminder_minutes_before is not None:
                fire_at = occurrence - timedelta(minutes=task.reminder_minutes_before)
                events.append(ReminderEvent(fire_at, occurrence, task, "extra"))
    return events
