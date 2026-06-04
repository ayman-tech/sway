"""Programmatic app icon (no asset file needed)."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


def make_app_pixmap(size: int = 64) -> QPixmap:
    """A rounded blue square with a white 'S', rendered at the requested size."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    s = size / 64.0
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#2b6cff"))
    painter.drawRoundedRect(QRect(round(4 * s), round(4 * s), round(56 * s), round(56 * s)),
                            14 * s, 14 * s)

    font = QFont()
    font.setPixelSize(round(38 * s))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    painter.end()
    return pixmap


def make_app_icon() -> QIcon:
    return QIcon(make_app_pixmap(64))
