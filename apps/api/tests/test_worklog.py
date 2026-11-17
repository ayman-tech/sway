from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api import worklog
from api.schemas import SettingsUpdate

TODAY = date(2026, 10, 21)


class FakeTable:
    """In-memory work_log_entries supporting the PostgREST calls worklog.py makes."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, int], dict] = {}
        self._op = "select"
        self._payload: dict = {}
        self._filters: list[tuple[str, str, object]] = []
        self._order: list[str] = []

    def _fresh(self, op: str, payload: dict | None = None) -> "FakeTable":
        query = FakeTable.__new__(FakeTable)
        query.rows = self.rows
        query._op = op
        query._payload = payload or {}
        query._filters = []
        query._order = []
        return query

    def select(self, _columns: str) -> "FakeTable":
        return self._fresh("select")

    def delete(self) -> "FakeTable":
        return self._fresh("delete")

    def upsert(self, payload: dict, on_conflict: str | None = None) -> "FakeTable":
        assert on_conflict == "user_id,entry_date,hour_slot"
        return self._fresh("upsert", payload)

    def eq(self, column: str, value: object) -> "FakeTable":
        self._filters.append(("eq", column, value))
        return self

    def gte(self, column: str, value: object) -> "FakeTable":
        self._filters.append(("gte", column, value))
        return self

    def lte(self, column: str, value: object) -> "FakeTable":
        self._filters.append(("lte", column, value))
        return self

    def lt(self, column: str, value: object) -> "FakeTable":
        self._filters.append(("lt", column, value))
        return self

    def match(self, values: dict) -> "FakeTable":
        for column, value in values.items():
            self.eq(column, value)
        return self

    def order(self, column: str) -> "FakeTable":
        self._order.append(column)
        return self

    def _matches(self, row: dict) -> bool:
        checks = {
            "eq": lambda a, b: a == b,
            "gte": lambda a, b: a >= b,
            "lte": lambda a, b: a <= b,
            "lt": lambda a, b: a < b,
        }
        return all(checks[op](row[column], value) for op, column, value in self._filters)

    def execute(self) -> SimpleNamespace:
        if self._op == "upsert":
            key = (self._payload["user_id"], self._payload["entry_date"], self._payload["hour_slot"])
            self.rows[key] = dict(self._payload)
            return SimpleNamespace(data=[self.rows[key]])
        matched = [row for row in self.rows.values() if self._matches(row)]
        if self._op == "delete":
            for row in matched:
                del self.rows[(row["user_id"], row["entry_date"], row["hour_slot"])]
            return SimpleNamespace(data=matched)
        matched.sort(key=lambda row: tuple(row[column] for column in self._order))
        return SimpleNamespace(data=matched)


@pytest.fixture
def user(monkeypatch: pytest.MonkeyPatch):
    table = FakeTable()
    client = SimpleNamespace(table=lambda name: table if name == "work_log_entries" else pytest.fail(name))
    monkeypatch.setattr(worklog, "utc_now", lambda: datetime(2026, 10, 21, 12, tzinfo=timezone.utc))
    return SimpleNamespace(id="u1", client=client, table=table)


def seed(user, entry_date: str, hour: int, note: str = "x", user_id: str = "u1") -> None:
    user.table.rows[(user_id, entry_date, hour)] = {
        "user_id": user_id,
        "entry_date": entry_date,
        "hour_slot": hour,
        "note": note,
    }


def test_window_covers_today_and_six_previous_days():
    assert worklog.window_start(TODAY) == date(2026, 10, 15)


def test_list_returns_window_and_prunes_older_rows(user):
    seed(user, "2026-10-14", 9)  # 7 days back: outside the window
    seed(user, "2026-10-15", 9, "oldest kept")
    seed(user, "2026-10-21", 22, "late")
    seed(user, "2026-10-21", 9, "early")
    seed(user, "2026-10-14", 9, "other user", user_id="u2")

    entries = worklog.list_entries(user, TODAY)

    assert [(e.entry_date.isoformat(), e.hour_slot) for e in entries] == [
        ("2026-10-15", 9),
        ("2026-10-21", 9),
        ("2026-10-21", 22),
    ]
    assert ("u1", "2026-10-14", 9) not in user.table.rows
    assert ("u2", "2026-10-14", 9) in user.table.rows  # other users are never touched


def test_put_upserts_and_trims_note(user):
    entry = worklog.put_entry(user, TODAY, 13, "  Fixed login bug \n", TODAY)

    assert entry.note == "Fixed login bug"
    assert user.table.rows[("u1", "2026-10-21", 13)]["note"] == "Fixed login bug"

    worklog.put_entry(user, TODAY, 13, "Reviewed PR", TODAY)
    assert len(user.table.rows) == 1
    assert user.table.rows[("u1", "2026-10-21", 13)]["note"] == "Reviewed PR"


def test_put_blank_note_deletes_row(user):
    seed(user, "2026-10-21", 13)

    worklog.put_entry(user, TODAY, 13, "   ", TODAY)

    assert user.table.rows == {}


def test_put_prunes_old_rows(user):
    seed(user, "2026-10-01", 9)

    worklog.put_entry(user, TODAY, 9, "now", TODAY)

    assert set(user.table.rows) == {("u1", "2026-10-21", 9)}


@pytest.mark.parametrize("entry_date", [date(2026, 10, 14), date(2026, 10, 22)])
def test_put_rejects_dates_outside_window(user, entry_date):
    with pytest.raises(HTTPException) as exc:
        worklog.put_entry(user, entry_date, 9, "x", TODAY)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("hour", [-1, 24])
def test_put_rejects_invalid_hour(user, hour):
    with pytest.raises(HTTPException) as exc:
        worklog.put_entry(user, TODAY, hour, "x", TODAY)
    assert exc.value.status_code == 400


def test_put_accepts_oldest_day_in_window(user):
    worklog.put_entry(user, date(2026, 10, 15), 9, "x", TODAY)
    assert ("u1", "2026-10-15", 9) in user.table.rows


def test_client_today_must_be_near_utc_today(user):
    seed(user, "2026-01-01", 9)
    far_future = date(2026, 12, 31)

    with pytest.raises(HTTPException) as exc:
        worklog.list_entries(user, far_future)

    assert exc.value.status_code == 400
    assert ("u1", "2026-01-01", 9) in user.table.rows  # a bad client cannot trigger a wipe


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_client_today_allows_timezone_skew(user, offset):
    worklog.list_entries(user, date(2026, 10, 21 + offset))


@pytest.mark.parametrize(
    "payload",
    [{"work_start_hour": 24}, {"work_start_hour": -1}, {"work_end_hour": 0}, {"work_end_hour": 25}],
)
def test_settings_reject_out_of_range_hours(payload):
    with pytest.raises(ValidationError):
        SettingsUpdate(**payload)


def test_settings_accept_night_shift():
    update = SettingsUpdate(work_start_hour=22, work_end_hour=6)
    assert (update.work_start_hour, update.work_end_hour) == (22, 6)


@pytest.mark.parametrize("goal", [0, -1, 169, 2.5, True, "25"])
def test_weekly_goal_rejects_invalid_values(goal):
    with pytest.raises(ValidationError):
        SettingsUpdate(work_weekly_goal_hours=goal)


@pytest.mark.parametrize("goal", [None, 1, 25, 168])
def test_weekly_goal_accepts_optional_whole_hours(goal):
    assert SettingsUpdate(work_weekly_goal_hours=goal).work_weekly_goal_hours == goal


def test_weekly_goal_settings_roundtrip(monkeypatch):
    from api.settings import get_user_settings, update_user_settings
    from types import SimpleNamespace
    class Table:
        row = {"user_id": "owner", "work_weekly_goal_hours": 25}
        def select(self, *_): return self
        def eq(self, key, value):
            assert key == "user_id" and value == "owner"
            return self
        def limit(self, *_): return self
        def upsert(self, row):
            assert row["user_id"] == "owner"
            self.row = row
            return self
        def execute(self): return SimpleNamespace(data=[self.row])
    table = Table()
    user = SimpleNamespace(id="owner", client=SimpleNamespace(table=lambda _: table))
    assert get_user_settings(user).work_weekly_goal_hours == 25
    assert update_user_settings(user, SettingsUpdate(work_weekly_goal_hours=30)).work_weekly_goal_hours == 30
    assert update_user_settings(user, SettingsUpdate(theme="dark")).work_weekly_goal_hours == 30
    assert update_user_settings(user, SettingsUpdate(work_weekly_goal_hours=None)).work_weekly_goal_hours is None
