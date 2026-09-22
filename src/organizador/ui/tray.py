"""Windows system-tray presence and quick actions."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from organizador.i18n import _
from organizador.ui.icons import app_icon


class TrayIcon(QObject):
    """Keep the file watcher available when the main window is hidden."""

    open_requested = Signal()
    inbox_requested = Signal()
    pause_requested = Signal(bool)
    undo_requested = Signal()
    settings_requested = Signal()
    check_updates_requested = Signal()
    install_update_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(_("SortInator · a preparar"))
        menu = QMenu()
        self.open_action = menu.addAction(_("Abrir SortInator"))
        self.inbox_action = menu.addAction(_("Caixa de Entrada"))
        menu.addSeparator()
        self.pause_action = menu.addAction(_("Pausar vigilância"))
        self.pause_action.setCheckable(True)
        self.undo_action = menu.addAction(_("Desfazer última organização"))
        self.update_action = menu.addAction(_("Procurar atualizações…"))
        self.install_update_action = menu.addAction("")
        self.install_update_action.setVisible(False)
        self.settings_action = menu.addAction(_("Definições"))
        menu.addSeparator()
        self.quit_action = menu.addAction(_("Sair"))
        self.tray.setContextMenu(menu)

        self.open_action.triggered.connect(self.open_requested)
        self.inbox_action.triggered.connect(self.inbox_requested)
        self.pause_action.toggled.connect(self.pause_requested)
        self.undo_action.triggered.connect(self.undo_requested)
        self.update_action.triggered.connect(self.check_updates_requested)
        self.install_update_action.triggered.connect(self.install_update_requested)
        self.settings_action.triggered.connect(self.settings_requested)
        self.quit_action.triggered.connect(self.quit_requested)
        self.tray.activated.connect(self._activated)
        self.tray.messageClicked.connect(self.open_requested)

    @property
    def available(self) -> bool:
        """Return whether the desktop provides a system tray."""

        return QSystemTrayIcon.isSystemTrayAvailable()

    def show(self) -> None:
        """Publish the tray icon."""

        self.tray.show()

    def hide(self) -> None:
        """Remove the tray icon."""

        self.tray.hide()

    def update_inbox_count(self, count: int) -> None:
        """Reflect pending files in both menu copy and tooltip."""

        self.inbox_action.setText(
            _("Caixa de Entrada ({count})").format(count=count) if count else _("Caixa de Entrada")
        )
        state = (
            _("({count}) por organizar").format(count=count)
            if count
            else _("Caixa de Entrada vazia")
        )
        self.tray.setToolTip(_("SortInator · {state}").format(state=state))

    def set_paused(self, paused: bool) -> None:
        """Synchronise the checkable pause action without emitting a loop."""

        self.pause_action.blockSignals(True)
        self.pause_action.setChecked(paused)
        self.pause_action.setText(_("Retomar vigilância") if paused else _("Pausar vigilância"))
        self.pause_action.blockSignals(False)

    def set_pending_update(self, version: str | None) -> None:
        """Show or hide the version-labelled install action."""

        self.set_update_state(version=version)

    def set_update_state(
        self,
        *,
        checking: bool = False,
        installing: bool = False,
        version: str | None = None,
    ) -> None:
        """Reflect the updater state across the check/install menu actions."""

        busy = checking or installing
        self.update_action.setEnabled(not busy)
        self.update_action.setText(
            _("A procurar atualizações…") if checking else _("Procurar atualizações…")
        )
        if version:
            self.install_update_action.setText(
                _("A instalar atualização {version}…").format(version=version)
                if installing
                else _("Instalar atualização {version}").format(version=version)
            )
        self.install_update_action.setVisible(version is not None)
        self.install_update_action.setEnabled(version is not None and not installing)

    def notify(
        self,
        title: str,
        message: str,
        *,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
    ) -> None:
        """Display a native tray notification."""

        self.tray.showMessage(title, message, icon, 4500)

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.open_requested.emit()
