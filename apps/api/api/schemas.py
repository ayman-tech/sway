"""API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class TaskOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    project_id: str | None = None
    priority: int = 0
    status: str = "pending"
    due_at: datetime | None = None
    due_date: date | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    end_date: date | None = None
    reminder_minutes_before: int | None = None
    recurrence_rule: str | None = None
    recurrence_timezone: str | None = None
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
    due_date: date | None = None
    end_at: datetime | None = None
    end_date: date | None = None
    reminder_minutes_before: int | None = None
    recurrence_rule: str | None = None
    recurrence_timezone: str | None = None


class TaskUpdate(TaskCreate):
    title: str | None = None


class TaskGroupOut(BaseModel):
    label: str
    overdue: bool = False
    tasks: list[TaskOut] = Field(default_factory=list)
    has_more: bool = False


class MeOut(BaseModel):
    id: str
    email: str | None


class SettingsOut(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    theme: str = "system"
    reminders_processed_through: datetime | None = None
    browser_notifications_enabled: bool = False


class SettingsUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    theme: str | None = None
    reminders_processed_through: datetime | None = None
    browser_notifications_enabled: bool | None = None


class ReminderOut(BaseModel):
    fire_at: datetime
    occurrence: datetime
    kind: str
    task: TaskOut


class ReminderBatchOut(BaseModel):
    processed_through: datetime
    reminders: list[ReminderOut] = Field(default_factory=list)


class GoogleStatusOut(BaseModel):
    configured: bool
    connected: bool
    setup_available: bool
    client_id: str | None = None
    redirect_uri: str
    account: str | None = None
    last_synced_at: datetime | None = None
    last_sync_error: str | None = None


class GoogleCredentialsUpdate(BaseModel):
    client_id: str = Field(min_length=1, max_length=512)
    client_secret: str = Field(min_length=1, max_length=1024)


class ApiKeyOut(BaseModel):
    key: str | None = None
    created_at: datetime | None = None


class GoogleConnectUrlOut(BaseModel):
    url: str


class GoogleSyncOut(BaseModel):
    imported: int
    skipped: bool = False


class AvailabilitySnapshot(BaseModel):
    selected_dates: list[date] = Field(min_length=1, max_length=14)
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=1, le=24)
    available_slots: dict[str, list[int]] = Field(default_factory=dict)
    busy_slots: dict[str, list[int]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "AvailabilitySnapshot":
        if self.end_hour <= self.start_hour:
            raise ValueError("End hour must be after start hour.")
        selected = [value.isoformat() for value in self.selected_dates]
        if len(set(selected)) != len(selected):
            raise ValueError("Selected dates must be unique.")
        selected_set = set(selected)
        slot_count = self.end_hour - self.start_hour
        for mapping_name, mapping in (
            ("available_slots", self.available_slots),
            ("busy_slots", self.busy_slots),
        ):
            if set(mapping) - selected_set:
                raise ValueError(f"{mapping_name} contains an unselected date.")
            for slots in mapping.values():
                if len(slots) != len(set(slots)):
                    raise ValueError(f"{mapping_name} contains duplicate slots.")
                if any(slot < 0 or slot >= slot_count for slot in slots):
                    raise ValueError(f"{mapping_name} contains an invalid slot.")
        for date_iso in selected_set:
            if set(self.available_slots.get(date_iso, [])) & set(self.busy_slots.get(date_iso, [])):
                raise ValueError("Available and busy slots cannot overlap.")
        return self


class AvailabilityShareCreate(BaseModel):
    snapshot: AvailabilitySnapshot
    creator_timezone: str = Field(min_length=1, max_length=128)


class AvailabilityShareCreatedOut(BaseModel):
    url: str
    expires_at: datetime


class AvailabilityShareOut(BaseModel):
    snapshot: AvailabilitySnapshot
    first_name: str | None = None
    creator_timezone: str
    created_at: datetime
    expires_at: datetime
