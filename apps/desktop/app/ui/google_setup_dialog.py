"""Dialog to enter Google OAuth client credentials (so no .env editing is needed)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

_HELP = (
    "Create a free OAuth client in Google Cloud (one time):\n"
    "1. console.cloud.google.com → new project\n"
    "2. APIs & Services → Library → enable “Google Calendar API”\n"
    "3. OAuth consent screen → External → add your email as a Test user\n"
    "4. Credentials → Create OAuth client ID → Web application\n"
    "5. Add the callback URI below as an authorized redirect URI\n"
    "6. Paste the Client ID and Client secret below."
)


class GoogleSetupDialog(QDialog):
    """Collects Client ID + secret. Read values via `values()` after exec()."""

    def __init__(
        self,
        parent: QWidget | None = None,
        client_id: str = "",
        redirect_uri: str = "",
    ) -> None:
        super().__init__(parent)
        self._client_id_value = client_id
        self._redirect_uri_value = redirect_uri
        self.setWindowTitle("Set up Google Calendar")
        self.setMinimumWidth(460)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        help_label = QLabel(_HELP)
        help_label.setObjectName("TaskSubtitle")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        layout.addSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._redirect_uri = QLineEdit(self._redirect_uri_value)
        self._redirect_uri.setReadOnly(True)
        form.addRow("Callback URI", self._redirect_uri)
        self._client_id = QLineEdit(self._client_id_value)
        self._client_id.setPlaceholderText("xxxx.apps.googleusercontent.com")
        form.addRow("Client ID", self._client_id)
        self._client_secret = QLineEdit()
        self._client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._client_secret.setPlaceholderText("GOCSPX-…")
        form.addRow("Client secret", self._client_secret)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save & Connect")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if self._client_id.text().strip() and self._client_secret.text().strip():
            self.accept()

    def values(self) -> tuple[str, str]:
        return self._client_id.text().strip(), self._client_secret.text().strip()
