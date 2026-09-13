"""Reusable, task-focused Qt widgets."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from organizador.i18n import _


def button(text: str, *, variant: str = "default") -> QPushButton:
    """Create a consistently styled action button."""

    result = QPushButton(text)
    result.setProperty("variant", variant)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    return result


class ElidedChipButton(QPushButton):
    """Checkable chip that keeps the start of a long label readable.

    The full label stays in the accessible name and can drive tooltips; the
    painted text is elided on the right so truncation stays obvious. The
    horizontal size policy is ignored so re-eliding never feeds back into the
    grid layout (which would otherwise oscillate between hints).
    """

    CHROME_WIDTH = 34

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setAccessibleName(text)
        self._apply_elide()

    def full_text(self) -> str:
        """Return the untruncated label."""

        return self._full_text

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        self.ensurePolished()
        available = max(24, self.width() - self.CHROME_WIDTH)
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, available
        )
        if elided != super().text():
            super().setText(elided)


def label(text: str, object_name: str) -> QLabel:
    """Create a label bound to one typography role."""

    result = QLabel(text)
    result.setObjectName(object_name)
    return result


def clear_layout(layout: QLayout) -> None:
    """Delete all widgets and child layouts from a layout."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        child = item.widget()
        if child is not None:
            child.hide()
            child.setParent(None)
            child.deleteLater()
        nested = item.layout()
        if nested is not None:
            while nested.count():
                nested_item = nested.takeAt(0)
                if nested_item is None:
                    continue
                nested_widget = nested_item.widget()
                if nested_widget is not None:
                    nested_widget.hide()
                    nested_widget.setParent(None)
                    nested_widget.deleteLater()


def format_size(size: int) -> str:
    """Format a byte count for compact file metadata."""

    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            decimals = 0 if unit == "B" else 1
            return f"{value:.{decimals}f} {unit}"
        value /= 1024
    return f"{size} B"  # pragma: no cover


def format_day(value: date | datetime | None) -> str:
    """Format a Portuguese-style calendar date."""

    if value is None:
        return _("Sem prazo")
    actual = value.date() if isinstance(value, datetime) else value
    return actual.strftime("%d/%m/%Y")


class PageHeading(QWidget):
    """Page title, supporting copy and optional actions."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        actions: list[QPushButton] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        copy_layout = QVBoxLayout()
        copy_layout.setSpacing(4)
        copy_layout.addWidget(label(title, "PageTitle"))
        subtitle_label = label(subtitle, "PageSubtitle")
        subtitle_label.setWordWrap(True)
        copy_layout.addWidget(subtitle_label)
        layout.addLayout(copy_layout, 1)
        for action in actions or []:
            layout.addWidget(action, 0, Qt.AlignmentFlag.AlignTop)


class EmptyState(QFrame):
    """An empty state that explains the next useful action."""

    action_requested = Signal()

    def __init__(
        self,
        title: str,
        body: str,
        action_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setMinimumHeight(180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(8)
        layout.addStretch(1)
        heading = label(title, "SectionTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        detail = label(body, "PageSubtitle")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setWordWrap(True)
        detail.setFixedWidth(520)
        detail.ensurePolished()
        detail.setMinimumHeight(detail.heightForWidth(520))
        detail.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout.addWidget(detail, 0, Qt.AlignmentFlag.AlignHCenter)
        if action_text:
            action = button(action_text, variant="primary")
            action.clicked.connect(self.action_requested)
            layout.addWidget(action, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)


class PathActionRow(QFrame):
    """Compact file row with callback-backed actions."""

    def __init__(
        self,
        title: str,
        detail: str,
        path: Path,
        open_callback: Callable[[Path], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ListRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(15, 11, 12, 11)
        row.setSpacing(12)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title_label = label(title, "RowTitle")
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy.addWidget(title_label)
        copy.addWidget(label(detail, "Muted"))
        row.addLayout(copy, 1)
        open_button = button(_("Abrir"), variant="quiet")
        open_button.clicked.connect(lambda: open_callback(path))
        row.addWidget(open_button)
