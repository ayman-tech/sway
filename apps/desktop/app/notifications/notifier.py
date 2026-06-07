"""System tray icon + native desktop notifications."""

from __future__ import annotations

import shutil
import subprocess
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.constants import APP_NAME
from app.ui.icon import make_app_icon


class Notifier(QObject):
    """Owns the tray icon and turns reminder events into desktop notifications.

    Keeping a tray icon present is what lets the app run in the background (window
    closed) and still fire reminders.
    """

    openRequested = Signal()
    quitRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(make_app_icon(), self)
        self._tray.setToolTip(APP_NAME)

        menu = QMenu()
        open_action = menu.addAction("Open Sway")
        open_action.triggered.connect(self.openRequested)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quitRequested)
        self._tray.setContextMenu(menu)

        self._tray.activated.connect(self._on_activated)
        self._tray.messageClicked.connect(self.openRequested)
        self._tray.show()

    @property
    def available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.openRequested.emit()

    def show_message(self, title: str, body: str) -> None:
        # A packaged .app has a bundle id, so native notifications work and show as
        # "Sway" (and can be set to persistent "Alerts" in System Settings). Running
        # from the interpreter has no bundle id, so on macOS fall back to osascript.
        use_osascript = (
            sys.platform == "darwin"
            and not getattr(sys, "frozen", False)
            and shutil.which("osascript")
        )
        if use_osascript:
            _macos_notify(title, body)
        else:
            self._tray.showMessage(
                title, body, QSystemTrayIcon.MessageIcon.Information, 10_000
            )


def _macos_notify(title: str, body: str) -> None:
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')

    script = (
        f'display notification "{esc(body)}" '
        f'with title "{esc(APP_NAME)}" subtitle "{esc(title)}"'
    )
    try:
        subprocess.Popen(["osascript", "-e", script])  # noqa: S603,S607 (fixed args)
    except OSError:
        pass
