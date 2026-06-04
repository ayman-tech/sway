"""App-wide constants and enums shared across Sway apps."""

from __future__ import annotations

from enum import IntEnum, StrEnum

APP_NAME = "Sway"
APP_ORG = "Sway"


class TaskStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class Priority(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def label(self) -> str:
        return {
            Priority.NONE: "None",
            Priority.LOW: "Low",
            Priority.MEDIUM: "Medium",
            Priority.HIGH: "High",
        }[self]


class SyncStatus(StrEnum):
    PENDING = "pending"
    SYNCED = "synced"


class Source(StrEnum):
    SWAY = "sway"
    GOOGLE = "google"


VIEW_TASKS = "tasks"
VIEW_CALENDAR = "calendar"
VIEW_COMPLETED = "completed"
VIEW_SETTINGS = "settings"
