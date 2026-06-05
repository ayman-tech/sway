"""TaskService: business logic for tasks. UI talks to this, never to the repo directly."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

from app.constants import TaskStatus
from app.models.task import Task
from app.repositories.sqlite_repo import TaskRepository
from app.services.recurrence import next_occurrence, occurrences_between
from app.utils.datetime_utils import to_iso, to_local, utc_now

# How far ahead the list view expands recurring occurrences.
LIST_HORIZON_DAYS = 30
# Completed tasks older than this are removed (and the Completed view is bounded to it).
COMPLETED_RETENTION_DAYS = 30


def _valid_end(due_at: datetime | None, end_at: datetime | None, has_time: bool) -> datetime | None:
    """An end time is only kept for timed tasks and must be strictly after the due time."""
    if not has_time or due_at is None or end_at is None:
        return None
    return end_at if end_at > due_at else None


@dataclass
class TaskGroup:
    """A labelled section of tasks for the grouped list views."""

    label: str
    tasks: list[Task] = field(default_factory=list)
    overdue: bool = False


class TaskService:
    def __init__(self, repo: TaskRepository) -> None:
        self._repo = repo

    def create_task(
        self,
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
        # Reminders and a duration (end_at) only make sense for tasks with a clock time.
        if not has_time:
            reminder_minutes_before = None
        end_at = _valid_end(due_at, end_at, has_time)
        # Recurrence needs an anchor date.
        if due_at is None:
            recurrence_rule = None
        task = Task(
            title=title,
            description=(description or None),
            due_at=due_at,
            has_time=has_time,
            end_at=end_at,
            reminder_minutes_before=reminder_minutes_before,
            recurrence_rule=recurrence_rule,
        )
        return self._repo.upsert(task)

    def update_task(
        self,
        task_id: str,
        *,
        title: str,
        description: str | None,
        due_at: datetime | None,
        has_time: bool,
        end_at: datetime | None = None,
        reminder_minutes_before: int | None,
        recurrence_rule: str | None = None,
    ) -> Task:
        existing = self._require(task_id)
        title = (title or "").strip()
        if not title:
            raise ValueError("Task title cannot be empty.")
        has_time = bool(due_at and has_time)
        if not has_time:
            reminder_minutes_before = None
        end_at = _valid_end(due_at, end_at, has_time)
        if due_at is None:
            recurrence_rule = None
        updated = existing.touched(
            title=title,
            description=(description or None),
            due_at=due_at,
            has_time=has_time,
            end_at=end_at,
            reminder_minutes_before=reminder_minutes_before,
            recurrence_rule=recurrence_rule,
        )
        return self._repo.upsert(updated)

    def set_reminder(self, task_id: str, reminder_minutes_before: int | None) -> Task:
        """Update only the additional reminder (used for read-only Google events)."""
        task = self._require(task_id)
        if not (task.due_at and task.has_time):
            reminder_minutes_before = None
        return self._repo.upsert(
            task.touched(reminder_minutes_before=reminder_minutes_before)
        )

    def complete_task(self, task_id: str) -> Task:
        task = self._require(task_id)
        if task.is_recurring and task.due_at is not None:
            return self._complete_occurrence(task)
        updated = task.touched(status=TaskStatus.COMPLETED, completed_at=utc_now())
        return self._repo.upsert(updated)

    def _complete_occurrence(self, series: Task) -> Task:
        """Complete the current occurrence of a recurring series.

        Records the current occurrence as its own completed task (for history / the
        Completed view) and advances the series to its next occurrence.
        """
        # Deterministic id from (series, occurrence) so two devices completing the same
        # occurrence converge to ONE completed row instead of creating duplicates.
        done_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"sway-occurrence:{series.id}:{to_iso(series.due_at)}")
        )
        done = Task(
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
        self._repo.upsert(done)
        self._advance_series(series)
        return done

    def skip_occurrence(self, task_id: str) -> None:
        """Delete just the current occurrence of a recurring series (no completion record).

        Advances the series to its next occurrence; soft-deletes the series if exhausted.
        Falls back to a plain delete for non-recurring tasks.
        """
        series = self._require(task_id)
        if not (series.is_recurring and series.due_at is not None):
            self._repo.upsert(series.touched(deleted_at=utc_now()))
            return
        self._advance_series(series)

    def _advance_series(self, series: Task) -> None:
        """Move a recurring series to its next occurrence, or soft-delete it if ended."""
        upcoming = next_occurrence(series, series.due_at)
        if upcoming is None:
            self._repo.upsert(series.touched(deleted_at=utc_now()))
        else:
            self._repo.upsert(series.touched(due_at=upcoming))

    def uncomplete_task(self, task_id: str) -> Task:
        task = self._require(task_id)
        updated = task.touched(status=TaskStatus.PENDING, completed_at=None)
        return self._repo.upsert(updated)

    def delete_task(self, task_id: str) -> None:
        """Soft delete."""
        task = self._require(task_id)
        self._repo.upsert(task.touched(deleted_at=utc_now()))

    def get_active_tasks(self) -> list[Task]:
        return self._repo.list_active()

    def get_completed_tasks(self) -> list[Task]:
        return self._repo.list_completed()

    def _occurrences_as_tasks(self, series: Task, start: datetime, end: datetime) -> list[Task]:
        """Virtual occurrence Tasks for a recurring series within [start, end].

        Each keeps the series' own id (so complete/edit/delete act on the series). The
        current occurrence (the one at series.due_at) is interactive; the rest are previews.
        """

        def is_current(occ: datetime) -> bool:
            return abs((occ - series.due_at).total_seconds()) < 1

        # Duration is constant across occurrences; shift end_at to each occurrence.
        duration = (
            series.end_at - series.due_at
            if series.end_at is not None and series.due_at is not None
            else None
        )
        return [
            replace(
                series,
                due_at=occ,
                end_at=(occ + duration) if duration is not None else None,
                is_preview=not is_current(occ),
            )
            for occ in occurrences_between(series, start, end)
        ]

    def _active_display_tasks(self, horizon: datetime) -> list[Task]:
        """Active tasks for the list view, capped to the next 30 days.

        Recurring series keep their actionable current occurrence, then only future
        preview occurrences through `horizon`. This avoids rendering a long backlog
        when a recurring task's current due date is far in the past.
        """
        tasks: list[Task] = []
        for task in self._repo.list_active():
            if task.is_recurring and task.due_at is not None:
                if task.due_at > horizon:
                    continue
                tasks.append(task)
                preview_start = max(utc_now(), task.due_at)
                for occurrence in self._occurrences_as_tasks(task, preview_start, horizon):
                    if occurrence.due_at != task.due_at:
                        tasks.append(occurrence)
            elif task.due_at is None or task.due_at <= horizon:
                tasks.append(task)
            else:
                continue
        return tasks

    def get_tasks_in_range(self, start: datetime, end: datetime) -> list[Task]:
        """Dated active tasks within [start, end], recurring series expanded. For the calendar."""
        tasks: list[Task] = []
        for task in self._repo.list_active():
            if task.due_at is None:
                continue
            if task.is_recurring:
                tasks.extend(self._occurrences_as_tasks(task, start, end))
            elif start <= task.due_at <= end:
                tasks.append(task)
        return tasks

    def get_active_groups(self) -> list[TaskGroup]:
        """Active tasks split into the five date buckets, by local calendar date.

        Buckets are mutually exclusive: Overdue (before today), Today, Next 7 Days
        (tomorrow..+7), Untimed (no due date), Later (beyond 7 days). Empty buckets
        are omitted. Dated buckets sort by due time; Untimed sorts newest-first.
        """
        today = datetime.now().astimezone().date()
        week_end = today + timedelta(days=7)
        overdue: list[Task] = []
        today_tasks: list[Task] = []
        next7: list[Task] = []
        untimed: list[Task] = []
        later: list[Task] = []

        horizon = utc_now() + timedelta(days=LIST_HORIZON_DAYS)
        for task in self._active_display_tasks(horizon):
            if task.due_at is None:
                untimed.append(task)
                continue
            d = to_local(task.due_at).date()
            if d < today:
                overdue.append(task)
            elif d == today:
                today_tasks.append(task)
            elif d <= week_end:
                next7.append(task)
            else:
                later.append(task)

        for bucket in (overdue, today_tasks, next7, later):
            bucket.sort(key=lambda t: t.due_at)
        untimed.sort(key=lambda t: t.created_at, reverse=True)

        groups = [
            TaskGroup("Overdue", overdue, overdue=True),
            TaskGroup("Today", today_tasks),
            TaskGroup("Next 7 Days", next7),
            TaskGroup("Untimed", untimed),
            TaskGroup("Later", later),
        ]
        return [g for g in groups if g.tasks]

    def get_completed_groups(self, since: datetime | None = None) -> list[TaskGroup]:
        """Completed tasks grouped by local completion date, most recent first.

        `since` bounds the query (e.g. last 30 days) so the view never renders an
        unbounded history; pass None to load everything.
        """
        today = datetime.now().astimezone().date()
        buckets: "OrderedDict[date | None, list[Task]]" = OrderedDict()
        for task in self._repo.list_completed(to_iso(since) if since else None):
            d = to_local(task.completed_at).date() if task.completed_at else None
            buckets.setdefault(d, []).append(task)
        return [TaskGroup(self._completed_label(d, today), tasks) for d, tasks in buckets.items()]

    def purge_old_completed(self) -> int:
        """Soft-delete completed tasks older than the retention window (syncs as tombstones)."""
        cutoff = utc_now() - timedelta(days=COMPLETED_RETENTION_DAYS)
        return self._repo.soft_delete_completed_before(to_iso(cutoff), to_iso(utc_now()))

    @staticmethod
    def _completed_label(d: date | None, today: date) -> str:
        if d is None:
            return "Completed"
        delta = (today - d).days
        if delta == 0:
            return "Today"
        if delta == 1:
            return "Yesterday"
        return d.strftime("%a, %d %b %Y")

    def get_task(self, task_id: str) -> Task | None:
        return self._repo.get(task_id)

    def _require(self, task_id: str) -> Task:
        task = self._repo.get(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        return task
