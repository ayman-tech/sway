"""Availability view — personal when2meet-style time-slot selector.

Phase 1: date selection + time-range setup (hourly slots).
Phase 2: a custom-painted grid where the user marks available slots by clicking/dragging.
Existing timed tasks/events are overlaid as read-only "busy" blocks (a task with no end
time is assumed to last 1 hour). State is persisted to the `settings` table.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimeZone, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.repositories.settings_repo import SettingsRepository
from app.services.auth_service import AuthService
from app.services.availability_share_service import (
    AvailabilityShareResult,
    AvailabilityShareService,
)
from app.services.task_service import TaskService
from app.ui.theme import get_theme
from app.utils.datetime_utils import to_local

_SETUP_KEY = "availability_setup"
_STATE_KEY = "availability_state"
_MAX_DATES = 14


@dataclass(frozen=True)
class AvailabilityPalette:
    available: QColor
    available_hover: QColor
    busy: QColor
    free: QColor
    free_hover: QColor
    grid_line: QColor
    header_bg: QColor
    header_text: QColor
    label_text: QColor
    swatch_border: QColor


_DARK_PALETTE = AvailabilityPalette(
    available=QColor("#2d7a3f"),
    available_hover=QColor("#3a9e52"),
    busy=QColor("#3d4663"),
    free=QColor("#2c2f37"),
    free_hover=QColor("#363a44"),
    grid_line=QColor("#3a3e48"),
    header_bg=QColor("#1b1d22"),
    header_text=QColor("#8b909a"),
    label_text=QColor("#e6e8ec"),
    swatch_border=QColor("#3a3e48"),
)
_LIGHT_PALETTE = AvailabilityPalette(
    available=QColor("#bfe8cf"),
    available_hover=QColor("#a9ddbd"),
    busy=QColor("#cbd6ee"),
    free=QColor("#f8fafc"),
    free_hover=QColor("#edf1f6"),
    grid_line=QColor("#d4dae3"),
    header_bg=QColor("#f4f5f7"),
    header_text=QColor("#6b7280"),
    label_text=QColor("#1d2129"),
    swatch_border=QColor("#cfd4db"),
)


def _availability_palette() -> AvailabilityPalette:
    return _LIGHT_PALETTE if get_theme() == "light" else _DARK_PALETTE


_TIME_COL_W = 64
_CELL_W = 96
_CELL_H = 32
_HEADER_H = 46
_HEADER_DAY_FONT_PT = 11
_HEADER_DATE_FONT_PT = 13
_ROW_LABEL_FONT_PT = 11

# State / busy maps.
AvailState = dict[str, list[int]]      # date_iso -> available slot indices
BusyMap = dict[str, dict[int, str]]    # date_iso -> {slot index: task title}


@dataclass
class AvailSetup:
    from_date: str   # ISO date
    to_date: str
    start_hour: int  # 0-23
    end_hour: int    # 1-24
    slot_minutes: int = 60  # hourly slots only
    selected_dates: list[str] | None = None

    def dates(self) -> list[date]:
        if self.selected_dates:
            return sorted({date.fromisoformat(d) for d in self.selected_dates})
        start = date.fromisoformat(self.from_date)
        end = date.fromisoformat(self.to_date)
        out, cur = [], start
        while cur <= end:
            out.append(cur)
            cur += timedelta(days=1)
        return out

    def slots_per_day(self) -> int:
        return self.end_hour - self.start_hour

    def date_label(self) -> str:
        dates = self.dates()
        if len(dates) <= 5:
            return ", ".join(f"{d.strftime('%b')} {d.day}" for d in dates)
        first, last = dates[0], dates[-1]
        return (
            f"{first.strftime('%b')} {first.day} to "
            f"{last.strftime('%b')} {last.day} · {len(dates)} selected dates"
        )

    def slot_label(self, idx: int) -> str:
        h = self.start_hour + idx
        if h == 0 or h == 24:
            return "12 AM"
        if h == 12:
            return "12 PM"
        return f"{h % 12} {'AM' if h < 12 else 'PM'}"


def compute_busy(setup: AvailSetup, task_service: TaskService) -> BusyMap:
    """Build the busy overlay from timed tasks/events overlapping the range."""
    dates = setup.dates()
    date_set = {d.isoformat() for d in dates}
    # UTC window covering every selected local date.
    start_utc = datetime.combine(dates[0], datetime.min.time()).astimezone().astimezone(timezone.utc)
    end_utc = (
        datetime.combine(dates[-1] + timedelta(days=1), datetime.min.time())
        .astimezone()
        .astimezone(timezone.utc)
    )
    busy: BusyMap = {}
    for task in task_service.get_tasks_in_range(start_utc, end_utc):
        if task.due_at is None:
            continue
        start_local = to_local(task.due_at)
        end_local = to_local(task.end_at) if task.end_at else start_local + timedelta(hours=1)
        d_iso = start_local.date().isoformat()
        if d_iso not in date_set:
            continue
        for r in range(setup.slots_per_day()):
            slot_start = start_local.replace(
                hour=setup.start_hour + r, minute=0, second=0, microsecond=0
            )
            slot_end = slot_start + timedelta(hours=1)
            if start_local < slot_end and end_local > slot_start:
                busy.setdefault(d_iso, {})[r] = task.title
    return busy


class AvailabilityGrid(QWidget):
    """Custom-painted interactive grid: columns = dates, rows = hourly slots.

    Click or drag to toggle availability on free cells. Busy cells (occupied by a task)
    are read-only. The drag direction (mark/clear) is locked to the first cell touched.
    """

    changed = Signal()

    def __init__(self, setup: AvailSetup, state: AvailState, busy: BusyMap) -> None:
        super().__init__()
        self._setup = setup
        self._busy = busy
        self._dates = setup.dates()
        self._slots = setup.slots_per_day()
        self._avail = self._initial_availability(state)
        self._drag_active = False
        self._drag_mark = True
        self._drag_last: tuple[int, int] | None = None
        self._hover: tuple[int, int] | None = None
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMouseTracking(True)

    def _initial_availability(self, state: AvailState) -> dict[str, set[int]]:
        availability: dict[str, set[int]] = {}
        for d in self._dates:
            d_iso = d.isoformat()
            if d_iso in state:
                availability[d_iso] = set(state[d_iso])
                continue
            busy_slots = set(self._busy.get(d_iso, {}))
            availability[d_iso] = set(range(self._slots)) - busy_slots
        return availability

    def state_as_dict(self) -> AvailState:
        return {
            d.isoformat(): sorted(self._avail.get(d.isoformat(), set()))
            for d in self._dates
        }

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(_TIME_COL_W + len(self._dates) * _CELL_W, _HEADER_H + self._slots * _CELL_H)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    # ---- painting ----

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        palette = _availability_palette()
        self._draw_header(painter, palette)
        self._draw_cells(painter, palette)

    def _draw_header(self, painter: QPainter, palette: AvailabilityPalette) -> None:
        painter.fillRect(0, 0, self.width(), _HEADER_H, palette.header_bg)
        for c, d in enumerate(self._dates):
            x = _TIME_COL_W + c * _CELL_W
            f = painter.font()
            f.setPointSize(_HEADER_DAY_FONT_PT)
            f.setBold(False)
            painter.setFont(f)
            painter.setPen(palette.header_text)
            painter.drawText(
                QRect(x, 4, _CELL_W, 18),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                d.strftime("%a"),
            )
            f.setPointSize(_HEADER_DATE_FONT_PT)
            f.setBold(True)
            painter.setFont(f)
            painter.setPen(palette.label_text)
            painter.drawText(
                QRect(x, 22, _CELL_W, 22),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                f"{d.strftime('%b')} {d.day}",
            )

    def _draw_cells(self, painter: QPainter, palette: AvailabilityPalette) -> None:
        for r in range(self._slots):
            y = _HEADER_H + r * _CELL_H
            f = painter.font()
            f.setPointSize(_ROW_LABEL_FONT_PT)
            f.setBold(False)
            painter.setFont(f)
            painter.setPen(palette.header_text)
            painter.drawText(
                QRect(0, y - _CELL_H // 2, _TIME_COL_W - 6, _CELL_H),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self._setup.slot_label(r),
            )
            for c, d in enumerate(self._dates):
                x = _TIME_COL_W + c * _CELL_W
                rect = QRect(x, y, _CELL_W, _CELL_H)
                d_iso = d.isoformat()
                is_hover = self._hover == (c, r)
                busy_title = self._busy.get(d_iso, {}).get(r)
                if busy_title is not None:
                    # Busy block only — no title shown (private when sharing/screenshotting).
                    painter.fillRect(rect.adjusted(1, 1, -1, -1), palette.busy)
                elif r in self._avail.get(d_iso, set()):
                    painter.fillRect(
                        rect.adjusted(1, 1, -1, -1),
                        palette.available_hover if is_hover else palette.available,
                    )
                else:
                    painter.fillRect(
                        rect.adjusted(1, 1, -1, -1),
                        palette.free_hover if is_hover else palette.free,
                    )
                painter.setPen(QPen(palette.grid_line, 1))
                painter.drawRect(rect)

    # ---- interaction ----

    def _cell_at(self, pos: QPoint) -> tuple[int, int] | None:
        x, y = pos.x() - _TIME_COL_W, pos.y() - _HEADER_H
        if x < 0 or y < 0:
            return None
        col, row = x // _CELL_W, y // _CELL_H
        if 0 <= col < len(self._dates) and 0 <= row < self._slots:
            return col, row
        return None

    def _is_busy(self, col: int, row: int) -> bool:
        return row in self._busy.get(self._dates[col].isoformat(), {})

    def _toggle(self, col: int, row: int, mark: bool) -> None:
        if self._is_busy(col, row):
            return
        slots = self._avail.setdefault(self._dates[col].isoformat(), set())
        slots.add(row) if mark else slots.discard(row)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        cell = self._cell_at(event.position().toPoint())
        if cell is None or self._is_busy(*cell):
            return
        col, row = cell
        self._drag_mark = row not in self._avail.get(self._dates[col].isoformat(), set())
        self._drag_active = True
        self._drag_last = cell
        self._toggle(col, row, self._drag_mark)
        self.update()
        self.changed.emit()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        cell = self._cell_at(event.position().toPoint())
        if self._drag_active and cell and cell != self._drag_last:
            self._toggle(cell[0], cell[1], self._drag_mark)
            self._drag_last = cell
            self.update()
            self.changed.emit()
        if cell != self._hover:
            self._hover = cell
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = False
            self._drag_last = None

    def leaveEvent(self, _event) -> None:  # noqa: N802
        self._hover = None
        self.update()


class _DateSelectionCalendar(QWidget):
    """Small month grid that toggles multiple selected dates."""

    datesChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._selected: set[str] = set()
        self._day_buttons: list[QPushButton] = []
        self._weekday_labels: list[QLabel] = []
        self._nav_buttons: list[QPushButton] = []
        self._month_label = QLabel()
        self._refreshing = False
        self._drag_active = False
        self._drag_mark = True
        self._drag_visited: set[str] = set()
        self._build()
        self._refresh()

    def selected_date_values(self) -> list[str]:
        return sorted(self._selected)

    def set_selected_dates(self, values: list[str]) -> None:
        self._selected = set(values)
        if values:
            first = date.fromisoformat(sorted(values)[0])
            self._year = first.year
            self._month = first.month
        self._refresh()
        self.datesChanged.emit()

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.StyleChange and not self._refreshing:
            self._refresh()
        return super().event(event)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched not in self._day_buttons:
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            iso = watched.property("date_iso")
            if not iso:
                return True
            self._drag_active = True
            self._drag_mark = iso not in self._selected
            self._drag_visited.clear()
            self._paint_date(iso)
            return True

        if event.type() == QEvent.Type.MouseMove and self._drag_active:
            button = self.childAt(self.mapFromGlobal(event.globalPosition().toPoint()))
            if button in self._day_buttons:
                self._paint_date(button.property("date_iso"))
            return True

        if event.type() == QEvent.Type.MouseButtonRelease and self._drag_active:
            self._drag_active = False
            self._drag_visited.clear()
            return True

        return super().eventFilter(watched, event)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        nav = QHBoxLayout()
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(0)
        prev_btn = QPushButton("‹")
        next_btn = QPushButton("›")
        for btn in (prev_btn, next_btn):
            btn.setFixedSize(34, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._nav_buttons.append(btn)
        prev_btn.clicked.connect(lambda: self._shift_month(-1))
        next_btn.clicked.connect(lambda: self._shift_month(1))
        self._month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(prev_btn)
        nav.addWidget(self._month_label, 1)
        nav.addWidget(next_btn)
        outer.addLayout(nav)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        for c, text in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(30)
            self._weekday_labels.append(label)
            grid.addWidget(label, 0, c)
        for r in range(6):
            for c in range(7):
                btn = QPushButton()
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(34)
                btn.clicked.connect(lambda _checked=False, b=btn: self._toggle_button_date(b))
                btn.installEventFilter(self)
                self._day_buttons.append(btn)
                grid.addWidget(btn, r + 1, c)
        outer.addLayout(grid)

    def _shift_month(self, delta: int) -> None:
        month = self._month + delta
        year = self._year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self._year = year
        self._month = month
        self._refresh()

    def _toggle_button_date(self, button: QPushButton) -> None:
        iso = button.property("date_iso")
        if not iso:
            return
        self._set_date_selected(iso, iso not in self._selected)

    def _paint_date(self, iso: str) -> None:
        if not iso or iso in self._drag_visited:
            return
        self._drag_visited.add(iso)
        self._set_date_selected(iso, self._drag_mark)

    def _set_date_selected(self, iso: str, selected: bool) -> None:
        if (iso in self._selected) == selected:
            return
        if selected:
            if len(self._selected) >= _MAX_DATES:
                return
            self._selected.add(iso)
        else:
            self._selected.remove(iso)
        self._refresh()
        self.datesChanged.emit()

    def _refresh(self) -> None:
        self._refreshing = True
        palette = _availability_palette()
        try:
            first = date(self._year, self._month, 1)
            grid_start = first - timedelta(days=first.weekday())
            self._month_label.setText(f"{first.strftime('%B')}    {self._year}")

            nav_bg = "#151619" if get_theme() == "dark" else "#eaecef"
            nav_fg = palette.label_text.name()
            self._set_widget_style(
                self._month_label,
                f"background-color: {nav_bg}; color: {nav_fg}; font-weight: 700;",
            )
            nav_btn_style = (
                "QPushButton { "
                f"background-color: {nav_bg}; color: {palette.header_text.name()}; "
                "border: none; border-radius: 0; font-size: 18px; font-weight: 700; "
                "}"
                f"QPushButton:hover {{ background-color: {palette.free_hover.name()}; "
                f"color: {palette.label_text.name()}; }}"
            )
            for btn in self._nav_buttons:
                self._set_widget_style(btn, nav_btn_style)

            weekday_style = (
                "background-color: transparent; "
                f"color: {palette.header_text.name()};"
            )
            for label in self._weekday_labels:
                self._set_widget_style(label, weekday_style)

            for i, btn in enumerate(self._day_buttons):
                d = grid_start + timedelta(days=i)
                iso = d.isoformat()
                in_month = d.month == self._month
                selected = iso in self._selected
                is_today = d == date.today()
                btn.setText(str(d.day))
                btn.setProperty("date_iso", iso)
                self._set_widget_style(
                    btn, self._day_button_style(palette, selected, in_month, is_today)
                )
        finally:
            self._refreshing = False

    @staticmethod
    def _set_widget_style(widget: QWidget, style: str) -> None:
        if widget.styleSheet() != style:
            widget.setStyleSheet(style)

    @staticmethod
    def _day_button_style(
        palette: AvailabilityPalette, selected: bool, in_month: bool, is_today: bool
    ) -> str:
        if selected:
            return (
                "QPushButton { background-color: #2b6cff; color: #ffffff; "
                "border: none; border-radius: 0; font-weight: 700; }"
                "QPushButton:hover { background-color: #3f7bff; }"
            )
        color = palette.label_text.name() if in_month else palette.header_text.name()
        hover_bg = palette.free_hover.name()
        border = "1px solid #2b6cff" if is_today else "none"
        return (
            "QPushButton { background-color: transparent; "
            f"color: {color}; border: {border}; border-radius: 0; font-weight: "
            f"{'700' if is_today else '400'}; }}"
            f"QPushButton:hover {{ background-color: {hover_bg}; }}"
        )


class _SetupWidget(QWidget):
    """Phase 1 — pick dates + hours."""

    confirmed = Signal(object)  # AvailSetup

    def __init__(self, saved: AvailSetup | None) -> None:
        super().__init__()
        self._build(saved)

    def _build(self, saved: AvailSetup | None) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)
        outer.addStretch(1)

        sub = QLabel(
            f"Click or drag to pick up to {_MAX_DATES} dates. Your timed tasks show as busy."
        )
        sub.setObjectName("TaskSubtitle")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self._date_calendar = _DateSelectionCalendar()
        self._date_calendar.set_selected_dates([date.today().isoformat()])
        grid.addWidget(self._date_calendar, 0, 0, 1, 2)

        self._start_hour = self._hour_combo("Start time")
        self._end_hour = self._hour_combo("End time")
        grid.addWidget(self._start_hour, 1, 0)
        grid.addWidget(self._end_hour, 1, 1)
        outer.addLayout(grid)

        btn = QPushButton("View Availability  →")
        btn.setObjectName("AddTaskButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._on_confirm)
        outer.addWidget(btn)
        outer.addStretch(2)

        if saved:
            self._restore(saved)

    def _restore(self, saved: AvailSetup) -> None:
        si = self._start_hour.findData(saved.start_hour)
        if si >= 0:
            self._start_hour.setCurrentIndex(si)
        ei = self._end_hour.findData(saved.end_hour)
        if ei >= 0:
            self._end_hour.setCurrentIndex(ei)

    def _selected_date_values(self) -> list[str]:
        return self._date_calendar.selected_date_values()

    @staticmethod
    def _hour_combo(placeholder: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem(placeholder, -1)
        for h in range(0, 25):
            if h == 0:
                label = "12:00 AM"
            elif h == 12:
                label = "12:00 PM"
            elif h == 24:
                label = "12:00 AM (next day)"
            else:
                label = f"{h % 12} :00 {'AM' if h < 12 else 'PM'}".replace(" :", ":")
            combo.addItem(label, h)
        return combo

    def _on_confirm(self) -> None:
        start_h, end_h = self._start_hour.currentData(), self._end_hour.currentData()
        if start_h == -1 or end_h == -1:
            QMessageBox.warning(self, "Missing times", "Please pick a start and end time.")
            return
        if end_h <= start_h:
            QMessageBox.warning(self, "Invalid times", "End time must be after start time.")
            return
        selected = self._selected_date_values()
        if not selected:
            QMessageBox.warning(self, "Missing dates", "Please choose at least one date.")
            return
        if len(selected) > _MAX_DATES:
            QMessageBox.warning(
                self, "Too many dates", f"Please choose {_MAX_DATES} dates or fewer."
            )
            return
        self.confirmed.emit(
            AvailSetup(selected[0], selected[-1], start_h, end_h, 60, selected)
        )


class _GridWidget(QWidget):
    """Phase 2 — scrollable grid + toolbar."""

    back = Signal()
    exportRequested = Signal()
    shareRequested = Signal()
    stateChanged = Signal()

    def __init__(
        self, setup: AvailSetup, state: AvailState, busy: BusyMap, share_enabled: bool
    ) -> None:
        super().__init__()
        self._grid: AvailabilityGrid | None = None
        self._legend_swatches: list[tuple[QLabel, str]] = []
        self._share_enabled = share_enabled
        self._build(setup, state, busy)

    def _build(self, setup: AvailSetup, state: AvailState, busy: BusyMap) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        back_btn = QPushButton("←  Edit dates")
        back_btn.setObjectName("LinkButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back)
        toolbar.addWidget(back_btn)
        toolbar.addStretch(1)
        self._share_btn = QPushButton("Share link")
        self._share_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._share_btn.setEnabled(self._share_enabled)
        if not self._share_enabled:
            self._share_btn.setToolTip("Sign in and configure API_PUBLIC_URL to share links.")
        self._share_btn.clicked.connect(self.shareRequested)
        toolbar.addWidget(self._share_btn)
        export_btn = QPushButton("Export HTML")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self.exportRequested)
        toolbar.addWidget(export_btn)
        layout.addLayout(toolbar)

        self._share_status = QLabel()
        self._share_status.setObjectName("TaskSubtitle")
        self._share_status.hide()
        layout.addWidget(self._share_status)

        self._share_result = QWidget()
        self._share_result.setObjectName("AuthCard")
        share_result_layout = QHBoxLayout(self._share_result)
        share_result_layout.setContentsMargins(12, 10, 12, 10)
        share_result_layout.setSpacing(10)
        share_result_text = QVBoxLayout()
        share_result_text.setSpacing(3)
        self._share_url = QLabel()
        self._share_url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._share_url.setWordWrap(True)
        share_result_text.addWidget(self._share_url)
        self._share_expiration = QLabel()
        self._share_expiration.setObjectName("TaskSubtitle")
        share_result_text.addWidget(self._share_expiration)
        share_result_layout.addLayout(share_result_text, 1)
        copy_share_btn = QPushButton("Copy")
        copy_share_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_share_btn.clicked.connect(self._copy_share_url)
        share_result_layout.addWidget(copy_share_btn)
        self._share_result.hide()
        layout.addWidget(self._share_result)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._grid = AvailabilityGrid(setup, state, busy)
        self._grid.changed.connect(self.stateChanged)
        scroll.setWidget(self._grid)
        layout.addWidget(scroll, 1)

        legend = QHBoxLayout()
        for color_key, text in [
            ("free", "Unavailable"),
            ("available", "Available"),
            ("busy", "Busy (task)"),
        ]:
            sw = QLabel()
            sw.setFixedSize(16, 16)
            self._legend_swatches.append((sw, color_key))
            legend.addWidget(sw)
            lbl = QLabel(text)
            lbl.setObjectName("TaskSubtitle")
            legend.addWidget(lbl)
            legend.addSpacing(14)
        legend.addStretch(1)
        layout.addLayout(legend)
        self._refresh_legend()

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.StyleChange:
            self._refresh_legend()
            if self._grid:
                self._grid.update()
        return super().event(event)

    def _refresh_legend(self) -> None:
        palette = _availability_palette()
        for swatch, color_key in self._legend_swatches:
            color = getattr(palette, color_key)
            swatch.setStyleSheet(
                "background-color: "
                f"{color.name()}; border: 1px solid {palette.swatch_border.name()}; "
                "border-radius: 3px;"
            )

    def current_state(self) -> AvailState:
        return self._grid.state_as_dict() if self._grid else {}

    def set_share_busy(self, busy: bool) -> None:
        self._share_btn.setDisabled(busy or not self._share_enabled)
        self._share_btn.setText("Creating link..." if busy else "Share link")

    def set_share_status(self, text: str) -> None:
        self._share_status.setText(text)
        self._share_status.setVisible(bool(text))

    def set_share_result(self, result: AvailabilityShareResult) -> None:
        self._share_url.setText(result.url)
        expires = datetime.fromisoformat(result.expires_at.replace("Z", "+00:00")).astimezone()
        expiration = expires.strftime("%b %d, %Y at %I:%M %p").replace(" 0", " ")
        self._share_expiration.setText(f"Expires {expiration}")
        self._share_result.show()

    def clear_share_result(self) -> None:
        self._share_result.hide()

    def _copy_share_url(self) -> None:
        QApplication.clipboard().setText(self._share_url.text())
        self.set_share_status("Share link copied to clipboard.")


class AvailabilityView(QWidget):
    """5th sidebar view: personal availability grid with task overlay."""

    _shareResult = Signal(int, bool, object)

    def __init__(
        self,
        settings_repo: SettingsRepository,
        task_service: TaskService,
        auth_service: AuthService | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings_repo
        self._tasks = task_service
        self._share_service = AvailabilityShareService(auth_service) if auth_service else None
        self._share_grid: _GridWidget | None = None
        self._share_request_id = 0
        self._stack = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)
        self._shareResult.connect(self._on_share_result)
        self._show_setup()

    # ---- persistence ----
    def _load_setup(self) -> AvailSetup | None:
        raw = self._settings.get(_SETUP_KEY)
        if not raw:
            return None
        try:
            return AvailSetup(**json.loads(raw))
        except (ValueError, TypeError):
            return None

    def _load_state(self) -> AvailState:
        raw = self._settings.get(_STATE_KEY)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    # ---- navigation ----
    def _clear_from(self, index: int) -> None:
        while self._stack.count() > index:
            w = self._stack.widget(index)
            self._stack.removeWidget(w)
            w.deleteLater()

    def _show_setup(self) -> None:
        self._share_request_id += 1
        self._share_grid = None
        self._clear_from(0)
        setup_w = _SetupWidget(self._load_setup())
        setup_w.confirmed.connect(self._on_setup_confirmed)
        self._stack.addWidget(setup_w)
        self._stack.setCurrentWidget(setup_w)

    def _on_setup_confirmed(self, setup: AvailSetup) -> None:
        self._settings.set(_SETUP_KEY, json.dumps(asdict(setup)))
        self._show_grid(setup)

    def _show_grid(self, setup: AvailSetup) -> None:
        self._clear_from(1)
        busy = compute_busy(setup, self._tasks)
        share_enabled = self._share_service is not None and self._share_service.is_available()
        grid_w = _GridWidget(setup, self._load_state(), busy, share_enabled)
        self._share_grid = grid_w
        grid_w.back.connect(self._show_setup)
        grid_w.stateChanged.connect(
            lambda: self._settings.set(_STATE_KEY, json.dumps(grid_w.current_state()))
        )
        grid_w.exportRequested.connect(
            lambda: self._on_export(setup, grid_w.current_state(), busy)
        )
        grid_w.shareRequested.connect(
            lambda: self._on_share(setup, grid_w.current_state(), busy)
        )
        self._stack.addWidget(grid_w)
        self._stack.setCurrentWidget(grid_w)

    def _on_export(self, setup: AvailSetup, state: AvailState, busy: BusyMap) -> None:
        from app.utils.availability_export import export_and_open

        export_and_open(setup, state, busy)

    def _on_share(self, setup: AvailSetup, state: AvailState, busy: BusyMap) -> None:
        if self._share_service is None or self._share_grid is None:
            return
        dates = setup.dates()
        busy_slots = {
            d.isoformat(): sorted(busy.get(d.isoformat(), {})) for d in dates
        }
        snapshot = {
            "selected_dates": [d.isoformat() for d in dates],
            "start_hour": setup.start_hour,
            "end_hour": setup.end_hour,
            "available_slots": {
                d.isoformat(): sorted(
                    set(state.get(d.isoformat(), [])) - set(busy_slots[d.isoformat()])
                )
                for d in dates
            },
            "busy_slots": busy_slots,
        }
        timezone_name = bytes(QTimeZone.systemTimeZoneId()).decode() or "UTC"
        self._share_request_id += 1
        request_id = self._share_request_id
        self._share_grid.set_share_busy(True)
        self._share_grid.set_share_status("")
        self._share_grid.clear_share_result()
        threading.Thread(
            target=self._share_worker,
            args=(request_id, snapshot, timezone_name),
            daemon=True,
        ).start()

    def _share_worker(self, request_id: int, snapshot: dict, timezone_name: str) -> None:
        try:
            result = self._share_service.create(snapshot, timezone_name) if self._share_service else None
            self._shareResult.emit(request_id, True, result)
        except Exception as exc:  # noqa: BLE001 - surface a clean message in the UI
            self._shareResult.emit(
                request_id, False, str(exc) or "Unable to create share link."
            )

    def _on_share_result(self, request_id: int, ok: bool, result: object) -> None:
        if self._share_grid is None or request_id != self._share_request_id:
            return
        self._share_grid.set_share_busy(False)
        if ok and isinstance(result, AvailabilityShareResult):
            QApplication.clipboard().setText(result.url)
            self._share_grid.set_share_result(result)
            self._share_grid.set_share_status("Share link copied to clipboard.")
        else:
            self._share_grid.set_share_status(str(result))
