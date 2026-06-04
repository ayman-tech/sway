"""Sway application entry point and top-level orchestration."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.constants import APP_NAME, APP_ORG
from app.db.database import Database
from app.notifications.notifier import Notifier
from app.repositories.settings_repo import SettingsRepository
from app.repositories.sqlite_repo import TaskRepository
from app.repositories.supabase_repo import SupabaseRepo
from app.services.auth_service import AuthService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.reminder_service import ReminderService
from app.services.sync_controller import SyncController
from app.services.sync_service import SyncService
from app.services.task_service import TaskService
from app.ui.auth_view import AuthView
from app.ui.icon import make_app_icon
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme, get_theme
from app.utils.logger import get_logger, setup_logging


class SwayApp:
    """Owns long-lived services and switches between the login and main windows."""

    def __init__(self, qapp: QApplication) -> None:
        self._qapp = qapp
        self._db = Database()
        self._settings = SettingsRepository(self._db)
        self._task_service = TaskService(TaskRepository(self._db))
        self._notifier = Notifier()
        self._reminders = ReminderService(self._task_service, self._settings, self._notifier)
        # Auth's session tokens are written from the sign-in worker thread, so its
        # settings use a thread-safe connection (never the GUI's).
        self._auth_db = Database(check_same_thread=False)
        self._auth = AuthService(SettingsRepository(self._auth_db))
        # Google service has its own thread-safe connection (token/syncToken), since
        # connect runs on a worker thread and import runs on the sync worker.
        self._google_db = Database(check_same_thread=False)
        self._google = GoogleCalendarService(SettingsRepository(self._google_db))
        self._sync = self._build_sync() if self._auth.is_configured() else None

        self._window: MainWindow | None = None
        self._auth_view: AuthView | None = None

        self._notifier.quitRequested.connect(self._qapp.quit)
        self._notifier.openRequested.connect(self._on_open)

    def _build_sync(self) -> SyncController:
        # The sync worker runs on a background thread, so it uses its OWN SQLite
        # connection (separate from the GUI's) to the same database file.
        sync_db = Database(check_same_thread=False)
        sync_service = SyncService(
            TaskRepository(sync_db),
            SupabaseRepo(self._auth),
            self._auth,
            SettingsRepository(sync_db),
            google_service=self._google,
        )
        return SyncController(sync_service, self._auth)

    def start(self) -> None:
        self._task_service.purge_old_completed()  # drop completed tasks past retention
        if self._auth.is_configured() and not self._auth.restore_session():
            self._show_login()
        else:
            self._show_main()
        self._reminders.start()

    # ---- window switching ----
    def _show_login(self) -> None:
        self._auth_view = AuthView(self._auth)
        self._auth_view.setWindowTitle(APP_NAME)
        self._auth_view.resize(440, 460)
        self._auth_view.authenticated.connect(self._on_authenticated)
        self._auth_view.show()

    def _on_authenticated(self) -> None:
        if self._auth_view is not None:
            self._auth_view.close()
            self._auth_view = None
        self._show_main()

    def _show_main(self) -> None:
        self._window = MainWindow(self._task_service, self._auth, self._sync, self._google)
        if self._notifier.available:
            self._window.set_minimize_to_tray(True)
        self._window.tasksChanged.connect(self._reminders.reschedule)
        if self._sync is not None:
            self._window.tasksChanged.connect(self._sync.request_sync)
        self._window.signOutRequested.connect(self._on_sign_out)
        self._window.show()
        if self._sync is not None:
            self._sync.start()

    def _on_sign_out(self) -> None:
        if self._sync is not None:
            self._sync.stop()
        self._auth.sign_out()
        if self._window is not None:
            self._window.set_minimize_to_tray(False)
            self._window.hide()
            self._window.deleteLater()
            self._window = None
        self._show_login()

    def _on_open(self) -> None:
        if self._window is not None:
            self._window.show_and_raise()
        elif self._auth_view is not None:
            self._auth_view.show()
            self._auth_view.raise_()
            self._auth_view.activateWindow()


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setWindowIcon(make_app_icon())
    apply_theme(get_theme())
    app.setQuitOnLastWindowClosed(False)  # keep running in the tray
    get_logger("sway").info("Starting Sway")

    sway = SwayApp(app)
    if not sway._notifier.available:
        app.setQuitOnLastWindowClosed(True)
    sway.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
