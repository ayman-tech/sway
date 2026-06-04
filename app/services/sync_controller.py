"""Runs sync off the GUI thread and on a schedule.

Network I/O happens on a worker thread; results come back via Qt signals (delivered to
the GUI thread). The SyncService it drives uses its own SQLite connection (see main.py),
so it never shares a connection with the GUI thread.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QTimer, Signal

from app.services.auth_service import AuthService
from app.services.sync_service import SyncService

_PERIODIC_INTERVAL_MS = 45_000


class SyncController(QObject):
    syncStarted = Signal()
    syncFinished = Signal(bool, str)  # ok, message

    def __init__(
        self, sync_service: SyncService, auth_service: AuthService, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._sync = sync_service
        self._auth = auth_service
        self._busy = False
        self._lock = threading.Lock()
        self._timer = QTimer(self)
        self._timer.setInterval(_PERIODIC_INTERVAL_MS)
        self._timer.timeout.connect(self.request_sync)

    def start(self) -> None:
        self._timer.start()
        self.request_sync()

    def stop(self) -> None:
        self._timer.stop()

    def request_sync(self) -> None:
        if self._auth.user is None:
            return
        with self._lock:
            if self._busy:
                return
            self._busy = True
        self.syncStarted.emit()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            result = self._sync.sync()
            ok, message = result.ok, result.message
        except Exception as exc:  # noqa: BLE001 (report any failure to the UI)
            ok, message = False, str(exc) or "Sync failed"
        finally:
            with self._lock:
                self._busy = False
        self.syncFinished.emit(ok, message)
