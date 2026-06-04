"""API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    project_id: str | None = None
    priority: int = 0
    status: str = "pending"
    due_at: datetime | None = None
    has_time: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None
    reminder_minutes_before: int | None = None
    recurrence_rule: str | None = None
    recurrence_parent_id: str | None = None
    google_event_id: str | None = None
    source: str = "sway"
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    is_preview: bool = False


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    due_at: datetime | None = None
    has_time: bool = False
    end_at: datetime | None = None
    reminder_minutes_before: int | None = None
    recurrence_rule: str | None = None


class TaskUpdate(TaskCreate):
    title: str | None = None


class TaskGroupOut(BaseModel):
    label: str
    overdue: bool = False
    tasks: list[TaskOut] = Field(default_factory=list)


class MeOut(BaseModel):
    id: str
    email: str | None


class SettingsOut(BaseModel):
    theme: str = "system"
    reminders_processed_through: datetime | None = None
    browser_notifications_enabled: bool = False


class SettingsUpdate(BaseModel):
    theme: str | None = None
    reminders_processed_through: datetime | None = None
    browser_notifications_enabled: bool | None = None


class ReminderOut(BaseModel):
    fire_at: datetime
    occurrence: datetime
    kind: str
    task: TaskOut


class GoogleStatusOut(BaseModel):
    connected: bool
    account: str | None = None


class GoogleConnectUrlOut(BaseModel):
    url: str


class GoogleSyncOut(BaseModel):
    imported: int
