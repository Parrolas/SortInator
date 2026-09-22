"""Main desktop shell.

THESIS: A campus records-office docket makes each incoming document visibly
move from intake to a named subject; it refuses the generic metric-card
dashboard. OWN-WORLD: deepest-ink navigation, a night canvas, raised docket
surfaces, teal action stamps, and thin rules. STORY: see what arrived, decide
its destination, then retrieve it or attach a deadline. FIRST VIEWPORT: a fixed
ink sidebar frames one intake strip above recent files and approaching work;
the primary folder action stays at the upper right. FORM: campus filing docket,
grounded candidate seven, seed 0268781f.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from organizador.config import AppConfig
from organizador.db import Database
from organizador.i18n import _
from organizador.ui import theme as ui_theme
from organizador.ui.pages import (
    HomePage,
    InboxPage,
    SearchPage,
    SettingsPage,
    SubjectsPage,
    TasksPage,
)
from organizador.ui.widgets import label


class MainWindow(QMainWindow):
    """Persistent navigation shell; closing hides it while the tray keeps running."""

    hidden_to_tray = Signal()
    quit_requested = Signal()
    palette_requested = Signal()

    def __init__(
        self, database: Database, config: AppConfig, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.config = config
        self.allow_close = False
        self.quit_on_close = False
        self.setWindowTitle("SortInator")
        self.setMinimumSize(980, 660)
        self.resize(1180, 760)

        central = QWidget()
        central.setObjectName("Canvas")
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.setCentralWidget(central)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(224)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(17, 24, 17, 18)
        sidebar_layout.setSpacing(8)
        sidebar_layout.addWidget(label(_("SortInator"), "Brand"))
        sidebar_layout.addWidget(label(_("estudo local"), "BrandDetail"))
        sidebar_layout.addSpacing(22)

        self.stack = QStackedWidget()
        self.home_page = HomePage(database)
        self.inbox_page = InboxPage(database, config)
        self.search_page = SearchPage(database)
        self.tasks_page = TasksPage(database)
        self.subjects_page = SubjectsPage(database, config)
        self.settings_page = SettingsPage(config)
        self.pages: dict[str, QWidget] = {
            "inicio": self.home_page,
            "inbox": self.inbox_page,
            "pesquisa": self.search_page,
            "tarefas": self.tasks_page,
            "disciplinas": self.subjects_page,
            "definicoes": self.settings_page,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        labels = (
            ("inicio", _("Início")),
            ("inbox", _("Caixa de Entrada")),
            ("pesquisa", _("Pesquisa")),
            ("tarefas", _("Tarefas")),
            ("disciplinas", _("Disciplinas")),
            ("definicoes", _("Definições")),
        )
        for index, (key, text) in enumerate(labels):
            nav = QPushButton(text)
            nav.setCheckable(True)
            nav.setProperty("nav", "true")
            nav.setCursor(Qt.CursorShape.PointingHandCursor)
            nav.clicked.connect(lambda _checked=False, page_key=key: self.show_page(page_key))
            self.nav_group.addButton(nav, index)
            self.nav_buttons[key] = nav
            sidebar_layout.addWidget(nav)

        sidebar_layout.addStretch(1)
        status_row = QHBoxLayout()
        status_row.setContentsMargins(8, 0, 8, 0)
        status_row.setSpacing(8)
        self.status_dot = QFrame()
        self.status_dot.setFixedSize(8, 8)
        tokens = ui_theme.current()
        self.status_dot.setStyleSheet(f"background: {tokens.status_ok}; border-radius: 4px;")
        self.status_label = QLabel(_("A iniciar…"))
        self.status_label.setStyleSheet(f"color: {tokens.status_text}; font-size: 12px;")
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label, 1)
        sidebar_layout.addLayout(status_row)

        shell.addWidget(self.sidebar)
        shell.addWidget(self.stack, 1)
        self.nav_buttons["inicio"].setChecked(True)

        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(
            lambda: self.palette_requested.emit()
        )
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            lambda: self.show_page("pesquisa")
        )
        for index, key in enumerate(self.pages, start=1):
            QShortcut(QKeySequence(f"Ctrl+{index}"), self).activated.connect(
                lambda page_key=key: self.show_page(page_key)
            )

    def show_page(self, key: str) -> None:
        """Navigate and refresh the selected page."""

        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        self.nav_buttons[key].setChecked(True)
        if key == "inbox":
            self.inbox_page.refresh()
        elif key == "tarefas":
            self.tasks_page.refresh()
        elif key == "disciplinas":
            self.subjects_page.refresh()
        elif key == "pesquisa":
            self.search_page.focus_search()

    def refresh_all(self, *, watching: bool, paused: bool) -> None:
        """Refresh all data-backed pages and navigation state."""

        self.home_page.refresh(watching=watching, paused=paused)
        self.inbox_page.refresh()
        self.tasks_page.refresh()
        self.subjects_page.refresh()
        self.search_page.refresh_filters()
        count = self.database.count_inbox_items()
        self.nav_buttons["inbox"].setText(
            _("Caixa de Entrada  {count}").format(count=count) if count else _("Caixa de Entrada")
        )
        self.set_runtime_status(watching=watching, paused=paused)

    def set_runtime_status(self, *, watching: bool, paused: bool) -> None:
        """Show watcher state without relying on colour alone."""

        if paused:
            self.status_label.setText(_("Vigilância em pausa"))
            color = ui_theme.current().status_warn
        elif watching:
            self.status_label.setText(_("A vigiar Downloads"))
            color = ui_theme.current().status_ok
        else:
            self.status_label.setText(_("Vigilância desligada"))
            color = ui_theme.current().status_off
        self.status_dot.setStyleSheet(f"background: {color}; border-radius: 4px;")

    def show_from_tray(self, page: str = "inicio") -> None:
        """Restore and focus the window from tray or a second launch."""

        self.show_page(page)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.allow_close:
            event.accept()
            return
        event.ignore()
        if self.quit_on_close:
            self.quit_requested.emit()
            return
        self.hide()
        self.hidden_to_tray.emit()
