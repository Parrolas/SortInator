"""Short-motion budget: entrance, thumb travel and the Contraste opt-out."""

from __future__ import annotations

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from organizador.ui.commands import Command
from organizador.ui.palette import CommandPalette
from organizador.ui.theme import animation_ms, apply_theme, get_theme
from organizador.ui.widgets import ToggleSwitch


def test_animation_budget_is_theme_aware(qt_app: QApplication) -> None:
    apply_theme(qt_app, get_theme("escuro"))
    assert animation_ms() == 140
    apply_theme(qt_app, get_theme("contraste"))
    assert animation_ms() == 0
    apply_theme(qt_app, get_theme("escuro"))


def test_switch_thumb_travels_and_settles(qt_app: QApplication) -> None:
    apply_theme(qt_app, get_theme("escuro"))
    switch = ToggleSwitch("Teste")
    switch.resize(220, 32)
    assert switch.thumb_position() == 0.0

    switch.setChecked(True)
    assert 0.0 <= switch.thumb_position() <= 1.0
    QTest.qWait(220)
    assert switch.thumb_position() == 1.0

    switch.setChecked(False)
    QTest.qWait(220)
    assert switch.thumb_position() == 0.0


def test_switch_thumb_is_instant_in_contraste(qt_app: QApplication) -> None:
    apply_theme(qt_app, get_theme("contraste"))
    switch = ToggleSwitch("Teste")
    switch.resize(220, 32)
    switch.setChecked(True)
    assert switch.thumb_position() == 1.0
    switch.setChecked(False)
    assert switch.thumb_position() == 0.0
    apply_theme(qt_app, get_theme("escuro"))


def test_palette_entrance_settles_within_the_budget(qt_app: QApplication) -> None:
    apply_theme(qt_app, get_theme("escuro"))
    parent = QWidget()
    palette = CommandPalette(parent)
    palette.open_with((Command(id="a", title="Alpha"),))
    QTest.qWait(220)
    settled = palette.pos()
    QTest.qWait(60)
    assert palette.pos() == settled
    palette.close()


def test_palette_entrance_is_instant_in_contraste(qt_app: QApplication) -> None:
    apply_theme(qt_app, get_theme("contraste"))
    parent = QWidget()
    palette = CommandPalette(parent)
    palette.open_with((Command(id="a", title="Alpha"),))
    QTest.qWait(60)
    settled = palette.pos()
    QTest.qWait(60)
    assert palette.pos() == settled
    palette.close()
    apply_theme(qt_app, get_theme("escuro"))
