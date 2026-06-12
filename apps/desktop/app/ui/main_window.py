"""Main application window: left sidebar + stacked views."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from PySide6.QtCore import QEvent, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.constants import APP_NAME
from app.repositories.settings_repo import SettingsRepository
from app.services.auth_service import AuthService
from app.services.api_key_service import ApiKeyError, ApiKeyService
from app.services.google_api_service import GoogleApiService, GoogleStatus
from app.services.sync_controller import SyncController
from app.services.task_service import COMPLETED_RETENTION_DAYS, TaskService
from app.ui.availability_view import AvailabilityView
from app.ui.calendar_view import CalendarView
from app.ui.google_setup_dialog import GoogleSetupDialog
from app.ui.settings_view import SettingsView
from app.ui.task_editor_dialog import TaskEditorDialog
from app.ui.task_list_view import TaskListView
from app.utils.datetime_utils import utc_now

_NAV_ITEMS = [
    ("tasks", "  ✓   Tasks", "Tasks"),
    ("calendar", "  ▦   Calendar", "Calendar"),
    ("completed", "  ◎   Completed", "Completed"),
    ("availability", "  ◈   Availability", "Availability"),
    ("settings", "  ⚙   Settings", "Settings"),
]
_TITLES = {key: title for key, _, title in _NAV_ITEMS}


class MainWindow(QWidget):
    tasksChanged = Signal()  # emitted after any task create/update/complete/delete
    signOutRequested = Signal()
    _googleResult = Signal(str, bool, object)
    _apiKeyResult = Signal(object, object)  # (key | None, created_at | None)

    def __init__(
        self,
        service: TaskService,
        auth_service: AuthService | None = None,
        sync_controller: SyncController | None = None,
        google_service: GoogleApiService | None = None,
        settings_repo: SettingsRepository | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._auth = auth_service
        self._sync = sync_controller
        self._google = google_service
        self._api_key_svc = ApiKeyService(auth_service) if auth_service else None
        self._google_status: GoogleStatus | None = None
        self._google_poll_attempts = 0
        self._google_poll = QTimer(self)
        self._google_poll.setInterval(2_000)
        self._google_poll.timeout.connect(self._refresh_google_status)
        if settings_repo is None:
            from app.db.database import Database
            settings_repo = SettingsRepository(Database())
        self._settings_repo = settings_repo
        self._minimize_to_tray = False
        self.setWindowTitle(APP_NAME)
        self.resize(960, 640)
        self._view_index: dict[str, int] = {}
        self._build()
        if self._sync is not None:
            self._sync.syncStarted.connect(
                lambda: self._settings_view.set_sync_status("Syncing…")
            )
            self._sync.syncFinished.connect(self._on_sync_finished)
        self._googleResult.connect(self._on_google_result)
        self._apiKeyResult.connect(self._settings_view.set_api_key)
        self.refresh()
        self._refresh_google_status()
        self._refresh_api_key()

    def set_minimize_to_tray(self, enabled: bool) -> None:
        self._minimize_to_tray = enabled

    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # When a tray icon is present, closing the window just hides it so reminders
        # keep firing in the background. Quit happens from the tray menu.
        if self._minimize_to_tray:
            event.ignore()
            self.hide()
        else:
            event.accept()

    def changeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # Sync when the window regains focus (one of the v1 sync triggers).
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            if self._sync is not None:
                self._sync.request_sync()
        super().changeEvent(event)

    # ---- sync ----
    def _on_sync_requested(self) -> None:
        if self._sync is not None:
            self._settings_view.set_sync_status("Syncing…")
            self._sync.request_sync(force_google=True)

    def _on_sync_finished(self, ok: bool, message: str) -> None:
        if ok:
            self.refresh()
            self._settings_view.set_sync_status(
                f"Last synced at {datetime.now().strftime('%I:%M %p').lstrip('0')}"
            )
        else:
            self._settings_view.set_sync_status(f"Sync error: {message}")
        self._refresh_google_status()

    # ---- Google Calendar ----
    def _on_google_setup(self) -> None:
        status = self._google_status
        if self._google is None or status is None:
            self._settings_view.set_google_status("Google status is still loading.")
            return
        if not status.setup_available:
            self._settings_view.set_google_status(
                "Google setup is unavailable until the API encryption key is configured."
            )
            return
        dialog = GoogleSetupDialog(
            self,
            client_id=status.client_id or "",
            redirect_uri=status.redirect_uri,
        )
        if not dialog.exec():
            return
        client_id, client_secret = dialog.values()
        self._settings_view.set_google_status("Saving credentials…")
        self._run_google("authorize", lambda: self._google.save_credentials(client_id, client_secret))

    def _on_google_connect(self) -> None:
        if self._google is None:
            return
        self._settings_view.set_google_status("Opening browser to authorize…")
        self._run_google("authorize", self._google.connect_url)

    def _on_google_disconnect(self) -> None:
        if self._google is not None:
            self._settings_view.set_google_status("Disconnecting…")
            self._run_google("disconnect", self._google.disconnect)

    def _refresh_api_key(self) -> None:
        if self._api_key_svc is None:
            return
        def worker() -> None:
            try:
                data = self._api_key_svc.get()
                self._apiKeyResult.emit(data.get("key"), data.get("created_at"))
            except ApiKeyError:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _on_api_key_regen(self) -> None:
        if self._api_key_svc is None:
            return
        def worker() -> None:
            try:
                data = self._api_key_svc.generate()
                self._apiKeyResult.emit(data.get("key"), data.get("created_at"))
            except ApiKeyError:
                self._apiKeyResult.emit(None, None)
        threading.Thread(target=worker, daemon=True).start()

    def _on_api_key_revoke(self) -> None:
        if self._api_key_svc is None:
            return
        def worker() -> None:
            try:
                self._api_key_svc.revoke()
                self._apiKeyResult.emit(None, None)
            except ApiKeyError:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_google_status(self) -> None:
        if self._google is not None:
            self._run_google("status", self._google.status)

    def _run_google(self, action: str, operation) -> None:
        def worker() -> None:
            try:
                self._googleResult.emit(action, True, operation())
            except Exception as exc:  # noqa: BLE001
                self._googleResult.emit(action, False, str(exc) or "Google Calendar request failed.")
        threading.Thread(target=worker, daemon=True).start()

    def _on_google_result(self, action: str, ok: bool, result: object) -> None:
        if not ok:
            self._settings_view.set_google_status(str(result))
            return
        if action == "authorize":
            QDesktopServices.openUrl(QUrl(str(result)))
            self._google_poll_attempts = 0
            self._google_poll.start()
            self._settings_view.set_google_status("Finish authorization in your browser…")
            return
        if action == "disconnect":
            self._refresh_google_status()
            return
        if action != "status" or not isinstance(result, GoogleStatus):
            return
        polling = self._google_poll.isActive()
        self._google_status = result
        self._settings_view.set_google_configured(result.configured)
        self._settings_view.set_google_connected(result.connected)
        if result.connected:
            self._google_poll.stop()
            self._settings_view.set_google_status(
                f"Connected as {result.account or 'Google Calendar'}"
            )
            if self._sync is not None and polling:
                self._sync.request_sync()
        elif result.last_sync_error:
            self._settings_view.set_google_status(result.last_sync_error)
        elif not result.setup_available:
            self._settings_view.set_google_status("Google setup is unavailable on the API server.")
        if polling:
            self._google_poll_attempts += 1
            if self._google_poll_attempts >= 60:
                self._google_poll.stop()

    # ---- construction ----
    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_stack(), 1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 18)
        layout.setSpacing(8)

        logo = QLabel(APP_NAME)
        logo.setObjectName("SidebarLogo")
        layout.addWidget(logo)

        add_btn = QPushButton("  +   Add task")
        add_btn.setObjectName("AddTaskButton")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_task)
        layout.addWidget(add_btn)
        layout.addSpacing(8)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        for i, (key, label, _title) in enumerate(_NAV_ITEMS):
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._switch_to(k))
            self._nav_group.addButton(btn, i)
            layout.addWidget(btn)
            if key == "tasks":
                btn.setChecked(True)

        layout.addStretch(1)
        return sidebar

    def _build_stack(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = QLabel("Tasks")
        self._header.setObjectName("ViewHeader")
        outer.addWidget(self._header)

        self._stack = QStackedWidget()

        # Tasks (active)
        self._tasks_view = TaskListView(empty_text="No tasks yet. Click “Add task” to begin.")
        self._tasks_view.taskToggled.connect(self._on_toggle)
        self._tasks_view.taskEditRequested.connect(self._on_edit_task)
        self._tasks_view.taskDeleteRequested.connect(self._on_delete_task)
        self._register_view("tasks", self._tasks_view)

        # Calendar (month view)
        self._calendar_view = CalendarView(self._service)
        self._calendar_view.taskToggled.connect(self._on_toggle)
        self._calendar_view.taskEditRequested.connect(self._on_edit_task)
        self._calendar_view.taskDeleteRequested.connect(self._on_delete_task)
        self._register_view("calendar", self._calendar_view)

        # Completed
        self._completed_view = TaskListView(empty_text="No completed tasks yet.")
        self._completed_view.taskToggled.connect(self._on_toggle)
        self._completed_view.taskDeleteRequested.connect(self._on_delete_task)
        self._register_view("completed", self._completed_view)

        # Availability (personal when2meet-style grid)
        self._availability_view = AvailabilityView(self._settings_repo, self._service, self._auth)
        self._register_view("availability", self._availability_view)

        # Settings
        account_email = self._auth.user.email if self._auth and self._auth.user else None
        self._settings_view = SettingsView(
            account_email=account_email,
            sync_enabled=self._sync is not None,
            google_available=self._google is not None,
            google_configured=False,
            google_connected=False,
        )
        self._settings_view.syncRequested.connect(self._on_sync_requested)
        self._settings_view.signOutRequested.connect(self.signOutRequested)
        self._settings_view.googleSetupRequested.connect(self._on_google_setup)
        self._settings_view.googleConnectRequested.connect(self._on_google_connect)
        self._settings_view.googleDisconnectRequested.connect(self._on_google_disconnect)
        self._settings_view.apiKeyRegenRequested.connect(self._on_api_key_regen)
        self._settings_view.apiKeyRevokeRequested.connect(self._on_api_key_revoke)
        self._register_view("settings", self._settings_view)

        outer.addWidget(self._stack, 1)
        return container

    def _register_view(self, key: str, widget: QWidget) -> None:
        self._view_index[key] = self._stack.addWidget(widget)

    # ---- navigation ----
    def _switch_to(self, key: str) -> None:
        self._stack.setCurrentIndex(self._view_index[key])
        self._header.setText(_TITLES[key])
        self.refresh()

    # ---- data refresh ----
    def refresh(self) -> None:
        self._tasks_view.set_groups(self._service.get_active_groups())
        self._refresh_completed()
        self._calendar_view.refresh()

    def _refresh_completed(self) -> None:
        # Completed tasks past the retention window are removed, so we just show the
        # bounded window (no "older" to load).
        cutoff = utc_now() - timedelta(days=COMPLETED_RETENTION_DAYS)
        self._completed_view.set_groups(self._service.get_completed_groups(since=cutoff))

    # ---- actions ----
    def _on_add_task(self) -> None:
        dialog = TaskEditorDialog(self)
        if dialog.exec():
            v = dialog.values()
            try:
                self._service.create_task(
                    v["title"],
                    description=v["description"],
                    due_at=v["due_at"],
                    due_date=v["due_date"],
                    end_at=v["end_at"],
                    end_date=v["end_date"],
                    reminder_minutes_before=v["reminder_minutes_before"],
                    recurrence_rule=v["recurrence_rule"],
                    recurrence_timezone=v["recurrence_timezone"],
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save", str(exc))
                return
            self.refresh()
            self.tasksChanged.emit()

    def _on_edit_task(self, task_id: str) -> None:
        task = self._service.get_task(task_id)
        if task is None:
            return
        dialog = TaskEditorDialog(self, task=task)
        if dialog.exec():
            v = dialog.values()
            try:
                if task.is_read_only:
                    # Google event: only the additional reminder is editable.
                    self._service.set_reminder(task_id, v["reminder_minutes_before"])
                else:
                    self._service.update_task(
                        task_id,
                        title=v["title"],
                        description=v["description"],
                        due_at=v["due_at"],
                        due_date=v["due_date"],
                        end_at=v["end_at"],
                        end_date=v["end_date"],
                        reminder_minutes_before=v["reminder_minutes_before"],
                        recurrence_rule=v["recurrence_rule"],
                        recurrence_timezone=v["recurrence_timezone"],
                    )
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save", str(exc))
                return
            self.refresh()
            self.tasksChanged.emit()

    def _on_toggle(self, task_id: str, completed: bool) -> None:
        if completed:
            self._service.complete_task(task_id)
        else:
            self._service.uncomplete_task(task_id)
        self.refresh()
        self.tasksChanged.emit()

    def _on_delete_task(self, task_id: str) -> None:
        task = self._service.get_task(task_id)
        if task is not None and task.is_recurring:
            choice = self._ask_recurring_delete(task.title)
            if choice == "cancel":
                return
            if choice == "this":
                self._service.skip_occurrence(task_id)
            else:
                self._service.delete_task(task_id)
        else:
            self._service.delete_task(task_id)
        self.refresh()
        self.tasksChanged.emit()

    def _ask_recurring_delete(self, title: str) -> str:
        """Ask whether to delete one occurrence or the whole series. Returns this|all|cancel.

        Custom dialog so we control button placement: Cancel on the left, the two
        delete actions on the right.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Delete recurring task")
        dialog.setMinimumWidth(380)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(6)

        heading = QLabel(f"“{title}” repeats.")
        heading.setStyleSheet("font-weight: 600;")
        layout.addWidget(heading)
        info = QLabel("Delete just this occurrence, or all of them?")
        info.setObjectName("TaskSubtitle")
        layout.addWidget(info)
        layout.addSpacing(10)

        result = {"value": "cancel"}
        cancel_btn = QPushButton("Cancel")
        this_btn = QPushButton("This occurrence")
        all_btn = QPushButton("All occurrences")
        this_btn.setDefault(True)
        cancel_btn.clicked.connect(dialog.reject)
        this_btn.clicked.connect(lambda: (result.update(value="this"), dialog.accept()))
        all_btn.clicked.connect(lambda: (result.update(value="all"), dialog.accept()))

        row = QHBoxLayout()
        row.addWidget(cancel_btn)
        row.addStretch(1)
        row.addWidget(this_btn)
        row.addWidget(all_btn)
        layout.addLayout(row)

        dialog.exec()
        return result["value"]
