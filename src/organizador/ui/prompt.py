"""Fast, keyboard-friendly filing prompt for newly completed downloads."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QDate, QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QColor, QCursor, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDateEdit,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from organizador.classifier import extract_due_date
from organizador.filer import render_final_name
from organizador.i18n import _
from organizador.models import FILE_KINDS, FiledDocument, FilingGuess, InboxItem, Subject
from organizador.ui.widgets import ElidedChipButton, button, clear_layout, format_size, label


class FilingPrompt(QWidget):
    """Collect a subject/type decision without interrupting the whole desktop."""

    filing_requested = Signal(int, int, str, str, bool, object, object)
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
        self.setFixedWidth(570)

        outer = QVBoxLayout(self)
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
        card_layout.setContentsMargins(22, 20, 22, 19)
        card_layout.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(12)
        heading_copy = QVBoxLayout()
        heading_copy.setSpacing(2)
        heading_copy.addWidget(label(_("Novo material de estudo"), "SectionTitle"))
        self.meta_label = label("", "Muted")
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

        self.duplicate_banner = QFrame()
        self.duplicate_banner.setObjectName("Panel")
        banner_layout = QVBoxLayout(self.duplicate_banner)
        banner_layout.setContentsMargins(12, 10, 12, 10)
        banner_layout.setSpacing(6)
        self.duplicate_label = label("", "Muted")
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
        card_layout.addWidget(self.duplicate_banner)
        self._duplicate: FiledDocument | None = None

        self.name_edit = QLineEdit()
        self.name_edit.setAccessibleName(_("Nome final do ficheiro"))
        self.name_edit.setToolTip(_("Podes corrigir o nome; a extensão original é preservada"))
        card_layout.addWidget(self.name_edit)
        self._programmatic_name = False
        self._custom_name = False
        self._prompt_subjects: list[Subject] = []
        self._prompt_template = "{nome_original}"
        self._prompt_original_name = ""
        self._prompt_when = datetime.now()
        self.name_edit.textChanged.connect(self._name_text_changed)

        subject_header = QHBoxLayout()
        subject_header.addWidget(label(_("Disciplina"), "RowTitle"))
        subject_header.addStretch(1)
        self.guess_label = label("", "Muted")
        subject_header.addWidget(self.guess_label)
        card_layout.addLayout(subject_header)
        self.subject_grid = QGridLayout()
        self.subject_grid.setHorizontalSpacing(8)
        self.subject_grid.setVerticalSpacing(8)
        card_layout.addLayout(self.subject_grid)
        self.subject_group = QButtonGroup(self)
        self.subject_group.setExclusive(True)
        self.subject_group.idClicked.connect(self._subject_clicked)

        card_layout.addWidget(label(_("Tipo de documento"), "RowTitle"))
        type_row = QHBoxLayout()
        type_row.setSpacing(7)
        self.type_group = QButtonGroup(self)
        self.type_group.setExclusive(True)
        self.type_group.idClicked.connect(self._option_changed)
        self.type_buttons: dict[str, QPushButton] = {}
        for kind in FILE_KINDS:
            type_button = QPushButton(kind)
            type_button.setCheckable(True)
            type_button.setProperty("chip", "true")
            type_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.type_group.addButton(type_button)
            self.type_buttons[kind] = type_button
            type_row.addWidget(type_button)
        card_layout.addLayout(type_row)

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
        card_layout.addLayout(task_row)

        self.error_label = label("", "ErrorText")
        self.error_label.setWordWrap(True)
        card_layout.addWidget(self.error_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        not_university = button(_("Não é da universidade"), variant="quiet")
        not_university.clicked.connect(self._return)
        later = button(_("Mais tarde"))
        later.clicked.connect(self._later)
        self.confirm_button = button(_("Organizar ficheiro"), variant="primary")
        self.confirm_button.setEnabled(False)
        self.confirm_button.clicked.connect(self._confirm)
        actions.addWidget(not_university)
        actions.addStretch(1)
        actions.addWidget(later)
        actions.addWidget(self.confirm_button)
        card_layout.addLayout(actions)

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
        origin_folder = item.original_path.parent.name or "Downloads"
        self.meta_label.setText(
            _("{size}  ·  recebido da pasta {folder}").format(
                size=format_size(item.size), folder=origin_folder
            )
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
        self.show()
        self.raise_()
        self.activateWindow()
        self.name_edit.setFocus()

    def show_error(self, message: str) -> None:
        """Keep the prompt open and explain a recoverable failure."""

        self.error_label.setText(message)
        self.timer.stop()
        self.confirm_button.setEnabled(self.selected_subject_id is not None)
        self.show()
        self.raise_()

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
        self.selected_subject_id = subject_id
        self.confirm_button.setEnabled(True)
        self._render_name()
        self._update_duplicate_banner()

    def _option_changed(self, _identifier: int) -> None:
        self._render_name()
        self._update_duplicate_banner()

    def _update_duplicate_banner(self) -> None:
        """Explain a duplicate match and enable replacement only on its folder."""

        duplicate = self._duplicate
        if duplicate is None:
            self.duplicate_banner.hide()
            self.replace_check.setChecked(False)
            return
        subject_name = next(
            (
                subject.name
                for subject in self._prompt_subjects
                if subject.id == duplicate.subject_id
            ),
            "",
        )
        location = f"{subject_name} / {duplicate.kind}" if subject_name else duplicate.kind
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
        template_subject = next(
            (
                subject
                for subject in self._prompt_subjects
                if subject.id == self.selected_subject_id
            ),
            None,
        )
        checked = self.type_group.checkedButton()
        kind = checked.text() if checked is not None else "Outros"
        self._programmatic_name = True
        try:
            self.name_edit.setText(
                render_final_name(
                    self._prompt_template,
                    subject_name=template_subject.name if template_subject else "",
                    subject_code=template_subject.code if template_subject else "",
                    kind=kind,
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
        if self.current_item_id is None or self.selected_subject_id is None:
            self.error_label.setText(_("Escolhe uma disciplina antes de organizar."))
            return
        checked = self.type_group.checkedButton()
        kind = checked.text() if checked is not None else "Outros"
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

    def _place_and_animate(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or self.screen()
        geometry = screen.availableGeometry()
        self.adjustSize()
        target = QPoint(
            geometry.left() + 18,
            geometry.bottom() - self.height() - 18,
        )
        self.move(target + QPoint(0, 28))
        self.animation = QPropertyAnimation(self, b"pos", self)
        self.animation.setDuration(190)
        self.animation.setStartValue(target + QPoint(0, 28))
        self.animation.setEndValue(target)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.start()
