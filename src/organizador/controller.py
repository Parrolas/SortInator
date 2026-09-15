"""Application orchestration between background services and Qt widgets."""

from __future__ import annotations

import copy
import logging
import os
import sqlite3
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from functools import partial
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
    QSystemTrayIcon,
)

from organizador import duplicates, notifications, ocr, updater
from organizador.classifier import guess_filing
from organizador.config import AppConfig, default_data_dir, parse_extensions
from organizador.db import Database
from organizador.filer import FilingError, FilingService, render_final_name
from organizador.i18n import _
from organizador.indexer import DocumentIndexer
from organizador.logging_setup import configure_logging
from organizador.models import (
    ExistingDownload,
    FiledDocument,
    FilingGuess,
    FindingReason,
    InboxItem,
    ReconciliationFinding,
    Subject,
)
from organizador.paths import normalise_path_key, resolve_contained
from organizador.reconcile import (
    adopt_untracked_subject_file,
    dismiss_finding,
    drop_missing_document,
    unregister_adopted_document,
    visible_findings,
)
from organizador.reconcile import apply as apply_reconciliation
from organizador.reconcile import scan as scan_reconciliation
from organizador.recovery import (
    BundleInfo,
    RecoveryBundle,
    RecoveryCoordinator,
)
from organizador.startup import refresh_windows_integration, set_launch_at_login
from organizador.ui.dialogs import (
    BackupListDialog,
    BulkFilingDialog,
    OnboardingDialog,
    SubjectDialog,
    SubjectFilesDialog,
)
from organizador.ui.main_window import MainWindow
from organizador.ui.notification_dialog import NotificationFilesDialog
from organizador.ui.pages import SettingsPayload
from organizador.ui.prompt import FilingPrompt
from organizador.ui.theme import apply_theme, get_theme
from organizador.ui.tray import TrayIcon
from organizador.updater import UpdateCheckResult, UpdateInfo, UpdateTransaction
from organizador.watcher import DownloadWatcher
from organizador.windows_shell import reveal_files

LOGGER = logging.getLogger(__name__)


class _UpdateInstallAborted(Exception):
    """The update worker stopped early because the application is shutting down."""


_INTAKE_NOTICE_WINDOW_MS = 10_000
_FILED_NOTICE_WINDOW_MS = 4_000
_FILED_IMMEDIATE_WINDOW_S = 10.0


@dataclass(frozen=True, slots=True)
class StartupState:
    """Whether onboarding completed and background services may start."""

    configured: bool
    services_ready: bool


@dataclass(frozen=True, slots=True)
class _TransferOutcome:
    """One finished background file transfer, marshalled to the GUI thread."""

    kind: str
    job: object
    result: object
    error: str | None


@dataclass(frozen=True, slots=True)
class _IngestJob:
    generation: int
    path: Path
    expected: ExistingDownload | None
    external: bool = False


@dataclass(frozen=True, slots=True)
class _FileJob:
    inbox_id: int
    subject_id: int
    kind: str
    filename: str
    create_task: bool
    due_date: date | None
    replace_document_id: int | None = None


@dataclass(frozen=True, slots=True)
class _ReturnJob:
    inbox_id: int
    watcher: DownloadWatcher | None
    unpause: bool


@dataclass(frozen=True, slots=True)
class _UndoJob:
    pass


@dataclass(frozen=True, slots=True)
class _BulkItem:
    inbox_id: int
    original_name: str
    final_name: str


@dataclass(frozen=True, slots=True)
class _BulkJob:
    items: tuple[_BulkItem, ...]
    subject_id: int
    kind: str
    create_task: bool
    due_date: date | None
    failures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _BackupOutcome:
    """One finished backup operation, marshalled to the GUI thread."""

    kind: str
    result: object
    error: str | None


@dataclass(frozen=True, slots=True)
class _BulkResult:
    handled: tuple[int, ...]
    filed: int
    failures: tuple[str, ...]
    documents: tuple[FiledDocument, ...]


def _deadline_copy(delta_days: int) -> str:
    if delta_days < 0:
        return _("está atrasada")
    if delta_days == 0:
        return _("vence hoje")
    if delta_days == 1:
        return _("vence amanhã")
    return _("vence em {count} dias").format(count=delta_days)


class AppController(QObject):
    """Own the long-running services and marshal worker events onto Qt's thread."""

    download_ready = Signal(int, object)
    index_completed = Signal(int, str)
    import_completed = Signal(int)
    transfer_finished = Signal(object)
    update_check_finished = Signal(object, bool, int)
    update_install_finished = Signal(object)
    backup_finished = Signal(object)
    windows_integration_ready = Signal(bool)

    def __init__(self, config: AppConfig, database: Database | None = None) -> None:
        super().__init__()
        self.config = config
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        configure_logging(self.config.data_dir)
        if database is None:
            database = Database(config.database_path)
            database.initialize()
        self.database = database
        self.filer = FilingService(config, self.database)
        self.indexer = DocumentIndexer(
            self.database,
            lambda file_id, error: self.index_completed.emit(file_id, error),
            ocr_languages=self._ocr_language_tags,
        )
        self.watcher: DownloadWatcher | None = None
        self.prompt_queue: deque[int] = deque()
        self.hide_notice_shown = False
        self._manual_import_active = False
        self._manual_imported = 0
        self._manual_import_skipped = 0
        self._manual_import_failed = 0
        self._manual_import_deferred = 0
        self._manual_import_pending = 0
        self._manual_import_complete = False
        self._manual_import_worker_skipped = 0
        self._manual_import_errors: list[str] = []
        self._watcher_generation = 0
        self._pending_update: UpdateInfo | None = None
        self._update_installing = False
        self._update_checking = False
        self._update_check_generation = 0
        self._update_transaction: UpdateTransaction | None = None
        self._update_restart_armed = False
        self._abort_update_install = False

        self.main_window = MainWindow(self.database, config)
        self.prompt = FilingPrompt(
            config.prompt_timeout_seconds, auto_close=config.prompt_timeout_enabled
        )
        self.tray = TrayIcon(self)
        self._native_notifications = False
        self._notification_dialog: NotificationFilesDialog | None = None
        self.windows_integration_ready.connect(self._set_native_notifications)
        self._connect_signals()

        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(60_000)
        self.reminder_timer.timeout.connect(self._check_deadlines)

        self._transfer_queue: deque[tuple[str, object, Callable[[], object]]] = deque()
        self._transfer_threads: set[threading.Thread] = set()
        self._transfer_lock = threading.Lock()
        self._transfer_claims: set[tuple[str, str]] = set()
        self._pending_transfers = 0
        self._shutting_down = False
        self._shutdown_complete = False
        self._shutdown_progress: QProgressDialog | None = None
        self._return_in_flight: set[int] = set()
        self._return_pause_owner: DownloadWatcher | None = None
        self._undo_in_flight = False
        self._bulk_filing_in_flight = False
        self._deferred_downloads: list[tuple[int, Path | ExistingDownload]] = []
        self._deferred_download_keys: set[str] = set()
        self._backup_dialog: BackupListDialog | None = None
        self._subject_files_dialog: SubjectFilesDialog | None = None

        self._intake_notice_names: list[str] = []
        self._intake_notice_timer = QTimer(self)
        self._intake_notice_timer.setSingleShot(True)
        self._intake_notice_timer.setInterval(_INTAKE_NOTICE_WINDOW_MS)
        self._intake_notice_timer.timeout.connect(self._flush_intake_notices)

        self._filed_pending: list[tuple[str, str, FiledDocument | None]] = []
        self._filed_notice_timer = QTimer(self)
        self._filed_notice_timer.setSingleShot(True)
        self._filed_notice_timer.setInterval(_FILED_NOTICE_WINDOW_MS)
        self._filed_notice_timer.timeout.connect(self._flush_filed_notices)
        self._last_filed_notice = 0.0

    def start(self, *, background: bool = False, smoke_test: bool = False) -> None:
        """Run first-time setup, start services and reveal the appropriate surface."""

        state = self.prepare(smoke_test=smoke_test)
        self.activate(state, background=background, smoke_test=smoke_test)

    def prepare(self, *, smoke_test: bool = False) -> StartupState:
        """Show the tray and run onboarding plus reconciliation without services."""

        application = QApplication.instance()
        if not isinstance(application, QApplication):  # pragma: no cover - invariant
            raise RuntimeError("QApplication must exist before AppController")
        if not self.tray.available:
            self.main_window.quit_on_close = True
        else:
            self.tray.show()

        configured = self.config.initialized and self.database.count_subjects() > 0
        if not configured and not smoke_test:
            onboarding = OnboardingDialog(self.config, self.database, self.filer, self.main_window)
            configured = onboarding.exec() == QDialog.DialogCode.Accepted

        services_ready = False
        if configured:
            try:
                self.config.ensure_directories()
            except (ValueError, OSError) as exc:
                QMessageBox.critical(
                    self.main_window,
                    _("Não foi possível abrir as pastas"),
                    _("Revê as Definições antes de ativar a vigilância.\n\n{error}").format(
                        error=exc
                    ),
                )
            else:
                self._reconcile_startup()
                services_ready = True
        return StartupState(configured=configured, services_ready=services_ready)

    def activate(
        self,
        state: StartupState,
        *,
        background: bool = False,
        smoke_test: bool = False,
    ) -> None:
        """Start background services and reveal the appropriate surface."""

        if state.services_ready:
            self._restart_watcher()
            self.indexer.submit_pending()
            self.reminder_timer.start()
            if self.config.check_updates_on_launch:
                self._begin_update_check(automatic=True)
            self._handle_legacy_rollback_bridge()
            if not smoke_test:
                self._show_pending_update_result()
        if (
            not smoke_test
            and updater.is_frozen()
            and self.config.data_dir.resolve() == default_data_dir().resolve()
        ):
            threading.Thread(
                target=self._prepare_windows_integration,
                name="windows-integration",
                daemon=True,
            ).start()

        self._refresh()
        self._refresh_backup_page()
        if background and state.configured and not smoke_test:
            self.main_window.hide()
        else:
            self.main_window.show_from_tray("inicio" if state.configured else "disciplinas")

    def _reconcile_startup(self) -> None:
        """Repair safe inbox states before background services inspect the folders."""

        try:
            report = scan_reconciliation(self.config, self.database)
            outcome = apply_reconciliation(self.database, report)
            stale = self.database.reset_stale_index_fingerprints()
            if stale:
                LOGGER.info("Startup requeued %s edited document(s) for indexing", stale)
            subjects = self.database.list_subjects()
            for item in outcome.recovered_items:
                guess = self._filing_guess(item.original_name, subjects)
                self.database.update_inbox_suggestion(item.id, guess.subject_id, guess.kind)
            remaining = scan_reconciliation(self.config, self.database)
            manual_paths = {finding.path for finding in visible_findings(self.database, remaining)}
        except sqlite3.Error as exc:
            LOGGER.exception("Startup reconciliation failed")
            self.tray.notify(
                _("Verificação de segurança incompleta"),
                _("Não foi possível rever o histórico local: {error}").format(error=exc),
            )
            return

        self.main_window.inbox_page.set_reconciliation_report(remaining)
        if report.finding_count:
            LOGGER.info(
                "Startup reconciliation found %s issue(s) and changed %s record(s)",
                report.finding_count,
                outcome.change_count,
            )
        for path in sorted(manual_paths, key=lambda value: str(value).casefold()):
            LOGGER.warning("Manual file reconciliation required: %s", path)

        if (
            not outcome.change_count
            and not manual_paths
            and not remaining.truncated
            and not remaining.incomplete
        ):
            return
        details: list[str] = []
        if outcome.change_count:
            details.append(
                (
                    _("{count} registos da Caixa de Entrada foram revistos")
                    if outcome.change_count != 1
                    else _("{count} registo da Caixa de Entrada foi revisto")
                ).format(count=outcome.change_count)
            )
        if manual_paths:
            count = len(manual_paths)
            details.append(
                (
                    _("{count} ficheiros precisam de revisão manual")
                    if count != 1
                    else _("{count} ficheiro precisa de revisão manual")
                ).format(count=count)
            )
        if remaining.truncated:
            details.append(_("a verificação atingiu o limite de segurança"))
        if remaining.incomplete:
            details.append(_("alguns caminhos não puderam ser verificados"))
        self.tray.notify(
            (
                _("Verificação de segurança incompleta")
                if remaining.incomplete
                else _("Verificação de segurança concluída")
            ),
            ". ".join(details) + ". " + _("Abre a Caixa de Entrada para rever."),
        )

    def shutdown(self) -> None:
        """Stop intake and keep Qt alive until all accepted transfers finish."""

        if self._shutting_down:
            return
        self._shutting_down = True

        if self._update_installing and not self._update_restart_armed:
            # The helper is not supervising yet; ask the worker to abort cleanly
            # between steps. When the helper already launched, shutdown proceeds
            # and the helper completes the update after this process exits.
            self._abort_update_install = True
        self.reminder_timer.stop()
        self._intake_notice_timer.stop()
        self._filed_notice_timer.stop()
        if self.watcher is not None:
            self.watcher.stop()
            self.watcher = None
        self.prompt.timer.stop()
        self.prompt.hide()
        self._poll_shutdown()

    def _poll_shutdown(self) -> None:
        if self._shutdown_complete:
            return
        if self._pending_transfers:
            if self._shutdown_progress is None:
                self._shutdown_progress = QProgressDialog(self.main_window)
                self._shutdown_progress.setWindowTitle(_("A terminar o Organizador"))
                self._shutdown_progress.setCancelButton(None)
                self._shutdown_progress.setRange(0, 0)
                self._shutdown_progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            self._shutdown_progress.setLabelText(
                _("A concluir {count} operações de ficheiros antes de sair…").format(
                    count=self._pending_transfers
                )
            )
            self._shutdown_progress.show()
            QTimer.singleShot(50, self._poll_shutdown)
            return
        self._shutdown_complete = True
        self._watcher_generation += 1
        self._reset_manual_import_state()
        self.indexer.shutdown()
        if self._shutdown_progress is not None:
            self._shutdown_progress.close()
        self.tray.hide()
        self.main_window.allow_close = True
        self.main_window.close()
        QApplication.quit()

    def show_main(self, page: str = "inicio") -> None:
        """Restore the window and refresh current data."""

        self._refresh()
        self.main_window.show_from_tray(page)

    def _connect_signals(self) -> None:
        self.download_ready.connect(self._ingest_download)
        self.index_completed.connect(self._index_finished)
        self.import_completed.connect(self._manual_import_finished)
        self.transfer_finished.connect(self._on_transfer_finished)
        self.tray.open_requested.connect(lambda: self.show_main("inicio"))
        self.tray.inbox_requested.connect(lambda: self.show_main("inbox"))
        self.tray.pause_requested.connect(self._set_paused)
        self.tray.undo_requested.connect(self._undo)
        self.tray.settings_requested.connect(lambda: self.show_main("definicoes"))
        self.tray.check_updates_requested.connect(lambda: self._begin_update_check(automatic=False))
        self.tray.install_update_requested.connect(self._install_pending_update)
        self.tray.quit_requested.connect(self.shutdown)
        self.update_check_finished.connect(self._on_update_check_finished)
        self.update_install_finished.connect(self._on_update_install_finished)
        self.backup_finished.connect(self._finish_backup)
        self.main_window.hidden_to_tray.connect(self._hidden_to_tray)
        self.main_window.quit_requested.connect(self.shutdown)

        self.main_window.home_page.open_path.connect(self._open_path)
        self.main_window.home_page.open_university.connect(
            lambda: self._open_path(self.config.university_root)
        )
        self.main_window.home_page.show_inbox.connect(lambda: self.show_main("inbox"))
        self.main_window.inbox_page.organise_requested.connect(self._organise_item)
        self.main_window.inbox_page.organise_selection_requested.connect(self._organise_selection)
        self.main_window.inbox_page.return_requested.connect(self._return_item)
        self.main_window.inbox_page.open_path.connect(self._open_path)
        self.main_window.inbox_page.import_existing_requested.connect(
            self._import_existing_downloads
        )
        self.main_window.inbox_page.adopt_requested.connect(self._adopt_untracked_file)
        self.main_window.inbox_page.drop_record_requested.connect(self._drop_missing_record)
        self.main_window.inbox_page.dismiss_finding_requested.connect(
            self._dismiss_reconciliation_finding
        )
        self.main_window.inbox_page.unregister_requested.connect(self._unregister_adopted_file)
        self.main_window.search_page.open_path.connect(self._open_path)
        self.main_window.search_page.reveal_path.connect(self._reveal_path)
        self.main_window.search_page.retry_requested.connect(self._retry_failed_indexes)
        self.main_window.tasks_page.changed.connect(self._refresh)
        self.main_window.subjects_page.add_requested.connect(self._add_subject)
        self.main_window.subjects_page.edit_requested.connect(self._edit_subject)
        self.main_window.subjects_page.archive_requested.connect(self._archive_subject)
        self.main_window.subjects_page.restore_requested.connect(self._restore_subject)
        self.main_window.subjects_page.view_files_requested.connect(self._view_subject_files)
        self.main_window.subjects_page.open_folder.connect(self._open_path)
        self.main_window.settings_page.save_requested.connect(self._save_settings)
        self.main_window.settings_page.backup_created_requested.connect(self.create_user_backup)
        self.main_window.settings_page.backup_export_requested.connect(self.export_new_backup)
        self.main_window.settings_page.backup_manager_requested.connect(self.open_backup_manager)
        self.main_window.settings_page.backup_open_folder_requested.connect(self.open_backup_folder)

        self.prompt.filing_requested.connect(self._file_item)
        self.prompt.later_requested.connect(self._prompt_finished)
        self.prompt.return_requested.connect(self._return_item)
        self.prompt.reveal_requested.connect(self._reveal_path)

    @staticmethod
    def _job_claims(job: object) -> set[tuple[str, str]]:
        if isinstance(job, _IngestJob):
            return {("path", normalise_path_key(job.path))}
        if isinstance(job, (_FileJob, _ReturnJob)):
            return {("inbox", str(job.inbox_id))}
        if isinstance(job, _BulkJob):
            return {("inbox", str(item.inbox_id)) for item in job.items}
        if isinstance(job, _UndoJob):
            return {("undo", "latest")}
        return set()

    def _can_transfer(self, job: object) -> bool:
        if isinstance(job, _UndoJob) and any(key[0] == "inbox" for key in self._transfer_claims):
            return False
        if (
            isinstance(job, (_FileJob, _ReturnJob, _BulkJob))
            and ("undo", "latest") in self._transfer_claims
        ):
            return False
        return not (
            self._shutting_down
            or self._update_installing
            or self._job_claims(job) & self._transfer_claims
        )

    def _submit_transfer(self, kind: str, job: object, work: Callable[[], object]) -> bool:
        """Accept one operation into a FIFO queue with at most one file mover."""

        if not self._can_transfer(job):
            return False
        self._transfer_claims.update(self._job_claims(job))
        self._pending_transfers += 1
        with self._transfer_lock:
            self._transfer_queue.append((kind, job, work))
            if self._transfer_threads:
                return True
            thread = threading.Thread(target=self._run_transfers, name="file-transfers")
            self._transfer_threads.add(thread)
            thread.start()
        return True

    def _run_transfers(self) -> None:
        while True:
            with self._transfer_lock:
                if not self._transfer_queue:
                    self._transfer_threads.discard(threading.current_thread())
                    return
                kind, job, work = self._transfer_queue.popleft()
            try:
                result = work()
            except FilingError as exc:
                outcome = _TransferOutcome(kind=kind, job=job, result=None, error=str(exc))
            except Exception as exc:  # never lose a worker outcome
                LOGGER.exception("Background file transfer failed")
                outcome = _TransferOutcome(
                    kind=kind, job=job, result=None, error=str(exc) or type(exc).__name__
                )
            else:
                outcome = _TransferOutcome(kind=kind, job=job, result=result, error=None)
            self.transfer_finished.emit(outcome)

    def _shutdown_transfers(self, timeout: float = 10.0) -> None:
        """Bounded worker wait for test cleanup; normal exit uses Qt polling."""

        deadline = time.monotonic() + timeout
        while True:
            with self._transfer_lock:
                alive = [thread for thread in self._transfer_threads if thread.is_alive()]
            if not alive:
                return
            if time.monotonic() >= deadline:
                LOGGER.warning("Leaving %s file transfer(s) running during shutdown", len(alive))
                return
            time.sleep(0.05)

    def _on_transfer_finished(self, outcome: object) -> None:
        if not isinstance(outcome, _TransferOutcome):
            LOGGER.error("Ignoring malformed transfer outcome")
            return
        self._transfer_claims.difference_update(self._job_claims(outcome.job))
        try:
            self._deliver_transfer(outcome)
        finally:
            self._pending_transfers = max(0, self._pending_transfers - 1)

    def _deliver_transfer(self, outcome: _TransferOutcome) -> None:
        job = outcome.job
        if outcome.kind == "ingest" and isinstance(job, _IngestJob):
            self._finish_ingested(job, outcome.result, outcome.error)
        elif outcome.kind == "file" and isinstance(job, _FileJob):
            self._finish_filed(job, outcome.result, outcome.error)
        elif outcome.kind == "return" and isinstance(job, _ReturnJob):
            self._finish_returned(job, outcome.result, outcome.error)
        elif outcome.kind == "undo" and isinstance(job, _UndoJob):
            self._finish_undone(job, outcome.result, outcome.error)
        elif outcome.kind == "bulk" and isinstance(job, _BulkJob):
            result = outcome.result if isinstance(outcome.result, _BulkResult) else None
            if result is None and outcome.error is None:
                LOGGER.error("Ignoring malformed bulk transfer outcome")
                return
            self._finish_bulk(job, result, outcome.error)
        else:
            LOGGER.error("Ignoring malformed transfer outcome")

    def _ocr_language_tags(self) -> tuple[str, ...] | None:
        """Provide OCR languages live, honouring the current toggle and language."""

        if not self.config.ocr_enabled:
            return None
        return ocr.preferred_language_tags(self.config.language)

    def _restart_watcher(self) -> None:
        self._watcher_generation += 1
        generation = self._watcher_generation
        interrupted_import = self._manual_import_active
        if self.watcher is not None:
            self.watcher.stop()
            self.watcher = None
        if interrupted_import:
            self._reset_manual_import_state()
            self.main_window.inbox_page.set_import_status(
                _(
                    "A importação foi interrompida. Os ficheiros ainda não importados "
                    "ficaram em Downloads."
                )
            )
        if not (self.config.initialized and self.database.count_subjects() > 0):
            return
        candidate = DownloadWatcher(
            self.config,
            lambda download: self.download_ready.emit(generation, download),
            lambda skipped: self.import_completed.emit(skipped),
        )
        try:
            candidate.start(observe=self.config.watch_enabled)
        except Exception as exc:
            LOGGER.exception("Could not start the Downloads watcher")
            with suppress(Exception):
                candidate.stop()
            self.watcher = None
            self.tray.notify(
                _("Vigilância de Downloads desligada"),
                _("Não foi possível abrir a pasta configurada: {error}").format(error=exc),
            )
            return
        self.watcher = candidate

    def _ingest_download(
        self,
        generation: int,
        candidate: Path | ExistingDownload,
    ) -> None:
        if self._shutting_down or generation != self._watcher_generation:
            return
        if self._update_installing:
            path = candidate.path if isinstance(candidate, ExistingDownload) else candidate
            key = normalise_path_key(path)
            if key not in self._deferred_download_keys:
                self._deferred_download_keys.add(key)
                self._deferred_downloads.append((generation, candidate))
            return
        if isinstance(candidate, ExistingDownload):
            expected: ExistingDownload | None = candidate
            path = candidate.path
        else:
            expected = None
            path = candidate
        job = _IngestJob(generation=generation, path=path, expected=expected)
        if not self._can_transfer(job):
            return
        if expected is not None:
            self._manual_import_pending += 1
        snapshot = expected or ExistingDownload.capture(path)
        self._submit_transfer(
            "ingest",
            job,
            lambda: self.filer.ingest(path, expected=snapshot) if snapshot is not None else None,
        )

    def organize_external_paths(self, paths: object) -> None:
        """Ingest files chosen through the Explorer context menu."""

        if self._shutting_down or not isinstance(paths, (list, tuple)):
            return
        if self._update_installing:
            self.tray.notify(
                _("Atualização em curso"),
                _("Tenta organizar o ficheiro quando a atualização terminar."),
            )
            return
        refused = False
        accepted: list[Path] = []
        seen: set[str] = set()
        for raw in paths:
            if not isinstance(raw, str) or not raw.strip():
                continue
            candidate = self._external_candidate(Path(raw))
            if candidate is None:
                refused = True
                continue
            key = normalise_path_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            accepted.append(candidate)
        for path in accepted:
            job = _IngestJob(
                generation=self._watcher_generation, path=path, expected=None, external=True
            )
            submitted = self._submit_transfer(
                "ingest", job, partial(self.filer.ingest_external, path)
            )
            if not submitted:
                refused = True
        if refused:
            self.tray.notify(
                _("Não foi possível recolher o ficheiro"),
                _(
                    "Este ficheiro não pode ser recolhido. Confirma que não está já "
                    "na Universidade e que a extensão é aceite."
                ),
            )

    def _external_candidate(self, path: Path) -> Path | None:
        """Validate one Explorer selection without touching the file."""

        try:
            candidate = path.absolute()
        except OSError:
            return None
        if not candidate.is_file() or not self.config.accepts(candidate):
            return None
        snapshot = ExistingDownload.capture(candidate)
        if snapshot is None or snapshot.size < self.config.minimum_file_size:
            return None
        for root in (self.config.university_root, self.config.data_dir):
            try:
                resolve_contained(candidate, root)
            except OSError:
                continue
            return None
        return candidate

    def _release_deferred_downloads(self) -> None:
        """Reconsider arrivals that update preparation put on hold."""

        deferred = self._deferred_downloads
        self._deferred_downloads = []
        self._deferred_download_keys.clear()
        for generation, candidate in deferred:
            self._ingest_download(generation, candidate)

    def _finish_ingested(self, job: _IngestJob, result: object, error: str | None) -> None:
        manual = job.expected is not None
        item = result if isinstance(result, InboxItem) else None
        if manual:
            if job.generation == self._watcher_generation:
                if error is not None:
                    LOGGER.warning("Could not ingest %s: %s", job.path, error)
                    self._manual_import_failed += 1
                    self._manual_import_errors.append(f"{job.path.name}: {error}")
                elif item is None:
                    self._manual_import_skipped += 1
                else:
                    self._manual_imported += 1
                    self._queue_ingested_item(item, notify=False)
            self._manual_import_delivered()
            return
        if error is not None:
            LOGGER.warning("Could not ingest %s: %s", job.path, error)
            self.tray.notify(_("Não foi possível recolher o ficheiro"), error)
            if not job.external and self.watcher is not None:
                self.watcher.requeue(job.path)
            return
        if item is None:
            if not job.external and self.watcher is not None and job.path.exists():
                self.watcher.requeue(job.path)
            return
        self._queue_ingested_item(item, notify=not job.external)

    def _manual_import_delivered(self) -> None:
        """Account one finished manual ingest and summarize when the batch lands."""

        self._manual_import_pending = max(0, self._manual_import_pending - 1)
        if (
            self._manual_import_active
            and self._manual_import_complete
            and self._manual_import_pending == 0
        ):
            self._show_manual_import_summary()

    def _queue_ingested_item(self, item: InboxItem, *, notify: bool) -> None:
        """Classify an ingested item and queue the normal human decision prompt."""

        subjects = self.database.list_subjects()
        guess = self._filing_guess(item.original_name, subjects)
        self.database.update_inbox_suggestion(item.id, guess.subject_id, guess.kind)
        if item.id not in self.prompt_queue and self.prompt.current_item_id != item.id:
            self.prompt_queue.append(item.id)
        if notify:
            self._queue_intake_notice(item.original_name)
            self._refresh()
        self._show_next_prompt()

    def _queue_intake_notice(self, name: str) -> None:
        """Collect intake names and surface one toast per batching window."""

        if self.config.quiet_intake or self._shutting_down:
            return
        self._intake_notice_names.append(name)
        if not self._intake_notice_timer.isActive():
            self._intake_notice_timer.start()

    def _flush_intake_notices(self) -> None:
        self._intake_notice_timer.stop()
        names = self._intake_notice_names
        self._intake_notice_names = []
        if not names or self.config.quiet_intake:
            return
        if len(names) == 1:
            message = _("{name} está pronto para organizar.").format(name=names[0])
        else:
            message = _("{count} ficheiros estão prontos para organizar.").format(count=len(names))
        self.tray.notify(_("Novo material na Caixa de Entrada"), message)

    def _prepare_windows_integration(self) -> None:
        self.windows_integration_ready.emit(
            bool(refresh_windows_integration(self.config.allowed_extensions))
        )

    def _set_native_notifications(self, ready: bool) -> None:
        self._native_notifications = ready

    def _filed_toast(self, title: str, message: str, documents: list[FiledDocument]) -> None:
        if self._native_notifications and documents:
            try:
                uri = notifications.save_action(self.database, documents)
                if notifications.show_toast(title, message, uri):
                    return
            except Exception:
                LOGGER.warning("Could not prepare filing notification", exc_info=True)
        self.tray.notify(title, message)

    def activate_notification(self, uri: str) -> None:
        if self._shutting_down:
            return
        documents, missing = notifications.resolve_action(self.database, uri)
        if missing:
            self.show_main()
            QMessageBox.information(
                self.main_window,
                _("Notificação indisponível"),
                _(
                    "A notificação expirou ou algum ficheiro já não está disponível. "
                    "Consulta os ficheiros na app."
                ),
            )
        if not documents:
            return
        if len({document.current_path.parent for document in documents}) == 1:
            try:
                reveal_files([document.current_path for document in documents])
                return
            except Exception:
                LOGGER.warning("Could not reveal notification files", exc_info=True)
        self.show_main()
        if self._notification_dialog is not None:
            self._notification_dialog.close()
        self._notification_dialog = NotificationFilesDialog(documents, self.main_window)
        self._notification_dialog.reveal_requested.connect(self._reveal_path)
        self._notification_dialog.show()

    def _notify_filed(
        self, name: str, destination: str, document: FiledDocument | None = None
    ) -> None:
        """Surface filing toasts: first is immediate, the rest join a batch."""

        if self.config.quiet_intake or self._shutting_down:
            return
        now = time.monotonic()
        if not self._filed_pending and now - self._last_filed_notice >= _FILED_IMMEDIATE_WINDOW_S:
            self._filed_toast(
                _("Ficheiro organizado"),
                _("{name} foi guardado em {destination}.").format(
                    name=name, destination=destination
                ),
                [document] if document is not None else [],
            )
            self._last_filed_notice = now
            return
        self._filed_pending.append((name, destination, document))
        if not self._filed_notice_timer.isActive():
            self._filed_notice_timer.start()

    def _flush_filed_notices(self) -> None:
        self._filed_notice_timer.stop()
        pending = self._filed_pending
        self._filed_pending = []
        if not pending or self.config.quiet_intake:
            return
        if len(pending) == 1:
            name, destination, document = pending[0]
            self._filed_toast(
                _("Ficheiro organizado"),
                _("{name} foi guardado em {destination}.").format(
                    name=name, destination=destination
                ),
                [document] if document is not None else [],
            )
            self._last_filed_notice = time.monotonic()
            return
        self._last_filed_notice = time.monotonic()
        self._filed_toast(
            _("Ficheiros organizados"),
            _("{count} ficheiros organizados").format(count=len(pending)),
            [document for _, _, document in pending if document is not None],
        )

    def _import_existing_downloads(self) -> None:
        if self._shutting_down or self._update_installing:
            return
        watcher = self.watcher
        if watcher is None or not watcher.active:
            QMessageBox.warning(
                self.main_window,
                _("Importação indisponível"),
                _("Conclui a configuração da aplicação antes de importar ficheiros."),
            )
            return
        if self._manual_import_active or watcher.manual_import_running:
            QMessageBox.information(
                self.main_window,
                _("Importação em curso"),
                _("Espera que o lote atual termine antes de iniciar outro."),
            )
            return
        try:
            plan = self.filer.plan_existing_downloads()
        except FilingError as exc:
            QMessageBox.warning(self.main_window, _("Não foi possível procurar"), str(exc))
            return
        if not plan.selected:
            QMessageBox.information(
                self.main_window,
                _("Nada para importar"),
                _("Não existem ficheiros elegíveis no nível principal de Downloads."),
            )
            return

        selected_count = len(plan.selected)
        remaining = plan.total - selected_count
        remaining_copy = (
            _(" Os outros {count} ficam em Downloads para um próximo lote.").format(count=remaining)
            if remaining
            else ""
        )
        answer = QMessageBox.question(
            self.main_window,
            _("Importar ficheiros existentes?"),
            _(
                "Foram encontrados {total} ficheiros elegíveis. "
                "Serão verificados no máximo {selected} e movidos para a Caixa de Entrada."
                "{remaining}\n\nCada ficheiro continuará a precisar da tua confirmação."
            ).format(total=plan.total, selected=selected_count, remaining=remaining_copy),
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._manual_import_active = True
        self._manual_imported = 0
        self._manual_import_skipped = 0
        self._manual_import_failed = 0
        self._manual_import_deferred = remaining
        self._manual_import_errors.clear()
        self.main_window.inbox_page.set_import_running(True)
        self.main_window.inbox_page.set_import_status(
            _("A verificar {count} ficheiro…").format(count=selected_count)
            if selected_count == 1
            else _("A verificar {count} ficheiros…").format(count=selected_count)
        )
        queued = watcher.enqueue_existing(plan.selected)
        if queued == 0:
            self._reset_manual_import_state()
            self.main_window.inbox_page.set_import_status(
                _("Os ficheiros mudaram ou já estavam a ser processados e ficaram em Downloads.")
            )

    def _manual_import_finished(self, worker_skipped: int) -> None:
        if not self._manual_import_active:
            return
        self._manual_import_worker_skipped += worker_skipped
        self._manual_import_complete = True
        if self._manual_import_pending > 0:
            return
        self._show_manual_import_summary()

    def _show_manual_import_summary(self) -> None:
        skipped = self._manual_import_skipped + self._manual_import_worker_skipped
        imported = self._manual_imported
        failed = self._manual_import_failed
        parts = [
            _("{count} importado").format(count=imported)
            if imported == 1
            else _("{count} importados").format(count=imported)
        ]
        if skipped:
            parts.append(
                _("{count} ignorado").format(count=skipped)
                if skipped == 1
                else _("{count} ignorados").format(count=skipped)
            )
        if failed:
            parts.append(_("{count} com erro").format(count=failed))
        message = ", ".join(parts) + "."
        if self._manual_import_deferred:
            message += " " + _("{count} não entraram neste lote e ficaram em Downloads.").format(
                count=self._manual_import_deferred
            )
        if self._manual_import_errors:
            shown_errors = "; ".join(self._manual_import_errors[:3])
            if len(self._manual_import_errors) > 3:
                shown_errors += " " + _("e mais {count}").format(
                    count=len(self._manual_import_errors) - 3
                )
            message += " " + _("Revê: {errors}.").format(errors=shown_errors)
        message += " " + _("Nenhum ficheiro foi substituído ou apagado.")
        self._reset_manual_import_state()
        self.main_window.inbox_page.set_import_status(message)
        self._refresh()
        self.tray.notify(_("Importação de Downloads concluída"), message)

    def _adopt_untracked_file(self, finding: ReconciliationFinding) -> None:
        if finding.reason is not FindingReason.UNTRACKED_SUBJECT_FILE:
            return
        answer = QMessageBox.question(
            self.main_window,
            "Adotar ficheiro existente?",
            f"{finding.path.name} será adicionado ao catálogo e à pesquisa local. "
            "O ficheiro não será movido, renomeado nem alterado.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            document = adopt_untracked_subject_file(self.config, self.database, finding)
        except (LookupError, ValueError, OSError, sqlite3.Error) as exc:
            QMessageBox.warning(self.main_window, _("Não foi possível adotar"), str(exc))
            self._refresh_reconciliation_report()
            return
        self.indexer.submit(document)
        self.main_window.inbox_page.set_import_status(
            _("{name} foi adotado sem mover o ficheiro.").format(name=document.current_path.name)
        )
        self._refresh_reconciliation_report()

    def _drop_missing_record(self, finding: ReconciliationFinding) -> None:
        if finding.reason is not FindingReason.MISSING_DOCUMENT or finding.document is None:
            return
        answer = QMessageBox.question(
            self.main_window,
            _("Remover registo em falta?"),
            _(
                "Será removido apenas o registo local e o índice de pesquisa. "
                "Nenhum ficheiro será apagado. Se o ficheiro reaparecer durante a operação, "
                "ficará visível para poder ser adotado novamente."
            ),
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            removed = drop_missing_document(self.database, finding.document)
        except sqlite3.Error as exc:
            LOGGER.exception("Could not drop missing catalog record")
            QMessageBox.warning(self.main_window, _("Não foi possível remover"), str(exc))
            self._refresh_reconciliation_report()
            return
        if not removed:
            QMessageBox.information(
                self.main_window,
                _("Registo mantido"),
                _("O ficheiro ou o registo mudou desde a verificação. Nada foi removido."),
            )
        self._refresh_reconciliation_report()

    def _dismiss_reconciliation_finding(self, finding: ReconciliationFinding) -> None:
        try:
            dismissed = dismiss_finding(self.database, finding)
        except sqlite3.Error as exc:
            QMessageBox.warning(self.main_window, _("Não foi possível guardar"), str(exc))
            return
        if dismissed:
            self.main_window.inbox_page.set_import_status(
                _("A ocorrência foi marcada como revista. O ficheiro não foi alterado.")
            )
            self._refresh_reconciliation_report()

    def _unregister_adopted_file(self, file_id: int) -> None:
        document = self.database.get_file(file_id)
        if document is None or document.origin != "adopted":
            self._refresh_reconciliation_report()
            return
        answer = QMessageBox.question(
            self.main_window,
            _("Remover do catálogo?"),
            _(
                "{name} deixará de aparecer na pesquisa e nos recentes. "
                "O ficheiro permanecerá exatamente onde está."
            ).format(name=document.current_path.name),
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            removed = unregister_adopted_document(self.database, document)
        except sqlite3.Error as exc:
            LOGGER.exception("Could not unregister adopted file")
            QMessageBox.warning(self.main_window, _("Não foi possível remover"), str(exc))
            self._refresh_reconciliation_report()
            return
        if not removed:
            QMessageBox.information(
                self.main_window,
                _("Registo mantido"),
                _("O registo mudou desde que a página foi aberta. Nada foi removido."),
            )
        else:
            self.main_window.inbox_page.set_import_status(
                _("{name} saiu do catálogo; o ficheiro ficou no lugar.").format(
                    name=document.current_path.name
                )
            )
        self._refresh_reconciliation_report()

    def _refresh_reconciliation_report(self) -> None:
        try:
            report = scan_reconciliation(self.config, self.database)
            visible_findings(self.database, report)
        except sqlite3.Error as exc:
            LOGGER.exception("Could not refresh reconciliation findings")
            QMessageBox.warning(self.main_window, _("Verificação incompleta"), str(exc))
            return
        self.main_window.inbox_page.set_reconciliation_report(report)
        self._refresh()

    def _organise_item(self, inbox_id: int) -> None:
        if self.prompt.current_item_id == inbox_id:
            self.prompt.raise_()
            self.prompt.activateWindow()
            return
        self.prompt_queue = deque(item for item in self.prompt_queue if item != inbox_id)
        self.prompt_queue.appendleft(inbox_id)
        if self.prompt.current_item_id is not None:
            self.prompt.close()
        else:
            self._show_next_prompt()

    def _show_next_prompt(self) -> None:
        if (
            self._shutting_down
            or self._update_installing
            or self.prompt.current_item_id is not None
        ):
            return
        while self.prompt_queue:
            inbox_id = self.prompt_queue.popleft()
            if ("inbox", str(inbox_id)) in self._transfer_claims:
                continue
            item = self.database.get_inbox_item(inbox_id)
            if item is None or item.status not in {"pending", "error"} or not item.path.is_file():
                continue
            subjects = self.database.list_subjects()
            if not subjects:
                self.show_main("disciplinas")
                return
            guess = self._filing_guess(item.original_name, subjects)
            self.database.update_inbox_suggestion(item.id, guess.subject_id, guess.kind)
            refreshed = self.database.get_inbox_item(item.id)
            candidate = refreshed or item
            self.prompt.show_item(
                candidate,
                subjects,
                guess,
                name_template=self.config.filename_template,
                duplicate=duplicates.find_duplicate(self.database, candidate),
            )
            return

    def _file_item(
        self,
        inbox_id: int,
        subject_id: int,
        kind: str,
        filename: str,
        create_task: bool,
        due_date: date | None,
        replace_document_id: int | None = None,
    ) -> None:
        job = _FileJob(
            inbox_id,
            subject_id,
            kind,
            filename,
            create_task,
            due_date,
            replace_document_id,
        )
        self._submit_transfer(
            "file",
            job,
            lambda: self.filer.file_document(
                inbox_id,
                subject_id,
                kind,
                filename,
                replace_document_id=replace_document_id,
            ),
        )

    def _finish_filed(self, job: _FileJob, result: object, error: str | None) -> None:
        if not isinstance(result, FiledDocument):
            if self._shutting_down:
                LOGGER.error("Filing failed during shutdown: %s", error)
                return
            self.prompt_queue.appendleft(job.inbox_id)
            self._show_next_prompt()
            self.prompt.show_error(error or _("Não foi possível organizar o ficheiro."))
            self._refresh()
            return
        document = result
        if job.create_task:
            self.database.add_task(
                f"Rever {Path(job.filename).stem}", job.subject_id, job.due_date, document.id
            )
        self.indexer.submit(document)
        subject = self.database.get_subject(job.subject_id)
        self._notify_filed(
            document.current_path.name,
            f"{subject.name if subject else job.kind} / {job.kind}",
            document,
        )
        self._refresh()
        QTimer.singleShot(120, self._show_next_prompt)

    def _return_item(self, inbox_id: int) -> None:
        if not self._can_transfer(_ReturnJob(inbox_id, None, False)):
            return
        self._return_in_flight.add(inbox_id)
        watcher = self.watcher
        observing = watcher is not None and watcher.running
        was_paused = watcher.paused if observing and watcher is not None else False
        if observing and watcher is not None and not was_paused:
            watcher.set_paused(True)
            self._return_pause_owner = watcher
        job = _ReturnJob(
            inbox_id=inbox_id,
            watcher=watcher,
            unpause=observing and not was_paused,
        )
        self._submit_transfer("return", job, lambda: self.filer.return_to_origin(inbox_id))

    def _finish_returned(self, job: _ReturnJob, result: object, error: str | None) -> None:
        self._return_in_flight.discard(job.inbox_id)
        watcher = job.watcher
        destination: Path | None = result if isinstance(result, Path) else None
        ignore_seconds = 30.0
        if error is not None:
            pending_return = None
            with suppress(sqlite3.Error):
                pending_return = next(
                    (
                        event
                        for event in self.database.list_pending_returns()
                        if event.inbox_id == job.inbox_id
                    ),
                    None,
                )
            if pending_return is not None:
                destination = pending_return.destination_path
                ignore_seconds = float("inf")
            item = self.database.get_inbox_item(job.inbox_id)
            if self._shutting_down:
                LOGGER.error("Return failed during shutdown: %s", error)
            elif item is not None:
                self.prompt_queue.appendleft(job.inbox_id)
                self._show_next_prompt()
                self.prompt.show_error(error)
            else:
                QMessageBox.warning(self.main_window, _("Não foi possível devolver"), error)
        if watcher is not None and destination is not None:
            watcher.ignore_self_move(destination, seconds=ignore_seconds)
        if not self._return_in_flight and self._return_pause_owner is not None:
            if not self._shutting_down:
                self._return_pause_owner.set_paused(False)
            self._return_pause_owner = None
        if error is not None or destination is None:
            return
        self.tray.notify(
            _("Ficheiro devolvido"),
            _("{name} voltou para {folder}.").format(
                name=destination.name, folder=destination.parent.name
            ),
        )
        self._refresh()
        QTimer.singleShot(120, self._show_next_prompt)

    def _prompt_finished(self, _inbox_id: int) -> None:
        self._refresh()
        QTimer.singleShot(120, self._show_next_prompt)

    def _undo(self) -> None:
        if not self._can_transfer(_UndoJob()):
            return
        self._undo_in_flight = True
        self._submit_transfer("undo", _UndoJob(), self.filer.undo_latest_filing)

    def _finish_undone(self, job: _UndoJob, result: object, error: str | None) -> None:
        del job
        self._undo_in_flight = False
        if error is not None:
            if self._shutting_down:
                LOGGER.error("Undo failed during shutdown: %s", error)
                return
            QMessageBox.warning(self.main_window, _("Não foi possível desfazer"), error)
            return
        item = result if isinstance(result, InboxItem) else None
        if item is None:
            self.tray.notify(
                _("Nada para desfazer"),
                _("Ainda não existe uma organização reversível."),
            )
            return
        subjects = self.database.list_subjects()
        guess = self._filing_guess(item.original_name, subjects)
        self.database.update_inbox_suggestion(item.id, guess.subject_id, guess.kind)
        self.prompt_queue.appendleft(item.id)
        self.tray.notify(
            _("Organização desfeita"),
            _("{name} voltou à Caixa de Entrada.").format(name=item.path.name),
        )
        self._refresh()
        self._show_next_prompt()

    def _filing_guess(self, filename: str, subjects: list[Subject]) -> FilingGuess:
        return guess_filing(filename, subjects, self.database.filing_hints())

    def _add_subject(self) -> None:
        dialog = SubjectDialog(parent=self.main_window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, code, color, keywords = dialog.values
        folder = self.filer.subject_folder_name(name, code)
        try:
            subject = self.database.add_subject(name, code, color, keywords, folder)
            self.filer.ensure_subject_structure(subject)
        except ValueError as exc:
            QMessageBox.warning(self.main_window, _("Não foi possível criar"), str(exc))
            return
        except (sqlite3.IntegrityError, OSError) as exc:
            QMessageBox.warning(
                self.main_window,
                _("Não foi possível criar"),
                _("Já existe uma disciplina ou pasta com esse nome.\n\n{error}").format(error=exc),
            )
            return
        if not self.config.initialized:
            self.config.initialized = True
            self.config.ensure_directories()
            self.config.save()
            self._restart_watcher()
        self._refresh()

    def _edit_subject(self, subject_id: int) -> None:
        subject = self.database.get_subject(subject_id)
        if subject is None:
            return
        dialog = SubjectDialog(subject, self.main_window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, code, color, keywords = dialog.values
        try:
            updated = self.database.update_subject(
                subject.id, name, code, color, keywords, subject.folder_name
            )
            self.filer.ensure_subject_structure(updated)
        except sqlite3.IntegrityError as exc:
            QMessageBox.warning(
                self.main_window,
                _("Não foi possível guardar"),
                _("Já existe uma disciplina com esse nome.\n\n{error}").format(error=exc),
            )
            return
        self._refresh()

    def _archive_subject(self, subject_id: int) -> None:
        if self.database.count_subjects() <= 1:
            QMessageBox.information(
                self.main_window,
                _("Mantém uma disciplina ativa"),
                _("Cria outra disciplina antes de arquivar esta."),
            )
            return
        subject = self.database.get_subject(subject_id)
        if subject is None:
            return
        answer = QMessageBox.question(
            self.main_window,
            _("Arquivar disciplina?"),
            _(
                "{name} deixa de aparecer nas escolhas. Os ficheiros e tarefas não são apagados."
            ).format(name=subject.name),
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.database.archive_subject(subject_id)
            self._refresh()

    def _restore_subject(self, subject_id: int) -> None:
        subject = self.database.get_subject(subject_id)
        if subject is None or subject.active:
            return
        conflicts = self.database.find_active_subject_conflicts(subject_id)
        if conflicts:
            QMessageBox.warning(
                self.main_window,
                _("Não foi possível restaurar"),
                _(
                    "Já existe uma disciplina ativa com o mesmo nome ou pasta: {names}. "
                    "Edita-a primeiro para libertar o nome."
                ).format(names=", ".join(conflicts)),
            )
            return
        answer = QMessageBox.question(
            self.main_window,
            _("Reativar disciplina?"),
            _(
                "{name} volta a aparecer nas escolhas de arquivo. "
                "Os ficheiros e tarefas não foram alterados."
            ).format(name=subject.name),
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            restored = self.database.set_subject_active(subject_id, True)
            self.filer.ensure_subject_structure(restored)
        except (sqlite3.Error, OSError) as exc:
            QMessageBox.warning(self.main_window, _("Não foi possível restaurar"), str(exc))
            return
        self._refresh()

    def _view_subject_files(self, subject_id: int) -> None:
        subject = self.database.get_subject(subject_id)
        if subject is None:
            return
        documents = self.database.list_subject_files(subject_id)
        dialog = SubjectFilesDialog(
            subject,
            documents,
            self.config.university_root / subject.folder_name,
            self.main_window,
        )
        dialog.open_requested.connect(self._open_path)
        dialog.reindex_requested.connect(self._reindex_document)
        self._subject_files_dialog = dialog
        try:
            dialog.exec()
        finally:
            self._subject_files_dialog = None

    def _reindex_document(self, file_id: int) -> None:
        """Queue one document for extraction again, with visible feedback."""

        document = self.database.get_file(file_id)
        if document is None:
            return
        dialog = self._subject_files_dialog
        if dialog is not None:
            dialog.mark_reindexing(file_id)
        if not self.indexer.reindex(document) and dialog is not None:
            dialog.set_reindex_notice(
                file_id,
                _(
                    "A fila de indexação está ocupada; "
                    "o documento será indexado assim que possível."
                ),
            )

    def _retry_failed_indexes(self) -> None:
        """Queue every failed document for extraction again."""

        for document in self.database.list_failed_index_documents():
            self.indexer.reindex(document)
        self.main_window.search_page.refresh_index_status()

    def _organise_selection(self, inbox_ids: object) -> None:
        if self._shutting_down or self._update_installing:
            return
        if not isinstance(inbox_ids, (tuple, list)):
            return
        items: list[InboxItem] = []
        failures: list[str] = []
        for inbox_id in inbox_ids:
            item = self.database.get_inbox_item(int(inbox_id))
            if item is None or item.status == "recovery":
                continue
            if not item.path.is_file():
                failures.append(f"{item.original_name}: o ficheiro já não está disponível")
                continue
            items.append(item)
        if not items and not failures:
            return
        subjects = self.database.list_subjects()
        if not subjects:
            self.show_main("disciplinas")
            return
        dialog = BulkFilingDialog(items, subjects, self.config.filename_template, self.main_window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        subject_id, kind, create_task, due_date = dialog.values
        subject = next(entry for entry in subjects if entry.id == subject_id)
        if self._bulk_filing_in_flight:
            self.main_window.inbox_page.set_import_status(
                _("Já existe uma organização em curso; espera que termine.")
            )
            return
        self._bulk_filing_in_flight = True
        planned = tuple(
            _BulkItem(
                inbox_id=item.id,
                original_name=item.original_name,
                final_name=render_final_name(
                    self.config.filename_template,
                    subject_name=subject.name,
                    subject_code=subject.code,
                    kind=kind,
                    original_name=item.original_name,
                    when=item.detected_at,
                ),
            )
            for item in items
        )
        job = _BulkJob(
            items=planned,
            subject_id=subject_id,
            kind=kind,
            create_task=create_task,
            due_date=due_date,
            failures=tuple(failures),
        )
        if not self._can_transfer(job):
            self._bulk_filing_in_flight = False
            self.main_window.inbox_page.set_import_status(
                _("Já existe uma organização em curso; espera que termine.")
            )
            return
        count = len(planned)
        self.main_window.inbox_page.set_import_status(
            (
                _("A organizar {count} ficheiros…")
                if count != 1
                else _("A organizar {count} ficheiro…")
            ).format(count=count)
        )
        self._submit_transfer("bulk", job, lambda: self._execute_bulk(job))

    def _execute_bulk(self, job: _BulkJob) -> _BulkResult:
        """File one confirmed batch on a worker thread."""

        handled: list[int] = []
        failures: list[str] = list(job.failures)
        documents: list[FiledDocument] = []
        filed = 0
        for item in job.items:
            try:
                document = self.filer.file_document(
                    item.inbox_id, job.subject_id, job.kind, item.final_name
                )
            except FilingError as exc:
                failures.append(f"{item.original_name}: {exc}")
                continue
            handled.append(item.inbox_id)
            filed += 1
            if job.create_task:
                self.database.add_task(
                    _("Rever {name}").format(name=Path(item.original_name).stem),
                    job.subject_id,
                    job.due_date,
                    document.id,
                )
            documents.append(document)
        return _BulkResult(
            handled=tuple(handled),
            filed=filed,
            failures=tuple(failures),
            documents=tuple(documents),
        )

    def _finish_bulk(self, job: _BulkJob, result: _BulkResult | None, error: str | None) -> None:
        del job
        self._bulk_filing_in_flight = False
        if result is None:
            self.main_window.inbox_page.set_import_status(
                error or _("Não foi possível concluir a organização.")
            )
            return
        for document in result.documents:
            self.indexer.submit(document)
        if result.documents and not self.config.quiet_intake and not self._shutting_down:
            self._filed_toast(
                _("Ficheiros organizados"),
                _("{count} ficheiros organizados").format(count=len(result.documents)),
                list(result.documents),
            )
        self.prompt_queue = deque(item for item in self.prompt_queue if item not in result.handled)
        if self.prompt.current_item_id in result.handled:
            self.prompt.close()
        filed = result.filed
        failures = result.failures
        if failures:
            shown = "; ".join(failures[:3])
            if len(failures) > 3:
                shown += " " + _("e mais {count}").format(count=len(failures) - 3)
            message = (
                _("{count} organizados, {failed} com erro. Revê: {errors}.")
                if filed != 1
                else _("{count} organizado, {failed} com erro. Revê: {errors}.")
            ).format(count=filed, failed=len(failures), errors=shown)
        else:
            message = (
                _("{count} organizados.").format(count=filed)
                if filed != 1
                else _("{count} organizado.").format(count=filed)
            )
        message += " " + _("Nenhum ficheiro foi substituído ou apagado. ")
        message += _("Só a organização mais recente pode ser desfeita.")
        self.main_window.inbox_page.set_import_status(message)
        self._refresh()

    def _save_settings(self, values: SettingsPayload) -> None:
        if self._pending_transfers or self._shutting_down or self._update_installing:
            self.main_window.settings_page.set_status(
                _("Espera que as operações de ficheiros terminem antes de guardar."), error=True
            )
            return
        if self._manual_import_active or (
            self.watcher is not None and self.watcher.manual_import_running
        ):
            self.main_window.settings_page.set_status(
                _("Espera que a importação de Downloads termine antes de guardar."),
                error=True,
            )
            return
        previous = copy.deepcopy(self.config)
        startup_changed = False
        try:
            self.config.university_root = values["university_root"]
            self.config.downloads_dir = values["downloads_dir"]
            self.config.allowed_extensions = parse_extensions(str(values["extensions"]))
            if not self.config.allowed_extensions:
                raise ValueError("Adiciona pelo menos uma extensão aceite.")
            self.config.minimum_file_size = int(values["minimum_file_size"])
            self.config.prompt_timeout_seconds = int(values["prompt_timeout_seconds"])
            self.config.prompt_timeout_enabled = bool(values["prompt_timeout_enabled"])
            self.config.reminder_lead_days = int(values["reminder_lead_days"])
            self.config.filename_template = str(values["filename_template"])
            self.config.theme = str(values["theme"])
            self.config.language = str(values["language"])
            self.config.check_updates_on_launch = bool(values["check_updates_on_launch"])
            self.config.ocr_enabled = bool(values["ocr_enabled"])
            self.config.quiet_intake = bool(values["quiet_intake"])
            self.config.watch_enabled = bool(values["watch_enabled"])
            desired_startup = bool(values["launch_at_login"])
            self.config.launch_at_login = desired_startup
            self.config.ensure_directories()
            for subject in self.database.list_subjects():
                self.filer.ensure_subject_structure(subject)
            if desired_startup != previous.launch_at_login:
                set_launch_at_login(desired_startup)
                startup_changed = True
            self.config.save()
        except (ValueError, OSError, TypeError) as exc:
            if startup_changed:
                with suppress(OSError):
                    set_launch_at_login(previous.launch_at_login)
            self._restore_config(previous)
            self.main_window.settings_page.set_status(str(exc), error=True)
            return
        self.prompt.set_timeout(
            self.config.prompt_timeout_seconds, auto_close=self.config.prompt_timeout_enabled
        )
        application = QApplication.instance()
        if isinstance(application, QApplication):
            apply_theme(application, get_theme(self.config.theme))
        with suppress(Exception):
            refresh_windows_integration(self.config.allowed_extensions)
        self._restart_watcher()
        self.main_window.settings_page.load_config(self.config)
        self.main_window.settings_page.set_status(_("Definições guardadas."))
        self._refresh()

    def _reset_manual_import_state(self) -> None:
        self._manual_import_active = False
        self._manual_imported = 0
        self._manual_import_skipped = 0
        self._manual_import_failed = 0
        self._manual_import_deferred = 0
        self._manual_import_pending = 0
        self._manual_import_complete = False
        self._manual_import_worker_skipped = 0
        self._manual_import_errors.clear()
        self.main_window.inbox_page.set_import_running(False)

    def _restore_config(self, previous: AppConfig) -> None:
        self.config.university_root = previous.university_root
        self.config.downloads_dir = previous.downloads_dir
        self.config.allowed_extensions = previous.allowed_extensions
        self.config.minimum_file_size = previous.minimum_file_size
        self.config.watch_enabled = previous.watch_enabled
        self.config.launch_at_login = previous.launch_at_login
        self.config.prompt_timeout_seconds = previous.prompt_timeout_seconds
        self.config.prompt_timeout_enabled = previous.prompt_timeout_enabled
        self.config.reminder_lead_days = previous.reminder_lead_days
        self.config.filename_template = previous.filename_template
        self.config.theme = previous.theme
        self.config.language = previous.language
        self.config.check_updates_on_launch = previous.check_updates_on_launch
        self.config.ocr_enabled = previous.ocr_enabled
        self.config.quiet_intake = previous.quiet_intake
        self.config.initialized = previous.initialized

    def create_user_backup(self, export_dir: Path | None = None) -> None:
        """Create a user snapshot, optionally exporting a portable archive."""

        if self._shutting_down or self._update_installing or self._pending_transfers:
            self.main_window.settings_page.set_backup_status(
                _("Espera que as operações de ficheiros terminem antes de criar a cópia."),
                error=True,
            )
            return
        self.main_window.settings_page.set_backup_busy(True)
        coordinator = RecoveryCoordinator(self.config.data_dir)

        def work() -> None:
            try:
                bundle = coordinator.create_snapshot()
                archive = (
                    coordinator.export_bundle_zip(bundle.path, export_dir)
                    if export_dir is not None
                    else None
                )
            except Exception as exc:
                LOGGER.exception("Could not create a backup")
                outcome = _BackupOutcome(kind="create", result=None, error=str(exc))
            else:
                outcome = _BackupOutcome(kind="create", result=archive or bundle.path, error=None)
            self.backup_finished.emit(outcome)

        threading.Thread(target=work, name="user-backup", daemon=True).start()

    def export_new_backup(self) -> None:
        """Create a snapshot and export it to a folder the user picks."""

        selected = QFileDialog.getExistingDirectory(self.main_window, _("Escolher pasta"))
        if not selected:
            return
        self.create_user_backup(Path(selected))

    def open_backup_folder(self) -> None:
        self._open_path(self.config.data_dir / "backups")

    def open_backup_manager(self) -> None:
        """Show the backup list and wire its restore, export and delete actions."""

        dialog = BackupListDialog(self._list_bundles(), self.main_window)
        self._backup_dialog = dialog
        dialog.import_requested.connect(lambda: self._import_backup(dialog))
        dialog.restore_requested.connect(self._request_restore)
        dialog.delete_requested.connect(lambda bundle: self._delete_backup(bundle, dialog))
        dialog.export_requested.connect(self._export_backup)
        try:
            dialog.exec()
        finally:
            self._backup_dialog = None

    def _list_bundles(self) -> tuple[BundleInfo, ...]:
        try:
            return RecoveryCoordinator(self.config.data_dir).list_bundles()
        except Exception:
            LOGGER.warning("Could not list backups", exc_info=True)
            return ()

    def _refresh_backup_page(self) -> None:
        self.main_window.settings_page.set_backup_inventory(self._list_bundles())

    def _import_backup(self, dialog: BackupListDialog) -> None:
        selected = QFileDialog.getOpenFileName(
            dialog,
            _("Importar cópia de segurança"),
            str(Path.home()),
            _("Cópias de segurança (*.zip)"),
        )
        if not selected or not selected[0]:
            return
        zip_path = Path(selected[0])
        self.main_window.settings_page.set_backup_busy(True)
        coordinator = RecoveryCoordinator(self.config.data_dir)

        def work() -> None:
            try:
                coordinator.import_bundle_zip(zip_path)
            except Exception as exc:
                LOGGER.exception("Could not import a backup")
                outcome = _BackupOutcome(kind="import", result=None, error=str(exc))
            else:
                outcome = _BackupOutcome(kind="import", result=zip_path, error=None)
            self.backup_finished.emit(outcome)

        threading.Thread(target=work, name="backup-import", daemon=True).start()

    def _export_backup(self, bundle: BundleInfo) -> None:
        suggested = f"Organizador-backup-{bundle.created_at:%Y-%m-%d}.zip"
        selected = QFileDialog.getSaveFileName(
            self._backup_dialog or self.main_window,
            _("Exportar cópia de segurança"),
            str(Path.home() / suggested),
            _("Cópias de segurança (*.zip)"),
        )
        if not selected or not selected[0]:
            return
        archive_path = Path(selected[0])
        if archive_path.suffix.casefold() != ".zip":
            archive_path = archive_path.with_name(f"{archive_path.name}.zip")
        self.main_window.settings_page.set_backup_busy(True)
        coordinator = RecoveryCoordinator(self.config.data_dir)

        def work() -> None:
            try:
                archive = coordinator.export_bundle_zip(bundle.path, archive_path)
            except Exception as exc:
                LOGGER.exception("Could not export a backup")
                outcome = _BackupOutcome(kind="export", result=None, error=str(exc))
            else:
                outcome = _BackupOutcome(kind="export", result=archive, error=None)
            self.backup_finished.emit(outcome)

        threading.Thread(target=work, name="backup-export", daemon=True).start()

    def _delete_backup(self, bundle: BundleInfo, dialog: BackupListDialog) -> None:
        answer = QMessageBox.question(
            dialog,
            _("Remover cópia"),
            _("Remover a cópia de {when}? Esta ação não pode ser desfeita.").format(
                when=bundle.created_at.astimezone().strftime("%d/%m/%Y %H:%M")
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            RecoveryCoordinator(self.config.data_dir).delete_bundle(bundle.path)
        except Exception as exc:
            LOGGER.exception("Could not delete a backup")
            QMessageBox.warning(self.main_window, _("Não foi possível remover"), str(exc))
            return
        dialog.set_bundles(self._list_bundles())
        self._refresh_backup_page()

    def _request_restore(self, bundle: BundleInfo) -> None:
        if self._shutting_down or self._update_installing or self._pending_transfers:
            QMessageBox.warning(
                self.main_window,
                _("Não foi possível restaurar"),
                _("Espera que as operações de ficheiros terminem antes de restaurar."),
            )
            return
        answer = QMessageBox.question(
            self.main_window,
            _("Restaurar cópia de segurança"),
            _(
                "Os dados atuais serão substituídos pela cópia de {when} e a app vai "
                "reiniciar. Os teus documentos não são alterados. Continuar?"
            ).format(when=bundle.created_at.astimezone().strftime("%d/%m/%Y %H:%M")),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            RecoveryCoordinator(self.config.data_dir).request_restore(bundle.path)
        except Exception as exc:
            LOGGER.exception("Could not stage a restore")
            QMessageBox.warning(self.main_window, _("Não foi possível restaurar"), str(exc))
            return
        if self._backup_dialog is not None:
            self._backup_dialog.accept()
        self._relaunch_for_restore()

    def _relaunch_for_restore(self) -> None:
        """Reopen the app once this process exits so the staged restore applies."""

        if not updater.is_frozen() or os.name != "nt":
            QMessageBox.information(
                self.main_window,
                _("Restaurar cópia de segurança"),
                _("Fecha e reabre o Organizador para concluir a reposição."),
            )
            self.shutdown()
            return
        executable = Path(sys.executable)
        command = (
            "Wait-Process -Id {pid} -ErrorAction SilentlyContinue; Start-Process -FilePath '{exe}'"
        ).format(pid=os.getpid(), exe=str(executable).replace("'", "''"))
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError:
            LOGGER.exception("Could not schedule the relaunch after a restore")
            QMessageBox.information(
                self.main_window,
                _("Restaurar cópia de segurança"),
                _("Fecha e reabre o Organizador para concluir a reposição."),
            )
        self.shutdown()

    def _finish_backup(self, outcome: object) -> None:
        if not isinstance(outcome, _BackupOutcome):
            LOGGER.error("Ignoring malformed backup outcome")
            return
        page = self.main_window.settings_page
        page.set_backup_busy(False)
        if outcome.error is not None:
            page.set_backup_status(
                _("Não foi possível concluir a cópia: {error}").format(error=outcome.error),
                error=True,
            )
            return
        if outcome.kind == "import" and self._backup_dialog is not None:
            self._backup_dialog.set_bundles(self._list_bundles())
        self._refresh_backup_page()
        if outcome.kind == "import":
            page.set_backup_status(_("Cópia importada. Escolhe-a na lista para restaurar."))
        elif outcome.kind == "export":
            page.set_backup_status(
                _("Cópia exportada: {name}").format(name=Path(str(outcome.result)).name)
            )
        elif outcome.result is not None and Path(str(outcome.result)).suffix.casefold() == ".zip":
            page.set_backup_status(
                _("Cópia criada e exportada: {name}").format(name=Path(str(outcome.result)).name)
            )
        else:
            page.set_backup_status(_("Cópia de segurança criada."))

    def _set_paused(self, paused: bool) -> None:
        if self._return_in_flight:
            self.tray.set_paused(True)
            return
        if self.watcher is not None and self.watcher.running:
            self.watcher.set_paused(paused)
        else:
            paused = False
        self.tray.set_paused(paused)
        self._refresh()

    def _refresh(self) -> None:
        watching = self.watcher is not None and self.watcher.running
        paused = self.watcher.paused if watching and self.watcher is not None else False
        self.main_window.refresh_all(watching=watching, paused=paused)
        self.tray.update_inbox_count(self.database.count_inbox_items())
        self.tray.set_paused(paused)

    def _handle_legacy_rollback_bridge(self) -> None:
        """Retain a pre-v0.6.2 rollback folder until a later healthy launch."""

        app_dir = updater.app_directory()
        if app_dir is None:
            return
        legacy = app_dir.parent / "Organizador.old"
        if not legacy.is_dir():
            return
        marker = self.config.data_dir / "updates" / "legacy-rollback-retained"
        try:
            if marker.is_file():
                marker.unlink()
                threading.Thread(
                    target=updater.cleanup_previous_version,
                    args=(app_dir,),
                    name="update-cleanup",
                    daemon=True,
                ).start()
            else:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text("retained\n", encoding="utf-8")
                LOGGER.info("Retaining legacy rollback folder %s until a later launch", legacy)
        except OSError:
            LOGGER.exception("Could not handle the legacy rollback folder %s", legacy)

    def _update_result_version(self, result: updater.UpdateResult) -> str:
        """Return a best-effort version label for a persisted update result."""

        transaction_id = result.transaction_id
        if len(transaction_id) != 32 or not transaction_id.isalnum():
            return ""
        manifest_path = (
            updater.updates_directory(self.config.data_dir) / transaction_id / "transaction.json"
        )
        try:
            transaction = updater.read_update_transaction(manifest_path)
        except (OSError, updater.UpdaterError, ValueError):
            return ""
        return ".".join(str(part) for part in transaction.version)

    def _show_pending_update_result(self) -> None:
        """Display persisted update outcomes once, then mark them seen."""

        try:
            results = updater.scan_unseen_update_results(self.config.data_dir)
        except OSError:
            LOGGER.exception("Could not scan persisted update results")
            return
        for result in results:
            version = self._update_result_version(result)
            if result.status is updater.UpdateResultStatus.SUCCEEDED:
                title = _("Atualização instalada")
                if version:
                    message = _("Atualização {version} instalada com sucesso.").format(
                        version=version
                    )
                else:
                    message = _("Atualização instalada com sucesso.")
                icon = QSystemTrayIcon.MessageIcon.Information
                box = QMessageBox.Icon.Information
            elif result.status is updater.UpdateResultStatus.ROLLED_BACK:
                title = _("Atualização revertida")
                if version:
                    message = _(
                        "A atualização {version} falhou e a versão anterior foi restaurada."
                    ).format(version=version)
                else:
                    message = _("A atualização falhou e a versão anterior foi restaurada.")
                icon = QSystemTrayIcon.MessageIcon.Warning
                box = QMessageBox.Icon.Warning
            else:
                title = _("Atualização falhou")
                message = _("A atualização falhou e a reposição automática não foi concluída.")
                if (
                    result.status is updater.UpdateResultStatus.FAILED_AFTER_COMMIT
                    and result.rollback_dir.is_dir()
                ):
                    message += " " + _("A versão anterior foi mantida em: {path}.").format(
                        path=result.rollback_dir
                    )
                icon = QSystemTrayIcon.MessageIcon.Critical
                box = QMessageBox.Icon.Critical
            if self.tray.available:
                self.tray.notify(title, message, icon=icon)
            elif box is QMessageBox.Icon.Information:
                QMessageBox.information(self.main_window, title, message)
            elif box is QMessageBox.Icon.Warning:
                QMessageBox.warning(self.main_window, title, message)
            else:
                QMessageBox.critical(self.main_window, title, message)
            try:
                updater.mark_scanned_update_result_seen(self.config.data_dir, result.transaction_id)
            except (OSError, ValueError, updater.UpdaterError):
                LOGGER.exception("Could not mark update result %s as seen", result.transaction_id)

    def _pending_version_text(self) -> str | None:
        """Return the pending update version label, if one is stored."""

        if self._pending_update is None:
            return None
        return ".".join(str(part) for part in self._pending_update.version)

    def _begin_update_check(self, *, automatic: bool) -> None:
        """Check for a newer release in a background thread."""

        if self._update_installing or self._update_checking:
            return
        if not updater.is_frozen():
            if not automatic:
                self.tray.notify(
                    _("Sem atualizações nesta instalação"),
                    _(
                        "A app está a correr em modo de desenvolvimento; "
                        "as atualizações aplicam-se apenas à versão instalada."
                    ),
                )
            return
        self._update_checking = True
        self._update_check_generation += 1
        generation = self._update_check_generation
        self.tray.set_update_state(checking=True, version=self._pending_version_text())

        def run() -> None:
            try:
                result: UpdateCheckResult = updater.check_latest_release()
            except Exception as exc:
                LOGGER.exception("Update check failed")
                result = UpdateCheckResult(
                    updater.UpdateCheckStatus.ERROR, error=str(exc) or type(exc).__name__
                )
            self.update_check_finished.emit(result, automatic, generation)

        threading.Thread(target=run, name="update-check", daemon=True).start()

    def _on_update_check_finished(self, result: object, automatic: bool, generation: int) -> None:
        if generation != self._update_check_generation:
            LOGGER.debug("Ignoring stale update check result")
            return
        self._update_checking = False
        if not isinstance(result, UpdateCheckResult):
            LOGGER.error("Ignoring malformed update check result")
            self.tray.set_update_state(version=self._pending_version_text())
            return
        if result.status is updater.UpdateCheckStatus.ERROR:
            self.tray.set_update_state(version=self._pending_version_text())
            if automatic:
                LOGGER.warning("Automatic update check failed: %s", result.error)
                return
            self.tray.notify(
                _("Não foi possível procurar atualizações."),
                result.error or _("Não foi possível instalar a atualização."),
                icon=QSystemTrayIcon.MessageIcon.Warning,
            )
            return
        if result.status is updater.UpdateCheckStatus.NO_UPDATE:
            self._pending_update = None
            self.tray.set_update_state(version=None)
            if not automatic:
                self.tray.notify(
                    _("Sem atualizações"),
                    _("O Organizador está atualizado."),
                )
            return
        info = result.update
        if info is None:  # pragma: no cover - guarded by the result type
            self.tray.set_update_state(version=self._pending_version_text())
            return
        self._pending_update = info
        version = ".".join(str(part) for part in info.version)
        self.tray.set_update_state(version=version)
        self.tray.notify(
            _("Atualização disponível"),
            _(
                "Organizador {version} está disponível. Escolhe "
                "“Instalar atualização” no menu do tabuleiro."
            ).format(version=version),
        )

    def _install_pending_update(self) -> None:
        if self._pending_transfers or self._manual_import_active or self._shutting_down:
            self.tray.notify(
                _("Atualização em espera"),
                _("Espera que as operações de ficheiros terminem antes de atualizar."),
            )
            return
        info = self._pending_update
        if info is None or self._update_installing or self._update_checking:
            return
        app_dir = updater.app_directory()
        if app_dir is None:
            self.tray.notify(
                _("Atualização falhou"),
                _("A atualização só se aplica à versão instalada."),
                icon=QSystemTrayIcon.MessageIcon.Warning,
            )
            return
        self._update_installing = True
        self._abort_update_install = False
        version = ".".join(str(part) for part in info.version)
        self.tray.set_update_state(installing=True, version=version)
        self.tray.notify(
            _("A instalar atualização…"),
            _("A transferir e a verificar Organizador {version}.").format(version=version),
        )

        def run() -> None:
            transaction: UpdateTransaction | None = None
            try:
                transaction = updater.create_update_transaction(
                    app_dir,
                    info.version,
                    data_dir=self.config.data_dir,
                    old_pid=os.getpid(),
                )
                if self._abort_update_install:
                    raise _UpdateInstallAborted
                zip_path = updater.download_and_verify(
                    info.zip_url, info.sha256_url, transaction.download_dir
                )
                if self._abort_update_install:
                    raise _UpdateInstallAborted
                staging = updater.extract_to_staging(zip_path, transaction.staging_dir)
                if self._abort_update_install:
                    raise _UpdateInstallAborted
                staged_version = updater.read_staged_release_version(staging)
                if staged_version is not None and staged_version != info.version:
                    raise updater.UpdaterError(
                        _("A atualização transferida não corresponde à versão {version}.").format(
                            version=version
                        )
                    )
                updater.write_update_helper(transaction)
            except _UpdateInstallAborted:
                if transaction is not None:
                    updater.abort_update_transaction(transaction)
                self.update_install_finished.emit(None)
                return
            except Exception as exc:
                LOGGER.exception("Update installation failed")
                if transaction is not None:
                    updater.abort_update_transaction(transaction)
                message = (
                    str(exc)
                    if isinstance(exc, updater.UpdaterError)
                    else _("Não foi possível instalar a atualização.")
                )
                self.update_install_finished.emit(message)
                return
            self.update_install_finished.emit(transaction)

        threading.Thread(target=run, name="update-install", daemon=True).start()

    def _on_update_install_finished(self, result: object) -> None:
        if result is None:
            # The worker aborted during shutdown; stay quiet and exit with the app.
            self._update_installing = False
            self._update_transaction = None
            return
        if isinstance(result, UpdateTransaction):
            transaction = result
            self._update_transaction = transaction
            try:
                updater.launch_update_helper(transaction, wait_ready=False)
            except Exception as exc:
                LOGGER.exception("Could not launch the update helper")
                updater.abort_update_transaction(transaction)
                self._update_installing = False
                self._update_transaction = None
                message = (
                    str(exc)
                    if isinstance(exc, updater.UpdaterError)
                    else _("Não foi possível instalar a atualização.")
                )
                self.tray.set_update_state(version=self._pending_version_text())
                self.tray.notify(
                    _("Atualização falhou"),
                    message,
                    icon=QSystemTrayIcon.MessageIcon.Warning,
                )
                self._release_deferred_downloads()
                return
            self._update_restart_armed = True
            self.tray.set_update_state(
                installing=True,
                version=".".join(str(part) for part in transaction.version),
            )
            deadline = time.monotonic() + transaction.ready_timeout_seconds
            self._wait_for_helper_ready(transaction, deadline)
            return
        self._update_installing = False
        message = (
            str(result)
            if isinstance(result, str) and result
            else _("Não foi possível instalar a atualização.")
        )
        self.tray.set_update_state(version=self._pending_version_text())
        self.tray.notify(
            _("Atualização falhou"),
            message,
            icon=QSystemTrayIcon.MessageIcon.Warning,
        )
        self._release_deferred_downloads()

    def _wait_for_helper_ready(self, transaction: UpdateTransaction, deadline: float) -> None:
        """Restart once the helper supervises, or abort the handoff on timeout."""

        if updater.helper_ready_received(transaction):
            self.tray.notify(
                _("Atualização pronta"),
                _("A reiniciar para aplicar a atualização…"),
            )
            self.shutdown()
            return
        if time.monotonic() >= deadline:
            LOGGER.error("Update helper did not become ready; aborting the handoff")
            updater.abort_update_transaction(transaction)
            self._update_installing = False
            self._update_restart_armed = False
            self._update_transaction = None
            self.tray.set_update_state(version=self._pending_version_text())
            self.tray.notify(
                _("Atualização falhou"),
                _("Não foi possível iniciar o assistente de atualização."),
                icon=QSystemTrayIcon.MessageIcon.Warning,
            )
            self._release_deferred_downloads()
            return
        QTimer.singleShot(150, lambda: self._wait_for_helper_ready(transaction, deadline))

    def run_update_handshake(
        self,
        transaction: UpdateTransaction,
        recovery_bundle: RecoveryBundle | None,
        coordinator: RecoveryCoordinator,
        state: StartupState,
        *,
        background: bool,
        commit_timeout_seconds: float = 60.0,
    ) -> None:
        """Drive the ready/commit/healthy protocol from the running event loop."""

        try:
            updater.validate_update_target(
                transaction.manifest_path,
                transaction.token,
                data_dir=self.config.data_dir,
            )
        except updater.UpdaterError as exc:
            LOGGER.error("Update target validation failed: %s", exc)
            QMessageBox.critical(
                self.main_window,
                _("Atualização inválida"),
                _("A atualização não corresponde a esta instalação. Nenhum ficheiro foi alterado."),
            )
            QApplication.exit(1)
            return
        updater.mark_update_ready(transaction.manifest_path, transaction.token)
        self._poll_update_commit(
            transaction,
            recovery_bundle,
            coordinator,
            state,
            background=background,
            deadline=time.monotonic() + commit_timeout_seconds,
        )

    def _poll_update_commit(
        self,
        transaction: UpdateTransaction,
        recovery_bundle: RecoveryBundle | None,
        coordinator: RecoveryCoordinator,
        state: StartupState,
        *,
        background: bool,
        deadline: float,
    ) -> None:
        """Activate after the helper commits, or continue alone when it never does."""

        if updater.update_commit_received(transaction) or time.monotonic() >= deadline:
            if not updater.update_commit_received(transaction):
                LOGGER.warning("Update commit marker never arrived; continuing startup alone")
            self._commit_update_handshake(
                transaction, recovery_bundle, coordinator, state, background=background
            )
            return
        QTimer.singleShot(
            100,
            lambda: self._poll_update_commit(
                transaction,
                recovery_bundle,
                coordinator,
                state,
                background=background,
                deadline=deadline,
            ),
        )

    def _commit_update_handshake(
        self,
        transaction: UpdateTransaction,
        recovery_bundle: RecoveryBundle | None,
        coordinator: RecoveryCoordinator,
        state: StartupState,
        *,
        background: bool,
    ) -> None:
        """Activate, validate the migration, acknowledge health, then close data rollback."""

        try:
            self.activate(state, background=background)
        except Exception:
            LOGGER.exception("Updated application failed to activate after commit")
            if recovery_bundle is not None:
                with suppress(Exception):
                    coordinator.restore_pending()
            QMessageBox.critical(
                self.main_window,
                _("Não foi possível concluir a atualização"),
                _(
                    "A nova versão não conseguiu arrancar. "
                    "Foi tentada a reposição da cópia de segurança."
                ),
            )
            QApplication.exit(1)
            return
        if recovery_bundle is not None:
            # Validate while the helper can still roll the binary back, so a
            # data failure never leaves the two rollback decisions misaligned.
            try:
                coordinator.validate_migrated(recovery_bundle)
            except Exception:
                LOGGER.exception("Migrated data failed validation before acknowledgement")
                with suppress(Exception):
                    coordinator.restore_pending()
                QMessageBox.critical(
                    self.main_window,
                    _("Não foi possível concluir a atualização"),
                    _(
                        "Os dados migrados não puderam ser validados. "
                        "A versão anterior foi mantida para recuperação manual."
                    ),
                )
                QApplication.exit(1)
                return
        try:
            updater.mark_update_healthy(transaction.manifest_path, transaction.token)
        except Exception:
            # The helper still owns the binary rollback; keep the data
            # rollback possible so both decisions stay aligned.
            LOGGER.exception("Could not acknowledge update health to the helper")
            if recovery_bundle is not None:
                with suppress(Exception):
                    coordinator.restore_pending()
            QApplication.exit(1)
            return
        if recovery_bundle is not None:
            try:
                coordinator.mark_healthy(recovery_bundle)
            except Exception:
                # The binary stays; startup recovery restores the pending
                # data backup and migrates again on the next launch.
                LOGGER.exception("Could not close the migration rollback window")
                QApplication.exit(1)
                return

    def _check_deadlines(self) -> None:
        today = date.today()
        for task in self.database.list_tasks(include_completed=False):
            if task.due_date is None or task.last_notified_on == today:
                continue
            lead = (
                task.reminder_lead_days
                if task.reminder_lead_days is not None
                else self.config.reminder_lead_days
            )
            delta = (task.due_date - today).days
            if delta > lead:
                continue
            subject = task.subject_name or _("Tarefa geral")
            self.tray.notify(
                subject,
                _("{title} {when}.").format(title=task.title, when=_deadline_copy(delta)),
            )
            self.database.mark_task_notified(task.id, today)

    def _index_finished(self, file_id: int, error: str) -> None:
        if error:
            LOGGER.warning("Indexing failed for file %s: %s", file_id, error)
        dialog = self._subject_files_dialog
        if dialog is not None:
            dialog.set_documents(self.database.list_subject_files(dialog.subject.id))
        self.indexer.submit_pending()
        if self.main_window.search_page.search_edit.text().strip():
            self.main_window.search_page.search()

    def _hidden_to_tray(self) -> None:
        if self.hide_notice_shown:
            return
        self.hide_notice_shown = True
        self.tray.notify(
            _("Organizador continua ativo"),
            _("A janela fechou, mas Downloads continua a ser vigiado no tabuleiro do sistema."),
        )

    def _open_path(self, value: Path | str) -> None:
        path = Path(value)
        if not path.exists():
            QMessageBox.warning(
                self.main_window,
                _("Caminho não encontrado"),
                _("Não foi possível encontrar:\n{path}").format(path=path),
            )
            return
        try:
            os.startfile(path)
        except OSError as exc:
            QMessageBox.warning(self.main_window, _("Não foi possível abrir"), str(exc))

    def _reveal_path(self, value: Path | str) -> None:
        path = Path(value)
        if not path.exists():
            self._open_path(path)
            return
        try:
            subprocess.Popen(["explorer.exe", "/select,", str(path)])
        except OSError as exc:
            QMessageBox.warning(self.main_window, _("Não foi possível mostrar"), str(exc))
