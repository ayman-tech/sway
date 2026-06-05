"""Shared task rules and view grouping."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone

from sway_core.constants import Source, TaskStatus
from sway_core.datetime_utils import to_iso, to_local, utc_now
from sway_core.models import Task
from sway_core.recurrence import next_occurrence, occurrences_between

LIST_HORIZON_DAYS = 30
COMPLETED_RETENTION_DAYS = 30


@dataclass
class TaskGroup:
    label: str
    tasks: list[Task] = field(default_factory=list)
    overdue: bool = False


def valid_end(due_at: datetime | None, end_at: datetime | None, has_time: bool) -> datetime | None:
    if not has_time or due_at is None or end_at is None:
        return None
    return end_at if end_at > due_at else None


def build_new_task(
    title: str,
    *,
    description: str | None = None,
    due_at: datetime | None = None,
    has_time: bool = False,
    end_at: datetime | None = None,
    reminder_minutes_before: int | None = None,
    recurrence_rule: str | None = None,
) -> Task:
    title = (title or "").strip()
    if not title:
        raise ValueError("Task title cannot be empty.")
    has_time = bool(due_at and has_time)
    if not has_time:
        reminder_minutes_before = None
    end_at = valid_end(due_at, end_at, has_time)
    if due_at is None:
        recurrence_rule = None
    return Task(
        title=title,
        description=(description or None),
        due_at=due_at,
        has_time=has_time,
        end_at=end_at,
        reminder_minutes_before=reminder_minutes_before,
        recurrence_rule=recurrence_rule,
    )


def build_updated_task(
    existing: Task,
    *,
    title: str,
    description: str | None,
    due_at: datetime | None,
    has_time: bool,
    end_at: datetime | None = None,
    reminder_minutes_before: int | None,
    recurrence_rule: str | None = None,
) -> Task:
    title = (title or "").strip()
    if not title:
        raise ValueError("Task title cannot be empty.")
    has_time = bool(due_at and has_time)
    if not has_time:
        reminder_minutes_before = None
    end_at = valid_end(due_at, end_at, has_time)
    if due_at is None:
        recurrence_rule = None
    return existing.touched(
        title=title,
        description=(description or None),
        due_at=due_at,
        has_time=has_time,
        end_at=end_at,
        reminder_minutes_before=reminder_minutes_before,
        recurrence_rule=recurrence_rule,
    )


def completed_occurrence(series: Task) -> Task:
    done_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"sway-occurrence:{series.id}:{to_iso(series.due_at)}"))
    return Task(
        id=done_id,
        title=series.title,
        description=series.description,
        due_at=series.due_at,
        has_time=series.has_time,
        status=TaskStatus.COMPLETED,
        completed_at=utc_now(),
        recurrence_parent_id=series.id,
        source=series.source,
    )


def advanced_series(series: Task) -> Task:
    upcoming = next_occurrence(series, series.due_at) if series.due_at is not None else None
    if upcoming is None:
        return series.touched(deleted_at=utc_now())
    return series.touched(due_at=upcoming)


def occurrences_as_tasks(series: Task, start: datetime, end: datetime) -> list[Task]:
    if series.due_at is None:
        return []

    def is_current(occ: datetime) -> bool:
        return abs((occ - series.due_at).total_seconds()) < 1

    duration = series.end_at - series.due_at if series.end_at is not None else None
    return [
        replace(
            series,
            due_at=occ,
            end_at=(occ + duration) if duration is not None else None,
            is_preview=not is_current(occ),
        )
        for occ in occurrences_between(series, start, end)
    ]


def _active_recurring_display_tasks(series: Task, horizon: datetime) -> list[Task]:
    """List-view expansion: current occurrence plus previews up to the horizon.

    A neglected recurring task can have an old current due date. Expanding from that
    date to the horizon creates a long backlog of virtual previews, so the list only
    keeps the actionable current occurrence and future previews.
    """
    if series.due_at is None:
        return []
    if series.due_at > horizon:
        return []
    display = [series]
    preview_start = max(utc_now(), series.due_at)
    for occurrence in occurrences_as_tasks(series, preview_start, horizon):
        if occurrence.due_at != series.due_at:
            display.append(occurrence)
    return display


def active_display_tasks(tasks: list[Task], horizon: datetime | None = None) -> list[Task]:
    horizon = horizon or (utc_now() + timedelta(days=LIST_HORIZON_DAYS))
    display: list[Task] = []
    for task in tasks:
        if task.is_recurring and task.due_at is not None:
            display.extend(_active_recurring_display_tasks(task, horizon))
        elif task.due_at is None or task.due_at <= horizon:
            display.append(task)
        else:
            continue
    return display


def tasks_in_range(tasks: list[Task], start: datetime, end: datetime) -> list[Task]:
    result: list[Task] = []
    for task in tasks:
        if task.due_at is None:
            continue
        if task.is_recurring:
            result.extend(occurrences_as_tasks(task, start, end))
        elif start <= task.due_at <= end:
            result.append(task)
    return result


def active_groups(tasks: list[Task]) -> list[TaskGroup]:
    today = datetime.now().astimezone().date()
    week_end = today + timedelta(days=7)
    overdue: list[Task] = []
    today_tasks: list[Task] = []
    next7: list[Task] = []
    untimed: list[Task] = []
    later: list[Task] = []

    for task in active_display_tasks(tasks):
        if task.due_at is None:
            untimed.append(task)
            continue
        local_due = to_local(task.due_at)
        if local_due is None:
            untimed.append(task)
            continue
        d = local_due.date()
        if d < today:
            overdue.append(task)
        elif d == today:
            today_tasks.append(task)
        elif d <= week_end:
            next7.append(task)
        else:
            later.append(task)

    for bucket in (overdue, today_tasks, next7, later):
        bucket.sort(key=lambda t: t.due_at or datetime.max.replace(tzinfo=timezone.utc))
    untimed.sort(key=lambda t: t.created_at, reverse=True)

    groups = [
        TaskGroup("Overdue", overdue, overdue=True),
        TaskGroup("Today", today_tasks),
        TaskGroup("Next 7 Days", next7),
        TaskGroup("Untimed", untimed),
        TaskGroup("Later", later),
    ]
    return [group for group in groups if group.tasks]


def completed_groups(tasks: list[Task], today: date | None = None) -> list[TaskGroup]:
    today = today or datetime.now().astimezone().date()
    buckets: "OrderedDict[date | None, list[Task]]" = OrderedDict()
    for task in tasks:
        d = to_local(task.completed_at).date() if task.completed_at else None
        buckets.setdefault(d, []).append(task)
    return [TaskGroup(completed_label(d, today), bucket) for d, bucket in buckets.items()]


def completed_label(d: date | None, today: date) -> str:
    if d is None:
        return "Completed"
    delta = (today - d).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    return d.strftime("%a, %d %b %Y")


def is_user_editable(task: Task) -> bool:
    return task.source != Source.GOOGLE
