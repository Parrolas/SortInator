"""Overlapping UI actions and crash recovery use only isolated coursework copies."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from organizador import reconcile, updater
from organizador.config import AppConfig
from organizador.controller import AppController, _BulkItem, _BulkJob, _MoveJob, _UndoJob
from organizador.db import Database
from organizador.filer import FilingError, FilingService
from organizador.models import FindingReason, Subject
from organizador.paths import IncompleteMoveError
from organizador.watcher import DownloadWatcher


def pump(app: QApplication, ready: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 10
    while not ready():
        assert time.monotonic() < deadline, "transfer failed to finish"
        app.processEvents()
        time.sleep(0.005)


@pytest.fixture
def controller(
    qt_app: QApplication, app_config: AppConfig, subject: Subject, monkeypatch: pytest.MonkeyPatch
) -> Iterator[AppController]:
    del subject
    result = AppController(app_config)
    monkeypatch.setattr(result.tray, "notify", lambda *args, **kwargs: None)
    monkeypatch.setattr(result, "_show_next_prompt", lambda: None)
    yield result
    if result.watcher is not None:
        result.watcher.stop()
    result._shutdown_transfers()
    pump(qt_app, lambda: result._pending_transfers == 0)
    result.indexer.shutdown()
    result.tray.hide()
    result.main_window.allow_close = True
    result.main_window.close()


def inbox(controller: AppController, name: str) -> int:
    path = controller.config.inbox_dir / name
    path.write_bytes(b"coursework" * 30)
    return controller.database.add_inbox_item(
        path, controller.config.downloads_dir / name, name, path.stat().st_size
    ).id


def test_fifo_queue_rejects_conflicting_file_return_undo_and_bulk(
    qt_app: QApplication,
    controller: AppController,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = inbox(controller, "first.pdf")
    second = inbox(controller, "second.pdf")
    started, release = threading.Event(), threading.Event()
    calls: list[int] = []
    real = controller.filer.file_document

    def slow(
        item: int,
        subject_id: int,
        kind: str,
        name: str,
        replace_document_id: int | None = None,
    ) -> object:
        calls.append(item)
        if item == first:
            started.set()
            assert release.wait(10)
        return real(item, subject_id, kind, name, replace_document_id=replace_document_id)

    monkeypatch.setattr(controller.filer, "file_document", slow)
    try:
        controller._file_item(first, subject.id, "Slides", "same.pdf", False, None)
        assert started.wait(5)
        controller._file_item(first, subject.id, "Slides", "duplicate.pdf", False, None)
        controller._return_item(first)
        controller._undo()
        bulk = _BulkJob(
            (_BulkItem(first, "first.pdf", "bulk.pdf"),), subject.id, "Slides", False, None
        )
        assert not controller._submit_transfer("bulk", bulk, lambda: controller._execute_bulk(bulk))
        controller._file_item(second, subject.id, "Slides", "same.pdf", False, None)
        assert calls == [first]
        assert controller._pending_transfers == 2
        with controller._transfer_lock:
            assert len(controller._transfer_threads) == 1
    finally:
        release.set()
    pump(qt_app, lambda: controller._pending_transfers == 0)
    assert calls == [first, second]
    folder = controller.config.university_root / subject.folder_name / "Slides"
    assert (folder / "same.pdf").read_bytes() == b"coursework" * 30
    assert (folder / "same (2).pdf").read_bytes() == b"coursework" * 30
    assert len(controller.database.list_files()) == 2


def test_move_and_undo_claims_exclude_each_other(
    qt_app: QApplication,
    controller: AppController,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = inbox(controller, "unico.pdf")
    controller._file_item(first, subject.id, "Slides", "unico.pdf", False, None)
    pump(qt_app, lambda: controller._pending_transfers == 0)
    document = controller.database.list_files()[0]

    started, release = threading.Event(), threading.Event()
    real_move = controller.filer.move_document

    def slow_move(file_id: int, subject_id: int, kind: str) -> object:
        started.set()
        assert release.wait(10)
        return real_move(file_id, subject_id, kind)

    monkeypatch.setattr(controller.filer, "move_document", slow_move)
    move_job = _MoveJob(document.id, subject.id, "Trabalhos")
    try:
        assert controller._submit_transfer(
            "move",
            move_job,
            lambda: controller.filer.move_document(document.id, subject.id, "Trabalhos"),
        )
        assert started.wait(5)
        assert not controller._submit_transfer("undo", _UndoJob(), lambda: None)
    finally:
        release.set()
    pump(qt_app, lambda: controller._pending_transfers == 0)
    moved = controller.database.get_file(document.id)
    assert moved is not None
    assert moved.kind == "Trabalhos"

    started_undo, release_undo = threading.Event(), threading.Event()
    real_undo = controller.filer.undo_latest_filing

    def slow_undo() -> object:
        started_undo.set()
        assert release_undo.wait(10)
        return real_undo()

    monkeypatch.setattr(controller.filer, "undo_latest_filing", slow_undo)
    try:
        controller._undo()
        assert started_undo.wait(5)
        assert not controller._submit_transfer(
            "move", _MoveJob(document.id, subject.id, "Outros"), lambda: None
        )
    finally:
        release_undo.set()
    pump(qt_app, lambda: controller._pending_transfers == 0)
    assert controller.database.list_files() == []


def test_quit_keeps_event_loop_alive_until_accepted_cross_drive_copy_finishes(
    qt_app: QApplication,
    controller: AppController,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from organizador import paths

    first = inbox(controller, "slow.pdf")
    started, release = threading.Event(), threading.Event()
    real_copy = paths._copy_windows_handles
    quit_calls: list[bool] = []
    monkeypatch.setattr(QApplication, "quit", lambda: quit_calls.append(True))
    monkeypatch.setattr(paths, "_rename_windows_handle", lambda *args: False)

    def slow_copy(*args: object) -> None:
        started.set()
        assert release.wait(10)
        real_copy(*args)

    monkeypatch.setattr(paths, "_copy_windows_handles", slow_copy)
    try:
        controller._file_item(first, subject.id, "Slides", "slow.pdf", True, None)
        assert started.wait(5)
        controller.shutdown()
        controller.shutdown()
        ticks: list[bool] = []
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, lambda: ticks.append(True))
        pump(qt_app, lambda: bool(ticks))
        assert not quit_calls
        assert controller._shutdown_progress is not None
        assert controller._shutdown_progress.isVisible()
        assert not controller._submit_transfer("undo", _UndoJob(), lambda: None)
    finally:
        release.set()
    pump(qt_app, lambda: bool(quit_calls))
    assert quit_calls == [True]
    assert controller._pending_transfers == 0
    document = controller.database.list_files()[0]
    assert document.current_path.read_bytes() == b"coursework" * 30
    assert len(controller.database.list_tasks()) == 1


def test_settings_and_updates_wait_for_queued_work_and_ui_completion(
    qt_app: QApplication, controller: AppController, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = threading.Event(), threading.Event()

    def slow() -> None:
        entered.set()
        assert release.wait(10)

    payloads: list[dict[str, object]] = []
    controller.main_window.settings_page.save_requested.connect(payloads.append)
    controller.main_window.settings_page._save()
    before = controller.config.university_root
    payload = payloads[-1]
    payload["university_root"] = before.parent / "changed-library"
    monkeypatch.setattr(
        updater, "app_directory", lambda: pytest.fail("update started during transfer")
    )
    try:
        controller._submit_transfer("undo", _UndoJob(), slow)
        assert entered.wait(5)
        controller._save_settings(payload)
        controller._install_pending_update()
        assert controller.config.university_root == before
        assert not (before.parent / "changed-library").exists()
        release.set()
        controller._shutdown_transfers()
        # The worker has finished, but its GUI completion is still queued.
        assert controller._pending_transfers == 1
        controller._save_settings(payload)
        assert controller.config.university_root == before
    finally:
        release.set()
    pump(qt_app, lambda: controller._pending_transfers == 0)
    controller._save_settings(payload)
    assert controller.config.university_root == before.parent / "changed-library"
    if controller.watcher is not None:
        controller.watcher.stop()


@pytest.mark.parametrize("phase", ["before_copy", "partial", "complete_before_record"])
def test_restart_never_publishes_an_interrupted_ingest_as_complete(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    source = app_config.downloads_dir / "crashed.pdf"
    original = b"important coursework" * 100
    source.write_bytes(original)

    def crash_move(src: Path, dst: Path, **kwargs: object) -> None:
        assert len(database.list_pending_ingests()) == 1
        if phase != "before_copy":
            dst.write_bytes(original[:50] if phase == "partial" else original)
        if phase == "complete_before_record":
            src.unlink()
        raise KeyboardInterrupt("simulated process termination")

    monkeypatch.setattr("organizador.filer.move_without_overwrite", crash_move)
    with pytest.raises(KeyboardInterrupt):
        filer.ingest(source)
    restarted = Database(app_config.database_path)
    restarted.initialize()
    report = reconcile.scan(app_config, restarted)
    assert not report.inbox_orphans
    reconcile.apply(restarted, report)
    remaining = reconcile.scan(app_config, restarted)
    if phase == "partial":
        assert source.read_bytes() == original
        assert (app_config.inbox_dir / source.name).read_bytes() == original[:50]
        assert all(item.status == "recovery" for item in restarted.list_inbox_items())
        assert any(
            f.reason == FindingReason.PENDING_INGEST_DESTINATION
            for f in reconcile.findings(remaining)
        )
        with pytest.raises(FilingError):
            filer.ingest(source)
        assert len(restarted.list_pending_ingests()) == 1
    elif phase == "before_copy":
        assert source.read_bytes() == original
        assert not restarted.list_inbox_items()
    else:
        item = restarted.list_inbox_items()[0]
        assert item.status == "pending"
        assert item.path.read_bytes() == original
        assert not source.exists()
    assert not remaining.inbox_orphans


def test_failed_ingest_cleanup_retains_journal_and_original(
    app_config: AppConfig, database: Database, filer: FilingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = app_config.downloads_dir / "partial.pdf"
    source.write_bytes(b"original" * 30)

    def incomplete(src: Path, dst: Path, **kwargs: object) -> None:
        dst.write_bytes(b"partial" * 3)
        raise IncompleteMoveError(dst)

    monkeypatch.setattr("organizador.filer.move_without_overwrite", incomplete)
    with pytest.raises(FilingError):
        filer.ingest(source)
    reconcile.apply(database, reconcile.scan(app_config, database))
    assert source.read_bytes() == b"original" * 30
    assert len(database.list_pending_ingests()) == 1
    assert database.list_inbox_items()[0].status == "recovery"


def test_killed_process_leaves_partial_copy_in_manual_review(
    app_config: AppConfig,
    database: Database,
) -> None:
    source = app_config.downloads_dir / "terminated.pdf"
    original = b"do not lose coursework" * 500
    source.write_bytes(original)
    app_config.save()
    marker = app_config.data_dir / "copy-started"
    code = r"""
import ctypes, sys, threading
from ctypes import wintypes
from pathlib import Path
from organizador import paths
from organizador.config import AppConfig
from organizador.db import Database
from organizador.filer import FilingService
config = AppConfig.load(Path(sys.argv[1]))
paths._rename_windows_handle = lambda *args: False
def partial_copy(kernel32, source, destination, size):
    write = kernel32.WriteFile
    write.argtypes = (wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                      ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID)
    write.restype = wintypes.BOOL
    written = wintypes.DWORD()
    content = b'do not lose coursework'
    assert write(destination, content, len(content), ctypes.byref(written), None)
    assert written.value == len(content)
    Path(sys.argv[3]).write_text('ready')
    threading.Event().wait(60)
paths._copy_windows_handles = partial_copy
FilingService(config, Database(config.database_path)).ingest(Path(sys.argv[2]))
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(app_config.data_dir), str(source), str(marker)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "child did not reach the interrupted copy"
    finally:
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=10)
    destination = app_config.inbox_dir / source.name
    assert source.read_bytes() == original
    assert destination.read_bytes() == b"do not lose coursework"
    report = reconcile.scan(app_config, database)
    assert report.inbox_orphans == ()
    reconcile.apply(database, report)
    assert len(database.list_pending_ingests()) == 1
    assert database.list_inbox_items()[0].status == "recovery"


def test_download_burst_preserves_collisions_retries_locks_and_survives_bad_pdf(
    qt_app: QApplication, controller: AppController, subject: Subject
) -> None:
    downloads = controller.config.downloads_dir
    originals = {
        "duplicate.txt": b"new coursework content" * 20,
        "locked.txt": b"temporarily locked coursework" * 20,
        "broken.pdf": b"not a valid PDF document" * 20,
    }
    for name, data in originals.items():
        (downloads / name).write_bytes(data)
    existing = controller.config.inbox_dir / "duplicate.txt"
    existing.write_bytes(b"older original")
    generation = controller._watcher_generation
    watcher = DownloadWatcher(
        controller.config,
        lambda candidate: controller.download_ready.emit(generation, candidate),
        retry_delays=(0.0,),
    )
    controller.watcher = watcher
    watcher.start(observe=False)
    with (downloads / "locked.txt").open("rb"):
        for name in originals:
            controller._ingest_download(generation, downloads / name)
        pump(qt_app, lambda: controller._pending_transfers == 0)
        assert watcher._retry_after
        assert (downloads / "locked.txt").read_bytes() == originals["locked.txt"]
        assert not controller.database.list_pending_ingests()
    watcher._sweep_once()
    pump(qt_app, lambda: len(controller.database.list_inbox_items()) == 3)
    pump(qt_app, lambda: controller._pending_transfers == 0)
    assert existing.read_bytes() == b"older original"
    for item in controller.database.list_inbox_items():
        assert item.path.read_bytes() == originals[item.original_name]
        controller._file_item(item.id, subject.id, "Slides", item.path.name, False, None)
    pump(qt_app, lambda: controller._pending_transfers == 0)
    pump(qt_app, lambda: all(d.indexed_at is not None for d in controller.database.list_files()))
    documents = controller.database.list_files()
    assert len(documents) == 3
    assert [d.original_name for d in documents if d.index_state == "failed"] == ["broken.pdf"]
    assert controller.database.search("coursework")
    assert controller.database.search("broken")
    for document in documents:
        assert document.current_path.read_bytes() == originals[document.original_name]
