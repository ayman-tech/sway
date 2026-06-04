"""Add / edit task dialog."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.task import Task
from app.services.recurrence import (
    REPEAT_OPTIONS,
    build_rule_string,
    parse_rule_string,
)
from app.ui.components.optional_datetime import OptionalDateField, OptionalTimeField
from app.utils.datetime_utils import to_local

# Optional earlier reminder, on top of the always-on reminder at the task time.
_EXTRA_REMINDER_OPTIONS = [
    ("10 min before", 10),
    ("30 min before", 30),
    ("1 hr before", 60),
    ("3 hr before", 180),
    ("1 day early", 1440),
]

# Duration presets (minutes); end_at = due_at + duration. "Custom…" prompts for minutes.
_DURATION_OPTIONS = [
    ("30 min", 30),
    ("1 hr", 60),
    ("2 hr", 120),
    ("3 hr", 180),
]


def _fmt_duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} hr {mins} min"
    if hours:
        return f"{hours} hr"
    return f"{mins} min"


class TaskEditorDialog(QDialog):
    """Collects task fields. Returns values via `values()` after exec().

    Minimal scheduling UI: a Date and a Time field, both "None" by default. A task
    has a due date once Date is set; Time is enabled only once a Date exists, and the
    reminder is enabled only once a Time exists.
    """

    def __init__(self, parent: QWidget | None = None, task: Task | None = None) -> None:
        super().__init__(parent)
        self._task = task
        self._custom_minutes: int | None = None
        self.setWindowTitle("Edit Task" if task else "New Task")
        self.setMinimumWidth(420)
        self._build()
        if task:
            self._load(task)
        self._sync_enabled()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("What needs to be done?")
        form.addRow("Title", self.title_edit)

        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("Notes (optional)")
        self.desc_edit.setFixedHeight(80)
        form.addRow("Description", self.desc_edit)

        self.date_field = OptionalDateField()
        self.date_field.changed.connect(self._sync_enabled)
        form.addRow("Date", self.date_field)

        self.time_field = OptionalTimeField()
        self.time_field.changed.connect(self._sync_enabled)
        form.addRow("Time", self.time_field)

        # Optional duration → end_at = due_at + duration (timed tasks only).
        self.duration_combo = QComboBox()
        self.duration_combo.addItem("None", None)
        for label, minutes in _DURATION_OPTIONS:
            self.duration_combo.addItem(label, minutes)
        self.duration_combo.addItem("Custom…", "custom")
        self.duration_combo.activated.connect(self._on_duration_activated)
        form.addRow("Duration", self.duration_combo)

        # Timed tasks always remind at the task time; this is an optional *earlier* reminder.
        self.reminder_combo = QComboBox()
        self.reminder_combo.addItem("None", None)
        for label, minutes in _EXTRA_REMINDER_OPTIONS:
            self.reminder_combo.addItem(label, minutes)
        self.reminder_combo.setToolTip(
            "Timed tasks always remind you at the task time. "
            "This adds an extra, earlier reminder."
        )
        form.addRow("Additional reminder", self.reminder_combo)

        # Recurrence: a Repeat preset plus an optional end date (empty = never).
        self.repeat_combo = QComboBox()
        for label, rule in REPEAT_OPTIONS:
            self.repeat_combo.addItem(label, rule)
        self.repeat_combo.currentIndexChanged.connect(self._sync_enabled)
        form.addRow("Repeat", self.repeat_combo)

        self.until_field = OptionalDateField(placeholder="Never")
        form.addRow("Repeat until", self.until_field)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync_enabled(self) -> None:
        has_date = self.date_field.value() is not None
        # No date → time is meaningless; disable and clear it.
        if not has_date and self.time_field.value() is not None:
            self.time_field.blockSignals(True)
            self.time_field.clear()
            self.time_field.blockSignals(False)
        self.time_field.setEnabled(has_date)

        has_time = has_date and self.time_field.value() is not None
        # No time → no reminder and no duration.
        if not has_time and self.reminder_combo.currentData() is not None:
            self.reminder_combo.setCurrentIndex(0)
        self.reminder_combo.setEnabled(has_time)
        if not has_time and self.duration_combo.currentData() is not None:
            self.duration_combo.setCurrentIndex(0)
        self.duration_combo.setEnabled(has_time)

        # Recurrence needs a date; the end-date only matters when repeating.
        if not has_date and self.repeat_combo.currentData() is not None:
            self.repeat_combo.setCurrentIndex(0)
        self.repeat_combo.setEnabled(has_date)
        repeats = self.repeat_combo.currentData() is not None
        if not repeats and self.until_field.value() is not None:
            self.until_field.clear()
        self.until_field.setEnabled(repeats)

    def _load(self, task: Task) -> None:
        self.title_edit.setText(task.title)
        self.desc_edit.setPlainText(task.description or "")
        if task.due_at:
            local = to_local(task.due_at)
            self.date_field.set_value(QDate(local.year, local.month, local.day))
            if task.has_time:
                self.time_field.set_value(QTime(local.hour, local.minute))
                ridx = self.reminder_combo.findData(task.reminder_minutes_before)
                if ridx >= 0:
                    self.reminder_combo.setCurrentIndex(ridx)
                if task.end_at is not None:
                    minutes = round((task.end_at - task.due_at).total_seconds() / 60)
                    if minutes > 0:
                        self._select_duration(minutes)
        if task.recurrence_rule:
            freq, interval, until = parse_rule_string(task.recurrence_rule)
            self._select_repeat((freq, interval))
            if until is not None:
                local_until = to_local(until)
                self.until_field.set_value(
                    QDate(local_until.year, local_until.month, local_until.day)
                )

    def _on_duration_activated(self, index: int) -> None:
        if self.duration_combo.itemData(index) != "custom":
            return
        minutes = self._prompt_custom_duration()
        if minutes:
            self._custom_minutes = minutes
            self.duration_combo.setItemText(index, f"Custom ({_fmt_duration(minutes)})")
        elif self._custom_minutes is None:
            self.duration_combo.setCurrentIndex(0)

    def _prompt_custom_duration(self) -> int | None:
        """Ask for a custom duration as hours + minutes. Returns total minutes (or None)."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom duration")
        layout = QVBoxLayout(dialog)

        row = QHBoxLayout()
        hours = QSpinBox()
        hours.setRange(0, 23)
        hours.setSuffix(" hr")
        minutes = QSpinBox()
        minutes.setRange(0, 59)
        minutes.setSingleStep(5)
        minutes.setSuffix(" min")
        default = self._custom_minutes if self._custom_minutes is not None else 60
        hours.setValue(default // 60)
        minutes.setValue(default % 60)
        row.addWidget(hours)
        row.addWidget(minutes)
        layout.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return (hours.value() * 60 + minutes.value()) or None

    def _select_duration(self, minutes: int) -> None:
        for i in range(self.duration_combo.count()):
            if self.duration_combo.itemData(i) == minutes:
                self.duration_combo.setCurrentIndex(i)
                return
        # No preset match → use the Custom slot.
        self._custom_minutes = minutes
        custom_idx = self.duration_combo.count() - 1
        self.duration_combo.setItemText(custom_idx, f"Custom ({_fmt_duration(minutes)})")
        self.duration_combo.setCurrentIndex(custom_idx)

    def _select_repeat(self, data: tuple[str, int]) -> None:
        # findData() doesn't match tuple userData by value, so compare manually.
        for i in range(self.repeat_combo.count()):
            if self.repeat_combo.itemData(i) == data:
                self.repeat_combo.setCurrentIndex(i)
                return

    def _on_accept(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Missing title", "Please enter a task title.")
            return
        self.accept()

    def values(self) -> dict:
        """Return the collected field values as a dict (datetimes in UTC)."""
        qdate = self.date_field.value()
        qtime = self.time_field.value()
        has_time = qdate is not None and qtime is not None

        due_at: datetime | None = None
        if qdate is not None:
            if has_time:
                local = datetime(
                    qdate.year(), qdate.month(), qdate.day(),
                    qtime.hour(), qtime.minute(),
                ).astimezone()
            else:
                local = datetime(qdate.year(), qdate.month(), qdate.day()).astimezone()
            due_at = local.astimezone(timezone.utc)

        end_at = None
        if has_time and due_at is not None:
            data = self.duration_combo.currentData()
            minutes = self._custom_minutes if data == "custom" else data
            if minutes:
                end_at = due_at + timedelta(minutes=minutes)

        recurrence_rule = None
        repeat = self.repeat_combo.currentData()
        if repeat is not None and due_at is not None:
            freq, interval = repeat
            until_dt = None
            until_q = self.until_field.value()
            if until_q is not None:
                until_dt = datetime(
                    until_q.year(), until_q.month(), until_q.day(), 23, 59, 59
                ).astimezone().astimezone(timezone.utc)
            recurrence_rule = build_rule_string(freq, interval, until_dt)

        return {
            "title": self.title_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip() or None,
            "due_at": due_at,
            "has_time": has_time,
            "end_at": end_at,
            "reminder_minutes_before": (
                self.reminder_combo.currentData() if has_time else None
            ),
            "recurrence_rule": recurrence_rule,
        }
