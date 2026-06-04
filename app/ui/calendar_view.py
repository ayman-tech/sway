"""Month calendar view: a custom-painted month grid + the selected day's tasks.

This is the same task data as the list view, arranged by date. Only tasks with a due
date appear here (Untimed tasks have no place on a calendar).
"""

from __future__ import annotations

import calendar as _calmod
from datetime import date, datetime, timedelta, timezone

from PySide6.QtCore import QDate, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.models.task import Task
from app.services.task_service import TaskGroup, TaskService
from app.ui.task_list_view import TaskListView
from app.utils.datetime_utils import to_local

_DOT = QColor("#2b6cff")
_DOT_SELECTED = QColor("#ffffff")
_DAY_MARKER_INSET = 6
_TASK_DOT_RADIUS = 2.5
_TASK_DOT_BOTTOM_PADDING = 5


class MonthCalendar(QCalendarWidget):
    """A month grid that paints a small dot under days that have tasks."""

    def __init__(self) -> None:
        super().__init__()
        self._counts: dict[date, int] = {}
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(
            QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
        )
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)

        header_fmt = QTextCharFormat()
        header_fmt.setForeground(QColor("#8b909a"))
        self.setHeaderTextFormat(header_fmt)
        # Clear Qt's default red weekend tint with an empty format, so weekend dates use
        # the same theme color as weekdays (and out-of-month dates stay dimmed via QSS).
        neutral_fmt = QTextCharFormat()
        self.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, neutral_fmt)
        self.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, neutral_fmt)
        self._style_month_buttons()

    def _style_month_buttons(self) -> None:
        for object_name, text in [
            ("qt_calendar_prevmonth", "‹"),
            ("qt_calendar_nextmonth", "›"),
        ]:
            button = self.findChild(QToolButton, object_name)
            if button is None:
                continue
            button.setIcon(QIcon())
            button.setText(text)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setFixedWidth(34)
            font = button.font()
            font.setPointSize(18)
            font.setBold(True)
            button.setFont(font)

    def set_task_dates(self, counts: dict[date, int]) -> None:
        self._counts = counts
        self.updateCells()

    def paintCell(self, painter: QPainter, rect, cell_date: QDate) -> None:  # noqa: N802
        super().paintCell(painter, rect, cell_date)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        marker_diameter = min(rect.width(), rect.height()) - _DAY_MARKER_INSET
        if cell_date == self.selectedDate():
            circle = QRectF(
                rect.center().x() - marker_diameter / 2,
                rect.center().y() - marker_diameter / 2,
                marker_diameter,
                marker_diameter,
            )
            painter.setBrush(_DOT)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(circle)

            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                str(cell_date.day()),
            )

        # Ring around today (the selected day already gets a filled highlight).
        if cell_date == QDate.currentDate() and cell_date != self.selectedDate():
            ring = QRectF(
                rect.center().x() - marker_diameter / 2,
                rect.center().y() - marker_diameter / 2,
                marker_diameter,
                marker_diameter,
            )
            pen = QPen(_DOT)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ring)

        # Dot under days that have tasks.
        if self._counts.get(cell_date.toPython()):
            color = _DOT_SELECTED if cell_date == self.selectedDate() else _DOT
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            dot_y = rect.center().y() + marker_diameter / 2 - _TASK_DOT_BOTTOM_PADDING
            painter.drawEllipse(
                QPointF(rect.center().x(), dot_y),
                _TASK_DOT_RADIUS,
                _TASK_DOT_RADIUS,
            )

        painter.restore()


class CalendarView(QWidget):
    """Month grid above, the selected day's tasks (sorted by time) below."""

    taskToggled = Signal(str, bool)
    taskEditRequested = Signal(str)
    taskDeleteRequested = Signal(str)

    def __init__(self, task_service: TaskService) -> None:
        super().__init__()
        self._service = task_service
        self._by_date: dict[date, list[Task]] = {}
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 12)
        layout.setSpacing(8)

        self._calendar = MonthCalendar()
        self._calendar.setMinimumHeight(320)
        self._calendar.selectionChanged.connect(self._update_detail)
        self._calendar.currentPageChanged.connect(lambda *_: self.refresh())
        layout.addWidget(self._calendar)

        self._day_title = QLabel()
        self._day_title.setObjectName("CalendarDayTitle")
        layout.addWidget(self._day_title)

        self._detail = TaskListView(
            empty_text="No tasks on this day.", show_headers=False, time_only=True
        )
        self._detail.taskToggled.connect(self.taskToggled)
        self._detail.taskEditRequested.connect(self.taskEditRequested)
        self._detail.taskDeleteRequested.connect(self.taskDeleteRequested)
        layout.addWidget(self._detail, 1)

    def refresh(self) -> None:
        """Expand tasks (incl. recurring occurrences) for the visible month."""
        start, end = self._visible_range()
        by_date: dict[date, list[Task]] = {}
        for task in self._service.get_tasks_in_range(start, end):
            if task.due_at is None:
                continue
            d = to_local(task.due_at).date()
            by_date.setdefault(d, []).append(task)
        self._by_date = by_date
        self._calendar.set_task_dates({d: len(v) for d, v in by_date.items()})
        self._update_detail()

    def _visible_range(self) -> tuple[datetime, datetime]:
        year = self._calendar.yearShown()
        month = self._calendar.monthShown()
        last_day = _calmod.monthrange(year, month)[1]
        # Pad by a week so occurrences on adjacent-month days shown in the grid count too.
        start_local = datetime(year, month, 1).astimezone() - timedelta(days=7)
        end_local = datetime(year, month, last_day, 23, 59, 59).astimezone() + timedelta(days=7)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    def _update_detail(self) -> None:
        qd = self._calendar.selectedDate()
        self._day_title.setText(qd.toString("dddd, d MMMM yyyy"))
        # Timed tasks first (ordered by time), then untimed (all-day) tasks.
        day_tasks = sorted(
            self._by_date.get(qd.toPython(), []),
            key=lambda t: (not t.has_time, t.due_at, t.created_at),
        )
        self._detail.set_groups([TaskGroup("", day_tasks)] if day_tasks else [])
