from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from sway_core.models import Task
from sway_core import task_logic
from api import tasks, main


@pytest.fixture
def frozen(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 21, 12, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(task_logic, "datetime", Clock)
    monkeypatch.setattr(task_logic, "utc_now", lambda: Clock.now(timezone.utc))
    return date(2026, 11, 21)


def test_seven_day_group_order_and_inclusive_local_boundary(frozen):
    items = [Task(title=str(n), due_date=frozen + timedelta(days=n)) for n in [-1, 0, 1, 2, 7, 8, 30, 31]]
    items += [Task(title="untimed"), Task(title="late on seventh day", due_at=datetime(2026, 11, 29, 4, 59, tzinfo=timezone.utc))]
    groups = task_logic.active_groups(items, "America/New_York", 7)
    assert [g.label for g in groups] == ["Overdue", "Today", "Tomorrow", "Untimed", "Next 7 Days"]
    assert [t.title for t in groups[-1].tasks] == ["2", "late on seventh day", "7"]
    assert "Later" in [g.label for g in task_logic.active_groups(items, "America/New_York")]


def test_later_ranges_filter_multiday_overlap_and_bound_recurrence(monkeypatch):
    entries = [
        Task(title="overlap", due_date=date(2026, 11, 20), end_date=date(2026, 12, 5)),
        Task(title="daily", due_date=date(2026, 11, 1), recurrence_rule="FREQ=DAILY"),
        Task(title="google", source="google", due_date=date(2026, 11, 29)),
        Task(title="untimed"),
    ]
    monkeypatch.setattr(tasks.TaskStore, "list_active", lambda self: entries)
    user = SimpleNamespace(id="owner", client=object())
    first = tasks.later_for(user, date(2026, 11, 29), date(2026, 12, 21), "America/New_York")
    second = tasks.later_for(user, date(2026, 12, 22), date(2027, 1, 20), "America/New_York")
    assert len([t for t in first if t.title == "daily"]) == 23
    assert len(second) == 30
    assert any(t.source == "google" for t in first)
    assert not any(t.title in {"overlap", "untimed"} for t in first)
    assert not ({(t.id, t.due_date) for t in first} & {(t.id, t.due_date) for t in second})


@pytest.mark.parametrize("start,end,zone", [
    (date(2026, 12, 2), date(2026, 12, 1), "UTC"),
    (date(2026, 12, 1), date(2026, 12, 31), "UTC"),
    (date(2026, 12, 1), date(2026, 12, 2), "not-a-zone"),
])
def test_invalid_later_ranges_rejected_before_storage(start, end, zone):
    with pytest.raises(HTTPException) as exc:
        tasks.later_for(None, start, end, zone)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_later_endpoint_requires_authentication():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        result = await client.get("/tasks/later?start_date=2026-12-01&end_date=2026-12-30")
    assert result.status_code == 401


def test_later_uses_authenticated_user_store(monkeypatch):
    seen = []
    class Store:
        def __init__(self, user): seen.append(user.id)
        def list_active(self): return [Task(title=seen[-1], due_date=date(2026, 12, 1))]
    monkeypatch.setattr(tasks, "TaskStore", Store)
    for owner in ("a", "b"):
        result = tasks.later_for(SimpleNamespace(id=owner), date(2026, 12, 1), date(2026, 12, 2), "UTC")
        assert result[0].title == owner
    assert seen == ["a", "b"]
