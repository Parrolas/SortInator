"""Persistent activation routing uses test documents and mocked Explorer only."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree

import pytest
from PySide6.QtWidgets import QApplication

from organizador import notifications
from organizador.config import AppConfig
from organizador.controller import AppController, StartupState
from organizador.db import Database
from organizador.filer import FilingService
from organizador.main import SingleInstance
from organizador.models import FiledDocument, Subject


@pytest.fixture
def document(filer: FilingService, app_config: AppConfig, subject: Subject) -> FiledDocument:
    path = app_config.downloads_dir / "José's apontamentos & resumo.txt"
    path.write_text("coursework contents " * 20)
    item = filer.ingest(path)
    assert item is not None
    return filer.file_document(item.id, subject.id, "Outros", path.name)


def test_action_survives_database_reopen_and_tracks_current_path(
    database: Database, document: FiledDocument
) -> None:
    uri = notifications.save_action(database, [document])
    renamed = document.current_path.with_name("novo nome.txt")
    document.current_path.rename(renamed)
    with database.connect() as connection:
        connection.execute(
            "UPDATE files SET current_path = ? WHERE id = ?", (str(renamed), document.id)
        )
        connection.commit()
    resolved, missing = notifications.resolve_action(Database(database.path), uri)
    assert not missing
    assert resolved[0].current_path == renamed


def test_overlapping_alerts_have_independent_targets(
    database: Database, document: FiledDocument
) -> None:
    first = notifications.save_action(database, [document])
    second = notifications.save_action(database, [])
    assert first != second
    assert notifications.resolve_action(database, first) == ([document], False)
    assert notifications.resolve_action(database, second) == ([], False)


@pytest.mark.parametrize("change", ["expired", "reused_id", "deleted", "undone"])
def test_stale_notification_never_opens_a_replacement(
    database: Database, document: FiledDocument, filer: FilingService, change: str
) -> None:
    uri = notifications.save_action(database, [document])
    if change == "deleted":
        document.current_path.unlink()
    elif change == "undone":
        filer.undo_latest_filing()
    else:
        with database.connect() as connection:
            if change == "expired":
                connection.execute("UPDATE notification_actions SET expires_at = 0")
            else:
                connection.execute("UPDATE files SET record_token = 'replacement'")
            connection.commit()
    assert notifications.resolve_action(database, uri) == ([], True)


@pytest.mark.parametrize(
    "uri",
    [
        "",
        "file:///C:/Windows/cmd.exe",
        "sortinator://notification/../x",
        "sortinator://notification/" + "a" * 32 + "?cmd=x",
    ],
)
def test_invalid_activation_is_rejected(database: Database, uri: str) -> None:
    assert notifications.resolve_action(database, uri) == ([], True)
    with pytest.raises(ValueError):
        notifications.toast_xml("Title", "Message", uri)


def test_xml_escapes_document_names_and_preserves_protocol_activation() -> None:
    uri = "sortinator://notification/" + "a" * 32
    root = ElementTree.fromstring(notifications.toast_xml("A&B <notes>", "José's file", uri))
    assert root.attrib == {"activationType": "protocol", "launch": uri}
    assert root.find("./visual/binding/text").text == "A&B <notes>"  # type: ignore[union-attr]


def test_single_instance_forwards_notification_without_generic_show(
    qt_app: QApplication, tmp_path: Path
) -> None:
    first = SingleInstance(tmp_path)
    actions: list[str] = []
    first.notification_requested.connect(actions.append)
    first.show_requested.connect(lambda: actions.append("show"))
    uri = "sortinator://notification/" + "a" * 32
    try:
        assert first.acquire()
        results: list[bool] = []

        def send() -> None:
            second = SingleInstance(tmp_path)
            results.append(second.acquire(uri))

        worker = threading.Thread(target=send)
        worker.start()
        deadline = time.monotonic() + 2
        while not actions and time.monotonic() < deadline:
            qt_app.processEvents()
        assert actions == [uri]
        worker.join(3)
        assert results == [False]
        delivered: list[str] = []
        first.set_notification_handler(delivered.append)
        qt_app.processEvents()
        assert delivered == [uri]
    finally:
        first.server.close()


def test_real_winrt_toast_object_has_activation_and_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    from winrt.windows.ui import notifications as native

    captured: list[native.ToastNotification] = []

    class Notifier:
        def show(self, toast: native.ToastNotification) -> None:
            captured.append(toast)

    class Manager:
        @staticmethod
        def create_toast_notifier_with_id(app_id: str) -> Notifier:
            assert app_id == "Parrolas.SortInator"
            return Notifier()

    monkeypatch.setattr(native, "ToastNotificationManager", Manager)
    uri = "sortinator://notification/" + "c" * 32
    assert notifications.show_toast("File organized", "Notes & exercises", uri)
    assert captured[0].expiration_time is not None
    assert captured[0].group == "filed"
    assert uri in captured[0].content.get_xml()


def test_controller_reveals_same_folder_and_lists_cross_folder_batch(
    qt_app: QApplication,
    app_config: AppConfig,
    database: Database,
    document: FiledDocument,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = AppController(app_config, database)
    revealed: list[list[Path]] = []
    monkeypatch.setattr("organizador.controller.reveal_files", revealed.append)
    try:
        uri = notifications.save_action(database, [document])
        controller.activate_notification(uri)
        assert revealed == [[document.current_path]]
        other = replace(document, current_path=app_config.downloads_dir / "other.txt")
        monkeypatch.setattr(
            notifications, "resolve_action", lambda *args: ([document, other], False)
        )
        controller.activate_notification(uri)
        assert controller._notification_dialog is not None
        assert controller._notification_dialog.isVisible()
        assert len(revealed) == 1
    finally:
        if controller._notification_dialog is not None:
            controller._notification_dialog.close()
        controller.indexer.shutdown()
        controller.main_window.allow_close = True
        controller.main_window.close()


def test_native_toasts_capture_every_batched_document_and_fall_back_safely(
    qt_app: QApplication,
    app_config: AppConfig,
    database: Database,
    document: FiledDocument,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qt_app
    controller = AppController(app_config, database)
    sent: list[str] = []
    fallback: list[str] = []
    monkeypatch.setattr(
        notifications, "show_toast", lambda title, message, uri: sent.append(uri) or True
    )
    monkeypatch.setattr(controller.tray, "notify", lambda title, message: fallback.append(title))
    controller._native_notifications = True
    try:
        controller._last_filed_notice = time.monotonic()
        controller._notify_filed("a", "subject", document)
        controller._notify_filed("b", "subject", document)
        controller._flush_filed_notices()
        assert len(sent) == 1
        with database.connect() as connection:
            row = connection.execute("SELECT documents_json FROM notification_actions").fetchone()
        assert len(json.loads(row[0])) == 2
        assert not fallback
        monkeypatch.setattr(notifications, "show_toast", lambda *args: False)
        controller._filed_toast("fallback", "message", [document])
        assert fallback == ["fallback"]
    finally:
        controller.indexer.shutdown()
        controller.main_window.allow_close = True
        controller.main_window.close()


def test_smoke_activation_skips_machine_integration(
    qt_app: QApplication,
    app_config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qt_app
    controller = AppController(app_config)
    monkeypatch.setattr("organizador.controller.updater.is_frozen", lambda: True)
    monkeypatch.setattr("organizador.controller.default_data_dir", lambda: app_config.data_dir)
    monkeypatch.setattr(
        controller, "_prepare_windows_integration", lambda: pytest.fail("real registration")
    )
    try:
        controller.activate(StartupState(True, False), smoke_test=True)
        assert not controller._native_notifications
    finally:
        controller.indexer.shutdown()
        controller.main_window.allow_close = True
        controller.main_window.close()


def test_pre_rename_notification_uri_still_resolves(database: Database) -> None:
    uri = notifications.save_action(database, [])
    legacy_uri = uri.replace("sortinator://", "organizador://", 1)

    assert notifications.notification_token(legacy_uri) is not None
    assert notifications.resolve_action(database, legacy_uri) == ([], False)
