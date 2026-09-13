"""Theme palette, stylesheet and switching tests."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from organizador.config import DEFAULT_THEME, THEME_IDS, AppConfig
from organizador.controller import AppController
from organizador.db import Database
from organizador.models import Subject
from organizador.ui import theme as ui_theme
from organizador.ui.main_window import MainWindow
from organizador.ui.pages import SettingsPayload
from organizador.ui.theme import THEMES, apply_theme, build_stylesheet, get_theme


def test_every_config_theme_id_has_a_palette_and_vice_versa() -> None:
    assert set(THEMES) == set(THEME_IDS)
    assert DEFAULT_THEME in THEMES
    for theme in THEMES.values():
        assert theme.id in THEME_IDS
        assert get_theme(theme.id) is theme
    assert get_theme("inexistente") is THEMES[DEFAULT_THEME]


def test_stylesheet_is_built_from_the_theme_tokens() -> None:
    claro_sheet = build_stylesheet(get_theme("claro"))
    assert get_theme("claro").canvas in claro_sheet
    assert get_theme("escuro").canvas not in claro_sheet
    assert claro_sheet != build_stylesheet(get_theme("contraste"))


def test_apply_theme_switches_the_active_tokens(
    qt_app: QApplication, app_config: AppConfig, database: Database
) -> None:
    del database
    claro = get_theme("claro")
    apply_theme(qt_app, claro)

    assert ui_theme.current() is claro
    assert qt_app.palette().color(QPalette.ColorRole.Window).name() == claro.canvas.casefold()

    apply_theme(qt_app, get_theme("escuro"))

    assert ui_theme.current().id == "escuro"


def test_every_theme_builds_the_full_window(
    qt_app: QApplication, app_config: AppConfig, subject: Subject
) -> None:
    del subject
    database = Database(app_config.database_path)
    database.initialize()
    try:
        for theme_id in THEME_IDS:
            apply_theme(qt_app, get_theme(theme_id))
            window = MainWindow(database, app_config)
            window.refresh_all(watching=True, paused=False)
            assert ui_theme.current().id == theme_id
            window.allow_close = True
            window.close()
    finally:
        apply_theme(qt_app, get_theme(DEFAULT_THEME))


def test_no_hardcoded_hex_colors_outside_theme_and_icons() -> None:
    ui_dir = Path(__file__).resolve().parents[1] / "src" / "organizador" / "ui"
    allowed = {"theme.py", "icons.py"}
    pattern = re.compile(r"#[0-9A-Fa-f]{6}\b")
    offenders: list[str] = []
    for path in sorted(ui_dir.glob("*.py")):
        if path.name in allowed:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert offenders == []


def test_theme_round_trips_through_settings(
    qt_app: QApplication,
    app_config: AppConfig,
    database: Database,
    subject: Subject,
) -> None:
    del database, subject
    controller = AppController(app_config)
    payload: SettingsPayload = {
        "university_root": app_config.university_root,
        "downloads_dir": app_config.downloads_dir,
        "extensions": ".pdf",
        "filename_template": "{nome_original}",
        "minimum_file_size": 1024,
        "prompt_timeout_seconds": 45,
        "prompt_timeout_enabled": False,
        "reminder_lead_days": 2,
        "theme": "claro",
        "language": "pt",
        "check_updates_on_launch": True,
        "ocr_enabled": True,
        "quiet_intake": False,
        "watch_enabled": True,
        "launch_at_login": False,
    }

    controller._save_settings(payload)

    assert ui_theme.current().id == "claro"
    assert app_config.theme == "claro"
    reloaded = AppConfig.load(app_config.data_dir)
    assert reloaded.theme == "claro"

    payload["theme"] = "escuro"
    payload["language"] = "pt"
    controller._save_settings(payload)

    assert ui_theme.current().id == "escuro"

    with pytest.raises(ValueError):
        AppConfig(data_dir=app_config.data_dir, theme="neon").validate()

    controller.indexer.shutdown()
    controller.tray.hide()
    controller.main_window.allow_close = True
    controller.main_window.close()
