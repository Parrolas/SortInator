"""Main application pages for the Operate-mode desktop surface."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TypedDict, cast

from PySide6.QtCore import QDate, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QResizeEvent, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from organizador import __version__
from organizador.config import THEME_IDS, AppConfig
from organizador.db import Database
from organizador.i18n import LANGUAGE_NAMES, _
from organizador.models import (
    FILE_KINDS,
    FiledDocument,
    FindingReason,
    InboxItem,
    ReconciliationFinding,
    ReconciliationReport,
    StudyTask,
    Subject,
)
from organizador.reconcile import DISMISSIBLE_FINDING_REASONS, visible_findings
from organizador.recovery import USER_MARKER, BundleInfo
from organizador.ui import theme as ui_theme
from organizador.ui.dialogs import TaskDialog
from organizador.ui.widgets import (
    ElidedLabel,
    EmptyState,
    PageHeading,
    PathActionRow,
    ToggleSwitch,
    WheelRedirector,
    button,
    clear_layout,
    format_day,
    format_size,
    hairline,
    label,
)


class SettingsPayload(TypedDict):
    """Validated value types emitted by the settings page."""

    university_root: Path
    downloads_dir: Path
    extensions: str
    minimum_file_size: int
    prompt_timeout_seconds: int
    prompt_timeout_enabled: bool
    reminder_lead_days: int
    filename_template: str
    theme: str
    language: str
    check_updates_on_launch: bool
    ocr_enabled: bool
    quiet_intake: bool
    watch_enabled: bool
    launch_at_login: bool


def _page_layout(widget: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(34, 28, 34, 30)
    layout.setSpacing(22)
    return layout


def _scroll_list() -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 4, 0)
    layout.setSpacing(9)
    area.setWidget(content)
    return area, content, layout


class HomePage(QWidget):
    """At-a-glance inbox and next-deadline view."""

    open_path = Signal(object)
    open_university = Signal()
    show_inbox = Signal()
    show_search = Signal()

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        page = QVBoxLayout(self)
        page.setContentsMargins(0, 0, 0, 0)
        self.body_area = QScrollArea()
        self.body_area.setWidgetResizable(True)
        self.body_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # The lists below are capped so the page fits on screen; the hidden
        # scroll bar is only a fallback for unusual scaling, never visible.
        self.body_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_area.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = _page_layout(body)
        open_button = button(_("Abrir pasta Universidade"))
        open_button.clicked.connect(self.open_university)
        layout.addWidget(
            PageHeading(
                _("O teu semestre, arrumado."),
                _("Os downloads novos aparecem aqui antes de irem para uma disciplina."),
                [open_button],
            )
        )

        self.intake_strip = QFrame()
        self.intake_strip.setObjectName("IntakeStrip")
        intake_layout = QHBoxLayout(self.intake_strip)
        intake_layout.setContentsMargins(18, 13, 14, 13)
        self.watch_label = label(_("A preparar a vigilância de Downloads…"), "RowTitle")
        self.inbox_button = button(_("Caixa de Entrada"), variant="quiet")
        self.inbox_button.clicked.connect(self.show_inbox)
        intake_layout.addWidget(self.watch_label, 1)
        intake_layout.addWidget(self.inbox_button)
        layout.addWidget(self.intake_strip)

        columns = QGridLayout()
        columns.setHorizontalSpacing(16)
        columns.setColumnStretch(0, 3)
        columns.setColumnStretch(1, 2)

        recent_panel = QFrame()
        recent_panel_layout = QVBoxLayout(recent_panel)
        recent_panel_layout.setContentsMargins(0, 7, 8, 0)
        recent_panel_layout.setSpacing(11)
        recent_header = QHBoxLayout()
        recent_header.setContentsMargins(0, 0, 0, 0)
        recent_header.setSpacing(8)
        recent_header.addWidget(label(_("Organizados recentemente"), "SectionTitle"), 1)
        self.search_link = button(_("Ver na pesquisa"), variant="quiet")
        self.search_link.clicked.connect(self.show_search.emit)
        recent_header.addWidget(self.search_link)
        recent_panel_layout.addLayout(recent_header)
        self.recent_layout = QVBoxLayout()
        self.recent_layout.setSpacing(8)
        recent_panel_layout.addLayout(self.recent_layout)
        recent_panel_layout.addStretch(1)
        columns.addWidget(recent_panel, 0, 0)

        task_panel = QFrame()
        task_panel_layout = QVBoxLayout(task_panel)
        task_panel_layout.setContentsMargins(8, 7, 0, 0)
        task_panel_layout.setSpacing(11)
        task_panel_layout.addWidget(label(_("Próximos prazos"), "SectionTitle"))
        self.deadline_layout = QVBoxLayout()
        self.deadline_layout.setSpacing(8)
        task_panel_layout.addLayout(self.deadline_layout)
        task_panel_layout.addStretch(1)
        columns.addWidget(task_panel, 0, 1)

        activity_panel = QFrame()
        activity_panel.setObjectName("Panel")
        activity_layout = QVBoxLayout(activity_panel)
        activity_layout.setContentsMargins(18, 14, 18, 16)
        activity_layout.setSpacing(8)
        activity_layout.addWidget(label(_("Tranquilidade"), "SectionTitle"))
        self.activity_label = label("", "Muted")
        self.activity_label.setWordWrap(True)
        activity_layout.addWidget(self.activity_label)
        columns.addWidget(activity_panel, 1, 0, 1, 2)
        columns.setRowStretch(0, 1)
        layout.addLayout(columns, 1)
        self.body_area.setWidget(body)
        page.addWidget(self.body_area)

    def refresh(self, *, watching: bool, paused: bool) -> None:
        """Refresh the operational summary."""

        inbox_count = self.database.count_inbox_items()
        if paused:
            self.watch_label.setText(_("Vigilância em pausa. Os novos downloads ficam onde estão."))
            self.intake_strip.setObjectName("WarningStrip")
        elif watching:
            self.watch_label.setText(
                _("Downloads vigiado. Só os formatos de estudo configurados entram.")
            )
            self.intake_strip.setObjectName("IntakeStrip")
        else:
            self.watch_label.setText(_("A vigilância de Downloads está desligada nas Definições."))
            self.intake_strip.setObjectName("WarningStrip")
        self.intake_strip.style().unpolish(self.intake_strip)
        self.intake_strip.style().polish(self.intake_strip)
        self.inbox_button.setText(
            _("Caixa de Entrada ({count})").format(count=inbox_count)
            if inbox_count
            else _("Caixa de Entrada")
        )

        clear_layout(self.recent_layout)
        recent = self.database.list_recent_files(limit=5)
        if not recent:
            empty_copy = label(
                _(
                    "O primeiro documento organizado aparece aqui. "
                    "A app não toca nos ficheiros antigos sem pedires."
                ),
                "Muted",
            )
            empty_copy.setWordWrap(True)
            self.recent_layout.addWidget(empty_copy)
        else:
            for document in recent:
                recent_subject = self.database.get_subject(document.subject_id)
                detail = _("{subject}  ·  {kind}  ·  {size}").format(
                    subject=recent_subject.name if recent_subject else _("Disciplina"),
                    kind=document.kind,
                    size=format_size(document.size),
                )
                self.recent_layout.addWidget(
                    PathActionRow(
                        document.current_path.name,
                        detail,
                        document.current_path,
                        lambda path: self.open_path.emit(path),
                    )
                )

        clear_layout(self.deadline_layout)
        tasks = self.database.list_tasks(include_completed=False)[:5]
        if not tasks:
            empty_copy = label(
                _(
                    "Ainda não há prazos. Cria uma tarefa ou associa-a "
                    "quando organizares um ficheiro."
                ),
                "Muted",
            )
            empty_copy.setWordWrap(True)
            self.deadline_layout.addWidget(empty_copy)
        else:
            for task in tasks:
                row = QFrame()
                row.setObjectName("ListRow")
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(13, 10, 13, 10)
                row_layout.setSpacing(2)
                title = label(task.title, "RowTitle")
                title.setWordWrap(True)
                row_layout.addWidget(title)
                task_subject = task.subject_name or _("Geral")
                row_layout.addWidget(
                    label(
                        _("{subject}  ·  {due}").format(
                            subject=task_subject, due=format_day(task.due_date)
                        ),
                        "Muted",
                    )
                )
                self.deadline_layout.addWidget(row)
        self._refresh_activity()

    def _refresh_activity(self) -> None:
        """Show the lifetime safety record as simple, honest counts."""

        summary = self.database.activity_summary()
        parts: list[str] = []
        if summary.organized:
            parts.append(
                _("{count} ficheiro organizado").format(count=summary.organized)
                if summary.organized == 1
                else _("{count} ficheiros organizados").format(count=summary.organized)
            )
        if summary.collisions_renamed:
            count = summary.collisions_renamed
            parts.append(
                _("{count} colisão de nomes resolvida sem substituir nada").format(count=count)
                if count == 1
                else _("{count} colisões de nomes resolvidas sem substituir nada").format(
                    count=count
                )
            )
        if summary.operations_recovered:
            count = summary.operations_recovered
            parts.append(
                _("{count} operação interrompida recuperada").format(count=count)
                if count == 1
                else _("{count} operações interrompidas recuperadas").format(count=count)
            )
        if summary.adopted:
            parts.append(
                _("{count} ficheiro adotado sem mover").format(count=summary.adopted)
                if summary.adopted == 1
                else _("{count} ficheiros adotados sem mover").format(count=summary.adopted)
            )
        if summary.undone:
            count = summary.undone
            parts.append(
                _("{count} organização desfeita").format(count=count)
                if count == 1
                else _("{count} organizações desfeitas").format(count=count)
            )
        if summary.returned:
            count = summary.returned
            parts.append(
                _("{count} devolução a Downloads").format(count=count)
                if count == 1
                else _("{count} devoluções a Downloads").format(count=count)
            )
        if parts:
            self.activity_label.setText(" · ".join(parts) + ".")
        else:
            self.activity_label.setText(
                _("A app ainda não tem histórico. Organiza o primeiro ficheiro para começar.")
            )


class InboxPage(QWidget):
    """Review every file that still needs a destination."""

    organise_requested = Signal(int)
    return_requested = Signal(int)
    open_path = Signal(object)
    import_existing_requested = Signal()
    adopt_requested = Signal(object)
    drop_record_requested = Signal(object)
    dismiss_finding_requested = Signal(object)
    unregister_requested = Signal(int)
    organise_selection_requested = Signal(object)

    def __init__(
        self,
        database: Database,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.config = config
        self.reconciliation_report: ReconciliationReport | None = None
        self._selected_ids: set[int] = set()
        layout = _page_layout(self)
        self.import_button = button("Importar de Downloads…")
        self.import_button.clicked.connect(self.import_existing_requested.emit)
        self.bulk_button = button(_("Organizar seleção"), variant="primary")
        self.bulk_button.setEnabled(False)
        self.bulk_button.clicked.connect(self._emit_selection)
        layout.addWidget(
            PageHeading(
                _("Caixa de Entrada"),
                _("Nada é arquivado sem uma decisão. Organiza agora ou deixa para mais tarde."),
                [self.import_button, self.bulk_button],
            )
        )
        self.summary_label = label("", "PageSubtitle")
        layout.addWidget(self.summary_label)
        self.import_status_label = label("", "Muted")
        self.import_status_label.setWordWrap(True)
        self.import_status_label.hide()
        layout.addWidget(self.import_status_label)
        area, _container, self.items_layout = _scroll_list()
        layout.addWidget(area, 1)

    def set_import_running(self, running: bool) -> None:
        """Prevent overlapping confirmed batches while the worker checks files."""

        self.import_button.setEnabled(not running)
        self.import_button.setText(_("A importar…") if running else _("Importar de Downloads…"))

    def _emit_selection(self) -> None:
        if self._selected_ids:
            self.organise_selection_requested.emit(tuple(sorted(self._selected_ids)))

    def _set_selected(self, item_id: int, selected: bool) -> None:
        if selected:
            self._selected_ids.add(item_id)
        else:
            self._selected_ids.discard(item_id)
        self._update_bulk_button()

    def _update_bulk_button(self) -> None:
        count = len(self._selected_ids)
        self.bulk_button.setText(
            _("Organizar seleção ({count})").format(count=count)
            if count
            else _("Organizar seleção")
        )
        self.bulk_button.setEnabled(count > 0 and self.database.count_subjects() > 0)

    def set_import_status(self, message: str) -> None:
        """Show non-modal progress or aggregate batch feedback."""

        self.import_status_label.setText(message)
        self.import_status_label.setVisible(bool(message))

    def set_reconciliation_report(self, report: ReconciliationReport) -> None:
        """Retain unresolved startup findings for safe, path-specific review."""

        self.reconciliation_report = report

    def refresh(self) -> None:
        """Rebuild the pending-file list."""

        items = self.database.list_inbox_items()
        adopted_documents = self.database.list_adopted_files()
        recovery_count = sum(item.status == "recovery" for item in items)
        pending_count = len(items) - recovery_count
        manual_findings = self._manual_findings()
        summary_parts: list[str] = []
        if pending_count and recovery_count:
            summary_parts.append(
                (
                    _("{count} ficheiros por decidir · {recovery} precisam de recuperação")
                    if pending_count != 1
                    else _("{count} ficheiro por decidir · {recovery} precisam de recuperação")
                ).format(count=pending_count, recovery=recovery_count)
            )
        elif recovery_count:
            summary_parts.append(
                _("{count} ficheiros precisam de recuperação manual").format(count=recovery_count)
                if recovery_count != 1
                else _("{count} ficheiro precisa de recuperação manual").format(
                    count=recovery_count
                )
            )
        elif pending_count:
            summary_parts.append(
                _("{count} ficheiros por decidir").format(count=pending_count)
                if pending_count != 1
                else _("{count} ficheiro por decidir").format(count=pending_count)
            )
        if manual_findings:
            count = len(manual_findings)
            summary_parts.append(
                _("{count} ocorrências do histórico precisam de revisão").format(count=count)
                if count != 1
                else _("{count} ocorrência do histórico precisa de revisão").format(count=count)
            )
        report = self.reconciliation_report
        if report is not None and (report.incomplete or report.truncated):
            summary_parts.append(_("verificação incompleta"))
        summary = " · ".join(summary_parts) if summary_parts else _("A caixa está vazia")
        self.summary_label.setText(summary)
        self._selected_ids &= {item.id for item in items}
        self._update_bulk_button()
        clear_layout(self.items_layout)
        if not items and not manual_findings:
            empty = EmptyState(
                _("Tudo no lugar"),
                _("Quando terminares um download elegível, ele aparece aqui e num pequeno popup."),
            )
            self.items_layout.addWidget(empty)
        subjects = {subject.id: subject for subject in self.database.list_subjects()}
        for item in items:
            self.items_layout.addWidget(self._row(item, subjects))
        if manual_findings:
            self.items_layout.addWidget(label(_("Revisão manual do histórico"), "SectionTitle"))
            for finding in manual_findings:
                self.items_layout.addWidget(self._finding_row(finding))
        if adopted_documents:
            self.items_layout.addWidget(label(_("Ficheiros adotados"), "SectionTitle"))
            for document in adopted_documents:
                self.items_layout.addWidget(self._adopted_row(document, subjects))
        self.items_layout.addStretch(1)

    def _row(self, item: InboxItem, subjects: dict[int, Subject]) -> QFrame:
        row = QFrame()
        row.setObjectName("ListRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(17, 13, 13, 13)
        row_layout.setSpacing(14)

        if item.status != "recovery":
            selected = QCheckBox()
            selected.setAccessibleName(_("Selecionar {name}").format(name=item.original_name))
            selected.setChecked(item.id in self._selected_ids)
            selected.toggled.connect(
                lambda checked, item_id=item.id: self._set_selected(item_id, checked)
            )
            row_layout.addWidget(selected)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = ElidedLabel(item.original_name, "RowTitle")
        copy.addWidget(title)
        if item.status == "recovery":
            metadata = _("Recuperação manual necessária  ·  {size}  ·  {when}").format(
                size=format_size(item.size),
                when=item.detected_at.strftime("%d/%m às %H:%M"),
            )
        else:
            subject = subjects.get(item.suggested_subject_id or -1)
            suggestion = subject.name if subject else _("Sem sugestão")
            metadata = _("{size}  ·  {when}  ·  Sugestão: {suggestion} / {kind}").format(
                size=format_size(item.size),
                when=item.detected_at.strftime("%d/%m às %H:%M"),
                suggestion=suggestion,
                kind=item.suggested_kind,
            )
        copy.addWidget(ElidedLabel(metadata, "Muted"))
        if item.last_error:
            error = label(item.last_error, "ErrorText")
            error.setWordWrap(True)
            copy.addWidget(error)
        row_layout.addLayout(copy, 1)

        open_button = button(
            _("Abrir Universidade") if item.status == "recovery" else _("Abrir"),
            variant="quiet",
        )
        open_path = self.config.university_root if item.status == "recovery" else item.path
        open_button.clicked.connect(lambda: self.open_path.emit(open_path))
        row_layout.addWidget(open_button)
        if item.status == "recovery":
            downloads_button = button(_("Abrir Downloads"))
            downloads_button.clicked.connect(lambda: self.open_path.emit(self.config.downloads_dir))
            row_layout.addWidget(downloads_button)
            return row
        return_button = button(_("Não é da universidade"))
        return_button.setToolTip(_("Devolver este ficheiro a Downloads"))
        return_button.clicked.connect(lambda: self.return_requested.emit(item.id))
        organise = button(_("Organizar"), variant="primary")
        organise.clicked.connect(lambda: self.organise_requested.emit(item.id))
        row_layout.addWidget(return_button)
        row_layout.addWidget(organise)
        return row

    def _manual_findings(self) -> tuple[ReconciliationFinding, ...]:
        report = self.reconciliation_report
        if report is None:
            return ()
        return visible_findings(self.database, report)

    def _finding_row(self, finding: ReconciliationFinding) -> QFrame:
        path = finding.path
        details = {
            FindingReason.PENDING_INGEST_SOURCE: _(
                "Download com recolha interrompida; o original foi mantido para revisão."
            ),
            FindingReason.PENDING_INGEST_DESTINATION: _(
                "Cópia por verificar; pode estar incompleta. Compara com o original em Downloads."
            ),
            FindingReason.PENDING_VERSION_SOURCE: _(
                "Renomeação de versão interrompida; o original foi mantido para revisão."
            ),
            FindingReason.PENDING_VERSION_DESTINATION: _(
                "Cópia da versão anterior por verificar; compara os ficheiros."
            ),
            FindingReason.PENDING_MOVE_SOURCE: _(
                "Origem de um movimento interrompido; não foi alterada no arranque."
            ),
            FindingReason.PENDING_MOVE_DESTINATION: _(
                "Destino de um movimento interrompido; compara antes de continuar."
            ),
            FindingReason.UNTRACKED_SUBJECT_FILE: _(
                "Encontrado numa disciplina sem registo. Não foi movido nem alterado."
            ),
            FindingReason.MISSING_DOCUMENT: _(
                "Documento registado que já não está no destino esperado."
            ),
            FindingReason.BROKEN_UNDO_EVENT: _(
                "Organização que não pode ser desfeita enquanto o ficheiro estiver em falta."
            ),
            FindingReason.PENDING_FILING_SOURCE: _(
                "Origem de uma organização interrompida; não foi alterada no arranque."
            ),
            FindingReason.PENDING_FILING_DESTINATION: _(
                "Destino de uma organização interrompida; compara antes de continuar."
            ),
            FindingReason.PENDING_RETURN_SOURCE: _(
                "Origem de uma devolução interrompida; não foi alterada no arranque."
            ),
            FindingReason.PENDING_RETURN_DESTINATION: _(
                "Destino em Downloads de uma devolução interrompida; compara os ficheiros."
            ),
            FindingReason.PENDING_UNDO_SOURCE: _(
                "Origem de uma operação de desfazer interrompida; não foi alterada no arranque."
            ),
            FindingReason.PENDING_UNDO_DESTINATION: _(
                "Operação de desfazer interrompida; confirma as pastas antes de continuar."
            ),
            FindingReason.LEGACY_INTERRUPTED_UNDO: _(
                "Ficheiro restaurado por uma operação de desfazer interrompida."
            ),
            FindingReason.UNSAFE_PATH: _(
                "O caminho registado já não é um ficheiro normal. Não foi seguido nem alterado."
            ),
            FindingReason.SUBJECT_FOLDER_COLLISION: _(
                "Duas disciplinas partilham a mesma pasta no Windows. Os documentos "
                "podem misturar-se; arquiva uma delas se for um engano."
            ),
        }
        row = QFrame()
        row.setObjectName("ListRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(17, 13, 13, 13)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        copy.addWidget(label(path.name, "RowTitle"))
        detail_label = label(details[finding.reason], "ErrorText")
        detail_label.setWordWrap(True)
        copy.addWidget(detail_label)
        path_label = label(str(path), "Muted")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy.addWidget(path_label)
        row_layout.addLayout(copy, 1)
        expected_parent = path.parent
        target = expected_parent if expected_parent.is_dir() else self.config.university_root
        open_button = button(_("Abrir pasta"), variant="quiet")
        open_button.clicked.connect(lambda: self.open_path.emit(target))
        row_layout.addWidget(open_button)
        if finding.reason is FindingReason.UNTRACKED_SUBJECT_FILE:
            adopt_button = button(_("Adotar"), variant="primary")
            adopt_button.setToolTip(_("Adicionar à pesquisa sem mover o ficheiro"))
            adopt_button.clicked.connect(lambda: self.adopt_requested.emit(finding))
            row_layout.addWidget(adopt_button)
        elif finding.reason is FindingReason.MISSING_DOCUMENT:
            drop_button = button(_("Remover registo"))
            drop_button.setToolTip(_("Remover apenas o registo local; nenhum ficheiro é apagado"))
            drop_button.clicked.connect(lambda: self.drop_record_requested.emit(finding))
            row_layout.addWidget(drop_button)
        if finding.reason in DISMISSIBLE_FINDING_REASONS:
            dismiss_button = button(_("Marcar revisto"), variant="quiet")
            dismiss_button.clicked.connect(lambda: self.dismiss_finding_requested.emit(finding))
            row_layout.addWidget(dismiss_button)
        return row

    def _adopted_row(
        self,
        document: FiledDocument,
        subjects: dict[int, Subject],
    ) -> QFrame:
        row = QFrame()
        row.setObjectName("ListRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(17, 13, 13, 13)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        copy.addWidget(label(document.current_path.name, "RowTitle"))
        subject = subjects.get(document.subject_id)
        copy.addWidget(
            label(
                _("{subject} · {kind} · adotado sem mover").format(
                    subject=subject.name if subject else _("Disciplina"),
                    kind=document.kind,
                ),
                "Muted",
            )
        )
        row_layout.addLayout(copy, 1)
        open_button = button(_("Abrir"), variant="quiet")
        open_button.clicked.connect(lambda: self.open_path.emit(document.current_path))
        row_layout.addWidget(open_button)
        unregister_button = button(_("Remover do catálogo"))
        unregister_button.clicked.connect(lambda: self.unregister_requested.emit(document.id))
        row_layout.addWidget(unregister_button)
        return row


class SearchPage(QWidget):
    """Full-text search over locally indexed study documents."""

    open_path = Signal(object)
    reveal_path = Signal(object)
    retry_requested = Signal()

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        layout = _page_layout(self)
        layout.addWidget(
            PageHeading(
                _("Pesquisar nos apontamentos"),
                _(
                    "Procura palavras dentro de PDFs, documentos Office, ficheiros de texto "
                    "e notebooks já organizados."
                ),
            )
        )
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            _("Ex.: regra da cadeia, normalização, Revolução Francesa…")
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setAccessibleName(_("Pesquisa nos documentos"))
        layout.addWidget(self.search_edit)
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(10)
        self.subject_combo = QComboBox()
        self.subject_combo.setAccessibleName(_("Filtrar por disciplina"))
        self.kind_combo = QComboBox()
        self.kind_combo.setAccessibleName(_("Filtrar por tipo de documento"))
        self.subject_combo.currentIndexChanged.connect(lambda _index: self.search())
        self.kind_combo.currentIndexChanged.connect(lambda _index: self.search())
        filter_row.addWidget(self.subject_combo, 1)
        filter_row.addWidget(self.kind_combo, 1)
        layout.addLayout(filter_row)
        self.refresh_filters()
        self.index_status_row = QHBoxLayout()
        self.index_status_row.setContentsMargins(0, 0, 0, 0)
        self.index_status_label = label("", "Muted")
        self.index_status_label.setWordWrap(True)
        self.index_status_row.addWidget(self.index_status_label, 1)
        self.retry_button = button(_("Tentar novamente"), variant="quiet")
        self.retry_button.clicked.connect(self.retry_requested)
        self.index_status_row.addWidget(self.retry_button)
        self.index_status_container = QWidget()
        self.index_status_container.setLayout(self.index_status_row)
        layout.addWidget(self.index_status_container)
        self.status_label = label(
            _(
                "A pesquisa é local. PDFs digitalizados só como imagem podem não ter "
                "texto pesquisável."
            ),
            "PageSubtitle",
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        area, _container, self.results_layout = _scroll_list()
        layout.addWidget(area, 1)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(260)
        self.timer.timeout.connect(self.search)
        self.search_edit.textChanged.connect(lambda: self.timer.start())
        self.search_edit.returnPressed.connect(self.search)

    def focus_search(self) -> None:
        """Put the cursor in the search field."""

        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def refresh_filters(self) -> None:
        """Rebuild the filter combos, preserving the current selection."""

        selected_subject, selected_kind = self.selected_filters()
        self.subject_combo.blockSignals(True)
        self.kind_combo.blockSignals(True)
        try:
            self.subject_combo.clear()
            self.subject_combo.addItem(_("Todas as disciplinas"), None)
            for subject in self.database.list_subjects(active_only=False):
                display = f"{subject.name} ({subject.code})" if subject.code else subject.name
                self.subject_combo.addItem(display, subject.id)
            self.kind_combo.clear()
            self.kind_combo.addItem(_("Todos os tipos"), None)
            for kind in FILE_KINDS:
                self.kind_combo.addItem(kind, kind)
            self._select_combo_value(self.subject_combo, selected_subject)
            self._select_combo_value(self.kind_combo, selected_kind)
        finally:
            self.subject_combo.blockSignals(False)
            self.kind_combo.blockSignals(False)

    @staticmethod
    def _select_combo_value(combo: QComboBox, value: object) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def selected_filters(self) -> tuple[int | None, str | None]:
        """Return the selected subject id and document kind, if any."""

        subject_id = self.subject_combo.currentData()
        kind = self.kind_combo.currentData()
        return (
            int(subject_id) if subject_id is not None else None,
            str(kind) if kind is not None else None,
        )

    def refresh_index_status(self) -> None:
        """Show pending/failed index counts and offer a retry when useful."""

        pending, failed, _active = self.database.index_summary()
        parts: list[str] = []
        if pending:
            parts.append(
                _("{count} documentos por indexar").format(count=pending)
                if pending != 1
                else _("1 documento por indexar")
            )
        if failed:
            parts.append(
                _("{count} documentos com falha na indexação").format(count=failed)
                if failed != 1
                else _("1 documento com falha na indexação")
            )
        self.index_status_container.setVisible(bool(parts))
        self.retry_button.setVisible(failed > 0)
        if parts:
            self.index_status_label.setText(" · ".join(parts))

    def search(self) -> None:
        """Execute and render a safe FTS query, honouring the active filters."""

        text = self.search_edit.text().strip()
        clear_layout(self.results_layout)
        self.refresh_index_status()
        subject_id, kind = self.selected_filters()
        if text:
            results = self.database.search(text, subject_id=subject_id, kind=kind)
        elif subject_id is None and kind is None:
            self.status_label.setText(
                _("A pesquisa é local. Escreve duas ou mais letras para começar.")
            )
            self.results_layout.addStretch(1)
            return
        else:
            results = self.database.browse_documents(subject_id=subject_id, kind=kind)
        if not results:
            self.status_label.setText(
                _(
                    "Sem resultados. O documento pode ainda estar a ser indexado "
                    "ou ser um PDF digitalizado."
                )
            )
            empty = EmptyState(
                _("Não encontrei essa expressão"),
                _(
                    "Experimenta menos palavras ou confirma se o ficheiro aparece "
                    "nos organizados recentes."
                ),
            )
            self.results_layout.addWidget(empty)
            self.results_layout.addStretch(1)
            return
        if text:
            self.status_label.setText(
                _("{count} resultados · os parênteses retos mostram a correspondência").format(
                    count=len(results)
                )
                if len(results) != 1
                else _("1 resultado · os parênteses retos mostram a correspondência")
            )
        else:
            self.status_label.setText(
                _("{count} documentos").format(count=len(results))
                if len(results) != 1
                else _("1 documento")
            )
        for result in results:
            row = QFrame()
            row.setObjectName("ListRow")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(17, 13, 15, 13)
            row_layout.setSpacing(7)
            top = QHBoxLayout()
            copy = QVBoxLayout()
            copy.setSpacing(2)
            copy.addWidget(label(result.title, "RowTitle"))
            if result.page > 0:
                meta = _("{subject}  ·  {kind}  ·  {location}").format(
                    subject=result.subject_name,
                    kind=result.kind,
                    location=self._location_copy(result.path, result.page),
                )
            else:
                meta = _("{subject}  ·  {kind}").format(
                    subject=result.subject_name,
                    kind=result.kind,
                )
            copy.addWidget(label(meta, "Muted"))
            top.addLayout(copy, 1)
            reveal = button(_("Mostrar na pasta"), variant="quiet")
            reveal.clicked.connect(
                lambda _checked=False, path=result.path: self.reveal_path.emit(path)
            )
            open_button = button(_("Abrir"))
            open_button.clicked.connect(
                lambda _checked=False, path=result.path: self.open_path.emit(path)
            )
            top.addWidget(reveal)
            top.addWidget(open_button)
            row_layout.addLayout(top)
            if result.snippet.strip():
                snippet = QLabel(result.snippet.replace("\n", " "))
                snippet.setWordWrap(True)
                snippet.setStyleSheet(f"color: {ui_theme.current().muted}; line-height: 1.35;")
                snippet.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                row_layout.addWidget(snippet)
            self.results_layout.addWidget(row)
        self.results_layout.addStretch(1)

    @staticmethod
    def _location_copy(path: Path, page: int) -> str:
        suffix = path.suffix.casefold()
        if suffix == ".pptx":
            return _("diapositivo {page}").format(page=page)
        if suffix == ".xlsx":
            return _("folha {page}").format(page=page)
        if suffix == ".docx":
            return _("documento")
        return _("página {page}").format(page=page)


class TasksPage(QWidget):
    """Subject-linked deadlines and completion state."""

    changed = Signal()

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self._selected_date: date | None = None
        layout = _page_layout(self)
        layout.addWidget(
            PageHeading(
                _("Tarefas e prazos"),
                _("Mantém cada entrega junto da disciplina a que pertence."),
            )
        )

        form_panel = QFrame()
        form_panel.setObjectName("Panel")
        form_layout = QHBoxLayout(form_panel)
        form_layout.setContentsMargins(16, 14, 14, 14)
        form_layout.setSpacing(10)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(_("Nova tarefa, por exemplo: entregar ficha 4"))
        self.title_edit.returnPressed.connect(self._add_task)
        self.subject_combo = QComboBox()
        self.subject_combo.setMinimumWidth(170)
        self.due_check = QCheckBox(_("Prazo"))
        self.due_check.setChecked(True)
        self.due_edit = QDateEdit(QDate.currentDate().addDays(7))
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDisplayFormat("dd/MM/yyyy")
        self.due_edit.setMinimumWidth(150)
        self.due_check.toggled.connect(self.due_edit.setEnabled)
        add = button(_("Adicionar"), variant="primary")
        add.clicked.connect(self._add_task)
        form_layout.addWidget(self.title_edit, 1)
        form_layout.addWidget(self.subject_combo)
        form_layout.addWidget(self.due_check)
        form_layout.addWidget(self.due_edit)
        form_layout.addWidget(add)
        layout.addWidget(form_panel)
        self.error_label = label("", "ErrorText")
        layout.addWidget(self.error_label)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.calendar_panel = QFrame()
        self.calendar_panel.setObjectName("Panel")
        self.calendar_panel.setFixedWidth(300)
        calendar_layout = QVBoxLayout(self.calendar_panel)
        calendar_layout.setContentsMargins(10, 8, 10, 10)
        self.calendar = QCalendarWidget()
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setMinimumWidth(260)
        self.calendar.clicked.connect(self._on_date_clicked)
        self.calendar.activated.connect(self._on_date_activated)
        calendar_layout.addWidget(self.calendar)

        right = QVBoxLayout()
        right.setSpacing(8)
        self.filter_row = QHBoxLayout()
        self.calendar_toggle = button(_("Calendário"))
        self.calendar_toggle.setCheckable(True)
        self.calendar_toggle.setVisible(False)
        self.calendar_toggle.toggled.connect(self._on_calendar_toggled)
        self.filter_label = label("", "Muted")
        self.clear_filter_button = button(_("Ver todas"), variant="quiet")
        self.clear_filter_button.clicked.connect(self._clear_date_filter)
        self.filter_row.addWidget(self.calendar_toggle)
        self.filter_row.addWidget(self.filter_label)
        self.filter_row.addStretch(1)
        self.filter_row.addWidget(self.clear_filter_button)
        right.addLayout(self.filter_row)
        area, _container, self.tasks_layout = _scroll_list()
        right.addWidget(area, 1)
        body.addLayout(right, 1)
        body.addWidget(self.calendar_panel, 0, Qt.AlignmentFlag.AlignTop)
        self.calendar_panel.setMaximumHeight(340)
        layout.addLayout(body, 1)
        self._narrow = False
        self._apply_calendar_layout(self.window().width())
        self.refresh()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_calendar_layout(self.window().width())

    def _apply_calendar_layout(self, width: int) -> None:
        """Collapse the calendar behind a toggle when the page gets narrow."""

        narrow = width < 1120
        if narrow == self._narrow:
            return
        self._narrow = narrow
        self.calendar_toggle.setVisible(narrow)
        if narrow:
            self.calendar_panel.setVisible(self.calendar_toggle.isChecked())
        else:
            self.calendar_panel.setVisible(True)

    def _on_calendar_toggled(self, checked: bool) -> None:
        if self._narrow:
            self.calendar_panel.setVisible(checked)

    def refresh(self) -> None:
        """Refresh subject choices and the task list."""

        current_subject = self.subject_combo.currentData()
        self.subject_combo.clear()
        self.subject_combo.addItem(_("Geral"), None)
        for subject in self.database.list_subjects():
            self.subject_combo.addItem(subject.name, subject.id)
        if current_subject is not None:
            index = self.subject_combo.findData(current_subject)
            if index >= 0:
                self.subject_combo.setCurrentIndex(index)

        clear_layout(self.tasks_layout)
        tasks = self.database.list_tasks()
        self._apply_calendar_marks(tasks)
        if self._selected_date is not None:
            visible = [task for task in tasks if task.due_date == self._selected_date]
            self.filter_label.setText(
                _("A mostrar tarefas de {date}").format(
                    date=self._selected_date.strftime("%d/%m/%Y")
                )
            )
            self.clear_filter_button.show()
        else:
            visible = tasks
            self.filter_label.clear()
            self.clear_filter_button.hide()
        if not visible:
            if self._selected_date is not None:
                self.tasks_layout.addWidget(
                    EmptyState(
                        _("Sem tarefas neste dia"),
                        _(
                            "Elimina o filtro para ver todas as tarefas "
                            "ou adiciona uma tarefa para este dia."
                        ),
                    )
                )
            else:
                self.tasks_layout.addWidget(
                    EmptyState(
                        _("Sem tarefas pendentes"),
                        _("Adiciona a próxima entrega acima ou cria-a ao organizar um documento."),
                    )
                )
            self.tasks_layout.addStretch(1)
            return
        for task in visible:
            self.tasks_layout.addWidget(self._row(task))
        self.tasks_layout.addStretch(1)

    def _apply_calendar_marks(self, tasks: list[StudyTask]) -> None:
        """Colour calendar days by the state of their deadlines."""

        self.calendar.setDateTextFormat(QDate(), QTextCharFormat())
        neutral = QTextCharFormat()
        neutral.setForeground(QColor(ui_theme.current().text))
        for weekend in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.calendar.setWeekdayTextFormat(weekend, neutral)
        by_date: dict[date, list[StudyTask]] = {}
        for task in tasks:
            if task.due_date is not None:
                by_date.setdefault(task.due_date, []).append(task)
        today = date.today()
        current = ui_theme.current()
        for due_date, day_tasks in by_date.items():
            format_ = QTextCharFormat()
            open_tasks = [task for task in day_tasks if not task.completed]
            if open_tasks:
                format_.setFontWeight(QFont.Weight.Bold)
                if due_date < today:
                    format_.setForeground(QColor(current.danger))
                    format_.setBackground(QColor(current.cal_mark_overdue))
                elif due_date == today:
                    format_.setForeground(QColor(current.warning))
                    format_.setBackground(QColor(current.cal_mark_today))
                else:
                    format_.setForeground(QColor(current.teal))
                    format_.setBackground(QColor(current.cal_mark_upcoming))
            else:
                format_.setForeground(QColor(current.muted))
                format_.setBackground(QColor(current.cal_mark_done))
            self.calendar.setDateTextFormat(
                QDate(due_date.year, due_date.month, due_date.day), format_
            )

    def _on_date_clicked(self, clicked: QDate) -> None:
        chosen = cast(date, clicked.toPython())
        if self._selected_date == chosen:
            self._clear_date_filter()
            return
        self._selected_date = chosen
        self.refresh()

    def _on_date_activated(self, chosen: QDate) -> None:
        picked = cast(date, chosen.toPython())
        self.due_check.setChecked(True)
        self.due_edit.setDate(QDate(picked.year, picked.month, picked.day))
        self.title_edit.setFocus()

    def _clear_date_filter(self) -> None:
        self._selected_date = None
        self.refresh()

    def _row(self, task: StudyTask) -> QFrame:
        row = QFrame()
        row.setObjectName("ListRow")
        tokens = ui_theme.current()
        if not task.completed and task.due_date:
            if task.due_date < date.today():
                row.setStyleSheet(f"QFrame#ListRow {{ background: {tokens.danger_soft}; }}")
            elif task.due_date == date.today():
                row.setStyleSheet(f"QFrame#ListRow {{ background: {tokens.warning_soft}; }}")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(15, 11, 11, 11)
        row_layout.setSpacing(12)
        completed = QCheckBox()
        completed.setAccessibleName(f"Concluir {task.title}")
        completed.setChecked(task.completed)
        completed.toggled.connect(
            lambda checked, task_id=task.id: self._toggle_task(task_id, checked)
        )
        row_layout.addWidget(completed)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title = label(task.title, "RowTitle")
        if task.completed:
            title.setStyleSheet(
                f"color: {ui_theme.current().muted}; text-decoration: line-through;"
            )
        copy.addWidget(title)
        subject = task.subject_name or _("Geral")
        due = self._due_copy(task)
        copy.addWidget(label(_("{subject}  ·  {due}").format(subject=subject, due=due), "Muted"))
        row_layout.addLayout(copy, 1)
        edit = button(_("Editar"))
        edit.clicked.connect(lambda: self._edit_task(task.id))
        row_layout.addWidget(edit)
        delete = button(_("Eliminar"), variant="danger")
        delete.clicked.connect(lambda: self._delete_task(task.id))
        row_layout.addWidget(delete)
        return row

    @staticmethod
    def _due_copy(task: StudyTask) -> str:
        if task.due_date is None:
            return _("Sem prazo")
        if task.completed:
            return format_day(task.due_date)
        delta = (task.due_date - date.today()).days
        if delta < 0:
            return _("Atrasada · {date}").format(date=format_day(task.due_date))
        if delta == 0:
            return _("Prazo hoje")
        if delta == 1:
            return _("Prazo amanhã")
        return _("Prazo em {count} dias · {date}").format(
            count=delta, date=format_day(task.due_date)
        )

    def _add_task(self) -> None:
        title = self.title_edit.text().strip()
        if not title:
            self.error_label.setText(_("Escreve uma tarefa antes de adicionar."))
            self.title_edit.setFocus()
            return
        due_date = (
            cast(date, self.due_edit.date().toPython()) if self.due_check.isChecked() else None
        )
        self.database.add_task(title, self.subject_combo.currentData(), due_date)
        self.title_edit.clear()
        self.error_label.clear()
        self.refresh()
        self.changed.emit()

    def _toggle_task(self, task_id: int, completed: bool) -> None:
        self.database.set_task_completed(task_id, completed)
        self.refresh()
        self.changed.emit()

    def _edit_task(self, task_id: int) -> None:
        task = self.database.get_task(task_id)
        if task is None:
            return
        dialog = TaskDialog(task, self.database.list_subjects(active_only=False), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        title, subject_id, due_date, reminder_lead_days = dialog.values
        try:
            self.database.update_task(task_id, title, subject_id, due_date, reminder_lead_days)
        except (LookupError, ValueError) as exc:
            self.error_label.setText(str(exc))
            return
        self.refresh()
        self.changed.emit()

    def _delete_task(self, task_id: int) -> None:
        self.database.delete_task(task_id)
        self.refresh()
        self.changed.emit()


class SubjectsPage(QWidget):
    """Subject configuration and physical-folder access."""

    add_requested = Signal()
    edit_requested = Signal(int)
    archive_requested = Signal(int)
    restore_requested = Signal(int)
    view_files_requested = Signal(int)
    open_folder = Signal(object)

    def __init__(
        self, database: Database, config: AppConfig, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.config = config
        self.show_archived = False
        layout = _page_layout(self)
        add = button(_("Adicionar disciplina"), variant="primary")
        add.clicked.connect(self.add_requested)
        layout.addWidget(
            PageHeading(
                _("Disciplinas"),
                _("Os códigos e palavras-chave tornam as sugestões de arquivo mais precisas."),
                [add],
            )
        )
        header_row = QHBoxLayout()
        self.summary_label = label("", "PageSubtitle")
        header_row.addWidget(self.summary_label, 1)
        self.archived_check = QCheckBox(_("Mostrar arquivadas"))
        self.archived_check.toggled.connect(self._set_show_archived)
        header_row.addWidget(self.archived_check)
        layout.addLayout(header_row)
        area, _container, self.subjects_layout = _scroll_list()
        layout.addWidget(area, 1)
        self.refresh()

    def _set_show_archived(self, show: bool) -> None:
        self.show_archived = show
        self.refresh()

    def refresh(self) -> None:
        """Render active subjects, and archived ones when the toggle is on."""

        subjects = self.database.list_subjects(active_only=not self.show_archived)
        summaries = self.database.count_files_by_subject()
        active_count = self.database.count_subjects()
        archived_count = len(self.database.list_subjects(active_only=False)) - active_count
        summary = (
            _("{count} disciplinas ativas").format(count=active_count)
            if active_count != 1
            else _("{count} disciplina ativa").format(count=active_count)
        )
        if self.show_archived and archived_count:
            summary += " · " + (
                _("{count} arquivadas").format(count=archived_count)
                if archived_count != 1
                else _("{count} arquivada").format(count=archived_count)
            )
        self.summary_label.setText(summary)
        clear_layout(self.subjects_layout)
        if not subjects:
            empty = EmptyState(
                _("Começa por uma disciplina"),
                _("Cria uma disciplina para a app saber onde guardar o próximo download."),
                _("Adicionar disciplina"),
            )
            empty.action_requested.connect(self.add_requested)
            self.subjects_layout.addWidget(empty)
            self.subjects_layout.addStretch(1)
            return
        for subject in subjects:
            self.subjects_layout.addWidget(self._row(subject, summaries))
        self.subjects_layout.addStretch(1)

    def _row(self, subject: Subject, summaries: dict[int, tuple[int, int]]) -> QFrame:
        row = QFrame()
        row.setObjectName("ListRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(15, 12, 12, 12)
        row_layout.setSpacing(13)
        swatch = QFrame()
        swatch.setFixedSize(13, 13)
        swatch.setStyleSheet(
            f"background: {subject.color}; border-radius: 6px; border: 1px solid {subject.color};"
        )
        row_layout.addWidget(swatch, 0, Qt.AlignmentFlag.AlignTop)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = subject.name + (f"  ·  {subject.code}" if subject.code else "")
        copy.addWidget(label(title, "RowTitle"))
        keyword_copy = ", ".join(subject.keywords) if subject.keywords else _("Sem palavras-chave")
        copy.addWidget(label(keyword_copy, "Muted"))
        subject_path = self.config.university_root / subject.folder_name
        folder_copy = label(_("Pasta: {name}").format(name=subject.folder_name), "Muted")
        folder_copy.setToolTip(str(subject_path))
        folder_copy.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy.addWidget(folder_copy)
        file_count, total_bytes = summaries.get(subject.id, (0, 0))
        if file_count:
            copy.addWidget(
                label(
                    _("{count} ficheiro · {size}").format(
                        count=file_count, size=format_size(total_bytes)
                    )
                    if file_count == 1
                    else _("{count} ficheiros · {size}").format(
                        count=file_count, size=format_size(total_bytes)
                    ),
                    "Muted",
                )
            )
        else:
            copy.addWidget(label(_("Ainda sem ficheiros organizados"), "Muted"))
        if not subject.active:
            copy.addWidget(label(_("Arquivada"), "Muted"))
        row_layout.addLayout(copy, 1)
        view_files = button(_("Ver ficheiros"))
        view_files.setToolTip(_("Mostrar os ficheiros organizados nesta disciplina"))
        view_files.clicked.connect(lambda: self.view_files_requested.emit(subject.id))
        open_button = button(_("Abrir pasta"), variant="quiet")
        open_button.clicked.connect(
            lambda: self.open_folder.emit(self.config.university_root / subject.folder_name)
        )
        edit = button(_("Editar"))
        edit.clicked.connect(lambda: self.edit_requested.emit(subject.id))
        row_layout.addWidget(view_files)
        row_layout.addWidget(open_button)
        row_layout.addWidget(edit)
        if subject.active:
            archive = button(_("Arquivar"), variant="danger")
            archive.setToolTip(_("Oculta a disciplina sem apagar os respetivos ficheiros"))
            archive.clicked.connect(lambda: self.archive_requested.emit(subject.id))
            row_layout.addWidget(archive)
        else:
            restore = button(_("Restaurar"), variant="primary")
            restore.setToolTip(_("Volta a mostrar a disciplina nas escolhas de arquivo"))
            restore.clicked.connect(lambda: self.restore_requested.emit(subject.id))
            row_layout.addWidget(restore)
        return row


class SettingsPage(QWidget):
    """File-system, intake and login settings."""

    save_requested = Signal(object)
    backup_created_requested = Signal()
    backup_export_requested = Signal()
    backup_manager_requested = Signal()
    backup_open_folder_requested = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        layout = _page_layout(self)
        layout.addWidget(
            PageHeading(
                _("Definições"),
                _("Controla exatamente quais ficheiros entram e onde ficam guardados."),
            )
        )

        body_area, _container, body_layout = _scroll_list()
        body_layout.setSpacing(22)

        def section(title: str) -> tuple[QVBoxLayout, QFormLayout]:
            if body_layout.count():
                body_layout.addWidget(hairline())
            content = QWidget()
            section_layout = QVBoxLayout(content)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(12)
            section_layout.addWidget(label(title, "SectionTitle"))
            fields = QFormLayout()
            fields.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            fields.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            fields.setVerticalSpacing(20)
            fields.setHorizontalSpacing(26)
            fields.setContentsMargins(0, 6, 0, 0)
            section_layout.addLayout(fields)
            body_layout.addWidget(content)
            return section_layout, fields

        folders_layout, form = section(_("Pastas e ficheiros"))

        self.root_edit = QLineEdit()
        root_row = QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_choose = button(_("Escolher…"))
        root_choose.clicked.connect(lambda: self._choose_folder(self.root_edit))
        root_row.addWidget(root_choose)
        form.addRow(_("Pasta Universidade"), root_row)

        self.downloads_edit = QLineEdit()
        downloads_row = QHBoxLayout()
        downloads_row.addWidget(self.downloads_edit, 1)
        downloads_choose = button(_("Escolher…"))
        downloads_choose.clicked.connect(lambda: self._choose_folder(self.downloads_edit))
        downloads_row.addWidget(downloads_choose)
        form.addRow(_("Pasta Downloads"), downloads_row)

        self.extensions_edit = QLineEdit()
        self.extensions_edit.setPlaceholderText(".pdf, .docx, .pptx, .ipynb")
        form.addRow(_("Extensões aceites"), self.extensions_edit)
        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("{nome_original}")
        self.template_edit.setToolTip(
            _("Tokens: {tokens}. A extensão original é sempre preservada.").format(
                tokens="{disciplina} {codigo} {tipo} {nome_original} {data} {ano} {mes} {dia}"
            )
        )
        form.addRow(_("Modelo do nome"), self.template_edit)
        self.minimum_size = QSpinBox()
        self.minimum_size.setRange(0, 100 * 1024 * 1024)
        self.minimum_size.setSuffix(_(" bytes"))
        form.addRow(_("Tamanho mínimo"), self.minimum_size)
        self.ocr_check = ToggleSwitch(_("Reconhecer texto em PDFs digitalizados (OCR)"))
        folders_layout.addWidget(self.ocr_check)
        note = label(
            _(
                "Alterar a pasta Universidade afeta os próximos ficheiros; "
                "os já organizados não são movidos automaticamente."
            ),
            "Muted",
        )
        note.setWordWrap(True)
        folders_layout.addWidget(note)

        watch_layout, form = section(_("Vigilância e notificações"))
        self.watch_check = ToggleSwitch(_("Vigiar novos ficheiros em Downloads"))
        self.startup_check = ToggleSwitch(_("Iniciar o SortInator quando entro no Windows"))
        self.quiet_check = ToggleSwitch(_("Silenciar notificações de arquivo"))
        self.quiet_check.setToolTip(
            _("Sem avisos de ficheiros organizados; erros e prazos continuam visíveis.")
        )
        form.addRow(self.watch_check)
        form.addRow(self.startup_check)
        form.addRow(self.quiet_check)
        self.auto_close_check = ToggleSwitch(_("Fechar o popup automaticamente"))
        self.auto_close_check.setToolTip(
            _("Sem esta opção, o popup fica aberto até escolheres uma ação.")
        )
        form.addRow(self.auto_close_check)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setSuffix(" s")
        form.addRow(_("Tempo do popup"), self.timeout_spin)
        self.auto_close_check.toggled.connect(self.timeout_spin.setEnabled)
        self.reminder_spin = QSpinBox()
        self.reminder_spin.setRange(0, 30)
        self.reminder_spin.setSuffix(_(" dias"))
        self.reminder_spin.setToolTip(_("Com quantos dias de antecedência avisar prazos"))
        form.addRow(_("Avisar prazos antes"), self.reminder_spin)

        _appearance_layout, form = section(_("Aparência e idioma"))
        self.theme_combo = QComboBox()
        for theme_id in THEME_IDS:
            self.theme_combo.addItem(ui_theme.get_theme(theme_id).display_name, theme_id)
        form.addRow(_("Tema"), self.theme_combo)
        self.language_combo = QComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self.language_combo.addItem(name, code)
        form.addRow(_("Idioma"), self.language_combo)
        language_note = label(_("O idioma novo é aplicado ao reiniciar a app."), "Muted")
        language_note.setContentsMargins(0, 8, 0, 0)
        form.addRow("", language_note)
        self.check_updates_check = ToggleSwitch(_("Procurar atualizações automaticamente"))
        watch_layout.addWidget(self.check_updates_check)

        backup_layout, _backup_form = section(_("Cópias de segurança"))
        self.backup_status = label(_("Ainda não há cópias de segurança."), "Muted")
        self.backup_status.setWordWrap(True)
        backup_layout.addWidget(self.backup_status)
        backup_row = QHBoxLayout()
        backup_row.setSpacing(8)
        self.backup_create_button = button(_("Criar cópia agora"), variant="primary")
        self.backup_create_button.clicked.connect(
            lambda _checked=False: self.backup_created_requested.emit()
        )
        self.backup_export_button = button(_("Criar e exportar .zip…"))
        self.backup_export_button.clicked.connect(
            lambda _checked=False: self.backup_export_requested.emit()
        )
        self.backup_manage_button = button(_("Restaurar…"))
        self.backup_manage_button.clicked.connect(
            lambda _checked=False: self.backup_manager_requested.emit()
        )
        self.backup_folder_button = button(_("Abrir pasta"), variant="quiet")
        self.backup_folder_button.clicked.connect(
            lambda _checked=False: self.backup_open_folder_requested.emit()
        )
        backup_row.addWidget(self.backup_create_button)
        backup_row.addWidget(self.backup_export_button)
        backup_row.addWidget(self.backup_manage_button)
        backup_row.addStretch(1)
        backup_row.addWidget(self.backup_folder_button)
        backup_layout.addLayout(backup_row)
        backup_note = label(
            _(
                "As cópias guardam o catálogo e as definições. "
                "Os teus documentos não são alterados."
            ),
            "Muted",
        )
        backup_note.setWordWrap(True)
        backup_layout.addWidget(backup_note)
        body_layout.addStretch(1)
        self.body_area = body_area
        layout.addWidget(body_area, 1)
        layout.addWidget(hairline())
        # Scrolling must never edit a value: the wheel only edits a spin or
        # combo that the user explicitly focused; otherwise it scrolls the page.
        WheelRedirector(
            self.body_area,
            (
                self.minimum_size,
                self.timeout_spin,
                self.reminder_spin,
                self.theme_combo,
                self.language_combo,
            ),
        )

        action_row = QHBoxLayout()
        self.status_label = label("", "SuccessText")
        self.status_label.setWordWrap(True)
        action_row.addWidget(self.status_label, 1)
        save = button(_("Guardar definições"), variant="primary")
        save.clicked.connect(self._save)
        action_row.addWidget(save)
        layout.addLayout(action_row)
        version_label = label(
            _(
                "SortInator v{version} · código MIT · "
                "componentes de terceiros com licenças próprias"
            ).format(version=__version__),
            "Muted",
        )
        version_label.setWordWrap(True)
        layout.addWidget(version_label)
        self.load_config(config)

    def load_config(self, config: AppConfig) -> None:
        """Populate controls from current persistent settings."""

        self.config = config
        self.root_edit.setText(str(config.university_root))
        self.root_edit.setCursorPosition(0)
        self.downloads_edit.setText(str(config.downloads_dir))
        self.downloads_edit.setCursorPosition(0)
        self.extensions_edit.setText(", ".join(config.allowed_extensions))
        self.template_edit.setText(config.filename_template)
        self.template_edit.setCursorPosition(0)
        self.minimum_size.setValue(max(0, config.minimum_file_size))
        self.timeout_spin.setValue(config.prompt_timeout_seconds)
        self.auto_close_check.setChecked(config.prompt_timeout_enabled)
        self.timeout_spin.setEnabled(config.prompt_timeout_enabled)
        self.reminder_spin.setValue(config.reminder_lead_days)
        theme_index = self.theme_combo.findData(config.theme)
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        language_index = self.language_combo.findData(config.language)
        self.language_combo.setCurrentIndex(language_index if language_index >= 0 else 0)
        self.watch_check.setChecked(config.watch_enabled)
        self.startup_check.setChecked(config.launch_at_login)
        self.check_updates_check.setChecked(config.check_updates_on_launch)
        self.ocr_check.setChecked(config.ocr_enabled)
        self.quiet_check.setChecked(config.quiet_intake)

    def set_status(self, message: str, *, error: bool = False) -> None:
        """Show settings persistence feedback."""

        self.status_label.setObjectName("ErrorText" if error else "SuccessText")
        self.status_label.setText(message)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_backup_inventory(self, bundles: tuple[BundleInfo, ...]) -> None:
        """Summarize the user snapshots in the backup panel."""

        user_bundles = [info for info in bundles if info.kind == USER_MARKER]
        if not user_bundles:
            self.backup_status.setObjectName("Muted")
            self.backup_status.setText(_("Ainda não há cópias de segurança."))
            return
        total = sum(info.size_bytes for info in user_bundles)
        when = user_bundles[0].created_at.astimezone().strftime("%d/%m/%Y %H:%M")
        self.backup_status.setObjectName("Muted")
        if len(user_bundles) == 1:
            self.backup_status.setText(
                _("Última cópia: {when} · {size}").format(when=when, size=format_size(total))
            )
        else:
            self.backup_status.setText(
                _("Última cópia: {when} · {count} cópias · {size}").format(
                    when=when, count=len(user_bundles), size=format_size(total)
                )
            )
        self.backup_status.style().unpolish(self.backup_status)
        self.backup_status.style().polish(self.backup_status)

    def set_backup_busy(self, busy: bool) -> None:
        """Lock the backup actions while a snapshot is being processed."""

        for control in (
            self.backup_create_button,
            self.backup_export_button,
            self.backup_manage_button,
        ):
            control.setEnabled(not busy)
        if busy:
            self.backup_status.setText(_("A processar a cópia de segurança…"))

    def set_backup_status(self, message: str, *, error: bool = False) -> None:
        """Show backup feedback without touching the settings status line."""

        self.backup_status.setObjectName("ErrorText" if error else "Muted")
        self.backup_status.setText(message)
        self.backup_status.style().unpolish(self.backup_status)
        self.backup_status.style().polish(self.backup_status)

    def _choose_folder(self, target: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, _("Escolher pasta"), target.text())
        if selected:
            target.setText(selected)

    def _save(self) -> None:
        payload: SettingsPayload = {
            "university_root": Path(self.root_edit.text().strip()).expanduser(),
            "downloads_dir": Path(self.downloads_edit.text().strip()).expanduser(),
            "extensions": self.extensions_edit.text(),
            "filename_template": self.template_edit.text().strip(),
            "minimum_file_size": self.minimum_size.value(),
            "prompt_timeout_seconds": self.timeout_spin.value(),
            "prompt_timeout_enabled": self.auto_close_check.isChecked(),
            "reminder_lead_days": self.reminder_spin.value(),
            "theme": str(self.theme_combo.currentData()),
            "language": str(self.language_combo.currentData()),
            "check_updates_on_launch": self.check_updates_check.isChecked(),
            "ocr_enabled": self.ocr_check.isChecked(),
            "quiet_intake": self.quiet_check.isChecked(),
            "watch_enabled": self.watch_check.isChecked(),
            "launch_at_login": self.startup_check.isChecked(),
        }
        self.save_requested.emit(payload)
