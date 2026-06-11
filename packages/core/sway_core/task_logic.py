"""Shared task rules and view grouping."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sway_core.constants import Source, TaskStatus
from sway_core.datetime_utils import to_iso, utc_now
from sway_core.models import Task
from sway_core.recurrence import (
    date_occurrences_between,
    next_date_occurrence,
    next_timed_occurrence,
    timed_occurrences_between,
    valid_timezone,
)

LIST_HORIZON_DAYS = 30
COMPLETED_RETENTION_DAYS = 30


@dataclass
class TaskGroup:
    label: str
    tasks: list[Task] = field(default_factory=list)
    overdue: bool = False
    has_more: bool = False


def _normalize_schedule(
    due_at: datetime | None,
    due_date: date | None,
    end_at: datetime | None,
    end_date: date | None,
    reminder_minutes_before: int | None,
    recurrence_rule: str | None,
    recurrence_timezone: str | None,
) -> tuple[datetime | None, date | None, datetime | None, date | None, int | None, str | None, str | None]:
    if due_at is not None and due_date is not None:
        raise ValueError("A task cannot have both a due time and an all-day date.")
    if due_at is not None:
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        due_at = due_at.astimezone(timezone.utc)
        if end_at is not None and end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)
        end_at = end_at.astimezone(timezone.utc) if end_at and end_at > due_at else None
        end_date = None
        due_date = None
        recurrence_timezone = valid_timezone(recurrence_timezone) if recurrence_rule else None
    elif due_date is not None:
        due_at = None
        end_at = None
        end_date = end_date if end_date and end_date > due_date else None
        reminder_minutes_before = None
        recurrence_timezone = None
    else:
        due_at = None
        due_date = None
        end_at = None
        end_date = None
        reminder_minutes_before = None
        recurrence_rule = None
        recurrence_timezone = None
    return due_at, due_date, end_at, end_date, reminder_minutes_before, recurrence_rule, recurrence_timezone


def build_new_task(
    title: str,
    *,
    description: str | None = None,
    due_at: datetime | None = None,
    due_date: date | None = None,
    end_at: datetime | None = None,
    end_date: date | None = None,
    reminder_minutes_before: int | None = None,
    recurrence_rule: str | None = None,
    recurrence_timezone: str | None = None,
) -> Task:
    title = (title or "").strip()
    if not title:
        raise ValueError("Task title cannot be empty.")
    schedule = _normalize_schedule(
        due_at, due_date, end_at, end_date, reminder_minutes_before, recurrence_rule, recurrence_timezone
    )
    return Task(
        title=title,
        description=description or None,
        due_at=schedule[0],
        due_date=schedule[1],
        end_at=schedule[2],
        end_date=schedule[3],
        reminder_minutes_before=schedule[4],
        recurrence_rule=schedule[5],
        recurrence_timezone=schedule[6],
    )


def build_updated_task(
    existing: Task,
    *,
    title: str,
    description: str | None,
    due_at: datetime | None,
    due_date: date | None,
    end_at: datetime | None = None,
    end_date: date | None = None,
    reminder_minutes_before: int | None,
    recurrence_rule: str | None = None,
    recurrence_timezone: str | None = None,
) -> Task:
    title = (title or "").strip()
    if not title:
        raise ValueError("Task title cannot be empty.")
    schedule = _normalize_schedule(
        due_at, due_date, end_at, end_date, reminder_minutes_before, recurrence_rule, recurrence_timezone
    )
    return existing.touched(
        title=title,
        description=description or None,
        due_at=schedule[0],
        due_date=schedule[1],
        end_at=schedule[2],
        end_date=schedule[3],
        reminder_minutes_before=schedule[4],
        recurrence_rule=schedule[5],
        recurrence_timezone=schedule[6],
    )


def occurrence_key(task: Task) -> str:
    return task.due_date.isoformat() if task.due_date is not None else (to_iso(task.due_at) or "undated")


def completed_occurrence(series: Task) -> Task:
    done_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"sway-occurrence:{series.id}:{occurrence_key(series)}"))
    return Task(
        id=done_id,
        title=series.title,
        description=series.description,
        due_at=series.due_at,
        due_date=series.due_date,
        end_at=series.end_at,
        end_date=series.end_date,
        status=TaskStatus.COMPLETED,
        completed_at=utc_now(),
        recurrence_parent_id=series.id,
        source=series.source,
    )


def advanced_series(series: Task) -> Task:
    if series.due_at is not None:
        upcoming = next_timed_occurrence(series, series.due_at)
        if upcoming is None:
            return series.touched(deleted_at=utc_now())
        duration = series.end_at - series.due_at if series.end_at else None
        return series.touched(due_at=upcoming, end_at=upcoming + duration if duration else None)
    if series.due_date is not None:
        upcoming_date = next_date_occurrence(series, series.due_date)
        if upcoming_date is None:
            return series.touched(deleted_at=utc_now())
        span = series.end_date - series.due_date if series.end_date else None
        return series.touched(due_date=upcoming_date, end_date=upcoming_date + span if span else None)
    return series.touched(deleted_at=utc_now())


def occurrences_as_tasks(
    series: Task,
    start: datetime,
    end: datetime,
    start_date: date,
    end_date: date,
) -> list[Task]:
    if series.due_at is not None:
        duration = series.end_at - series.due_at if series.end_at else None
        return [
            replace(series, due_at=occ, end_at=occ + duration if duration else None, is_preview=occ != series.due_at)
            for occ in timed_occurrences_between(series, start, end)
        ]
    if series.due_date is not None:
        span = series.end_date - series.due_date if series.end_date else None
        return [
            replace(series, due_date=occ, end_date=occ + span if span else None, is_preview=occ != series.due_date)
            for occ in date_occurrences_between(series, start_date, end_date)
        ]
    return []


def _task_date(task: Task, timezone_name: str) -> date | None:
    if task.due_date is not None:
        return task.due_date
    if task.due_at is not None:
        return task.due_at.astimezone(ZoneInfo(valid_timezone(timezone_name))).date()
    return None


def active_display_tasks(tasks: list[Task], timezone_name: str = "UTC") -> list[Task]:
    now = utc_now()
    today = datetime.now(ZoneInfo(valid_timezone(timezone_name))).date()
    horizon = now + timedelta(days=LIST_HORIZON_DAYS)
    horizon_date = today + timedelta(days=LIST_HORIZON_DAYS)
    display: list[Task] = []
    for task in tasks:
        if task.is_recurring and task.is_dated:
            task_due = _task_date(task, timezone_name)
            if (task.due_at is not None and task.due_at > horizon) or (
                task_due is not None and task.due_date is not None and task_due > horizon_date
            ):
                continue
            display.append(task)
            for occurrence in occurrences_as_tasks(task, now, horizon, today, horizon_date):
                if occurrence_key(occurrence) != occurrence_key(task):
                    display.append(occurrence)
        elif task.due_at is None or task.due_at <= horizon:
            if task.due_date is None or task.due_date <= horizon_date:
                display.append(task)
    return display


def _all_day_overlaps(task: Task, start: date, end: date) -> bool:
    if task.due_date is None:
        return False
    task_end = task.end_date or (task.due_date + timedelta(days=1))
    return task.due_date < end and task_end > start


def tasks_in_range(tasks: list[Task], start: datetime, end: datetime, start_date: date, end_date: date) -> list[Task]:
    result: list[Task] = []
    for task in tasks:
        if not task.is_dated:
            continue
        if task.is_recurring:
            result.extend(occurrences_as_tasks(task, start, end, start_date, end_date))
        elif task.due_at is not None and start <= task.due_at <= end:
            result.append(task)
        elif _all_day_overlaps(task, start_date, end_date):
            result.append(task)
    return result


_LATER_HORIZON_DAYS = 30


def active_groups(tasks: list[Task], timezone_name: str = "UTC") -> list[TaskGroup]:
    today = datetime.now(ZoneInfo(valid_timezone(timezone_name))).date()
    week_end = today + timedelta(days=7)
    later_cutoff = today + timedelta(days=_LATER_HORIZON_DAYS)
    buckets: dict[str, list[Task]] = {"Overdue": [], "Today": [], "Next 7 Days": [], "Untimed": [], "Later": []}
    later_overflow = 0
    for task in active_display_tasks(tasks, timezone_name):
        due = _task_date(task, timezone_name)
        if due is None:
            buckets["Untimed"].append(task)
        elif due < today:
            buckets["Overdue"].append(task)
        elif due == today:
            buckets["Today"].append(task)
        elif due <= week_end:
            buckets["Next 7 Days"].append(task)
        elif due <= later_cutoff:
            buckets["Later"].append(task)
        else:
            later_overflow += 1
    for name in ("Overdue", "Today", "Next 7 Days", "Later"):
        buckets[name].sort(
            key=lambda task: (
                _task_date(task, timezone_name) or date.max,
                task.due_at is None,
                task.due_at or datetime.max.replace(tzinfo=timezone.utc),
            )
        )
    buckets["Untimed"].sort(key=lambda task: task.created_at, reverse=True)
    groups = []
    for name, bucket in buckets.items():
        if not bucket and not (name == "Later" and later_overflow):
            continue
        has_more = name == "Later" and later_overflow > 0
        groups.append(TaskGroup(name, bucket, overdue=name == "Overdue", has_more=has_more))
    return groups


def completed_groups(tasks: list[Task], today: date | None = None) -> list[TaskGroup]:
    today = today or datetime.now().astimezone().date()
    buckets: "OrderedDict[date | None, list[Task]]" = OrderedDict()
    for task in tasks:
        completed_date = task.completed_at.astimezone().date() if task.completed_at else None
        buckets.setdefault(completed_date, []).append(task)
    return [TaskGroup(completed_label(day, today), bucket) for day, bucket in buckets.items()]


def completed_label(day: date | None, today: date) -> str:
    if day is None:
        return "Completed"
    delta = (today - day).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    return day.strftime("%a, %d %b %Y")


def is_user_editable(task: Task) -> bool:
    return task.source != Source.GOOGLE
