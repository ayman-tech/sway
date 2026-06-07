from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from api.main import due_reminders
from sway_core.models import Task


class _TaskStore:
    def __init__(self, _user, tasks: list[Task]) -> None:
        self._tasks = tasks

    def list_active(self) -> list[Task]:
        return self._tasks


class ReminderCursorTests(unittest.TestCase):
    def test_response_cursor_matches_the_single_server_processing_boundary(self) -> None:
        processed_through = datetime(2026, 6, 7, 14, 0, tzinfo=timezone.utc)
        tasks = [
            Task(title="Due now", due_at=processed_through),
            Task(title="Due after boundary", due_at=processed_through + timedelta(seconds=1)),
        ]

        with (
            patch("api.main.utc_now", return_value=processed_through) as now,
            patch("api.main.TaskStore", side_effect=lambda user: _TaskStore(user, tasks)),
        ):
            batch = due_reminders(
                since=(processed_through - timedelta(minutes=1)).isoformat(),
                user=object(),
            )

        now.assert_called_once_with()
        self.assertEqual(batch.processed_through, processed_through)
        self.assertEqual([reminder.task.title for reminder in batch.reminders], ["Due now"])

    def test_empty_response_still_advances_with_server_time(self) -> None:
        processed_through = datetime(2026, 6, 7, 14, 0, tzinfo=timezone.utc)

        with (
            patch("api.main.utc_now", return_value=processed_through),
            patch("api.main.TaskStore", side_effect=lambda user: _TaskStore(user, [])),
        ):
            batch = due_reminders(user=object())

        self.assertEqual(batch.processed_through, processed_through)
        self.assertEqual(batch.reminders, [])


if __name__ == "__main__":
    unittest.main()
