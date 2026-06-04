"""A scrollable, grouped list of task cards. Reused for the active and completed views."""

from __future__ import annotations

from collections.abc import Iterable

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.task_service import TaskGroup
from app.ui.components.task_card import TaskCard


class _GroupHeader(QWidget):
    """A section header: uppercase label + task count, red when overdue."""

    def __init__(self, label: str, count: int, overdue: bool) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 12, 4, 4)
        layout.setSpacing(8)

        title = QLabel(label.upper())
        title.setObjectName("GroupHeader")
        title.setProperty("overdue", overdue)
        layout.addWidget(title)

        count_label = QLabel(str(count))
        count_label.setObjectName("GroupCount")
        layout.addWidget(count_label)
        layout.addStretch(1)


class TaskListView(QWidget):
    """Renders tasks as cards under labelled group headers."""

    taskToggled = Signal(str, bool)
    taskEditRequested = Signal(str)
    taskDeleteRequested = Signal(str)

    def __init__(self, empty_text: str = "Nothing here yet.", show_headers: bool = True) -> None:
        super().__init__()
        self._empty_text = empty_text
        self._show_headers = show_headers
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(16, 8, 16, 16)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

    def set_groups(
        self,
        groups: Iterable[TaskGroup],
        footer: tuple[str, Callable[[], None]] | None = None,
    ) -> None:
        self._clear()
        groups = list(groups)
        if not groups:
            self._add_empty_state()
        else:
            for group in groups:
                if self._show_headers:
                    self._insert(_GroupHeader(group.label, len(group.tasks), group.overdue))
                for task in group.tasks:
                    self._insert(self._make_card(task, overdue=group.overdue))
        if footer is not None:
            self._insert(self._make_footer(*footer))

    def _make_footer(self, text: str, callback: Callable[[], None]) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(4, 8, 4, 4)
        button = QPushButton(text)
        button.setObjectName("LinkButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: callback())
        row.addWidget(button)
        row.addStretch(1)
        return wrap

    def _make_card(self, task, overdue: bool) -> TaskCard:
        card = TaskCard(task, overdue=overdue)
        card.toggled.connect(self.taskToggled)
        card.editRequested.connect(self.taskEditRequested)
        card.deleteRequested.connect(self.taskDeleteRequested)
        return card

    def _add_empty_state(self) -> None:
        empty = QLabel(self._empty_text)
        empty.setObjectName("EmptyState")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._insert(empty)

    def _insert(self, widget: QWidget) -> None:
        # Keep the trailing stretch last.
        self._list_layout.insertWidget(self._list_layout.count() - 1, widget)

    def _clear(self) -> None:
        while self._list_layout.count() > 1:  # keep the trailing stretch
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
