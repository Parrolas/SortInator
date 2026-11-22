"""Fast, keyboard-friendly filing prompt for newly completed downloads."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import (
    QDate,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QCloseEvent, QColor, QCursor, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QBoxLayout,
    QButtonGroup,
    QCheckBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from organizador.classifier import extract_due_date
from organizador.filer import render_final_name
from organizador.i18n import _
from organizador.models import FILE_KINDS, FiledDocument, FilingGuess, InboxItem, Subject
from organizador.paths import create_subdirectory, existing_subdirectory
from organizador.ui.widgets import (
    ElidedChipButton,
    ElidedLabel,
    button,
    clear_layout,
    format_size,
    label,
)

_PROMPT_WIDTH = 570
_SCREEN_MARGIN = 18


def _set_elided_text(widget: ElidedLabel, text: str) -> None:
    widget.setText(text)
    widget.setToolTip(text)
    widget.setAccessibleName(text)


class _SubfolderPicker(QDialog):
    """Browse one level at a time and optionally create a folder there."""

    def __init__(
        self,
        root: Path,
        base_parts: tuple[str, ...],
        breadcrumb: tuple[str, ...],
        subfolder: tuple[str, ...],
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Escolher subpasta…"))
        self.resize(510, 310)
        self.root = root
        self.base_parts = base_parts
        self.breadcrumb = breadcrumb
        self.subfolder = subfolder

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.location = ElidedLabel("")
        header.addWidget(self.location, 1)
        self.new_folder_button = button(_("Nova pasta…"), variant="quiet")
        self.new_folder_button.setAutoDefault(False)
        self.new_folder_button.clicked.connect(self._show_folder_editor)
        header.addWidget(self.new_folder_button)
        layout.addLayout(header)

        self.folder_editor = QWidget()
        editor_layout = QHBoxLayout(self.folder_editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        self.folder_name_edit = QLineEdit()
        self.folder_name_edit.setPlaceholderText(_("Nome da pasta"))
        self.folder_name_edit.setAccessibleName(_("Nome da pasta"))
        self.folder_name_edit.returnPressed.connect(self._create_folder)
        editor_layout.addWidget(self.folder_name_edit, 1)
        self.create_folder_button = button(_("Criar pasta"))
        self.create_folder_button.setAutoDefault(False)
        self.create_folder_button.clicked.connect(self._create_folder)
        editor_layout.addWidget(self.create_folder_button)
        layout.addWidget(self.folder_editor)

        self.folders = QListWidget()
        self.folders.setAccessibleName(_("Subpastas"))
        self.folders.itemDoubleClicked.connect(lambda _item: self._open_selected())
        layout.addWidget(self.folders, 1)
        self.status = label("", "Muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        actions = QHBoxLayout()
        self.back_button = button(_("Pasta acima"))
        self.back_button.clicked.connect(self._up)
        self.open_button = button(_("Abrir pasta"))
        self.open_button.clicked.connect(self._open_selected)
        self.folders.currentItemChanged.connect(
            lambda current, _previous: self.open_button.setEnabled(current is not None)
        )
        cancel = button(_("Cancelar"))
        cancel.clicked.connect(self.reject)
        self.use_button = button(_("Usar esta pasta"), variant="primary")
        self.use_button.clicked.connect(self.accept)
        for control in (self.back_button, self.open_button, cancel, self.use_button):
            control.setAutoDefault(False)
        actions.addWidget(self.back_button)
        actions.addWidget(self.open_button)
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(self.use_button)
        layout.addLayout(actions)
        self._refresh()

    def _open_selected(self) -> None:
        item = self.folders.currentItem()
        if item is not None:
            self.subfolder += (item.text(),)
            self._refresh()

    def _up(self) -> None:
        self.subfolder = self.subfolder[:-1]
        self._refresh()

    def _show_folder_editor(self) -> None:
        self.folder_editor.show()
        self.folder_name_edit.setFocus()

    def _create_folder(self) -> None:
        if self.folder_editor.isHidden():
            return
        name = self.folder_name_edit.text()
        try:
            create_subdirectory(self.root, self.base_parts + self.subfolder, name)
        except ValueError:
            self.status.setText(_("Escolhe um nome de pasta válido."))
        except FileExistsError:
            self.status.setText(_("Já existe um ficheiro ou uma pasta com este nome."))
        except OSError:
            self.status.setText(_("Não foi possível criar a pasta."))
        else:
            self.subfolder += (name,)
            self._refresh()
            self.use_button.setFocus()
            return
        self.folder_name_edit.setFocus()

    def _refresh(self) -> None:
        _set_elided_text(self.location, " → ".join(self.breadcrumb + self.subfolder))
        self.folder_editor.hide()
        self.folder_name_edit.clear()
        self.back_button.setEnabled(bool(self.subfolder))
        self.folders.clear()
        self.open_button.setEnabled(False)
        parts = self.base_parts + self.subfolder
        try:
            directory = existing_subdirectory(self.root, parts)
            children = sorted(directory.iterdir(), key=lambda path: path.name.casefold())
        except OSError:
            self.status.setText(_("Não foi possível abrir esta pasta."))
            self.use_button.setEnabled(False)
            self.new_folder_button.setEnabled(False)
            return
        for child in children:
            try:
                existing_subdirectory(directory, (child.name,))
            except OSError:
                continue
            self.folders.addItem(child.name)
        self.status.setText("" if self.folders.count() else _("Esta pasta não tem subpastas."))
        self.use_button.setEnabled(True)
        self.new_folder_button.setEnabled(True)


class FilingPrompt(QWidget):
    """Collect a subject/type decision without interrupting the whole desktop."""

    filing_requested = Signal(int, int, str, str, bool, object, object, object)
    later_requested = Signal(int)
    return_requested = Signal(int)
    reveal_requested = Signal(object)

    def __init__(
        self,
        timeout_seconds: int = 45,
        *,
        auto_close: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.timeout_seconds = timeout_seconds
        self.auto_close = auto_close
        self.current_item_id: int | None = None
        self.selected_subject_id: int | None = None
        self.remaining = timeout_seconds
        self._shortcuts: list[QShortcut] = []
        self._closing_by_action = False

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        outer = QVBoxLayout(self)
        self._outer_layout = outer
        outer.setContentsMargins(22, 22, 22, 28)
        self.card = QFrame()
        self.card.setObjectName("PromptCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        self._card_layout = card_layout
        card_layout.setContentsMargins(22, 20, 22, 19)
        card_layout.setSpacing(14)

        top = QHBoxLayout()
        self._header_layout = top
        top.setSpacing(12)
        heading_copy = QVBoxLayout()
        heading_copy.setSpacing(2)
        heading_copy.addWidget(ElidedLabel(_("Novo material de estudo"), "SectionTitle"))
        self.meta_label = ElidedLabel("", "Muted")
        heading_copy.addWidget(self.meta_label)
        top.addLayout(heading_copy, 1)
        self.countdown_label = label("", "Muted")
        top.addWidget(self.countdown_label, 0, Qt.AlignmentFlag.AlignTop)
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("PromptClose")
        self.close_button.setToolTip(_("Não é da universidade: devolve o ficheiro"))
        self.close_button.setAccessibleName(_("Não é da universidade: devolve o ficheiro"))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self._return)
        top.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        card_layout.addLayout(top)

        self.body_scroll = QScrollArea()
        self.body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body_scroll.setWidgetResizable(True)
        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(card_layout.spacing())
        self.body_scroll.setWidget(body)
        card_layout.addWidget(self.body_scroll, 1)

        self.duplicate_banner = QFrame()
        self.duplicate_banner.setObjectName("Panel")
        banner_layout = QVBoxLayout(self.duplicate_banner)
        banner_layout.setContentsMargins(12, 10, 12, 10)
        banner_layout.setSpacing(6)
        self.duplicate_label = label("", "Muted")
        self.duplicate_label.setTextFormat(Qt.TextFormat.PlainText)
        self.duplicate_label.setWordWrap(True)
        banner_layout.addWidget(self.duplicate_label)
        banner_row = QHBoxLayout()
        self.reveal_duplicate_button = button(_("Ver existente"), variant="quiet")
        self.reveal_duplicate_button.clicked.connect(self._reveal_duplicate)
        banner_row.addWidget(self.reveal_duplicate_button)
        self.replace_check = QCheckBox(_("Substituir a versão anterior"))
        self.replace_check.setToolTip(
            _("A versão atual fica na pasta com o sufixo «versão anterior».")
        )
        banner_row.addWidget(self.replace_check)
        banner_row.addStretch(1)
        banner_layout.addLayout(banner_row)
        self.duplicate_banner.hide()
        self._body_layout.addWidget(self.duplicate_banner)
        self._duplicate: FiledDocument | None = None

        self.name_edit = QLineEdit()
        self.name_edit.setAccessibleName(_("Nome final do ficheiro"))
        self.name_edit.setToolTip(_("Podes corrigir o nome; a extensão original é preservada"))
        self._body_layout.addWidget(self.name_edit)
        self._programmatic_name = False
        self._custom_name = False
        self._prompt_subjects: list[Subject] = []
        self._prompt_template = "{nome_original}"
        self._prompt_original_name = ""
        self._prompt_when = datetime.now()
        self._university_root: Path | None = None
        self._subfolder: tuple[str, ...] = ()
        self.name_edit.textChanged.connect(self._name_text_changed)

        subject_header = QHBoxLayout()
        subject_header.addWidget(label(_("Disciplina"), "RowTitle"))
        subject_header.addStretch(1)
        self.guess_label = label("", "Muted")
        subject_header.addWidget(self.guess_label)
        self._body_layout.addLayout(subject_header)
        self.subject_grid = QGridLayout()
        self.subject_grid.setHorizontalSpacing(8)
        self.subject_grid.setVerticalSpacing(8)
        self._body_layout.addLayout(self.subject_grid)
        self.subject_group = QButtonGroup(self)
        self.subject_group.setExclusive(True)
        self.subject_group.idClicked.connect(self._subject_clicked)

        self._body_layout.addWidget(label(_("Tipo de documento"), "RowTitle"))
        type_row = QHBoxLayout()
        type_row.setSpacing(7)
        self.type_group = QButtonGroup(self)
        self.type_group.setExclusive(True)
        self.type_group.idToggled.connect(self._option_changed)
        self.type_buttons: dict[str, QPushButton] = {}
        for kind in FILE_KINDS:
            type_button = QPushButton(kind)
            type_button.setCheckable(True)
            type_button.setProperty("chip", "true")
            type_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.type_group.addButton(type_button)
            self.type_buttons[kind] = type_button
            type_row.addWidget(type_button)
        self._body_layout.addLayout(type_row)

        destination_row = QHBoxLayout()
        self.destination_label = ElidedLabel("", "Muted")
        destination_row.addWidget(self.destination_label, 1)
        self.subfolder_button = button(_("Escolher subpasta…"), variant="quiet")
        self.subfolder_button.clicked.connect(self._choose_subfolder)
        destination_row.addWidget(self.subfolder_button)
        self._body_layout.addLayout(destination_row)

        task_row = QHBoxLayout()
        self.task_check = QCheckBox(_("Criar tarefa"))
        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDisplayFormat("dd/MM/yyyy")
        self.due_edit.setMinimumWidth(150)
        self.due_edit.setEnabled(False)
        self.task_check.toggled.connect(self.due_edit.setEnabled)
        task_row.addWidget(self.task_check)
        task_row.addWidget(self.due_edit)
        task_row.addStretch(1)
        self._body_layout.addLayout(task_row)

        self.error_label = label("", "ErrorText")
        self.error_label.setWordWrap(True)
        self._body_layout.addWidget(self.error_label)

        actions = QHBoxLayout()
        self._actions_layout = actions
        actions.setSpacing(8)
        self.return_button = button(_("Não é da universidade"), variant="quiet")
        self.return_button.clicked.connect(self._return)
        later = button(_("Mais tarde"))
        later.clicked.connect(self._later)
        self.confirm_button = button(_("Organizar ficheiro"), variant="primary")
        self.confirm_button.setEnabled(False)
        self.confirm_button.clicked.connect(self._confirm)
        actions.addWidget(self.return_button)
        actions.addStretch(1)
        actions.addWidget(later)
        actions.addWidget(self.confirm_button)
        card_layout.addLayout(actions)

        self.animation = QPropertyAnimation(self, b"pos", self)
        self.animation.setDuration(190)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self._later)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self).activated.connect(self._confirm)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self).activated.connect(self._confirm)

    def show_item(
        self,
        item: InboxItem,
        subjects: list[Subject],
        guess: FilingGuess,
        name_template: str = "{nome_original}",
        duplicate: FiledDocument | None = None,
        *,
        university_root: Path | None = None,
    ) -> None:
        """Populate and reveal the prompt for an inbox item."""

        self.current_item_id = item.id
        self.selected_subject_id = guess.subject_id
        self.error_label.clear()
        self._custom_name = False
        self._duplicate = duplicate
        self.replace_check.setChecked(False)
        self._prompt_subjects = list(subjects)
        self._prompt_template = name_template
        self._prompt_original_name = item.original_name
        self._prompt_when = item.detected_at
        self._university_root = university_root
        self._subfolder = ()
        origin_folder = item.original_path.parent.name or "Downloads"
        _set_elided_text(
            self.meta_label,
            _("{size}  ·  recebido da pasta {folder}").format(
                size=format_size(item.size), folder=origin_folder
            ),
        )
        self.guess_label.setText(
            _("Sugestão {percent}%").format(percent=guess.confidence)
            if guess.subject_id is not None
            else _("Escolhe uma opção")
        )

        for old_button in self.subject_group.buttons():
            self.subject_group.removeButton(old_button)
        clear_layout(self.subject_grid)
        for shortcut in self._shortcuts:
            shortcut.setParent(None)
            shortcut.deleteLater()
        self._shortcuts.clear()
        for index, subject in enumerate(subjects, start=1):
            display_name = f"{index}  {subject.name}" if index <= 9 else subject.name
            subject_button = ElidedChipButton(display_name)
            subject_button.setCheckable(True)
            subject_button.setProperty("chip", "true")
            subject_button.setCursor(Qt.CursorShape.PointingHandCursor)
            tooltip_parts = [display_name]
            if subject.code:
                tooltip_parts.append(subject.code)
            keywords = ", ".join(subject.keywords)
            if keywords:
                tooltip_parts.append(keywords)
            subject_button.setToolTip("\n".join(tooltip_parts))
            self.subject_group.addButton(subject_button, subject.id)
            self.subject_grid.addWidget(subject_button, (index - 1) // 3, (index - 1) % 3)
            if subject.id == guess.subject_id:
                subject_button.setChecked(True)
            if index <= 9:
                shortcut = QShortcut(QKeySequence(str(index)), self)
                shortcut.activated.connect(
                    lambda subject_id=subject.id, target=subject_button: self._choose_subject(
                        subject_id, target
                    )
                )
                self._shortcuts.append(shortcut)
        for kind, type_button in self.type_buttons.items():
            type_button.setChecked(kind == guess.kind)
        if not any(type_button.isChecked() for type_button in self.type_buttons.values()):
            self.type_buttons["Outros"].setChecked(True)
        self._render_name()
        self._update_destination()
        self.name_edit.selectAll()
        self._update_duplicate_banner()

        inferred_due = extract_due_date(item.original_name)
        self.task_check.setChecked(inferred_due is not None)
        due = inferred_due or (date.today() + timedelta(days=7))
        self.due_edit.setDate(QDate(due.year, due.month, due.day))
        self.confirm_button.setEnabled(self.selected_subject_id is not None)

        self.remaining = self.timeout_seconds
        self._update_countdown()
        self._sync_countdown()
        self._place_and_animate()
        self.body_scroll.verticalScrollBar().setValue(0)
        self.body_scroll.horizontalScrollBar().setValue(0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.name_edit.setFocus()

    def set_duplicate(self, duplicate: FiledDocument | None) -> None:
        """Attach a duplicate found after the prompt was already shown."""

        if self.current_item_id is None:
            return
        self._duplicate = duplicate
        self._update_duplicate_banner()
        if self.isVisible():
            self._place()

    def show_error(self, message: str) -> None:
        """Keep the prompt open and explain a recoverable failure."""

        self.error_label.setText(message)
        self.timer.stop()
        self.confirm_button.setEnabled(self.selected_subject_id is not None)
        self._place()
        self.show()
        self.raise_()
        self.body_scroll.ensureWidgetVisible(self.error_label)

    def set_timeout(self, seconds: int, *, auto_close: bool) -> None:
        """Update auto-close behaviour for future prompts."""

        self.timeout_seconds = max(10, seconds)
        self.auto_close = auto_close

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.current_item_id is not None and not self._closing_by_action:
            event.ignore()
            self._later()
            return
        event.accept()

    def _subject_clicked(self, subject_id: int) -> None:
        if self.selected_subject_id != subject_id:
            self._subfolder = ()
        self.selected_subject_id = subject_id
        self.confirm_button.setEnabled(True)
        self._update_destination()
        self._render_name()
        self._update_duplicate_banner()

    def _option_changed(self, _identifier: int, checked: bool) -> None:
        if not checked:
            return
        self._subfolder = ()
        self._update_destination()
        self._render_name()
        self._update_duplicate_banner()

    def _selected_subject(self) -> Subject | None:
        return next(
            (
                subject
                for subject in self._prompt_subjects
                if subject.id == self.selected_subject_id
            ),
            None,
        )

    def _selected_kind(self) -> str:
        checked = self.type_group.checkedButton()
        return checked.text() if checked is not None else "Outros"

    def _update_destination(self) -> None:
        subject = self._selected_subject()
        available = self._university_root is not None
        self.subfolder_button.setVisible(available)
        self.subfolder_button.setEnabled(subject is not None)
        self.destination_label.setVisible(available and subject is not None)
        if subject is not None:
            path = " → ".join((subject.name, self._selected_kind(), *self._subfolder))
            _set_elided_text(self.destination_label, _("Destino: {path}").format(path=path))

    def _choose_subfolder(self) -> None:
        subject = self._selected_subject()
        root = self._university_root
        item_id = self.current_item_id
        if subject is None or root is None or item_id is None:
            return
        kind = self._selected_kind()
        picker = _SubfolderPicker(
            root, (subject.folder_name, kind), (subject.name, kind), self._subfolder, self
        )
        resume_countdown = self.timer.isActive()
        self.timer.stop()
        try:
            accepted = picker.exec() == QDialog.DialogCode.Accepted
            if accepted and self.current_item_id == item_id:
                self._subfolder = picker.subfolder
                self._update_destination()
        finally:
            picker.deleteLater()
            if resume_countdown and self.current_item_id == item_id and self.isVisible():
                self.timer.start()

    def _update_duplicate_banner(self) -> None:
        """Explain a duplicate match and enable replacement only on its folder."""

        duplicate = self._duplicate
        if duplicate is None:
            self.duplicate_banner.hide()
            self.replace_check.setChecked(False)
            return
        subject = next(
            (subject for subject in self._prompt_subjects if subject.id == duplicate.subject_id),
            None,
        )
        parts = [subject.name, duplicate.kind] if subject is not None else [duplicate.kind]
        if subject is not None and self._university_root is not None:
            base = self._university_root / subject.folder_name / duplicate.kind
            if duplicate.current_path.parent.is_relative_to(base):
                parts.extend(duplicate.current_path.parent.relative_to(base).parts)
        location = " / ".join(parts)
        self.duplicate_label.setText(
            _("Já tens este ficheiro em {location}: {name}").format(
                location=location, name=duplicate.current_path.name
            )
        )
        checked = self.type_group.checkedButton()
        same_destination = (
            duplicate.subject_id == self.selected_subject_id
            and checked is not None
            and checked.text() == duplicate.kind
        )
        self.replace_check.setEnabled(same_destination)
        if not same_destination:
            self.replace_check.setChecked(False)
        self.duplicate_banner.show()

    def _reveal_duplicate(self) -> None:
        if self._duplicate is not None:
            self.reveal_requested.emit(self._duplicate.current_path)

    def _name_text_changed(self) -> None:
        if self._programmatic_name:
            return
        self._custom_name = True

    def _render_name(self) -> None:
        """Regenerate the filename preview while the user has not taken over."""

        if self._custom_name:
            return
        template_subject = self._selected_subject()
        self._programmatic_name = True
        try:
            self.name_edit.setText(
                render_final_name(
                    self._prompt_template,
                    subject_name=template_subject.name if template_subject else "",
                    subject_code=template_subject.code if template_subject else "",
                    kind=self._selected_kind(),
                    original_name=self._prompt_original_name,
                    when=self._prompt_when,
                )
            )
        finally:
            self._programmatic_name = False

    def _choose_subject(self, subject_id: int, target: QPushButton) -> None:
        target.setChecked(True)
        self._subject_clicked(subject_id)

    def _confirm(self) -> None:
        if self.current_item_id is None:
            return
        if self.selected_subject_id is None:
            self.show_error(_("Escolhe uma disciplina antes de organizar."))
            return
        kind = self._selected_kind()
        item_id = self.current_item_id
        subject_id = self.selected_subject_id
        create_task = self.task_check.isChecked()
        due_date = self.due_edit.date().toPython() if create_task else None
        replace_document_id = (
            self._duplicate.id
            if self.replace_check.isChecked() and self._duplicate is not None
            else None
        )
        self._finish_action()
        self.filing_requested.emit(
            item_id,
            subject_id,
            kind,
            self.name_edit.text().strip(),
            create_task,
            due_date,
            replace_document_id,
            self._subfolder,
        )

    def _later(self) -> None:
        if self.current_item_id is None:
            return
        item_id = self.current_item_id
        self._finish_action()
        self.later_requested.emit(item_id)

    def _return(self) -> None:
        if self.current_item_id is None:
            return
        item_id = self.current_item_id
        self._finish_action()
        self.return_requested.emit(item_id)

    def _finish_action(self) -> None:
        self.timer.stop()
        self.current_item_id = None
        self.selected_subject_id = None
        self._closing_by_action = True
        self.hide()
        self._closing_by_action = False

    def _sync_countdown(self) -> None:
        """Start or stop the auto-close countdown to match the setting."""

        self.countdown_label.setVisible(self.auto_close)
        if self.auto_close:
            self.timer.start()
        else:
            self.timer.stop()

    def _tick(self) -> None:
        self.remaining -= 1
        if self.remaining <= 0:
            self._later()
            return
        self._update_countdown()

    def _update_countdown(self) -> None:
        self.countdown_label.setText(_("Mais tarde em {count}s").format(count=self.remaining))

    def _work_area(self, *, new_item: bool = False) -> QRect:
        screen = self.screen()
        if new_item:
            screen = QGuiApplication.screenAt(QCursor.pos()) or screen
        return screen.availableGeometry()

    def _fit_to_work_area(self, geometry: QRect) -> QPoint:
        """Measure the content at its actual width and cap the window to the monitor."""

        self.animation.stop()
        self.ensurePolished()
        margin = _SCREEN_MARGIN
        width = min(_PROMPT_WIDTH, max(1, geometry.width() - 2 * margin))
        outer = self._outer_layout.contentsMargins()
        card = self._card_layout.contentsMargins()
        frame = self.card.contentsMargins()
        horizontal_insets = sum(
            margins.left() + margins.right() for margins in (outer, card, frame)
        )
        body_width = max(1, width - horizontal_insets)

        actions = self._actions_layout
        # On an unusually narrow display the header's close button still offers Return.
        self.return_button.setVisible(self.return_button.minimumSizeHint().width() <= body_width)
        actions.setDirection(QBoxLayout.Direction.LeftToRight)
        if actions.minimumSize().width() > body_width:
            actions.setDirection(QBoxLayout.Direction.TopToBottom)

        chrome_height = (
            sum(margins.top() + margins.bottom() for margins in (outer, card, frame))
            + self._header_layout.sizeHint().height()
            + actions.sizeHint().height()
            + 2 * self._card_layout.spacing()
        )
        body_height = self._body_layout.totalHeightForWidth(body_width)
        if body_height < 0:
            body_height = self._body_layout.sizeHint().height()
        height = min(chrome_height + body_height, max(1, geometry.height() - 2 * margin))
        self.setFixedWidth(width)
        self.resize(width, height)

        return QPoint(
            geometry.left() + min(margin, max(0, geometry.width() - self.width())),
            max(geometry.top(), geometry.bottom() + 1 - self.height() - margin),
        )

    def _place(self) -> None:
        self.move(self._fit_to_work_area(self._work_area()))

    def _place_and_animate(self) -> None:
        geometry = self._work_area(new_item=True)
        target = self._fit_to_work_area(geometry)
        slide = min(28, max(0, geometry.bottom() + 1 - target.y() - self.height()))
        start = target + QPoint(0, slide)
        self.move(start)
        self.animation.setStartValue(start)
        self.animation.setEndValue(target)
        self.animation.start()
