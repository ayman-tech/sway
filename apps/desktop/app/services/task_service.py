"""Desktop task service backed by the local repository and shared domain rules."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QTimeZone

from app.constants import TaskStatus
from app.models.task import Task
from app.repositories.sqlite_repo import TaskRepository
from app.utils.datetime_utils import to_iso, utc_now
from sway_core.task_logic import (
    COMPLETED_RETENTION_DAYS,
    LIST_HORIZON_DAYS,
    TaskGroup,
    active_groups,
    advanced_series,
    build_new_task,
    build_updated_task,
    completed_groups,
    completed_occurrence,
    tasks_in_range,
)
from sway_core.recurrence import valid_timezone


class TaskService:
    def __init__(self, repo: TaskRepository) -> None:
        self._repo = repo

    def create_task(
        self,
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
        return self._repo.upsert(build_new_task(
            title,
            description=description,
            due_at=due_at,
            due_date=due_date,
            end_at=end_at,
            end_date=end_date,
            reminder_minutes_before=reminder_minutes_before,
            recurrence_rule=recurrence_rule,
            recurrence_timezone=recurrence_timezone,
        ))

    def update_task(
        self,
        task_id: str,
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
        existing = self._require(task_id)
        return self._repo.upsert(build_updated_task(
            existing,
            title=title,
            description=description,
            due_at=due_at,
            due_date=due_date,
            end_at=end_at,
            end_date=end_date,
            reminder_minutes_before=reminder_minutes_before,
            recurrence_rule=recurrence_rule,
            recurrence_timezone=recurrence_timezone,
        ))

    def set_reminder(self, task_id: str, reminder_minutes_before: int | None) -> Task:
        task = self._require(task_id)
        if task.due_at is None:
            reminder_minutes_before = None
        return self._repo.upsert(task.touched(reminder_minutes_before=reminder_minutes_before))

    def complete_task(self, task_id: str) -> Task:
        task = self._require(task_id)
        if task.is_recurring and task.is_dated:
            done = self._repo.upsert(completed_occurrence(task))
            self._repo.upsert(advanced_series(task))
            return done
        return self._repo.upsert(task.touched(status=TaskStatus.COMPLETED, completed_at=utc_now()))

    def skip_occurrence(self, task_id: str) -> None:
        task = self._require(task_id)
        self._repo.upsert(advanced_series(task) if task.is_recurring and task.is_dated else task.touched(deleted_at=utc_now()))

    def uncomplete_task(self, task_id: str) -> Task:
        return self._repo.upsert(self._require(task_id).touched(status=TaskStatus.PENDING, completed_at=None))

    def delete_task(self, task_id: str) -> None:
        self._repo.upsert(self._require(task_id).touched(deleted_at=utc_now()))

    def get_active_tasks(self) -> list[Task]:
        return self._repo.list_active()

    def get_completed_tasks(self) -> list[Task]:
        return self._repo.list_completed()

    def get_tasks_in_range(self, start: datetime, end: datetime) -> list[Task]:
        return tasks_in_range(
            self._repo.list_active(),
            start,
            end,
            start.astimezone().date(),
            end.astimezone().date() + timedelta(days=1),
        )

    def get_active_groups(self) -> list[TaskGroup]:
        timezone_name = valid_timezone(bytes(QTimeZone.systemTimeZoneId()).decode() or "UTC")
        return active_groups(self._repo.list_active(), timezone_name)

    def get_completed_groups(self, since: datetime | None = None) -> list[TaskGroup]:
        return completed_groups(self._repo.list_completed(to_iso(since) if since else None))

    def purge_old_completed(self) -> int:
        cutoff = utc_now() - timedelta(days=COMPLETED_RETENTION_DAYS)
        return self._repo.soft_delete_completed_before(to_iso(cutoff), to_iso(utc_now()))

    def get_task(self, task_id: str) -> Task | None:
        return self._repo.get(task_id)

    def _require(self, task_id: str) -> Task:
        task = self._repo.get(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        return task


__all__ = ["COMPLETED_RETENTION_DAYS", "LIST_HORIZON_DAYS", "TaskGroup", "TaskService"]
