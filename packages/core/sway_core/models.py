"""Shared Sway task domain model."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from sway_core.constants import Priority, Source, SyncStatus, TaskStatus
from sway_core.datetime_utils import utc_now
from sway_core.ids import new_id


@dataclass
class Task:
    title: str
    id: str = field(default_factory=new_id)
    description: str | None = None
    project_id: str | None = None
    priority: int = Priority.NONE
    status: str = TaskStatus.PENDING

    due_at: datetime | None = None
    has_time: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None
    reminder_minutes_before: int | None = None
    recurrence_rule: str | None = None
    recurrence_parent_id: str | None = None

    cloud_id: str | None = None
    google_event_id: str | None = None
    source: str = Source.SWAY
    sync_status: str = SyncStatus.PENDING
    last_synced_at: datetime | None = None

    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    deleted_at: datetime | None = None

    is_preview: bool = False

    @property
    def is_recurring(self) -> bool:
        return bool(self.recurrence_rule)

    @property
    def is_completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def is_read_only(self) -> bool:
        return self.source == Source.GOOGLE

    def touched(self, **changes) -> "Task":
        changes.setdefault("sync_status", SyncStatus.PENDING)
        return replace(self, updated_at=utc_now(), **changes)
