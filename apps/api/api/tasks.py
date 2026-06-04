"""Task repository and service helpers for Supabase-backed web tasks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from api.auth import CurrentUser
from api.schemas import TaskCreate, TaskOut, TaskUpdate
from sway_core.constants import Source, TaskStatus
from sway_core.datetime_utils import to_iso, utc_now
from sway_core.models import Task
from sway_core.task_logic import (
    COMPLETED_RETENTION_DAYS,
    active_groups,
    advanced_series,
    build_new_task,
    build_updated_task,
    completed_groups,
    completed_occurrence,
    tasks_in_range,
)


def task_to_row(task: Task, user_id: str) -> dict:
    return {
        "id": task.id,
        "user_id": user_id,
        "title": task.title,
        "description": task.description,
        "project_id": task.project_id,
        "priority": int(task.priority),
        "status": str(task.status),
        "due_at": to_iso(task.due_at),
        "has_time": bool(task.has_time),
        "start_at": to_iso(task.start_at),
        "end_at": to_iso(task.end_at),
        "reminder_minutes_before": task.reminder_minutes_before,
        "recurrence_rule": task.recurrence_rule,
        "recurrence_parent_id": task.recurrence_parent_id,
        "google_event_id": task.google_event_id,
        "source": str(task.source),
        "completed_at": to_iso(task.completed_at),
        "created_at": to_iso(task.created_at),
        "updated_at": to_iso(task.updated_at),
        "deleted_at": to_iso(task.deleted_at),
    }


def task_from_row(row: dict) -> Task:
    from sway_core.datetime_utils import from_iso

    return Task(
        id=row["id"],
        title=row["title"],
        description=row.get("description"),
        project_id=row.get("project_id"),
        priority=row.get("priority") or 0,
        status=row.get("status") or "pending",
        due_at=from_iso(row.get("due_at")),
        has_time=bool(row.get("has_time")),
        start_at=from_iso(row.get("start_at")),
        end_at=from_iso(row.get("end_at")),
        reminder_minutes_before=row.get("reminder_minutes_before"),
        recurrence_rule=row.get("recurrence_rule"),
        recurrence_parent_id=row.get("recurrence_parent_id"),
        google_event_id=row.get("google_event_id"),
        source=row.get("source") or "sway",
        completed_at=from_iso(row.get("completed_at")),
        created_at=from_iso(row.get("created_at")),
        updated_at=from_iso(row.get("updated_at")),
        deleted_at=from_iso(row.get("deleted_at")),
    )


def task_out(task: Task) -> TaskOut:
    return TaskOut.model_validate(task.__dict__)


class TaskStore:
    def __init__(self, user: CurrentUser) -> None:
        self.user = user
        self.client = user.client

    def list_all(self) -> list[Task]:
        res = self.client.table("tasks").select("*").order("created_at", desc=True).execute()
        return [task_from_row(row) for row in (res.data or [])]

    def list_active(self) -> list[Task]:
        return [t for t in self.list_all() if t.deleted_at is None and t.status == TaskStatus.PENDING]

    def list_completed(self, since: datetime | None = None) -> list[Task]:
        tasks = [
            t for t in self.list_all()
            if t.deleted_at is None and t.status == TaskStatus.COMPLETED
        ]
        if since is not None:
            tasks = [t for t in tasks if t.completed_at is not None and t.completed_at >= since]
        return sorted(
            tasks,
            key=lambda t: t.completed_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    def get(self, task_id: str) -> Task:
        res = self.client.table("tasks").select("*").eq("id", task_id).limit(1).execute()
        if not res.data:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")
        return task_from_row(res.data[0])

    def upsert(self, task: Task) -> Task:
        res = self.client.table("tasks").upsert(task_to_row(task, self.user.id)).execute()
        if res.data:
            return task_from_row(res.data[0])
        return self.get(task.id)

    def purge_old_completed(self) -> None:
        cutoff = utc_now() - timedelta(days=COMPLETED_RETENTION_DAYS)
        for task in self.list_completed():
            if task.completed_at and task.completed_at < cutoff and task.deleted_at is None:
                self.upsert(task.touched(deleted_at=utc_now()))


def create_task(user: CurrentUser, payload: TaskCreate) -> Task:
    store = TaskStore(user)
    try:
        return store.upsert(build_new_task(**payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


def update_task(user: CurrentUser, task_id: str, payload: TaskUpdate) -> Task:
    store = TaskStore(user)
    existing = store.get(task_id)
    data = payload.model_dump(exclude_unset=True)
    if existing.source == Source.GOOGLE:
        allowed = {"reminder_minutes_before"}
        if any(key not in allowed for key in data):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Google Calendar tasks are read-only.")
        return store.upsert(existing.touched(reminder_minutes_before=data.get("reminder_minutes_before")))
    merged = {
        "title": data.get("title", existing.title),
        "description": data.get("description", existing.description),
        "due_at": data.get("due_at", existing.due_at),
        "has_time": data.get("has_time", existing.has_time),
        "end_at": data.get("end_at", existing.end_at),
        "reminder_minutes_before": data.get(
            "reminder_minutes_before", existing.reminder_minutes_before
        ),
        "recurrence_rule": data.get("recurrence_rule", existing.recurrence_rule),
    }
    try:
        return store.upsert(build_updated_task(existing, **merged))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


def complete_task(user: CurrentUser, task_id: str) -> Task:
    store = TaskStore(user)
    task = store.get(task_id)
    if task.is_recurring and task.due_at is not None:
        done = store.upsert(completed_occurrence(task))
        store.upsert(advanced_series(task))
        return done
    return store.upsert(task.touched(status=TaskStatus.COMPLETED, completed_at=utc_now()))


def uncomplete_task(user: CurrentUser, task_id: str) -> Task:
    store = TaskStore(user)
    task = store.get(task_id)
    return store.upsert(task.touched(status=TaskStatus.PENDING, completed_at=None))


def delete_task(user: CurrentUser, task_id: str) -> None:
    store = TaskStore(user)
    task = store.get(task_id)
    store.upsert(task.touched(deleted_at=utc_now()))


def skip_occurrence(user: CurrentUser, task_id: str) -> None:
    store = TaskStore(user)
    task = store.get(task_id)
    if task.is_recurring and task.due_at is not None:
        store.upsert(advanced_series(task))
    else:
        store.upsert(task.touched(deleted_at=utc_now()))


def groups_for(user: CurrentUser):
    return active_groups(TaskStore(user).list_active())


def completed_for(user: CurrentUser):
    store = TaskStore(user)
    store.purge_old_completed()
    since = utc_now() - timedelta(days=COMPLETED_RETENTION_DAYS)
    return completed_groups(store.list_completed(since))


def calendar_for(user: CurrentUser, start: datetime, end: datetime) -> list[Task]:
    return tasks_in_range(TaskStore(user).list_active(), start, end)
