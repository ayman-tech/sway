from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from app.db.database import Database
from app.models.task import Task
from app.repositories.sqlite_repo import TaskRepository
from app.services.sync_service import SyncService
from sway_core.constants import Source


def test_google_tasks_are_never_returned_for_desktop_push() -> None:
    with TemporaryDirectory() as directory:
        database = Database(Path(directory) / "sway.db")
        repository = TaskRepository(database)
        repository.upsert(Task(title="Sway task"))
        repository.upsert(Task(title="Google task", source=Source.GOOGLE))

        pending = repository.list_pending_sync()
        pending_google = repository.list_pending_google_state()

        assert [task.title for task in pending] == ["Sway task"]
        assert [task.title for task in pending_google] == ["Google task"]
        database.close()


def test_google_api_failure_does_not_block_desktop_task_pull() -> None:
    class Tasks:
        def soft_delete_completed_before(self, *_args):
            return 0

        def list_pending_sync(self):
            return []

        def list_pending_google_state(self):
            return []

        def get(self, _task_id):
            return None

        def upsert(self, task):
            return task

    class Cloud:
        pulled = False

        def push(self, _tasks):
            return None

        def pull(self, _since):
            self.pulled = True
            return []

    class Google:
        def push_task_state(self, _task):
            return None

        def sync(self, force=False):
            raise RuntimeError("offline")

    class Settings:
        def get(self, _key):
            return None

        def set(self, _key, _value):
            return None

    cloud = Cloud()
    service = SyncService(
        Tasks(),
        cloud,
        SimpleNamespace(user=SimpleNamespace(id="user-id")),
        Settings(),
        google_service=Google(),
    )

    result = service.sync()

    assert result.ok
    assert cloud.pulled
