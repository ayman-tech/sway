"""Minimal nullable date / time fields.

Each field shows "None" until the user picks a value, and exposes a small ✕ to clear
back to None. No checkboxes — absence of a value *is* the "unset" state.
"""

from __future__ import annotations

from PySide6.QtCore import QDate, QPoint, QTime, Qt, Signal
from PySide6.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


class _BaseOptionalField(QWidget):
    """Shared layout: a field button (opens a popup) + a clear button."""

    changed = Signal()

    def __init__(self, placeholder: str) -> None:
        super().__init__()
        self._placeholder = placeholder
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._button = QPushButton(placeholder)
        self._button.setObjectName("FieldButton")
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.clicked.connect(self._open_popup)
        layout.addWidget(self._button, 1)

        self._clear_btn = QPushButton("✕")
        self._clear_btn.setObjectName("FieldClearBtn")
        self._clear_btn.setFixedSize(26, 26)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setToolTip("Clear")
        self._clear_btn.clicked.connect(lambda: self.clear())
        layout.addWidget(self._clear_btn)

        self._refresh()

    # subclasses implement these
    def _display_text(self) -> str:
        raise NotImplementedError

    def _open_popup(self) -> None:
        raise NotImplementedError

    def _has_value(self) -> bool:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def _refresh(self) -> None:
        self._button.setText(self._display_text() if self._has_value() else self._placeholder)
        # Clear button is always visible (clicking with no value is a harmless no-op).

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 (Qt override)
        super().setEnabled(enabled)
        self._button.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)


class OptionalDateField(_BaseOptionalField):
    def __init__(self, placeholder: str = "None") -> None:
        self._value: QDate | None = None
        super().__init__(placeholder)

    def _has_value(self) -> bool:
        return self._value is not None

    def _display_text(self) -> str:
        return self._value.toString("ddd, dd MMM yyyy") if self._value else self._placeholder

    def value(self) -> QDate | None:
        return self._value

    def set_value(self, date: QDate | None) -> None:
        self._value = date
        self._refresh()
        self.changed.emit()

    def clear(self) -> None:
        self.set_value(None)

    def _open_popup(self) -> None:
        popup = QWidget(self, Qt.WindowType.Popup)
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(4, 4, 4, 4)
        cal = QCalendarWidget()
        cal.setGridVisible(False)
        cal.setSelectedDate(self._value or QDate.currentDate())
        cal.clicked.connect(lambda d: (self.set_value(d), popup.close()))
        layout.addWidget(cal)
        popup.move(self._button.mapToGlobal(QPoint(0, self._button.height() + 2)))
        popup.show()


class OptionalTimeField(_BaseOptionalField):
    def __init__(self, placeholder: str = "None") -> None:
        self._value: QTime | None = None
        super().__init__(placeholder)

    def _has_value(self) -> bool:
        return self._value is not None

    def _display_text(self) -> str:
        return self._value.toString("hh:mm AP") if self._value else self._placeholder

    def value(self) -> QTime | None:
        return self._value

    def set_value(self, time: QTime | None) -> None:
        self._value = time
        self._refresh()
        self.changed.emit()

    def clear(self) -> None:
        self.set_value(None)

    def _open_popup(self) -> None:
        popup = QWidget(self, Qt.WindowType.Popup)
        layout = QHBoxLayout(popup)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        editor = QTimeEdit(self._value or QTime(9, 0))
        editor.setDisplayFormat("hh:mm AP")
        layout.addWidget(editor)
        ok = QPushButton("Set")
        ok.clicked.connect(lambda: (self.set_value(editor.time()), popup.close()))
        layout.addWidget(ok)
        popup.move(self._button.mapToGlobal(QPoint(0, self._button.height() + 2)))
        popup.show()
