"""Keyboard command palette: type to find, Enter to run, Escape to leave."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QModelIndex,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QCloseEvent, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from organizador.i18n import _
from organizador.ui import theme as ui_theme
from organizador.ui.commands import Command, lookup
from organizador.ui.widgets import BoundedDialog, hairline

_LOOKUP_DEBOUNCE_MS = 150
_ROW_HEIGHT = 40
_ENTRANCE_OFFSET = 10
_MAX_RESULTS = 12


class _LookupSignals(QObject):
    """Marshals worker results back to the palette on the interface thread."""

    results_ready = Signal(str, object)


class _LookupJob(QRunnable):
    """Filter one query snapshot off the interface thread."""

    def __init__(self, query: str, commands: Sequence[Command], signals: _LookupSignals) -> None:
        super().__init__()
        self._query = query
        self._commands = commands
        self._signals = signals

    def run(self) -> None:
        matches = lookup(self._query, self._commands)[:_MAX_RESULTS]
        self._signals.results_ready.emit(self._query, matches)


class CommandPalette(BoundedDialog):
    """Frameless palette card centred on the main window."""

    command_activated = Signal(object)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(False)
        self.setFixedWidth(560)
        self._commands: tuple[Command, ...] = ()
        self._shortcuts: list[QShortcut] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("PromptCard")
        outer.addWidget(card)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        self.input = QLineEdit()
        self.input.setObjectName("PaletteInput")
        self.input.setPlaceholderText(_("Escreve um comando…"))
        self.input.setClearButtonEnabled(True)
        self.input.textChanged.connect(self._queue_lookup)
        self.input.installEventFilter(self)
        card_layout.addWidget(self.input)
        card_layout.addWidget(hairline())

        self.empty_label = QLabel(_("Sem correspondências"))
        self.empty_label.setObjectName("Muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        card_layout.addWidget(self.empty_label)

        self.rows = QListWidget()
        self.rows.setObjectName("PaletteList")
        self.rows.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rows.itemActivated.connect(self._activate_row)
        self.rows.clicked.connect(self._activate_index)
        card_layout.addWidget(self.rows, 1)

        self._lookup_timer = QTimer(self)
        self._lookup_timer.setSingleShot(True)
        self._lookup_timer.setInterval(_LOOKUP_DEBOUNCE_MS)
        self._lookup_timer.timeout.connect(self._run_lookup)

        self._lookup_signals = _LookupSignals(self)
        self._lookup_signals.results_ready.connect(self._on_results)

        self._entrance = QPropertyAnimation(self, b"pos", self)
        self._entrance.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._install_shortcuts()

    def open_with(self, commands: Sequence[Command]) -> None:
        """Show the palette over the current commands and focus the query."""

        self._commands = tuple(commands)
        self.input.clear()
        self._populate(lookup("", self._commands))
        self.show()
        duration = ui_theme.animation_ms()
        target = self.pos()
        if duration:
            self._entrance.stop()
            self._entrance.setDuration(duration)
            self._entrance.setStartValue(target + QPoint(0, _ENTRANCE_OFFSET))
            self._entrance.setEndValue(target)
            self.move(target + QPoint(0, _ENTRANCE_OFFSET))
            self._entrance.start()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Fallback handling for keys that reach the dialog itself."""

        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Handle palette keys from the query field without losing typing focus."""

        if watched is self.input and isinstance(event, QKeyEvent):
            if event.type() != QEvent.Type.KeyPress:
                return False
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._move_selection(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move_selection(-1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate_current()
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._entrance.stop()
        for shortcut in self._shortcuts:
            shortcut.deleteLater()
        self._shortcuts.clear()
        super().closeEvent(event)

    def _install_shortcuts(self) -> None:
        # Widget-level context keeps Escape scoped to this palette.
        shortcut = QShortcut(QKeySequence("Escape"), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.close)
        self._shortcuts.append(shortcut)

    def _queue_lookup(self) -> None:
        self._lookup_timer.start()

    def _run_lookup(self) -> None:
        query = self.input.text().strip()
        QThreadPool.globalInstance().start(_LookupJob(query, self._commands, self._lookup_signals))

    def _on_results(self, query: str, matches: object) -> None:
        """Accept one worker outcome; stale answers are discarded, not shown."""

        if query != self.input.text().strip():
            return
        if isinstance(matches, tuple) and all(isinstance(item, Command) for item in matches):
            self._populate(matches)

    def _populate(self, matches: Sequence[Command]) -> None:
        self.rows.clear()
        for command in matches:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 8, 10, 8)
            row_layout.setSpacing(8)
            title = QLabel(command.title)
            title.setTextFormat(Qt.TextFormat.PlainText)
            row_layout.addWidget(title, 1)
            if command.shortcut:
                hint = QLabel(command.shortcut)
                hint.setObjectName("Muted")
                hint.setTextFormat(Qt.TextFormat.PlainText)
                row_layout.addWidget(hint)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, command)
            self.rows.addItem(item)
            self.rows.setItemWidget(item, row)
            item.setSizeHint(QSize(row.sizeHint().width(), _ROW_HEIGHT))
        has_rows = bool(matches)
        self.rows.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)
        if has_rows:
            self.rows.setCurrentRow(0)
        self._fit_height()

    def _fit_height(self) -> None:
        """Keep the card compact when few rows match and bounded when many do."""

        rows = self.rows.count()
        target = 88 + rows * _ROW_HEIGHT
        if self.isVisible():
            geometry = self.screen().availableGeometry()
            target = min(target, geometry.height() - 120)
        self.setFixedHeight(target)

    def _move_selection(self, delta: int) -> None:
        if self.rows.count() == 0:
            return
        current = self.rows.currentRow()
        target = max(0, min(self.rows.count() - 1, current + delta))
        self.rows.setCurrentRow(target)

    def _activate_current(self) -> None:
        item = self.rows.currentItem()
        if item is not None:
            self._activate_row(item)

    def _activate_index(self, index: QModelIndex) -> None:
        self._activate_row(self.rows.item(index.row()))

    def _activate_row(self, item: QListWidgetItem) -> None:
        command = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(command, Command):
            return
        self.close()
        self.command_activated.emit(command)
