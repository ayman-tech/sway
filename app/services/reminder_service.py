"""Schedules and fires task reminders.

Model: every timed task always reminds at its due time; an optional `reminder_minutes_before`
adds an extra earlier reminder. We poll on a short interval (robust to sleep/clock changes)
and deliver any reminder whose fire time has passed since we last delivered one.

`reminders_processed_through` (persisted) marks the fire-time of the most recent delivered
reminder. On startup, reminders that came due while the app was closed are caught up; their
fire time is > processed_through and <= now.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from PySide6.QtCore import QObject, QTimer

from app.models.task import Task
from app.repositories.settings_repo import SettingsRepository
from app.services.recurrence import occurrences_between
from app.services.task_service import TaskService
from app.utils.datetime_utils import from_iso, to_iso, to_local, utc_now

_CHECK_INTERVAL_MS = 30_000
_SETTING_KEY = "reminders_processed_through"
# Cap how far back startup catch-up reaches, so a long absence (esp. with recurring
# tasks) doesn't dump dozens of stale notifications at once.
_CATCHUP_MAX_DAYS = 2


class _MessageSink(Protocol):
    def show_message(self, title: str, body: str) -> None: ...


@dataclass
class _ReminderEvent:
    fire_at: datetime
    occurrence: datetime  # the task's due time this reminder is for
    task: Task
    kind: str  # "due" | "extra"


class ReminderService(QObject):
    def __init__(
        self,
        task_service: TaskService,
        settings_repo: SettingsRepository,
        notifier: _MessageSink,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tasks = task_service
        self._settings = settings_repo
        self._notifier = notifier

        self._timer = QTimer(self)
        self._timer.setInterval(_CHECK_INTERVAL_MS)
        self._timer.timeout.connect(self._check)

        stored = self._settings.get(_SETTING_KEY)
        if stored is None:
            # First run: start the clock now so we don't fire for pre-existing past tasks.
            self._processed_through = utc_now()
            self._settings.set(_SETTING_KEY, to_iso(self._processed_through))
        else:
            self._processed_through = from_iso(stored)

    def start(self) -> None:
        self._check()  # startup catch-up for reminders missed while closed
        self._timer.start()

    def reschedule(self) -> None:
        """Call after tasks change; delivers anything already due, picks up new ones."""
        self._check()

    def _events_between(self, start: datetime, end: datetime) -> list[_ReminderEvent]:
        """Reminder events whose occurrence falls in [start, end].

        Each timed task yields a "due" event at the occurrence time and, if configured,
        an "extra" event `reminder_minutes_before` earlier. Recurring tasks expand into
        one pair of events per occurrence in the window.
        """
        events: list[_ReminderEvent] = []
        for task in self._tasks.get_active_tasks():
            if not (task.due_at and task.has_time):
                continue
            # Google events already notify via Google; don't double up.
            if task.is_read_only:
                continue
            if task.is_recurring:
                occurrences = occurrences_between(task, start, end)
            else:
                occurrences = [task.due_at] if start <= task.due_at <= end else []
            for occ in occurrences:
                events.append(_ReminderEvent(occ, occ, task, "due"))
                if task.reminder_minutes_before is not None:
                    fire = occ - timedelta(minutes=task.reminder_minutes_before)
                    events.append(_ReminderEvent(fire, occ, task, "extra"))
        return events

    def _check(self) -> None:
        now = utc_now()
        floor = now - timedelta(days=_CATCHUP_MAX_DAYS)
        start = max(self._processed_through, floor)
        # Widen the generation window by a day so an "extra" reminder whose occurrence is
        # shortly after `now` (with a large lead) is still produced and filtered correctly.
        events = self._events_between(start, now + timedelta(days=1))
        due = sorted(
            (e for e in events if start < e.fire_at <= now), key=lambda e: e.fire_at
        )
        for event in due:
            self._deliver(event)
        if now > self._processed_through:
            self._processed_through = now
            self._settings.set(_SETTING_KEY, to_iso(now))

    def _deliver(self, event: _ReminderEvent) -> None:
        local = to_local(event.occurrence)
        time_str = local.strftime("%I:%M %p").lstrip("0")
        if event.kind == "due":
            body = f"Due now · {time_str}"
        else:
            body = f"Upcoming · due at {time_str}"
        self._notifier.show_message(event.task.title, body)
