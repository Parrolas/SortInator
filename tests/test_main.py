"""Startup logging and frozen exception-surface tests."""

from __future__ import annotations

import logging
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from organizador.config import AppConfig
from organizador.db import Database
from organizador.logging_setup import configure_logging, log_uncaught_exception
from organizador.main import (
    SingleInstance,
    build_parser,
    load_config_safely,
    reload_config_after_restore,
    run_ondemand_backup,
    split_update_arguments,
    stage_requested_restore,
)
from organizador.recovery import RecoveryCoordinator


def test_configure_logging_is_idempotent_for_same_path(tmp_path: Path) -> None:
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        configure_logging(tmp_path)
        configure_logging(tmp_path)
        matching = [
            handler
            for handler in root.handlers
            if isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename).resolve() == (tmp_path / "organizador.log").resolve()
        ]
        assert len(matching) == 1
        assert matching[0].maxBytes == 1_500_000
        assert matching[0].backupCount == 2
    finally:
        for handler in list(root.handlers):
            if handler not in before:
                root.removeHandler(handler)
                handler.close()


def test_uncaught_exception_hook_is_safe_without_stderr(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(sys, "stderr", None)
    with caplog.at_level(logging.CRITICAL, logger="organizador.logging_setup"):
        try:
            raise RuntimeError("hidden crash")
        except RuntimeError as exc:
            log_uncaught_exception(type(exc), exc, exc.__traceback__)

    assert "Unhandled exception" in caplog.text
    assert "hidden crash" in caplog.text


def test_uncaught_exception_hook_preserves_console_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delegated: list[BaseException] = []
    monkeypatch.setattr(sys, "stderr", object())
    monkeypatch.setattr(
        sys,
        "__excepthook__",
        lambda _kind, error, _traceback: delegated.append(error),
    )
    error = RuntimeError("visible crash")

    log_uncaught_exception(type(error), error, error.__traceback__)

    assert delegated == [error]


def test_unexpected_settings_failure_uses_safe_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail_load(_data_dir: Path | None = None) -> AppConfig:
        raise RuntimeError("unexpected settings failure")

    monkeypatch.setattr(AppConfig, "load", fail_load)

    with caplog.at_level(logging.ERROR, logger="organizador.main"):
        config, error = load_config_safely(tmp_path)

    assert config == AppConfig(data_dir=tmp_path)
    assert isinstance(error, RuntimeError)
    assert "unexpected settings failure" in caplog.text


def test_split_update_arguments_requires_paired_values(tmp_path: Path) -> None:
    manifest = tmp_path / "transaction.json"

    assert split_update_arguments(None, None) is None
    assert split_update_arguments(manifest, "token") == (manifest, "token")
    with pytest.raises(ValueError):
        split_update_arguments(None, "token")
    with pytest.raises(ValueError):
        split_update_arguments(manifest, None)


def test_build_parser_accepts_hidden_update_arguments() -> None:
    parsed = build_parser().parse_args(
        ["--update-manifest", "state/transaction.json", "--update-token", "secret"]
    )

    assert parsed.update_manifest == Path("state/transaction.json")
    assert parsed.update_token == "secret"
    assert build_parser().parse_args([]).update_manifest is None


def test_build_parser_accepts_backup_arguments() -> None:
    parsed = build_parser().parse_args(["--backup-now", "saida", "--restore-from", "copia.zip"])

    assert parsed.backup_now == Path("saida")
    assert parsed.restore_from == Path("copia.zip")
    defaults = build_parser().parse_args([])
    assert defaults.backup_now is None
    assert defaults.restore_from is None


def test_ondemand_backup_and_staged_restore_roundtrip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    database = Database(data_dir / "organizador.db")
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO subjects(name, code, color, keywords_json, folder_name, created_at)
            VALUES ('Cálculo I', 'MAT101', '#087A74', '[]', 'MAT101 - Cálculo I', '2026-01-01')
            """
        )
        connection.commit()
    export_dir = tmp_path / "exports"
    export_dir.mkdir()

    assert run_ondemand_backup(data_dir, export_dir) == 0

    output = capsys.readouterr().out.strip()
    assert output.startswith("ZIP:")
    archive = Path(output.split("ZIP:", 1)[1])
    assert archive.is_file()

    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()

    assert stage_requested_restore(data_dir, archive) == 0

    request_output = capsys.readouterr().out.strip()
    assert request_output.startswith("PEDIDO:")
    outcome = RecoveryCoordinator(data_dir).consume_restore_request()

    assert outcome is not None
    with database.connect() as connection:
        count = int(connection.execute("SELECT COUNT(*) FROM subjects").fetchone()[0])
    assert count == 1


def test_single_instance_blocks_a_second_copy_of_the_same_data(
    qt_app: QApplication, tmp_path: Path
) -> None:
    del qt_app
    first = SingleInstance(tmp_path)
    second = SingleInstance(tmp_path)
    elsewhere = SingleInstance(tmp_path.parent / "outros-dados")
    try:
        assert first.acquire() is True
        assert second.acquire() is False
        assert elsewhere.acquire() is True
    finally:
        first.server.close()
        elsewhere.server.close()


def test_single_instance_forwards_explorer_selection(qt_app: QApplication, tmp_path: Path) -> None:
    first = SingleInstance(tmp_path)
    selections: list[list[str]] = []
    first.organize_requested.connect(selections.append)
    first.show_requested.connect(lambda: selections.append(["show"]))
    selected = [str(tmp_path / "aula.pdf"), str(tmp_path / "ficha.pdf")]
    try:
        assert first.acquire()
        results: list[bool] = []

        def send() -> None:
            second = SingleInstance(tmp_path)
            results.append(second.acquire(None, selected))

        worker = threading.Thread(target=send)
        worker.start()
        deadline = time.monotonic() + 2
        while not selections and time.monotonic() < deadline:
            qt_app.processEvents()
        assert selections == [selected]
        worker.join(3)
        assert results == [False]
        delivered: list[list[str]] = []
        first.set_organize_handler(delivered.append)
        qt_app.processEvents()
        assert delivered == [selected]
    finally:
        first.server.close()


def test_reload_config_after_restore_picks_up_rewritten_settings(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[Exception] = []
    monkeypatch.setattr(
        "organizador.main._warn_unreadable_settings", lambda error: warnings.append(error)
    )
    downloads = tmp_path.parent / f"{tmp_path.name}-downloads"
    config = AppConfig(data_dir=tmp_path, downloads_dir=downloads)
    config.save()

    reloaded, error = reload_config_after_restore(qt_app, tmp_path)
    assert error is None
    assert not warnings
    assert reloaded.downloads_dir == downloads

    restored = AppConfig(
        data_dir=tmp_path, downloads_dir=tmp_path.parent / f"{tmp_path.name}-original"
    )
    restored.save()

    reloaded, error = reload_config_after_restore(qt_app, tmp_path)

    assert error is None
    assert reloaded.downloads_dir == tmp_path.parent / f"{tmp_path.name}-original"


def test_reload_config_after_restore_reports_unreadable_settings(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[Exception] = []
    monkeypatch.setattr(
        "organizador.main._warn_unreadable_settings", lambda error: warnings.append(error)
    )
    (tmp_path / "settings.json").write_text("{corrompido", encoding="utf-8")

    config, error = reload_config_after_restore(qt_app, tmp_path)

    assert config == AppConfig(data_dir=tmp_path)
    assert error is not None
    assert len(warnings) == 1
