"""Task domain model."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from app.constants import Priority, Source, SyncStatus, TaskStatus
from app.utils.datetime_utils import utc_now
from app.utils.ids import new_id


@dataclass
class Task:
    """A single task.

    Fields beyond the M1 scope (start_at/end_at, reminder, recurrence, sync, google)
    are present from the start so the SQLite/Supabase schema is forward-compatible
    with later milestones, even though the UI only uses a subset for now.
    """

    title: str
    id: str = field(default_factory=new_id)
    description: str | None = None
    project_id: str | None = None
    priority: int = Priority.NONE
    status: str = TaskStatus.PENDING

    # Scheduling
    due_at: datetime | None = None
    has_time: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None

    # Reminders. Timed tasks always remind at the task time (implicit, not stored).
    # This optional offset adds an *extra* earlier reminder (minutes before due).
    reminder_minutes_before: int | None = None

    # Recurrence (RRULE string, e.g. "FREQ=WEEKLY;INTERVAL=2")
    recurrence_rule: str | None = None
    recurrence_parent_id: str | None = None

    # Cloud / external sync
    cloud_id: str | None = None
    google_event_id: str | None = None
    source: str = Source.SWAY
    sync_status: str = SyncStatus.PENDING
    last_synced_at: datetime | None = None

    # Bookkeeping
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    deleted_at: datetime | None = None

    # Transient (not persisted): set on virtual occurrences of a recurring series.
    # A "preview" is a future occurrence shown read-only in the list/calendar.
    is_preview: bool = False

    @property
    def is_recurring(self) -> bool:
        return bool(self.recurrence_rule)

    @property
    def is_completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def is_read_only(self) -> bool:
        """Google-imported items are shown read-only in Sway."""
        return self.source == Source.GOOGLE

    def touched(self, **changes) -> "Task":
        """Return a copy with `changes` applied, updated_at bumped, and marked for sync."""
        changes.setdefault("sync_status", SyncStatus.PENDING)
        return replace(self, updated_at=utc_now(), **changes)
