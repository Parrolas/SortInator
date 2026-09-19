"""Reusable, task-focused Qt widgets."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from organizador.i18n import _
from organizador.ui import theme as ui_theme


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


class ToggleSwitch(QCheckBox):
    """A checkbox contract painted as a switch, including keyboard focus.

    The state change itself is immediate; only the thumb travels, within the
    shared short-motion budget (instant in Contraste).
    """

    TRACK_OFF_X = 5.0
    TRACK_ON_X = 18.0

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._thumb_t = 1.0 if self.isChecked() else 0.0
        self._thumb_animation = QVariantAnimation(self)
        self._thumb_animation.valueChanged.connect(self._apply_thumb)
        self.toggled.connect(self._animate_thumb)

    def thumb_position(self) -> float:
        """Return the animated thumb position, 0.0 off and 1.0 on."""

        return self._thumb_t

    def sizeHint(self) -> QSize:
        return QSize(52 + self.fontMetrics().horizontalAdvance(self.text()), 32)

    def minimumSizeHint(self) -> QSize:
        return QSize(80, 32)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        text = self.fontMetrics().boundingRect(
            QRect(0, 0, max(1, width - 56), 10000),
            Qt.TextFlag.TextWordWrap,
            self.text(),
        )
        return max(32, text.height() + 8)

    def hitButton(self, pos: QPoint) -> bool:
        return self.rect().contains(pos)

    def _apply_thumb(self, value: object) -> None:
        if isinstance(value, (int, float)):
            self._thumb_t = float(value)
        self.update()

    def _animate_thumb(self, checked: bool) -> None:
        self.update()
        duration = min(120, ui_theme.animation_ms())
        if not duration:
            self._thumb_t = 1.0 if checked else 0.0
            return
        self._thumb_animation.stop()
        self._thumb_animation.setDuration(duration)
        self._thumb_animation.setStartValue(self._thumb_t)
        self._thumb_animation.setEndValue(1.0 if checked else 0.0)
        self._thumb_animation.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        tokens = ui_theme.current()
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(2, (self.height() - 20) / 2, 34, 20)
        painter.setPen(QPen(QColor(tokens.border), 1))
        painter.setBrush(QColor(tokens.teal_fill if self.isChecked() else tokens.chip_bg))
        if not self.isEnabled():
            painter.setOpacity(0.45)
        painter.drawRoundedRect(track, 10, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens.primary_fg if self.isChecked() else tokens.muted))
        thumb_x = self.TRACK_OFF_X + (self.TRACK_ON_X - self.TRACK_OFF_X) * self._thumb_t
        painter.drawEllipse(QRectF(thumb_x, track.y() + 3, 14, 14))
        painter.setPen(QColor(tokens.text if self.isEnabled() else tokens.disabled_fg))
        painter.drawText(
            self.rect().adjusted(48, 4, -4, -4),
            Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
            self.text(),
        )
        if self.hasFocus():
            painter.setPen(QPen(QColor(tokens.teal), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect().adjusted(0, 0, -1, -1)), 6, 6)


class BoundedDialog(QDialog):
    """Retain the native frame while keeping dialogs within the desktop work area."""

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if (layout := self.layout()) is not None:
            layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        geometry = self.screen().availableGeometry().adjusted(16, 40, -16, -16)
        self.setMinimumSize(
            min(self.minimumWidth(), geometry.width()),
            min(self.minimumHeight(), geometry.height()),
        )
        self.setMaximumSize(geometry.size())
        self.resize(min(self.width(), geometry.width()), min(self.height(), geometry.height()))
        self.move(
            max(geometry.left(), min(self.x(), geometry.right() - self.width() + 1)),
            max(geometry.top(), min(self.y(), geometry.bottom() - self.height() + 1)),
        )


def hairline() -> QFrame:
    """Return a one-pixel divider between rows or regions."""

    line = QFrame()
    line.setObjectName("Hairline")
    line.setFixedHeight(1)
    line.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    return line


class WheelRedirector(QObject):
    """Scrolls the host area when the wheel lands on a value control.

    Spin boxes and combos eat the wheel to change their value, which lets a
    casual page scroll edit a setting by accident. The wheel always scrolls
    the host area instead; values change through typing, arrow keys or the
    control's own steppers.
    """

    def __init__(self, area: QScrollArea, watch: Sequence[QWidget]) -> None:
        super().__init__(area)
        self._area = area
        for control in watch:
            control.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel:
            QApplication.sendEvent(self._area.verticalScrollBar(), event)
            return True
        return False
