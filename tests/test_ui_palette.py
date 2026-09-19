"""Command registry and keyboard palette behavior."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from organizador.config import AppConfig
from organizador.controller import AppController
from organizador.models import Subject
from organizador.ui.commands import Command, CommandRegistry, fold, lookup
from organizador.ui.palette import CommandPalette
from organizador.ui.theme import apply_theme, get_theme
from organizador.ui.widgets import BoundedDialog


def _wait_until(predicate: Callable[[], bool], timeout_ms: int = 2000) -> bool:
    """Let the event loop run until the debounced lookup chain delivers."""

    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if predicate():
            return True
        QTest.qWait(40)
    return predicate()


def _registry() -> CommandRegistry:
    result = CommandRegistry()
    result.register(Command(id="page.inicio", title="Início", shortcut="Ctrl+1"))
    result.register(Command(id="page.tarefas", title="Tarefas", shortcut="Ctrl+3"))
    result.register(Command(id="page.definicoes", title="Definições", shortcut="Ctrl+6"))
    result.register(
        Command(id="action.import", title="Importar de Downloads…", keywords="existente")
    )
    result.register(Command(id="action.pause", title="Pausar vigilância", keywords="vigilância"))
    return result


def test_fold_matches_accents_and_case() -> None:
    assert fold("Pausar Vigilância") == "pausar vigilancia"
    assert fold("Início") == "inicio"


def test_lookup_ranks_title_then_keywords() -> None:
    commands = _registry().commands()
    assert lookup("", commands) == commands

    # Title prefix ranks first; "Impor**tar**" follows as a title containment.
    assert [command.id for command in lookup("tar", commands)] == ["page.tarefas", "action.import"]
    assert [command.id for command in lookup("tarefa", commands)] == ["page.tarefas"]

    # "vigi" matches the title of one command and its own keyword only.
    assert [command.id for command in lookup("vigi", commands)] == ["action.pause"]

    # A keyword that appears in no title still surfaces its command.
    assert [command.id for command in lookup("existente", commands)] == ["action.import"]

    # Accented queries reach the folded title ("iní" also lands in Definições).
    assert [command.id for command in lookup("iní", commands)] == [
        "page.inicio",
        "page.definicoes",
    ]

    assert lookup("nada que corresponde", commands) == ()


def test_registry_ignores_duplicate_ids() -> None:
    registry = CommandRegistry()
    registry.register(Command(id="page.inicio", title="Início"))
    registry.register(Command(id="page.inicio", title="Duplicado"))

    assert len(registry.commands()) == 1
    assert registry.commands()[0].title == "Início"


def test_palette_filters_debounced_and_runs_commands(qt_app: QApplication) -> None:
    apply_theme(qt_app, get_theme("escuro"))
    ran: list[str] = []
    commands = (
        Command(id="page.inicio", title="Início", shortcut="Ctrl+1"),
        Command(
            id="action.import",
            title="Importar de Downloads…",
            callback=lambda: ran.append("action.import"),
        ),
    )
    parent = QWidget()
    palette = CommandPalette(parent)
    palette.command_activated.connect(lambda command: ran.append(command.id))
    palette.open_with(commands)

    assert palette.isVisible()
    assert palette.rows.count() == 2
    assert palette.rows.currentRow() == 0

    QTest.keyClicks(palette.input, "importar")

    assert _wait_until(lambda: palette.rows.count() == 1)
    assert palette.rows.isVisible()
    assert not palette.empty_label.isVisible()

    QTest.keyClick(palette.input, Qt.Key.Key_Return)

    assert ran == ["action.import"]
    assert not palette.isVisible()


def test_palette_shows_empty_state_and_recovers(qt_app: QApplication) -> None:
    apply_theme(qt_app, get_theme("escuro"))
    parent = QWidget()
    palette = CommandPalette(parent)
    palette.open_with(
        (Command(id="page.inicio", title="Início"), Command(id="page.tarefas", title="Tarefas"))
    )

    QTest.keyClicks(palette.input, "zzzz sem correspondencia")

    assert _wait_until(lambda: not palette.rows.isVisible())
    assert palette.empty_label.isVisible()

    palette.input.clear()

    assert _wait_until(lambda: palette.rows.isVisible() and palette.rows.count() == 2)

    assert palette.rows.isVisible()
    assert palette.rows.count() == 2
    assert not palette.empty_label.isVisible()

    palette.close()


def test_palette_arrow_keys_move_selection(qt_app: QApplication) -> None:
    apply_theme(qt_app, get_theme("escuro"))
    parent = QWidget()
    palette = CommandPalette(parent)
    palette.open_with((Command(id="a", title="Alpha"), Command(id="b", title="Beta")))

    assert palette.rows.currentRow() == 0
    QTest.keyClick(palette.input, Qt.Key.Key_Down)
    assert palette.rows.currentRow() == 1
    QTest.keyClick(palette.input, Qt.Key.Key_Down)
    assert palette.rows.currentRow() == 1
    QTest.keyClick(palette.input, Qt.Key.Key_Up)
    assert palette.rows.currentRow() == 0

    palette.close()


def test_palette_is_a_bounded_dialog(qt_app: QApplication) -> None:
    parent = QWidget()
    palette = CommandPalette(parent)
    assert isinstance(palette, BoundedDialog)


def test_controller_registry_and_palette_lifecycle(
    qt_app: QApplication, app_config: AppConfig, subject: Subject
) -> None:
    del subject
    controller = AppController(app_config)
    try:
        registry = controller._build_command_registry()
        ids = [command.id for command in registry.commands()]
        assert ids[0] == "page.inicio"
        assert "page.definicoes" in ids
        assert "search.notes" in ids
        assert "action.import" in ids
        assert "action.backup" in ids
        # No watcher is running in this test, so the pause toggle is absent.
        assert "action.pause" not in ids

        command = next(item for item in registry.commands() if item.id == "page.tarefas")
        callback = command.callback
        assert callback is not None
        callback()
        assert (
            controller.main_window.stack.currentWidget() is controller.main_window.pages["tarefas"]
        )

        controller.show_command_palette()
        palette = controller._command_palette
        assert palette is not None and palette.isVisible()
        assert palette.rows.count() == len(registry.commands())
        palette.close()
        assert not palette.isVisible()
    finally:
        controller.indexer.shutdown()
        controller.tray.hide()
        controller.main_window.allow_close = True
        controller.main_window.close()
