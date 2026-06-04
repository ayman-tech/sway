"""A single task row widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.models.task import Task
from app.utils.datetime_utils import to_local


class TaskCard(QFrame):
    """Shows one task. Emits signals the parent view forwards to the service layer."""

    toggled = Signal(str, bool)  # task_id, completed
    editRequested = Signal(str)
    deleteRequested = Signal(str)

    def __init__(self, task: Task, overdue: bool = False, time_only: bool = False) -> None:
        super().__init__()
        self._task = task
        self._overdue = overdue
        self._time_only = time_only
        self.delete_btn: QPushButton | None = None
        self.setObjectName("TaskCard")
        self.setProperty("completed", task.is_completed)
        if not task.is_preview:
            # Clickable to edit (Google events open a reminder-only editor).
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Recurring previews can't be toggled (complete the current occurrence instead).
        # Google events CAN be marked done locally — but can't be deleted or edited.
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self._task.is_completed)
        if self._task.is_preview:
            self.checkbox.setEnabled(False)
            self.checkbox.setToolTip("Upcoming occurrence — complete the current one to advance")
        else:
            if self._task.is_read_only:
                self.checkbox.setToolTip("Mark done in Sway (won’t change Google Calendar)")
            self.checkbox.toggled.connect(
                lambda checked: self.toggled.emit(self._task.id, checked)
            )
        layout.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addSpacing(6)

        self.title_label = QLabel(self._task.title)
        self.title_label.setObjectName("TaskTitle")
        if self._task.is_completed:
            self.title_label.setProperty("completed", True)

        if self._time_only:
            # Calendar day list: title left, time right (date is already on the header).
            layout.addWidget(self.title_label, 1)
            time_text = self._time_text()
            if time_text:
                time_label = QLabel(time_text)
                time_label.setObjectName("TaskSubtitle")
                time_label.setProperty("overdue", self._overdue)
                layout.addWidget(time_label, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            text_col.addWidget(self.title_label)
            subtitle = self._subtitle()
            if subtitle:
                sub = QLabel(subtitle)
                sub.setObjectName("TaskSubtitle")
                sub.setProperty("overdue", self._overdue)
                text_col.addWidget(sub)
            layout.addLayout(text_col, 1)

        # Deleting isn't offered on recurring previews or read-only Google events.
        if not (self._task.is_preview or self._task.is_read_only):
            self.delete_btn = QPushButton("✕")
            self.delete_btn.setObjectName("TaskDeleteBtn")
            self.delete_btn.setFixedSize(24, 24)
            self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.delete_btn.setToolTip("Delete task")
            self.delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self._task.id))
            layout.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    @staticmethod
    def _fmt_time(dt) -> str:
        return to_local(dt).strftime("%I:%M %p").lstrip("0")

    def _time_text(self) -> str:
        """Just the time range (no date) for the calendar day list. Empty if untimed."""
        if not (self._task.due_at and self._task.has_time):
            return ""
        text = self._fmt_time(self._task.due_at)
        if self._task.end_at is not None:
            text += " – " + self._fmt_time(self._task.end_at)
        return text

    def _subtitle(self) -> str:
        parts: list[str] = []
        if self._task.due_at:
            local = to_local(self._task.due_at)
            if self._task.has_time:
                text = local.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")
                if self._task.end_at is not None:
                    end_local = to_local(self._task.end_at)
                    text += " – " + end_local.strftime("%I:%M %p").replace(" 0", " ").lstrip("0")
                parts.append(text)
            else:
                parts.append(local.strftime("%a %d %b"))
            if self._task.has_time:
                if self._task.is_read_only:
                    # Google events only remind if the user added one.
                    if self._task.reminder_minutes_before is not None:
                        parts.append("⏰")
                else:
                    # Timed tasks always remind at the task time; "+1" marks an extra reminder.
                    parts.append(
                        "⏰+1" if self._task.reminder_minutes_before is not None else "⏰"
                    )
        if self._task.is_recurring:
            parts.append("⟳")
        return "   ·   ".join(parts)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # Single click anywhere on the card (the checkbox and ✕ consume their own
        # clicks) opens the editor. Google events open a reminder-only editor.
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._task.is_preview
            and self.rect().contains(event.position().toPoint())
        ):
            self.editRequested.emit(self._task.id)
        super().mouseReleaseEvent(event)
