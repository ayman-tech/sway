"""Tier-1 sync: device SQLite ⇆ Supabase. Offline-first, last-write-wins by updated_at."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.repositories.settings_repo import SettingsRepository
from app.repositories.sqlite_repo import TaskRepository
from app.repositories.supabase_repo import SupabaseRepo
from app.services.auth_service import AuthService
from app.services.google_api_service import GoogleApiService
from app.services.task_service import COMPLETED_RETENTION_DAYS
from app.utils.datetime_utils import from_iso, to_iso, utc_now

_LAST_PULL_KEY = "last_pull_at"
# Re-fetch this much before the high-water mark each pull, to avoid missing a row that
# committed at ~the same instant the mark advanced (works with server-set timestamps).
_PULL_OVERLAP_SECONDS = 60


@dataclass
class SyncResult:
    ok: bool
    pushed: int = 0
    pulled: int = 0
    message: str = ""


class SyncService:
    def __init__(
        self,
        task_repo: TaskRepository,
        supabase_repo: SupabaseRepo,
        auth_service: AuthService,
        settings_repo: SettingsRepository,
        google_service: GoogleApiService | None = None,
    ) -> None:
        self._tasks = task_repo
        self._cloud = supabase_repo
        self._auth = auth_service
        self._settings = settings_repo
        self._google = google_service

    def sync(self, force_google: bool = False) -> SyncResult:
        if self._auth.user is None:
            return SyncResult(ok=False, message="Not signed in.")

        # Retention: tombstone completed tasks older than the window (then push below).
        cutoff = utc_now() - timedelta(days=COMPLETED_RETENTION_DAYS)
        self._tasks.soft_delete_completed_before(to_iso(cutoff), to_iso(utc_now()))

        # 1) Send only user-owned state for Google rows through FastAPI task actions.
        if self._google is not None:
            for task in self._tasks.list_pending_google_state():
                try:
                    self._google.push_task_state(task)
                    self._tasks.mark_synced(task.id, to_iso(utc_now()))
                except Exception:  # noqa: BLE001 - retry on the next sync
                    break

        # 2) Push every locally-pending Sway row (creates, edits, completes, soft-deletes).
        pending = self._tasks.list_pending_sync()
        self._cloud.push(pending)
        now_iso = to_iso(utc_now())
        for task in pending:
            self._tasks.mark_synced(task.id, now_iso)

        # 3) Ask FastAPI to import Google changes. Failure must not block task sync.
        if self._google is not None:
            try:
                self._google.sync(force=force_google)
            except Exception:  # noqa: BLE001
                pass

        # 4) Pull rows changed remotely since our last pull; last-write-wins.
        # Query a little BEFORE last_pull_at (overlap) so a row that landed at/just under
        # the previous high-water mark can't be skipped forever. Re-fetched rows we already
        # have are no-ops (cloud.updated_at == local.updated_at → not newer).
        since = self._settings.get(_LAST_PULL_KEY) or None
        pull_since = since
        if since:
            pull_since = to_iso(from_iso(since) - timedelta(seconds=_PULL_OVERLAP_SECONDS))
        remote = self._cloud.pull(pull_since)
        applied = 0
        newest: datetime | None = from_iso(since) if since else None
        for cloud_task in remote:
            local = self._tasks.get(cloud_task.id)
            if local is None or (
                cloud_task.updated_at is not None
                and local.updated_at is not None
                and cloud_task.updated_at > local.updated_at
            ):
                self._tasks.upsert(cloud_task)
                applied += 1
            if cloud_task.updated_at is not None and (
                newest is None or cloud_task.updated_at > newest
            ):
                newest = cloud_task.updated_at
        if newest is not None:
            self._settings.set(_LAST_PULL_KEY, to_iso(newest))

        return SyncResult(ok=True, pushed=len(pending), pulled=applied, message="Synced")
