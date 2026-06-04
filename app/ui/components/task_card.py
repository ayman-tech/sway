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

    def __init__(self, task: Task, overdue: bool = False) -> None:
        super().__init__()
        self._task = task
        self._overdue = overdue
        self.delete_btn: QPushButton | None = None
        self.setObjectName("TaskCard")
        self.setProperty("completed", task.is_completed)
        if not task.is_read_only:
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

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.title_label = QLabel(self._task.title)
        self.title_label.setObjectName("TaskTitle")
        if self._task.is_completed:
            self.title_label.setProperty("completed", True)
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
                # Timed tasks always remind at the task time; "+1" marks an extra reminder.
                parts.append("🔔+1" if self._task.reminder_minutes_before is not None else "🔔")
        if self._task.is_recurring:
            parts.append("⟳")
        return "   ·   ".join(parts)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # Single click anywhere on the card (the checkbox and ✕ consume their own
        # clicks) opens the editor — unless the task is read-only (Google-imported).
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._task.is_read_only
            and self.rect().contains(event.position().toPoint())
        ):
            self.editRequested.emit(self._task.id)
        super().mouseReleaseEvent(event)
