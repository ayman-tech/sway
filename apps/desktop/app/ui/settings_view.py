"""Settings: account, sync, and (later) Google Calendar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import apply_theme, get_theme, set_theme
from app.utils import autostart


class SettingsView(QWidget):
    syncRequested = Signal()
    signOutRequested = Signal()
    googleSetupRequested = Signal()
    googleConnectRequested = Signal()
    googleDisconnectRequested = Signal()
    apiKeyRegenRequested = Signal()
    apiKeyRevokeRequested = Signal()

    def __init__(
        self,
        account_email: str | None,
        sync_enabled: bool,
        google_available: bool = True,
        google_configured: bool = False,
        google_connected: bool = False,
    ) -> None:
        super().__init__()
        self._sync_enabled = sync_enabled
        self._google_available = google_available
        self._google_configured = google_configured
        self._google_connected = google_connected
        self._build(account_email)

    def _build(self, account_email: str | None) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 8, 20, 20)
        outer.setSpacing(8)

        # Account
        outer.addWidget(self._section("ACCOUNT"))
        if account_email:
            outer.addWidget(QLabel(f"Signed in as {account_email}"))
            sign_out = QPushButton("Sign out")
            sign_out.setCursor(Qt.CursorShape.PointingHandCursor)
            sign_out.clicked.connect(self.signOutRequested)
            outer.addWidget(self._left(sign_out))
        else:
            note = QLabel("Local only — cloud sync isn’t configured on this device.")
            note.setObjectName("TaskSubtitle")
            note.setWordWrap(True)
            outer.addWidget(note)

        outer.addSpacing(10)

        # Appearance
        outer.addWidget(self._section("APPEARANCE"))
        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)
        theme_row.addWidget(QLabel("Theme"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Dark", "dark")
        self._theme_combo.addItem("Light", "light")
        self._theme_combo.setMinimumContentsLength(6)
        self._theme_combo.setMinimumWidth(120)
        self._theme_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        idx = self._theme_combo.findData(get_theme())
        self._theme_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._theme_combo.activated.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_combo)
        theme_row.addStretch(1)
        outer.addLayout(theme_row)

        outer.addSpacing(10)

        # Startup
        outer.addWidget(self._section("STARTUP"))
        self._login_check = QCheckBox("Start Sway at login")
        self._login_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_check.setChecked(autostart.is_enabled())
        self._login_check.setEnabled(autostart.is_supported())
        self._login_check.toggled.connect(autostart.set_enabled)
        outer.addWidget(self._login_check)

        outer.addSpacing(10)

        # Sync
        outer.addWidget(self._section("SYNC"))
        sync_row = QHBoxLayout()
        self._sync_btn = QPushButton("Sync now")
        self._sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sync_btn.setEnabled(self._sync_enabled)
        self._sync_btn.clicked.connect(self.syncRequested)
        sync_row.addWidget(self._sync_btn)
        sync_row.addStretch(1)
        outer.addLayout(sync_row)
        self._status = QLabel("Idle." if self._sync_enabled else "Not configured.")
        self._status.setObjectName("TaskSubtitle")
        outer.addWidget(self._status)

        outer.addSpacing(10)

        # Google Calendar
        outer.addWidget(self._section("GOOGLE CALENDAR"))
        self._google_btn = QPushButton()
        self._google_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._google_btn.clicked.connect(self._on_google_clicked)
        outer.addWidget(self._left(self._google_btn))
        self._google_status = QLabel()
        self._google_status.setObjectName("TaskSubtitle")
        outer.addWidget(self._google_status)
        self._google_change_btn = QPushButton("Change credentials")
        self._google_change_btn.setObjectName("LinkButton")
        self._google_change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._google_change_btn.clicked.connect(self.googleSetupRequested)
        outer.addWidget(self._left(self._google_change_btn))
        self._refresh_google()

        outer.addSpacing(10)

        # Sway API Key
        outer.addWidget(self._section("SWAY API KEY"))
        self._api_key_field = QLineEdit()
        self._api_key_field.setReadOnly(True)
        self._api_key_field.setPlaceholderText("No key generated yet.")
        self._api_key_field.setMinimumWidth(320)
        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        key_row.addWidget(self._api_key_field, 1)
        self._api_key_copy_btn = QPushButton("Copy")
        self._api_key_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._api_key_copy_btn.setEnabled(False)
        self._api_key_copy_btn.clicked.connect(self._copy_api_key)
        key_row.addWidget(self._api_key_copy_btn)
        outer.addLayout(key_row)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._api_key_regen_btn = QPushButton("Generate key")
        self._api_key_regen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._api_key_regen_btn.clicked.connect(self.apiKeyRegenRequested)
        btn_row.addWidget(self._api_key_regen_btn)
        self._api_key_revoke_btn = QPushButton("Revoke key")
        self._api_key_revoke_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._api_key_revoke_btn.setVisible(False)
        self._api_key_revoke_btn.clicked.connect(self.apiKeyRevokeRequested)
        btn_row.addWidget(self._api_key_revoke_btn)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        outer.addStretch(1)

    def _on_google_clicked(self) -> None:
        if not self._google_configured:
            self.googleSetupRequested.emit()
        elif self._google_connected:
            self.googleDisconnectRequested.emit()
        else:
            self.googleConnectRequested.emit()

    def _refresh_google(self) -> None:
        self._google_btn.setEnabled(self._google_available)
        # The "Change credentials" link is only useful once some are saved.
        self._google_change_btn.setVisible(self._google_available and self._google_configured)
        if not self._google_available:
            self._google_btn.setText("Set up Google Calendar")
            self._google_status.setText("Sign in and configure the Sway API to use Google Calendar.")
        elif not self._google_configured:
            self._google_btn.setText("Set up Google Calendar")
            self._google_status.setText("Connect your Google Calendar to import events.")
        elif self._google_connected:
            self._google_btn.setText("Disconnect Google Calendar")
            self._google_status.setText("Connected — your events import read-only.")
        else:
            self._google_btn.setText("Connect Google Calendar")
            self._google_status.setText("Not connected.")

    def set_google_configured(self, configured: bool) -> None:
        self._google_configured = configured
        self._refresh_google()

    def set_google_connected(self, connected: bool) -> None:
        self._google_connected = connected
        self._refresh_google()

    def set_google_status(self, text: str) -> None:
        self._google_status.setText(text)

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("GroupHeader")
        return label

    @staticmethod
    def _left(widget: QWidget) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(widget)
        row.addStretch(1)
        return wrap

    def _on_theme_changed(self, _index: int) -> None:
        name = self._theme_combo.currentData()
        set_theme(name)
        apply_theme(name)  # live

    def set_sync_status(self, text: str) -> None:
        self._status.setText(text)

    def set_api_key(self, key: str | None, created_at: str | None = None) -> None:
        if key:
            self._api_key_field.setText(key)
            self._api_key_copy_btn.setEnabled(True)
            self._api_key_regen_btn.setText("Regenerate key")
            self._api_key_revoke_btn.setVisible(True)
        else:
            self._api_key_field.clear()
            self._api_key_copy_btn.setEnabled(False)
            self._api_key_regen_btn.setText("Generate key")
            self._api_key_revoke_btn.setVisible(False)

    def _copy_api_key(self) -> None:
        text = self._api_key_field.text()
        if text:
            QGuiApplication.clipboard().setText(text)
