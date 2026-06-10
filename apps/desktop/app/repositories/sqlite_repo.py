"""SQLite repository for tasks. Pure persistence; no business logic."""

from __future__ import annotations

from datetime import date

from app.db.database import Database
from app.models.task import Task
from app.utils.datetime_utils import from_iso, to_iso

_COLUMNS = [
    "id", "cloud_id", "google_event_id", "source",
    "title", "description", "project_id", "priority", "status",
    "due_at", "due_date", "start_at", "end_at", "end_date",
    "reminder_minutes_before", "recurrence_rule", "recurrence_timezone", "recurrence_parent_id",
    "completed_at", "created_at", "updated_at", "deleted_at",
    "sync_status", "last_synced_at",
]


def _to_row(task: Task) -> dict:
    return {
        "id": task.id,
        "cloud_id": task.cloud_id,
        "google_event_id": task.google_event_id,
        "source": str(task.source),
        "title": task.title,
        "description": task.description,
        "project_id": task.project_id,
        "priority": int(task.priority),
        "status": str(task.status),
        "due_at": to_iso(task.due_at),
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "start_at": to_iso(task.start_at),
        "end_at": to_iso(task.end_at),
        "end_date": task.end_date.isoformat() if task.end_date else None,
        "reminder_minutes_before": task.reminder_minutes_before,
        "recurrence_rule": task.recurrence_rule,
        "recurrence_timezone": task.recurrence_timezone,
        "recurrence_parent_id": task.recurrence_parent_id,
        "completed_at": to_iso(task.completed_at),
        "created_at": to_iso(task.created_at),
        "updated_at": to_iso(task.updated_at),
        "deleted_at": to_iso(task.deleted_at),
        "sync_status": str(task.sync_status),
        "last_synced_at": to_iso(task.last_synced_at),
    }


def _from_row(row) -> Task:
    return Task(
        id=row["id"],
        cloud_id=row["cloud_id"],
        google_event_id=row["google_event_id"],
        source=row["source"],
        title=row["title"],
        description=row["description"],
        project_id=row["project_id"],
        priority=row["priority"],
        status=row["status"],
        due_at=from_iso(row["due_at"]),
        due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
        start_at=from_iso(row["start_at"]),
        end_at=from_iso(row["end_at"]),
        end_date=date.fromisoformat(row["end_date"]) if row["end_date"] else None,
        reminder_minutes_before=row["reminder_minutes_before"],
        recurrence_rule=row["recurrence_rule"],
        recurrence_timezone=row["recurrence_timezone"],
        recurrence_parent_id=row["recurrence_parent_id"],
        completed_at=from_iso(row["completed_at"]),
        created_at=from_iso(row["created_at"]),
        updated_at=from_iso(row["updated_at"]),
        deleted_at=from_iso(row["deleted_at"]),
        sync_status=row["sync_status"],
        last_synced_at=from_iso(row["last_synced_at"]),
    )


class TaskRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def _conn(self):
        return self._db.conn

    def upsert(self, task: Task) -> Task:
        row = _to_row(task)
        placeholders = ", ".join(f":{c}" for c in _COLUMNS)
        assignments = ", ".join(f"{c} = :{c}" for c in _COLUMNS if c != "id")
        self._conn().execute(
            f"INSERT INTO tasks ({', '.join(_COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {assignments}",
            row,
        )
        self._conn().commit()
        return task

    def get(self, task_id: str) -> Task | None:
        cur = self._conn().execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        return _from_row(row) if row else None

    def list_active(self) -> list[Task]:
        """All not-deleted, not-completed tasks."""
        cur = self._conn().execute(
            "SELECT * FROM tasks WHERE deleted_at IS NULL AND status = 'pending' "
            "ORDER BY (due_at IS NULL AND due_date IS NULL), due_date ASC, due_at ASC"
        )
        return [_from_row(r) for r in cur.fetchall()]

    def list_completed(self, since: str | None = None) -> list[Task]:
        if since is not None:
            cur = self._conn().execute(
                "SELECT * FROM tasks WHERE deleted_at IS NULL AND status = 'completed' "
                "AND completed_at >= ? ORDER BY completed_at DESC",
                (since,),
            )
        else:
            cur = self._conn().execute(
                "SELECT * FROM tasks WHERE deleted_at IS NULL AND status = 'completed' "
                "ORDER BY completed_at DESC"
            )
        return [_from_row(r) for r in cur.fetchall()]

    def soft_delete_completed_before(self, cutoff: str, now: str) -> int:
        """Tombstone completed, not-yet-deleted tasks finished before `cutoff`. Returns count."""
        cur = self._conn().execute(
            "UPDATE tasks SET deleted_at = ?, updated_at = ?, sync_status = 'pending' "
            "WHERE status = 'completed' AND deleted_at IS NULL AND completed_at < ?",
            (now, now, cutoff),
        )
        self._conn().commit()
        return cur.rowcount

    def list_all(self) -> list[Task]:
        cur = self._conn().execute(
            "SELECT * FROM tasks WHERE deleted_at IS NULL ORDER BY created_at DESC"
        )
        return [_from_row(r) for r in cur.fetchall()]

    # ---- sync support ----
    def list_pending_sync(self) -> list[Task]:
        """Pending Sway-owned rows; Google rows are written only by FastAPI."""
        cur = self._conn().execute(
            "SELECT * FROM tasks WHERE sync_status = 'pending' AND source != 'google' "
            "ORDER BY updated_at ASC"
        )
        return [_from_row(r) for r in cur.fetchall()]

    def list_pending_google_state(self) -> list[Task]:
        """Google rows with user-owned completion/reminder state to send through FastAPI."""
        cur = self._conn().execute(
            "SELECT * FROM tasks WHERE sync_status = 'pending' AND source = 'google' "
            "ORDER BY updated_at ASC"
        )
        return [_from_row(r) for r in cur.fetchall()]

    def mark_synced(self, task_id: str, last_synced_at: str) -> None:
        """Flag a row as synced WITHOUT touching updated_at (avoids a re-push loop)."""
        self._conn().execute(
            "UPDATE tasks SET sync_status = 'synced', last_synced_at = ? WHERE id = ?",
            (last_synced_at, task_id),
        )
        self._conn().commit()
