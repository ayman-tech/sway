from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from sway_core.google import parse_event_when
from sway_core.models import Task
from sway_core.recurrence import date_occurrences_between, timed_occurrences_between
from sway_core.task_logic import advanced_series, build_new_task, completed_occurrence, tasks_in_range


class SchedulingTests(unittest.TestCase):
    def test_google_all_day_event_stays_date_only(self) -> None:
        when = parse_event_when({
            "start": {"date": "2026-06-06"},
            "end": {"date": "2026-06-09"},
        })
        self.assertEqual(when, (None, date(2026, 6, 6), None, date(2026, 6, 9)))

    def test_timed_and_all_day_due_fields_are_mutually_exclusive(self) -> None:
        with self.assertRaises(ValueError):
            build_new_task(
                "Invalid",
                due_at=datetime(2026, 6, 6, tzinfo=timezone.utc),
                due_date=date(2026, 6, 6),
            )

    def test_all_day_span_overlaps_each_covered_calendar_range(self) -> None:
        task = Task(title="Conference", due_date=date(2026, 6, 6), end_date=date(2026, 6, 9))
        result = tasks_in_range(
            [task],
            datetime(2026, 6, 8, tzinfo=timezone.utc),
            datetime(2026, 6, 9, tzinfo=timezone.utc),
            date(2026, 6, 8),
            date(2026, 6, 9),
        )
        self.assertEqual(result, [task])

    def test_all_day_recurrence_uses_calendar_dates(self) -> None:
        task = Task(title="Daily", due_date=date(2026, 6, 6), recurrence_rule="FREQ=DAILY")
        self.assertEqual(
            date_occurrences_between(task, date(2026, 6, 6), date(2026, 6, 8)),
            [date(2026, 6, 6), date(2026, 6, 7), date(2026, 6, 8)],
        )

    def test_all_day_completion_and_advance_keep_date_only_schedule(self) -> None:
        task = Task(title="Daily", due_date=date(2026, 6, 6), recurrence_rule="FREQ=DAILY")
        done = completed_occurrence(task)
        upcoming = advanced_series(task)
        self.assertEqual(done.due_date, date(2026, 6, 6))
        self.assertIsNone(done.due_at)
        self.assertEqual(upcoming.due_date, date(2026, 6, 7))

    def test_timed_recurrence_keeps_wall_time_across_dst(self) -> None:
        task = Task(
            title="Daily standup",
            due_at=datetime(2026, 3, 7, 14, tzinfo=timezone.utc),
            recurrence_rule="FREQ=DAILY",
            recurrence_timezone="America/New_York",
        )
        occurrences = timed_occurrences_between(
            task,
            datetime(2026, 3, 7, tzinfo=timezone.utc),
            datetime(2026, 3, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(
            occurrences,
            [
                datetime(2026, 3, 7, 14, tzinfo=timezone.utc),
                datetime(2026, 3, 8, 13, tzinfo=timezone.utc),
                datetime(2026, 3, 9, 13, tzinfo=timezone.utc),
            ],
        )

    def test_timed_recurrence_until_uses_the_recurrence_timezone(self) -> None:
        task = Task(
            title="Late daily task",
            due_at=datetime(2026, 3, 7, 6, tzinfo=timezone.utc),
            recurrence_rule="FREQ=DAILY;UNTIL=20260309T035959Z",
            recurrence_timezone="America/New_York",
        )
        occurrences = timed_occurrences_between(
            task,
            datetime(2026, 3, 7, tzinfo=timezone.utc),
            datetime(2026, 3, 11, tzinfo=timezone.utc),
        )
        self.assertEqual(len(occurrences), 2)


if __name__ == "__main__":
    unittest.main()
