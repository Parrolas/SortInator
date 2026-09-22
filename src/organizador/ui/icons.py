"""Application icons: committed logo asset with a programmatic fallback."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# The app icon is deliberately theme-independent: one recognizable mark everywhere.
ICON_INK = "#08111D"
ICON_ACCENT = "#49CFC0"


def _asset_path(name: str) -> Path | None:
    """Resolve a bundled asset, both from source and from the packaged app."""

    candidates: list[Path] = []
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base is not None:
        candidates.append(Path(frozen_base) / "assets" / name)
    candidates.append(Path(__file__).resolve().parent.parent.parent.parent / "assets" / name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def app_icon(size: int = 64) -> QIcon:
    """Return the SortInator mark, falling back to the drawn tile without assets."""

    logo = _asset_path("icon-square.png")
    if logo is not None:
        icon = QIcon(str(logo))
        if not icon.isNull():
            return icon
    return _drawn_icon(size)


def _drawn_icon(size: int) -> QIcon:
    """Draw the legacy filed-page mark as a filed page inside an ink tile."""

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    tile = QRectF(size * 0.05, size * 0.05, size * 0.9, size * 0.9)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ICON_INK))
    painter.drawRoundedRect(tile, size * 0.19, size * 0.19)

    page = QPainterPath()
    page.moveTo(QPointF(size * 0.29, size * 0.22))
    page.lineTo(QPointF(size * 0.62, size * 0.22))
    page.lineTo(QPointF(size * 0.73, size * 0.34))
    page.lineTo(QPointF(size * 0.73, size * 0.76))
    page.lineTo(QPointF(size * 0.29, size * 0.76))
    page.closeSubpath()
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawPath(page)

    pen = QPen(QColor(ICON_ACCENT), max(2, int(size * 0.055)))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    for ratio in (0.43, 0.56, 0.69):
        painter.drawLine(QPointF(size * 0.39, size * ratio), QPointF(size * 0.64, size * ratio))
    painter.end()
    return QIcon(pixmap)
