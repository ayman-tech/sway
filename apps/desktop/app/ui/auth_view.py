"""Sway login / create-account screen (email + password via Supabase)."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.auth_service import AuthService


class AuthView(QWidget):
    """Collects credentials and authenticates. Emits `authenticated` on success.

    Network calls run on a worker thread; the result is marshalled back to the GUI
    thread via the private `_result` signal.
    """

    authenticated = Signal()
    _result = Signal(bool, str)

    def __init__(self, auth_service: AuthService) -> None:
        super().__init__()
        self._auth = auth_service
        self._signing_up = False
        self._build()
        self._result.connect(self._on_result)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        card = QWidget()
        card.setObjectName("AuthCard")
        card.setFixedWidth(340)
        col = QVBoxLayout(card)
        col.setContentsMargins(28, 28, 28, 28)
        col.setSpacing(10)

        title = QLabel("Sway")
        title.setObjectName("SidebarLogo")
        col.addWidget(title)
        self._subtitle = QLabel("Sign in to sync your tasks across devices.")
        self._subtitle.setObjectName("TaskSubtitle")
        self._subtitle.setWordWrap(True)
        col.addWidget(self._subtitle)
        col.addSpacing(6)

        self._email = QLineEdit()
        self._email.setPlaceholderText("Email")
        col.addWidget(self._email)
        self._password = QLineEdit()
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.returnPressed.connect(self._submit)
        col.addWidget(self._password)

        self._error = QLabel("")
        self._error.setObjectName("AuthError")
        self._error.setWordWrap(True)
        self._error.hide()
        col.addWidget(self._error)

        self._submit_btn = QPushButton("Sign in")
        self._submit_btn.setObjectName("AddTaskButton")
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.clicked.connect(self._submit)
        col.addWidget(self._submit_btn)

        self._toggle_btn = QPushButton("Don’t have an account? Create one")
        self._toggle_btn.setObjectName("LinkButton")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle_mode)
        col.addWidget(self._toggle_btn)

        row.addWidget(card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def _toggle_mode(self) -> None:
        self._signing_up = not self._signing_up
        if self._signing_up:
            self._submit_btn.setText("Create account")
            self._toggle_btn.setText("Already have an account? Sign in")
            self._subtitle.setText("Create an account to sync your tasks across devices.")
        else:
            self._submit_btn.setText("Sign in")
            self._toggle_btn.setText("Don’t have an account? Create one")
            self._subtitle.setText("Sign in to sync your tasks across devices.")
        self._error.hide()

    def _submit(self) -> None:
        email = self._email.text().strip()
        password = self._password.text()
        if not email or not password:
            self._show_error("Enter your email and password.")
            return
        self._set_busy(True)
        signing_up = self._signing_up
        threading.Thread(
            target=self._worker, args=(email, password, signing_up), daemon=True
        ).start()

    def _worker(self, email: str, password: str, signing_up: bool) -> None:
        try:
            if signing_up:
                self._auth.sign_up(email, password)
            else:
                self._auth.sign_in(email, password)
            self._result.emit(True, "")
        except Exception as exc:  # noqa: BLE001
            self._result.emit(False, str(exc))

    def _on_result(self, ok: bool, message: str) -> None:
        self._set_busy(False)
        if ok:
            self._password.clear()
            self._error.hide()
            self.authenticated.emit()
        else:
            self._show_error(message)

    def _set_busy(self, busy: bool) -> None:
        self._email.setDisabled(busy)
        self._password.setDisabled(busy)
        self._toggle_btn.setDisabled(busy)
        self._submit_btn.setDisabled(busy)
        if busy:
            self._submit_btn.setText("Please wait…")
        else:
            self._submit_btn.setText("Create account" if self._signing_up else "Sign in")

    def _show_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.show()
