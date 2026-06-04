"""Theme loading + persistence (dark / light), stored via QSettings."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.utils.resources import resource_path

THEMES = ("dark", "light")
_DEFAULT = "dark"
_KEY = "theme"


def get_theme() -> str:
    value = QSettings().value(_KEY, _DEFAULT)
    return value if value in THEMES else _DEFAULT


def set_theme(name: str) -> None:
    QSettings().setValue(_KEY, name if name in THEMES else _DEFAULT)


def load_stylesheet(name: str) -> str:
    path = resource_path("app", "assets", "styles", f"{name}.qss")
    try:
        return path.read_text()
    except OSError:
        return ""


def apply_theme(name: str) -> None:
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(load_stylesheet(name))
