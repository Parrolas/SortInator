"""Executable entry point and single-instance Windows coordination."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import logging
import sys
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from organizador import updater
from organizador.config import APP_NAME, AppConfig, default_data_dir
from organizador.controller import AppController
from organizador.db import Database, DatabaseHealthError, NewerDatabaseError
from organizador.i18n import _, set_language
from organizador.logging_setup import configure_logging, log_uncaught_exception
from organizador.notifications import notification_token
from organizador.recovery import RecoveryBundle, RecoveryCoordinator, RecoveryError
from organizador.startup import refresh_windows_integration, unregister_windows_integration
from organizador.ui.icons import app_icon
from organizador.ui.theme import apply_theme, get_theme
from organizador.windows_shell import AppMutex

LOGGER = logging.getLogger(__name__)


class SingleInstance(QObject):
    """Notify the running process instead of starting a second file watcher."""

    show_requested = Signal()
    notification_requested = Signal(str)
    organize_requested = Signal(list)

    def __init__(self, data_dir: Path) -> None:
        super().__init__()
        digest = hashlib.sha1(str(data_dir.resolve()).encode("utf-8")).hexdigest()[:12]
        self.name = f"organizador-{digest}"
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._receive)
        self._activation_handler: Callable[[str], None] | None = None
        self._queued_activations: list[str] = []
        self._organize_handler: Callable[[list[str]], None] | None = None
        self._queued_organize: list[list[str]] = []
        self.notification_requested.connect(self._dispatch_notification)
        self.organize_requested.connect(self._dispatch_organize)

    def _dispatch_notification(self, uri: str) -> None:
        if self._activation_handler is None:
            self._queued_activations.append(uri)
        else:
            self._activation_handler(uri)

    def _dispatch_organize(self, paths: list[str]) -> None:
        if self._organize_handler is None:
            self._queued_organize.append(paths)
        else:
            self._organize_handler(paths)

    def set_notification_handler(self, handler: Callable[[str], None]) -> None:
        """Hold activations received during startup until the catalog is ready."""
        self._activation_handler = handler
        queued, self._queued_activations = self._queued_activations, []
        for uri in queued:
            QTimer.singleShot(0, lambda value=uri: handler(value))

    def set_organize_handler(self, handler: Callable[[list[str]], None]) -> None:
        """Deliver Explorer selections received during startup once ready."""
        self._organize_handler = handler
        queued, self._queued_organize = self._queued_organize, []
        for paths in queued:
            QTimer.singleShot(0, lambda value=paths: handler(value))

    def acquire(
        self,
        notification_uri: str | None = None,
        organize_paths: Sequence[str] | None = None,
    ) -> bool:
        """Listen for future launches or ask an existing process to show itself."""

        probe = QLocalSocket()
        probe.connectToServer(self.name)
        if probe.waitForConnected(250):
            message = self._activation_payload(notification_uri, organize_paths)
            probe.write(message)
            probe.flush()
            probe.waitForBytesWritten(250)
            # Keep the pipe alive until the server consumes its activation.
            # Disconnecting immediately can discard pending writes on Windows.
            probe.waitForReadyRead(2000)
            probe.disconnectFromServer()
            if probe.state() != QLocalSocket.LocalSocketState.UnconnectedState:
                probe.waitForDisconnected(500)
            return False
        QLocalServer.removeServer(self.name)
        return self.server.listen(self.name)

    @staticmethod
    def _activation_payload(
        notification_uri: str | None,
        organize_paths: Sequence[str] | None,
    ) -> bytes:
        data: dict[str, object] = {}
        if notification_uri is not None:
            data["notification"] = notification_uri
        if organize_paths:
            data["organize"] = [str(path) for path in organize_paths if path]
        if not data:
            return b"show"
        return json.dumps(data).encode("utf-8")

    def _receive(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            socket.waitForReadyRead(100)
            payload = bytes(socket.readAll().data())
            socket.write(b"received")
            socket.flush()
            socket.waitForBytesWritten(250)
            socket.disconnectFromServer()
            socket.deleteLater()
            if payload == b"show":
                self.show_requested.emit()
            elif len(payload) <= 4096:
                try:
                    data = json.loads(payload)
                except (ValueError, UnicodeError):
                    continue
                if not isinstance(data, dict):
                    continue
                uri = data.get("notification")
                if isinstance(uri, str) and notification_token(uri) is not None:
                    self.notification_requested.emit(uri)
                raw_paths = data.get("organize")
                if isinstance(raw_paths, list):
                    paths = [item for item in raw_paths if isinstance(item, str) and item][:32]
                    if paths:
                        self.organize_requested.emit(paths)


def build_parser() -> argparse.ArgumentParser:
    """Create the small command-line surface used by startup and tests."""

    parser = argparse.ArgumentParser(description="Organizador de ficheiros de estudo")
    parser.add_argument(
        "--background", action="store_true", help="Arrancar apenas no tabuleiro do sistema"
    )
    parser.add_argument("--notification-uri", help=argparse.SUPPRESS)
    parser.add_argument("--organize", action="append", help=argparse.SUPPRESS)
    parser.add_argument("--register-integration", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--unregister-integration", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--data-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--update-manifest", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--update-token", help=argparse.SUPPRESS)
    return parser


def split_update_arguments(manifest: Path | None, token: str | None) -> tuple[Path, str] | None:
    """Return paired update handshake arguments, or ``None`` for normal startup."""

    if manifest is None and token is None:
        return None
    if manifest is None or token is None:
        raise ValueError("--update-manifest and --update-token must be used together")
    return manifest, token


def load_config_safely(data_dir: Path) -> tuple[AppConfig, Exception | None]:
    """Return safe defaults when any settings-loading failure reaches startup."""

    try:
        return AppConfig.load(data_dir), None
    except Exception as exc:
        LOGGER.exception("Could not load application settings")
        return AppConfig(data_dir=data_dir), exc


def _warn_unreadable_settings(error: Exception) -> None:
    QMessageBox.warning(
        None,
        _("Definições danificadas"),
        _(
            "Não foi possível ler as definições guardadas. "
            "A app abriu com valores seguros para poderes corrigi-las.\n\n{error}"
        ).format(error=error),
    )


def reload_config_after_restore(
    application: QApplication, data_dir: Path
) -> tuple[AppConfig, Exception | None]:
    """Reload settings after a recovery restore replaced them on disk.

    The restored backup may point at folders that differ from the config the
    session loaded earlier; re-reading keeps the running app consistent with
    its own restored configuration.
    """

    config, error = load_config_safely(data_dir)
    if error is not None:
        _warn_unreadable_settings(error)
    set_language(config.language)
    apply_theme(application, get_theme(config.theme))
    return config, error


def _set_app_user_model_id() -> None:
    """Give the packaged app a stable identity for tray notifications."""

    if not getattr(sys, "frozen", False):
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            ctypes.c_wchar_p("Parrolas.Organizador")
        )
    except Exception:  # pragma: no cover - cosmetic Windows integration
        LOGGER.warning("Could not set the application user model id", exc_info=True)


def main(argv: list[str] | None = None) -> int:
    """Create Qt, enforce one instance and run the application."""

    arguments = build_parser().parse_args(argv)
    if arguments.notification_uri and notification_token(arguments.notification_uri) is None:
        return 2
    if arguments.register_integration or arguments.unregister_integration:
        if not updater.is_frozen() or arguments.notification_uri:
            return 2
        if arguments.unregister_integration:
            unregister_windows_integration()
            return 0
        config, _error = load_config_safely(arguments.data_dir or default_data_dir())
        return 0 if refresh_windows_integration(config.allowed_extensions) else 1
    target_data_dir = arguments.data_dir or default_data_dir()
    sys.excepthook = log_uncaught_exception
    _set_app_user_model_id()
    try:
        configure_logging(target_data_dir)
    except Exception as exc:
        logging_error: Exception | None = exc
    else:
        logging_error = None
    application = QApplication(sys.argv[:1])
    application.setApplicationName(APP_NAME)
    application.setOrganizationName(APP_NAME)
    application.setQuitOnLastWindowClosed(False)
    application.setWindowIcon(app_icon())
    if updater.is_frozen() and not arguments.smoke_test:
        mutex = AppMutex()
        application.aboutToQuit.connect(mutex.close)

    if logging_error is not None:
        QMessageBox.critical(
            None,
            _("Não foi possível iniciar o registo"),
            _(
                "A pasta de dados da aplicação não está disponível. "
                "Nenhum ficheiro foi alterado.\n\n{error}"
            ).format(error=logging_error),
        )
        return 1

    config, config_error = load_config_safely(target_data_dir)
    if config_error is not None:
        _warn_unreadable_settings(config_error)
    set_language(config.language)
    apply_theme(application, get_theme(config.theme))

    try:
        update_arguments = split_update_arguments(arguments.update_manifest, arguments.update_token)
    except ValueError:
        QMessageBox.critical(
            None,
            _("Atualização inválida"),
            _("Os argumentos da atualização estão incompletos. Nenhum ficheiro foi alterado."),
        )
        return 1

    # One data set, one manager: copies installed in different folders share
    # the per-user database, so a data-dir guard must reject a second copy
    # before it can watch, migrate or recover the same files.
    instance = SingleInstance(target_data_dir)
    acquired = True
    if not arguments.smoke_test:
        acquired = instance.acquire(arguments.notification_uri, arguments.organize)
    if not acquired:
        return 0

    # One installation, one updater: frozen processes rendezvous on the
    # install folder so two profiles can never update the same binaries
    # concurrently.
    install_dir = updater.app_directory()
    install_instance = SingleInstance(install_dir) if install_dir is not None else None
    if (
        install_dir is not None
        and not arguments.smoke_test
        and install_instance is not None
        and not install_instance.acquire(arguments.notification_uri)
    ):
        return 0

    coordinator = RecoveryCoordinator(target_data_dir)
    try:
        restored = coordinator.restore_pending()
    except Exception as exc:
        LOGGER.exception("Could not recover a pending migration")
        QMessageBox.critical(
            None,
            _("Não foi possível recuperar os dados"),
            _(
                "Existe uma cópia de segurança de migração que não pôde ser restaurada "
                "automaticamente. Nenhum ficheiro foi alterado.\n\n{error}"
            ).format(error=exc),
        )
        return 1
    if restored is not None:
        LOGGER.warning(
            "Restored pre-migration backup from an interrupted update: %s", restored.path
        )
        config, config_error = reload_config_after_restore(application, target_data_dir)

    with suppress(Exception):
        updater.prune_abandoned_update_state(target_data_dir)
    if install_dir is not None:
        with suppress(Exception):
            updater.prune_completed_rollback_directories(install_dir, target_data_dir)

    database = Database(config.database_path)
    bundle: RecoveryBundle | None = None
    try:
        if database.inspect_schema().requires_migration:
            bundle = coordinator.prepare_migration()
        database.initialize()
        database.validate_health().require_healthy()
    except NewerDatabaseError:
        LOGGER.error("Refusing to open a database from a newer application version")
        QMessageBox.critical(
            None,
            _("Versão da base de dados mais recente"),
            _(
                "Esta base de dados foi criada por uma versão mais recente do Organizador. "
                "Abre a versão mais recente da app. Nenhum ficheiro foi alterado."
            ),
        )
        return 1
    except Exception as exc:
        LOGGER.exception("Could not migrate application data")
        with suppress(Exception):
            coordinator.restore_pending()
        QMessageBox.critical(
            None,
            _("Não foi possível atualizar os dados"),
            _(
                "A aplicação não conseguiu preparar o catálogo local. "
                "Foi tentada a reposição da cópia de segurança.\n\n{error}"
            ).format(error=exc),
        )
        return 1

    try:
        controller = AppController(config, database=database)
    except Exception as exc:
        LOGGER.exception("Could not initialize application data")
        if bundle is not None:
            with suppress(Exception):
                coordinator.restore_pending()
        QMessageBox.critical(
            None,
            _("Não foi possível abrir os dados"),
            _(
                "A aplicação não conseguiu abrir o catálogo local. "
                "Consulta organizador.log antes de tentar novamente.\n\n{error}"
            ).format(error=exc),
        )
        return 1
    instance.show_requested.connect(controller.show_main)
    instance.set_notification_handler(controller.activate_notification)
    instance.set_organize_handler(controller.organize_external_paths)
    if install_instance is not None:
        install_instance.show_requested.connect(controller.show_main)
        install_instance.set_notification_handler(controller.activate_notification)

    if update_arguments is not None:
        manifest_path = update_arguments[0]
        try:
            transaction = updater.read_update_transaction(manifest_path)
        except updater.UpdaterError as exc:
            LOGGER.error("Could not read the update transaction: %s", exc)
            QMessageBox.critical(
                None,
                _("Atualização inválida"),
                _("A atualização não pôde ser validada. Nenhum ficheiro foi alterado."),
            )
            return 1
        if transaction.result_path.exists():
            LOGGER.info(
                "Update %s already has a recorded outcome; starting normally",
                transaction.transaction_id,
            )
        elif not updater.is_frozen():
            QMessageBox.critical(
                None,
                _("Atualização inválida"),
                _("A atualização só se aplica à versão instalada."),
            )
            return 1
        else:
            state = controller.prepare()
            QTimer.singleShot(
                0,
                lambda: controller.run_update_handshake(
                    transaction,
                    bundle,
                    coordinator,
                    state,
                    background=arguments.background,
                ),
            )
            return int(application.exec())

    try:
        controller.start(
            background=(
                arguments.background or bool(arguments.notification_uri) or bool(arguments.organize)
            ),
            smoke_test=arguments.smoke_test,
        )
    except Exception as exc:
        LOGGER.exception("Application failed to start after migration")
        if bundle is not None:
            with suppress(Exception):
                coordinator.restore_pending()
        QMessageBox.critical(
            None,
            _("Não foi possível concluir o arranque"),
            _(
                "A aplicação não conseguiu concluir o arranque. "
                "Foi tentada a reposição da cópia de segurança.\n\n{error}"
            ).format(error=exc),
        )
        return 1
    if bundle is not None:
        try:
            coordinator.mark_healthy(bundle)
        except (RecoveryError, DatabaseHealthError, OSError) as exc:
            LOGGER.exception("Could not mark migrated data healthy")
            with suppress(Exception):
                coordinator.restore_pending()
            QMessageBox.critical(
                None,
                _("Não foi possível atualizar os dados"),
                _(
                    "Os dados migrados não puderam ser validados. "
                    "Foi tentada a reposição da cópia de segurança.\n\n{error}"
                ).format(error=exc),
            )
            return 1
    with suppress(Exception):
        coordinator.prune_healthy_backups()
    if arguments.smoke_test:
        QTimer.singleShot(900, controller.shutdown)
    elif arguments.organize:
        selected = list(arguments.organize)
        QTimer.singleShot(0, lambda: controller.organize_external_paths(selected))
    elif arguments.notification_uri:
        QTimer.singleShot(0, lambda: controller.activate_notification(arguments.notification_uri))
    exit_code = application.exec()
    return int(exit_code)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
