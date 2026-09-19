"""Retained features: settings groups, calendar folding and fixed save row."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from organizador.config import DEFAULT_THEME, AppConfig
from organizador.db import Database
from organizador.models import Subject
from organizador.ui.main_window import MainWindow
from organizador.ui.theme import apply_theme, get_theme
from organizador.ui.widgets import ToggleSwitch

GROUP_TITLES = (
    "Pastas e ficheiros",
    "Vigilância e notificações",
    "Aparência e idioma",
    "Cópias de segurança",
)


def _wheel() -> QWheelEvent:
    position = QPoint(8, 8)
    return QWheelEvent(
        position,
        position,
        QPoint(0, -120),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def _window(app_config: AppConfig) -> MainWindow:
    window = MainWindow(Database(app_config.database_path), app_config)
    window.resize(1180, 760)
    return window


def test_settings_page_has_four_titled_groups(
    qt_app: QApplication, app_config: AppConfig, subject: Subject
) -> None:
    del subject
    apply_theme(qt_app, get_theme(DEFAULT_THEME))
    window = _window(app_config)
    try:
        titles = {
            text
            for text in (
                item.text()
                for item in window.settings_page.findChildren(QLabel)
                if item.objectName() == "SectionTitle"
            )
        }
        for group in GROUP_TITLES:
            assert group in titles, group
    finally:
        window.allow_close = True
        window.close()


def test_settings_switches_replace_checkboxes(
    qt_app: QApplication, app_config: AppConfig, subject: Subject
) -> None:
    del subject
    apply_theme(qt_app, get_theme(DEFAULT_THEME))
    window = _window(app_config)
    try:
        page = window.settings_page
        for switch in (
            page.ocr_check,
            page.watch_check,
            page.startup_check,
            page.quiet_check,
            page.auto_close_check,
            page.check_updates_check,
        ):
            assert isinstance(switch, ToggleSwitch)

        save_buttons = [
            control
            for control in page.findChildren(QPushButton)
            if control.text() == "Guardar definições"
        ]
        assert len(save_buttons) == 1
        assert not page.body_area.isAncestorOf(save_buttons[0])
    finally:
        window.allow_close = True
        window.close()


def test_calendar_folds_behind_the_toggle_on_narrow_windows(
    qt_app: QApplication, app_config: AppConfig, subject: Subject
) -> None:
    del subject
    apply_theme(qt_app, get_theme(DEFAULT_THEME))
    window = _window(app_config)
    try:
        window.show()
        window.show_page("tarefas")
        QTest.qWait(60)
        page = window.tasks_page
        assert page.calendar_panel.isVisible()
        assert page.calendar_panel.width() == 300
        assert not page.calendar_toggle.isVisible()

        window.resize(1050, 700)
        QTest.qWait(60)
        assert not page.calendar_panel.isVisible()
        assert page.calendar_toggle.isVisible()

        page.calendar_toggle.click()
        QTest.qWait(60)
        assert page.calendar_panel.isVisible()

        page.calendar_toggle.click()
        QTest.qWait(60)
        assert not page.calendar_panel.isVisible()

        window.resize(1180, 760)
        QTest.qWait(60)
        assert page.calendar_panel.isVisible()
        assert not page.calendar_toggle.isVisible()
    finally:
        window.allow_close = True
        window.close()


def test_calendar_weekends_use_the_regular_text_colour(
    qt_app: QApplication, app_config: AppConfig, subject: Subject
) -> None:
    del subject
    theme = get_theme(DEFAULT_THEME)
    apply_theme(qt_app, theme)
    window = _window(app_config)
    try:
        sunday = window.tasks_page.calendar.weekdayTextFormat(Qt.DayOfWeek.Sunday)
        assert sunday.foreground().color().name() == theme.text.casefold()
        saturday = window.tasks_page.calendar.weekdayTextFormat(Qt.DayOfWeek.Saturday)
        assert saturday.foreground().color().name() == theme.text.casefold()
    finally:
        window.allow_close = True
        window.close()


def test_wheel_never_edits_a_spin_or_combo(
    qt_app: QApplication, app_config: AppConfig, subject: Subject
) -> None:
    del subject
    apply_theme(qt_app, get_theme(DEFAULT_THEME))
    window = _window(app_config)
    try:
        page = window.settings_page
        window.show()
        window.show_page("definicoes")
        page.resize(1180, 620)
        QTest.qWait(40)
        scrollbar = page.body_area.verticalScrollBar()
        scrollbar.setMaximum(400)
        scrollbar.setValue(0)

        # Unfocused: the wheel scrolls the page and edits nothing.
        before = page.minimum_size.value()
        QApplication.sendEvent(page.minimum_size, _wheel())
        QTest.qWait(40)
        assert page.minimum_size.value() == before
        assert scrollbar.value() > 0

        # Even focused, the wheel scrolls instead of changing the value.
        page.minimum_size.setValue(5000)
        page.minimum_size.setFocus()
        scrollbar.setValue(0)
        QApplication.sendEvent(page.minimum_size, _wheel())
        QTest.qWait(40)
        assert page.minimum_size.value() == 5000
        assert scrollbar.value() > 0

        page.theme_combo.clearFocus()
        before_theme = page.theme_combo.currentIndex()
        QApplication.sendEvent(page.theme_combo, _wheel())
        QTest.qWait(40)
        assert page.theme_combo.currentIndex() == before_theme
    finally:
        window.allow_close = True
        window.close()
