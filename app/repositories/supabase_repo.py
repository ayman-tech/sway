"""Talks to the Supabase `tasks` table. Push local rows up, pull remote rows down.

The local SQLite row id is reused as the cloud row id, so no id-mapping is needed.
Local-only bookkeeping columns (sync_status, last_synced_at, cloud_id) are not sent.
"""

from __future__ import annotations

from app.constants import SyncStatus
from app.models.task import Task
from app.services.auth_service import AuthService
from app.utils.datetime_utils import from_iso, to_iso


def _to_cloud(task: Task, user_id: str) -> dict:
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


def _from_cloud(row: dict) -> Task:
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
        sync_status=SyncStatus.SYNCED,
    )


class SupabaseRepo:
    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    def push(self, tasks: list[Task]) -> None:
        if not tasks:
            return
        client = self._auth.client
        user = self._auth.user
        if client is None or user is None:
            raise RuntimeError("Not signed in.")
        rows = [_to_cloud(t, user.id) for t in tasks]
        client.table("tasks").upsert(rows).execute()

    def pull(self, since_iso: str | None) -> list[Task]:
        client = self._auth.client
        if client is None:
            raise RuntimeError("Not signed in.")
        query = client.table("tasks").select("*")
        if since_iso:
            query = query.gt("updated_at", since_iso)
        res = query.order("updated_at").execute()
        return [_from_cloud(row) for row in (res.data or [])]
