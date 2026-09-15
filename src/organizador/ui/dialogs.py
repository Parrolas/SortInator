"""Focused setup, task-editing, subject-editing and bulk-filing dialogs."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from contextlib import suppress
from datetime import date, timedelta
from pathlib import Path
from typing import cast

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from organizador.config import AppConfig
from organizador.db import Database
from organizador.filer import FilingService, render_final_name
from organizador.i18n import _
from organizador.models import FILE_KINDS, FiledDocument, InboxItem, StudyTask, Subject
from organizador.recovery import PRE_RESTORE_MARKER, USER_MARKER, BundleInfo
from organizador.ui import theme as ui_theme
from organizador.ui.widgets import button, clear_layout, format_size, label


class SubjectDialog(QDialog):
    """Create or edit a subject's matching metadata."""

    def __init__(self, subject: Subject | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.subject = subject
        self.color = subject.color if subject else ui_theme.current().teal
        self.setWindowTitle(_("Editar disciplina") if subject else _("Nova disciplina"))
        self.setModal(True)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 24)
        root.setSpacing(18)
        root.addWidget(
            label(_("Editar disciplina") if subject else _("Adicionar disciplina"), "PageTitle")
        )
        root.addWidget(
            label(
                _("As palavras-chave ajudam a reconhecer ficheiros pelo nome."),
                "PageSubtitle",
            )
        )

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)
        self.name_edit = QLineEdit(subject.name if subject else "")
        self.name_edit.setPlaceholderText(_("Ex.: Cálculo I"))
        self.code_edit = QLineEdit(subject.code if subject else "")
        self.code_edit.setPlaceholderText(_("Ex.: MAT101"))
        self.keywords_edit = QLineEdit(", ".join(subject.keywords) if subject else "")
        self.keywords_edit.setPlaceholderText(_("Ex.: cálculo, derivadas, integrais"))
        self.color_button = QPushButton()
        self.color_button.setMinimumWidth(120)
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()
        form.addRow(_("Nome"), self.name_edit)
        form.addRow(_("Código"), self.code_edit)
        form.addRow(_("Palavras-chave"), self.keywords_edit)
        form.addRow(_("Cor"), self.color_button)
        root.addLayout(form)

        self.error_label = label("", "ErrorText")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = button(_("Cancelar"))
        cancel.clicked.connect(self.reject)
        save = button(_("Guardar disciplina"), variant="primary")
        save.clicked.connect(self._validate)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)
        self.name_edit.setFocus()

    @property
    def values(self) -> tuple[str, str, str, tuple[str, ...]]:
        """Return validated name, code, colour and keywords."""

        keywords = tuple(
            item.strip() for item in re.split(r"[,;]", self.keywords_edit.text()) if item.strip()
        )
        return self.name_edit.text().strip(), self.code_edit.text().strip(), self.color, keywords

    def _choose_color(self) -> None:
        selected = QColorDialog.getColor(QColor(self.color), self, _("Cor da disciplina"))
        if selected.isValid():
            self.color = selected.name()
            self._update_color_button()

    def _update_color_button(self) -> None:
        color = QColor(self.color)
        channels = (color.redF(), color.greenF(), color.blueF())
        linear = tuple(
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        )
        luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
        dark_ink = QColor(8, 17, 29).name()
        white = QColor(Qt.GlobalColor.white).name()
        foreground = dark_ink if luminance > 0.18 else white
        self.color_button.setText(self.color.upper())
        self.color_button.setStyleSheet(
            f"QPushButton {{ background: {self.color}; color: {foreground}; "
            f"border-color: {self.color}; }}"
        )

    def _validate(self) -> None:
        if not self.name_edit.text().strip():
            self.error_label.setText(_("Escreve o nome da disciplina para continuar."))
            self.name_edit.setFocus()
            return
        self.accept()


class TaskDialog(QDialog):
    """Edit an existing study task's title, subject, deadline and reminder."""

    def __init__(
        self,
        task: StudyTask,
        subjects: Sequence[Subject],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Editar tarefa"))
        self.setModal(True)
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 24)
        root.setSpacing(18)
        root.addWidget(label(_("Editar tarefa"), "PageTitle"))

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)

        self.title_edit = QLineEdit(task.title)
        self.title_edit.setAccessibleName(_("Título da tarefa"))
        form.addRow(_("Tarefa"), self.title_edit)

        self.subject_combo = QComboBox()
        for subject in subjects:
            name = (
                subject.name
                if subject.active
                else _("{name} (arquivada)").format(name=subject.name)
            )
            self.subject_combo.addItem(name, subject.id)
        current = self.subject_combo.findData(task.subject_id)
        if current >= 0:
            self.subject_combo.setCurrentIndex(current)
        form.addRow(_("Disciplina"), self.subject_combo)

        self.due_check = QCheckBox(_("Prazo"))
        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDisplayFormat("dd/MM/yyyy")
        self.due_edit.setEnabled(task.due_date is not None)
        if task.due_date is not None:
            self.due_edit.setDate(QDate(task.due_date.year, task.due_date.month, task.due_date.day))
        else:
            fallback = date.today() + timedelta(days=7)
            self.due_edit.setDate(QDate(fallback.year, fallback.month, fallback.day))
        self.due_check.setChecked(task.due_date is not None)
        self.due_check.toggled.connect(self.due_edit.setEnabled)
        due_row = QHBoxLayout()
        due_row.addWidget(self.due_check)
        due_row.addWidget(self.due_edit)
        due_row.addStretch(1)
        form.addRow(_("Prazo"), due_row)

        self.reminder_combo = QComboBox()
        self._reminder_choices: tuple[tuple[int | None, str], ...] = (
            (None, _("Padrão das Definições")),
            (0, _("No dia")),
            (1, _("1 dia antes")),
            (2, _("2 dias antes")),
            (3, _("3 dias antes")),
            (7, _("1 semana antes")),
        )
        for value, text in self._reminder_choices:
            self.reminder_combo.addItem(text, value)
        lead_index = self.reminder_combo.findData(task.reminder_lead_days)
        self.reminder_combo.setCurrentIndex(lead_index if lead_index >= 0 else 0)
        form.addRow(_("Aviso"), self.reminder_combo)
        root.addLayout(form)

        self.error_label = label("", "ErrorText")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = button(_("Cancelar"))
        cancel.clicked.connect(self.reject)
        save = button(_("Guardar tarefa"), variant="primary")
        save.clicked.connect(self._validate)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)
        self.title_edit.setFocus()

    @property
    def values(self) -> tuple[str, int | None, date | None, int | None]:
        """Return title, subject id, due date and per-task reminder lead."""

        due = (
            cast(date | None, self.due_edit.date().toPython())
            if self.due_check.isChecked()
            else None
        )
        lead = self.reminder_combo.currentData()
        return self.title_edit.text().strip(), self.subject_combo.currentData(), due, lead

    def _validate(self) -> None:
        if not self.title_edit.text().strip():
            self.error_label.setText(_("Escreve o título da tarefa para continuar."))
            self.title_edit.setFocus()
            return
        self.accept()


class OnboardingDialog(QDialog):
    """First-run setup for the university root and initial subject."""

    def __init__(
        self,
        config: AppConfig,
        database: Database,
        filer: FilingService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.database = database
        self.filer = filer
        self.setWindowTitle(_("Preparar o Organizador"))
        self.setModal(True)
        self.setMinimumSize(820, 540)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        statement = QFrame()
        statement.setObjectName("Sidebar")
        statement.setFixedWidth(292)
        statement_layout = QVBoxLayout(statement)
        statement_layout.setContentsMargins(32, 38, 32, 34)
        statement_layout.setSpacing(14)
        brand = label(_("Organizador"), "Brand")
        statement_layout.addWidget(brand)
        promise = QLabel(_("Downloads arrumados\nantes de se perderem."))
        tokens = ui_theme.current()
        promise.setStyleSheet(
            f"color: {tokens.sidebar_text_active}; font-size: 27px; font-weight: 700;"
        )
        promise.setWordWrap(True)
        statement_layout.addWidget(promise)
        explanation = QLabel(
            _(
                "Os ficheiros elegíveis passam primeiro por uma Caixa de Entrada segura. "
                "Tu confirmas a disciplina e nada é substituído."
            )
        )
        explanation.setStyleSheet(
            f"color: {tokens.onboarding_text}; font-size: 14px; line-height: 1.4;"
        )
        explanation.setWordWrap(True)
        statement_layout.addWidget(explanation)
        statement_layout.addStretch(1)
        privacy = QLabel(
            _("Tudo fica neste computador. Nenhum documento é enviado para a internet.")
        )
        privacy.setStyleSheet(f"color: {tokens.onboarding_muted}; font-size: 12px;")
        privacy.setWordWrap(True)
        statement_layout.addWidget(privacy)
        outer.addWidget(statement)

        content = QWidget()
        content.setObjectName("Canvas")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(38, 34, 38, 30)
        content_layout.setSpacing(18)
        content_layout.addWidget(label(_("Escolhe o teu ponto de partida"), "PageTitle"))
        subtitle = label(
            _("Podes alterar estas opções depois. Começa por criar uma disciplina."),
            "PageSubtitle",
        )
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)

        form = QFormLayout()
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(18)

        folder_row = QHBoxLayout()
        self.root_edit = QLineEdit(str(config.university_root))
        choose = button(_("Escolher…"))
        choose.clicked.connect(self._choose_folder)
        folder_row.addWidget(self.root_edit, 1)
        folder_row.addWidget(choose)
        form.addRow(_("Pasta Universidade"), folder_row)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(_("Ex.: Cálculo I"))
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText(_("Ex.: MAT101 (opcional)"))
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText(_("Ex.: cálculo, derivadas, integrais"))
        form.addRow(_("Primeira disciplina"), self.name_edit)
        form.addRow(_("Código"), self.code_edit)
        form.addRow(_("Palavras-chave"), self.keywords_edit)
        content_layout.addLayout(form)

        self.watch_check = QCheckBox(_("Começar a vigiar Downloads depois da configuração"))
        self.watch_check.setChecked(config.watch_enabled)
        content_layout.addWidget(self.watch_check)
        self.error_label = label("", "ErrorText")
        self.error_label.setWordWrap(True)
        content_layout.addWidget(self.error_label)
        content_layout.addStretch(1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        finish = button(_("Criar a minha organização"), variant="primary")
        finish.setMinimumWidth(210)
        finish.clicked.connect(self._finish)
        action_row.addWidget(finish)
        content_layout.addLayout(action_row)
        outer.addWidget(content, 1)
        self.name_edit.setFocus()

    def reject(self) -> None:
        """Confirm leaving first-run setup incomplete."""

        answer = QMessageBox.question(
            self,
            _("Sair da configuração?"),
            _(
                "Sem uma disciplina, a app não começa a mover downloads. "
                "Podes voltar a configurar depois."
            ),
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            super().reject()

    def _choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, _("Escolher pasta Universidade"), self.root_edit.text()
        )
        if selected:
            self.root_edit.setText(selected)

    def _finish(self) -> None:
        name = self.name_edit.text().strip()
        root = Path(self.root_edit.text().strip()).expanduser()
        if not name:
            self.error_label.setText(_("Escreve o nome da primeira disciplina."))
            self.name_edit.setFocus()
            return
        if not str(root).strip():
            self.error_label.setText(_("Escolhe uma pasta para a Universidade."))
            self.root_edit.setFocus()
            return
        old_root = self.config.university_root
        old_watch_enabled = self.config.watch_enabled
        old_initialized = self.config.initialized
        created_subject: Subject | None = None
        self.config.university_root = root
        self.config.watch_enabled = self.watch_check.isChecked()
        self.config.initialized = True
        try:
            self.config.ensure_directories()
            code = self.code_edit.text().strip()
            keywords = tuple(
                item.strip()
                for item in re.split(r"[,;]", self.keywords_edit.text())
                if item.strip()
            )
            folder = self.filer.subject_folder_name(name, code)
            created_subject = self.database.add_subject(
                name, code, ui_theme.current().teal, keywords, folder
            )
            self.filer.ensure_subject_structure(created_subject)
            self.config.save()
        except (ValueError, OSError, sqlite3.IntegrityError) as exc:
            if created_subject is not None:
                with suppress(sqlite3.Error):
                    self.database.delete_subject(created_subject.id)
            self.config.university_root = old_root
            self.config.watch_enabled = old_watch_enabled
            self.config.initialized = old_initialized
            self.error_label.setText(f"Não foi possível concluir: {exc}")
            return
        self.accept()


class BulkFilingDialog(QDialog):
    """One explicit decision for filing several inbox files together."""

    def __init__(
        self,
        items: Sequence[InboxItem],
        subjects: Sequence[Subject],
        name_template: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.items = tuple(items)
        self.subjects = tuple(subjects)
        self.name_template = name_template
        count = len(self.items)
        self.setWindowTitle(_("Organizar seleção"))
        self.setModal(True)
        self.setMinimumWidth(600)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 24)
        root.setSpacing(14)
        root.addWidget(
            label(
                _("Organizar {count} ficheiro").format(count=count)
                if count == 1
                else _("Organizar {count} ficheiros").format(count=count),
                "PageTitle",
            )
        )
        subtitle = label(
            _(
                "Todos vão para a mesma disciplina e tipo. Cada ficheiro mantém o seu "
                "próprio histórico; só a última organização pode ser desfeita."
            ),
            "PageSubtitle",
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.subject_combo = QComboBox()
        for subject in self.subjects:
            self.subject_combo.addItem(subject.name, subject.id)
        self.subject_combo.currentIndexChanged.connect(self._update_preview)
        form.addRow(_("Disciplina"), self.subject_combo)

        self.type_combo = QComboBox()
        for kind in FILE_KINDS:
            self.type_combo.addItem(kind, kind)
        self.type_combo.setCurrentIndex(self.type_combo.findData("Slides"))
        self.type_combo.currentIndexChanged.connect(self._update_preview)
        form.addRow(_("Tipo"), self.type_combo)

        self.task_check = QCheckBox(_("Criar tarefa para cada ficheiro"))
        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDisplayFormat("dd/MM/yyyy")
        self.due_edit.setEnabled(False)
        self.task_check.toggled.connect(self.due_edit.setEnabled)
        fallback = date.today() + timedelta(days=7)
        self.due_edit.setDate(QDate(fallback.year, fallback.month, fallback.day))
        form.addRow(self.task_check)
        form.addRow(_("Prazo das tarefas"), self.due_edit)
        root.addLayout(form)

        root.addWidget(label(_("Nomes finais"), "RowTitle"))
        self.preview_label = label("", "Muted")
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.preview_label)

        self.error_label = label("", "ErrorText")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = button(_("Cancelar"))
        cancel.clicked.connect(self.reject)
        accept = button(
            _("Organizar {count} ficheiro").format(count=count)
            if count == 1
            else _("Organizar {count} ficheiros").format(count=count),
            variant="primary",
        )
        accept.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(accept)
        root.addLayout(actions)
        self._update_preview()

    def _current_subject(self) -> Subject | None:
        subject_id = self.subject_combo.currentData()
        for subject in self.subjects:
            if subject.id == subject_id:
                return subject
        return None

    def _update_preview(self) -> None:
        subject = self._current_subject()
        lines: list[str] = []
        for item in self.items:
            final = render_final_name(
                self.name_template,
                subject_name=subject.name if subject else "",
                subject_code=subject.code if subject else "",
                kind=self.type_combo.currentData() or "Outros",
                original_name=item.original_name,
                when=item.detected_at,
            )
            lines.append(f"{item.original_name}  →  {final}")
        self.preview_label.setText("\n".join(lines))

    @property
    def values(self) -> tuple[int, str, bool, date | None]:
        """Return subject id, kind, whether to create tasks, and the task due date."""

        due = (
            cast(date | None, self.due_edit.date().toPython())
            if self.task_check.isChecked()
            else None
        )
        kind = self.type_combo.currentData()
        subject_id = self.subject_combo.currentData()
        if subject_id is None or kind is None:  # pragma: no cover - combo is always populated
            raise RuntimeError("A seleção de disciplina e tipo é obrigatória.")
        return int(subject_id), str(kind), self.task_check.isChecked(), due


class BackupListDialog(QDialog):
    """List existing snapshots with restore, export and delete actions."""

    import_requested = Signal()
    restore_requested = Signal(object)
    export_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, bundles: Sequence[BundleInfo], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bundles = tuple(bundles)
        self.setWindowTitle(_("Cópias de segurança"))
        self.setModal(True)
        self.setMinimumSize(640, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(12)
        root.addWidget(label(_("Cópias de segurança"), "PageTitle"))
        root.addWidget(
            label(_("Restaurar substitui o catálogo e as definições atuais."), "PageSubtitle")
        )

        area = QScrollArea()
        area.setWidgetResizable(True)
        content = QWidget()
        self.list_layout = QVBoxLayout(content)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(8)
        area.setWidget(content)
        root.addWidget(area, 1)

        actions = QHBoxLayout()
        import_button = button(_("Importar .zip…"))
        import_button.clicked.connect(lambda _checked=False: self.import_requested.emit())
        close = button(_("Fechar"))
        close.clicked.connect(self.reject)
        actions.addWidget(import_button)
        actions.addStretch(1)
        actions.addWidget(close)
        root.addLayout(actions)
        self.set_bundles(self.bundles)

    def set_bundles(self, bundles: Sequence[BundleInfo]) -> None:
        """Rebuild the list after an import or delete."""

        self.bundles = tuple(bundles)
        clear_layout(self.list_layout)
        if not self.bundles:
            self.list_layout.addWidget(label(_("Ainda não há cópias de segurança."), "Muted"))
        for bundle in self.bundles:
            self.list_layout.addWidget(self._row(bundle))
        self.list_layout.addStretch(1)

    def _row(self, bundle: BundleInfo) -> QWidget:
        row = QFrame()
        row.setObjectName("ListRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(15, 11, 12, 11)
        layout.setSpacing(12)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        when = bundle.created_at.astimezone().strftime("%d/%m/%Y %H:%M")
        copy.addWidget(label(f"{self._kind_label(bundle.kind)} · {when}", "RowTitle"))
        copy.addWidget(
            label(
                _("{size} · esquema {version}").format(
                    size=format_size(bundle.size_bytes),
                    version=bundle.database_user_version,
                ),
                "Muted",
            )
        )
        layout.addLayout(copy, 1)
        restore = button(_("Restaurar"), variant="primary")
        restore.setEnabled(bundle.kind in {USER_MARKER, PRE_RESTORE_MARKER, "migration"})
        restore.clicked.connect(lambda _checked=False: self.restore_requested.emit(bundle))
        layout.addWidget(restore)
        export = button(_("Exportar"), variant="quiet")
        export.clicked.connect(lambda _checked=False: self.export_requested.emit(bundle))
        layout.addWidget(export)
        if bundle.kind == USER_MARKER:
            delete = button(_("Remover"), variant="danger")
            delete.clicked.connect(lambda _checked=False: self.delete_requested.emit(bundle))
            layout.addWidget(delete)
        return row

    @staticmethod
    def _kind_label(kind: str) -> str:
        if kind == USER_MARKER:
            return _("Manual")
        if kind == "migration":
            return _("Antes de atualizar")
        if kind == PRE_RESTORE_MARKER:
            return _("Antes de restaurar")
        return _("Do sistema")


class SubjectFilesDialog(QDialog):
    """Read-only overview of one subject's organised files."""

    open_requested = Signal(object)
    reindex_requested = Signal(int)
    move_requested = Signal(int)

    def __init__(
        self,
        subject: Subject,
        documents: Sequence[FiledDocument],
        folder_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.subject = subject
        self.documents = tuple(documents)
        self.folder_path = folder_path
        self.setWindowTitle(_("Ficheiros de {name}").format(name=subject.name))
        self.setModal(True)
        self.setMinimumSize(620, 540)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(12)
        title = subject.name + (f"  ·  {subject.code}" if subject.code else "")
        root.addWidget(label(title, "PageTitle"))
        count = len(self.documents)
        total_bytes = sum(document.size for document in self.documents)
        root.addWidget(
            label(
                _("{count} ficheiro · {size}").format(count=count, size=format_size(total_bytes))
                if count == 1
                else _("{count} ficheiros · {size}").format(
                    count=count, size=format_size(total_bytes)
                ),
                "PageSubtitle",
            )
        )
        kind_parts = [
            f"{kind} {sum(1 for document in self.documents if document.kind == kind)}"
            for kind in FILE_KINDS
            if any(document.kind == kind for document in self.documents)
        ]
        if kind_parts:
            root.addWidget(label(" · ".join(kind_parts), "Muted"))

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.content = QWidget()
        self.list_layout = QVBoxLayout(self.content)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(8)
        self.area.setWidget(self.content)
        root.addWidget(self.area, 1)
        self.pending_labels: dict[int, QLabel] = {}
        self.reindex_buttons: dict[int, QPushButton] = {}
        self.move_buttons: dict[int, QPushButton] = {}
        self.set_documents(documents)

        actions = QHBoxLayout()
        actions.addStretch(1)
        folder_button = button(_("Abrir pasta"), variant="quiet")
        folder_button.clicked.connect(
            lambda checked=False: self.open_requested.emit(self.folder_path)
        )
        close = button(_("Fechar"))
        close.clicked.connect(self.reject)
        actions.addWidget(folder_button)
        actions.addWidget(close)
        root.addLayout(actions)

    def set_documents(self, documents: Sequence[FiledDocument]) -> None:
        """Rebuild the rows from fresh data, preserving the scroll position."""

        self.documents = tuple(documents)
        self.pending_labels.clear()
        self.reindex_buttons.clear()
        self.move_buttons.clear()
        position = self.area.verticalScrollBar().value()
        clear_layout(self.list_layout)
        if not self.documents:
            empty = label(
                _("Ainda não há ficheiros organizados nesta disciplina."),
                "Muted",
            )
            empty.setWordWrap(True)
            self.list_layout.addWidget(empty)
        for document in self.documents:
            self.list_layout.addWidget(self._row(document))
        self.list_layout.addStretch(1)
        self.area.verticalScrollBar().setValue(position)

    def mark_reindexing(self, file_id: int) -> None:
        """Show that one document is being extracted again."""

        button = self.reindex_buttons.get(file_id)
        if button is not None:
            button.setEnabled(False)
        self.set_row_notice(file_id, _("A reindexar…"))

    def mark_moving(self, file_id: int) -> None:
        """Show that one document is being moved to another folder."""

        button = self.move_buttons.get(file_id)
        if button is not None:
            button.setEnabled(False)
        self.set_row_notice(file_id, _("A mover…"))

    def set_row_notice(self, file_id: int, message: str) -> None:
        """Attach one transient status message to a document row."""

        note = self.pending_labels.get(file_id)
        if note is not None:
            note.setText(message)
            note.show()

    def _row(self, document: FiledDocument) -> QFrame:
        row = QFrame()
        row.setObjectName("ListRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14, 10, 10, 10)
        row_layout.setSpacing(12)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        name = label(document.current_path.name, "RowTitle")
        name.setWordWrap(True)
        copy.addWidget(name)
        copy.addWidget(
            label(
                _("{kind} · {size} · organizado {date}").format(
                    kind=document.kind,
                    size=format_size(document.size),
                    date=document.filed_at.strftime("%d/%m/%Y"),
                ),
                "Muted",
            )
        )
        if document.index_state == "failed":
            failed_note = label(
                _("Falha na indexação — o ficheiro continua pesquisável pelo nome."),
                "Muted",
            )
            failed_note.setWordWrap(True)
            copy.addWidget(failed_note)
        pending_note = label("", "Muted")
        pending_note.setWordWrap(True)
        pending_note.hide()
        copy.addWidget(pending_note)
        self.pending_labels[document.id] = pending_note
        row_layout.addLayout(copy, 1)
        reindex_button = button(_("Reindexar"), variant="quiet")
        reindex_button.clicked.connect(
            lambda checked=False, file_id=document.id: self.reindex_requested.emit(file_id)
        )
        self.reindex_buttons[document.id] = reindex_button
        row_layout.addWidget(reindex_button)
        move_button = button(_("Mover"))
        move_button.clicked.connect(
            lambda checked=False, file_id=document.id: self.move_requested.emit(file_id)
        )
        self.move_buttons[document.id] = move_button
        row_layout.addWidget(move_button)
        open_button = button(_("Abrir"), variant="quiet")
        open_button.clicked.connect(
            lambda checked=False, path=document.current_path: self.open_requested.emit(path)
        )
        row_layout.addWidget(open_button)
        return row


class MoveDocumentDialog(QDialog):
    """Choose the new subject and type folder for a catalogued document."""

    def __init__(
        self,
        document: FiledDocument,
        subjects: Sequence[Subject],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.setWindowTitle(_("Mover ficheiro"))
        self.setModal(True)
        self.setMinimumWidth(430)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(12)
        root.addWidget(label(_("Mover ficheiro"), "PageTitle"))
        root.addWidget(label(document.current_path.name, "RowTitle"))

        form = QFormLayout()
        self.subject_combo = QComboBox()
        for subject in subjects:
            self.subject_combo.addItem(subject.name, subject.id)
        current_subject = self.subject_combo.findData(document.subject_id)
        if current_subject >= 0:
            self.subject_combo.setCurrentIndex(current_subject)
        form.addRow(_("Disciplina"), self.subject_combo)
        self.kind_combo = QComboBox()
        for kind in FILE_KINDS:
            self.kind_combo.addItem(kind)
        current_kind = self.kind_combo.findText(document.kind)
        if current_kind >= 0:
            self.kind_combo.setCurrentIndex(current_kind)
        form.addRow(_("Tipo"), self.kind_combo)
        root.addLayout(form)

        self.hint_label = label(_("Escolhe outra disciplina ou outro tipo para mover."), "Muted")
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)
        self.error_label = label("", "ErrorText")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = button(_("Cancelar"))
        cancel.clicked.connect(self.reject)
        self.move_button = button(_("Mover"), variant="primary")
        self.move_button.clicked.connect(self._confirm)
        actions.addWidget(cancel)
        actions.addWidget(self.move_button)
        root.addLayout(actions)

        self.subject_combo.currentIndexChanged.connect(self._update_move_button)
        self.kind_combo.currentIndexChanged.connect(self._update_move_button)
        self._update_move_button()

    def selection(self) -> tuple[int, str]:
        """Return the chosen subject id and document type."""

        return int(self.subject_combo.currentData()), self.kind_combo.currentText()

    def show_error(self, message: str) -> None:
        """Explain a recoverable failure without closing the dialog."""

        self.error_label.setText(message)

    def _update_move_button(self) -> None:
        subject_id, kind = self.selection()
        changed = (subject_id, kind) != (self.document.subject_id, self.document.kind)
        self.move_button.setEnabled(changed)
        self.hint_label.setVisible(not changed)
        if changed:
            self.error_label.clear()

    def _confirm(self) -> None:
        subject_id, kind = self.selection()
        if subject_id == self.document.subject_id and kind == self.document.kind:
            return
        self.accept()
