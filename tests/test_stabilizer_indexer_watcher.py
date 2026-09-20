"""Background service boundary tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from stat import S_IFLNK
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication
from watchdog.events import FileCreatedEvent, FileMovedEvent

from organizador.config import AppConfig
from organizador.db import Database
from organizador.indexer import MAX_PENDING_INDEX_JOBS, DocumentIndexer, _cap_pages
from organizador.models import ExistingDownload, Subject
from organizador.stabilizer import wait_until_stable
from organizador.watcher import DownloadEventHandler, DownloadWatcher


def _file_record(database: Database, subject: Subject, path: Path) -> int:
    inbox = database.add_inbox_item(
        path, path.parent / "original.txt", path.name, path.stat().st_size
    )
    return database.record_filing(inbox.id, subject.id, "Outros", path).id


def test_stabilizer_accepts_unchanged_file_and_rejects_temporary(tmp_path: Path) -> None:
    stable = tmp_path / "aula.pdf"
    stable.write_bytes(b"complete")
    temporary = tmp_path / "aula.pdf.crdownload"
    temporary.write_bytes(b"partial")

    assert wait_until_stable(stable, interval=0.01, stable_samples=1, timeout=0.2)
    assert not wait_until_stable(temporary, interval=0.01, timeout=0.05)


def test_event_handler_uses_created_and_final_moved_path(tmp_path: Path) -> None:
    candidates: list[Path] = []
    handler = DownloadEventHandler(candidates.append)
    created = tmp_path / "notes.pdf"
    final = tmp_path / "slides.pdf"

    handler.on_created(FileCreatedEvent(str(created)))
    handler.on_moved(FileMovedEvent(str(tmp_path / "slides.part"), str(final)))

    assert candidates == [created, final]


def test_native_watcher_detects_a_new_stable_download(app_config: AppConfig) -> None:
    config = app_config
    ready = Event()
    candidates: list[Path] = []

    def received(path: Path) -> None:
        candidates.append(path)
        ready.set()

    watcher = DownloadWatcher(config, received)
    watcher.start()
    try:
        candidate = config.downloads_dir / "nova_aula.pdf"
        candidate.write_bytes(b"completed download")
        assert ready.wait(5.0), "watchdog did not emit the completed download"
        assert candidates == [candidate.resolve()]
    finally:
        watcher.stop()


def test_native_watcher_ignores_a_file_returned_by_the_app(app_config: AppConfig) -> None:
    ready = Event()
    watcher = DownloadWatcher(app_config, lambda _path: ready.set())
    watcher.start()
    try:
        watcher.set_paused(True)
        returned = app_config.downloads_dir / "not_university.pdf"
        returned.write_bytes(b"returned by Organizador")
        watcher.ignore_self_move(returned)
        watcher.set_paused(False)

        assert not ready.wait(3.0), "the watcher re-ingested its own returned file"
    finally:
        watcher.stop()


def test_paused_arrivals_are_released_after_resume(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready: list[Path] = []
    monkeypatch.setattr("organizador.watcher.wait_until_stable", lambda *_args, **_kwargs: True)
    watcher = DownloadWatcher(app_config, ready.append)
    watcher.start(observe=False)
    try:
        watcher.set_paused(True)
        candidate = app_config.downloads_dir / "chegou-em-pausa.pdf"
        candidate.write_bytes(b"paused arrival content")
        watcher.enqueue(candidate)
        watcher._sweep_once()
        assert ready == []

        watcher.set_paused(False)
        deadline = monotonic() + 5.0
        while not ready and monotonic() < deadline:
            sleep(0.02)

        assert [path.name for path in ready] == ["chegou-em-pausa.pdf"]
    finally:
        watcher.stop()


def test_resume_does_not_requeue_an_ignored_return(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready: list[Path] = []
    monkeypatch.setattr("organizador.watcher.wait_until_stable", lambda *_args, **_kwargs: True)
    watcher = DownloadWatcher(app_config, ready.append)
    watcher.start(observe=False)
    try:
        returned = app_config.downloads_dir / "devolvido-em-pausa.pdf"
        returned.write_bytes(b"returned by Organizador")
        watcher.set_paused(True)
        watcher.enqueue(returned)
        watcher.ignore_self_move(returned)
        watcher.set_paused(False)

        sleep(0.3)
        watcher._sweep_once()
        watcher._sweep_once()

        assert ready == []
    finally:
        watcher.stop()


def test_pause_during_stabilization_requeues_after_resume(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready: list[Path] = []
    holders: list[DownloadWatcher] = []
    paused_once = False

    def pause_then_stable(*_args: object, **_kwargs: object) -> bool:
        nonlocal paused_once
        if not paused_once:
            paused_once = True
            holders[0].set_paused(True)
        return True

    monkeypatch.setattr("organizador.watcher.wait_until_stable", pause_then_stable)
    watcher = DownloadWatcher(app_config, ready.append)
    holders.append(watcher)
    watcher.start(observe=False)
    try:
        candidate = app_config.downloads_dir / "pausado-a-estabilizar.pdf"
        candidate.write_bytes(b"stabilizing when pause began")
        watcher.enqueue(candidate)
        deadline = monotonic() + 5.0
        while watcher._pending and monotonic() < deadline:
            sleep(0.02)
        assert ready == []

        watcher.set_paused(False)
        deadline = monotonic() + 5.0
        while not ready and monotonic() < deadline:
            sleep(0.02)

        assert [path.name for path in ready] == ["pausado-a-estabilizar.pdf"]
    finally:
        watcher.stop()


def test_watcher_uses_one_key_for_directory_aliases(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ready = Event()
    candidate = app_config.downloads_dir / "returned.pdf"
    candidate.write_bytes(b"returned by Organizador")
    alias_dir = tmp_path / "downloads-alias"
    alias_path = alias_dir / candidate.name
    original_resolve = Path.resolve

    def resolve_alias(path: Path, strict: bool = False) -> Path:
        if path == alias_dir:
            return app_config.downloads_dir.resolve(strict=strict)
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve_alias)
    monkeypatch.setattr("organizador.watcher.wait_until_stable", lambda *_args, **_kwargs: True)
    watcher = DownloadWatcher(app_config, lambda _path: ready.set())
    watcher.start(observe=False)
    try:
        watcher.ignore_self_move(alias_path)
        watcher.enqueue(candidate)

        assert not ready.wait(0.2)
    finally:
        watcher.stop()


def test_watcher_retries_a_download_after_stabilization_timeout(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0
    ready = Event()

    def stabilize(*_args: object, **_kwargs: object) -> bool:
        nonlocal attempts
        attempts += 1
        return attempts > 1

    monkeypatch.setattr("organizador.watcher.wait_until_stable", stabilize)
    watcher = DownloadWatcher(app_config, lambda _path: ready.set(), retry_delays=(0.0,))
    watcher.start(observe=False)
    try:
        candidate = app_config.downloads_dir / "slow-download.pdf"
        candidate.write_bytes(b"eventually stable")
        watcher.enqueue(candidate)

        deadline = monotonic() + 2.0
        while not ready.is_set() and monotonic() < deadline:
            watcher._sweep_once()
            sleep(0.01)

        assert ready.is_set()
        assert attempts == 2
    finally:
        watcher.stop()


def test_stopping_manual_import_reports_unprocessed_candidates(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    stabilization_started = Event()
    completed: list[int] = []

    def wait_for_stop(*_args: object, **kwargs: object) -> bool:
        stabilization_started.set()
        stop_event = kwargs["stop_event"]
        assert isinstance(stop_event, Event)
        stop_event.wait(2.0)
        return False

    monkeypatch.setattr("organizador.watcher.wait_until_stable", wait_for_stop)
    candidate_path = app_config.downloads_dir / "manual.pdf"
    candidate_path.write_bytes(b"manual candidate")
    candidate = ExistingDownload.capture(candidate_path)
    assert candidate is not None
    watcher = DownloadWatcher(app_config, lambda _path: None, completed.append)
    watcher.start(observe=False)

    assert watcher.enqueue_existing([candidate]) == 1
    assert stabilization_started.wait(1.0)
    watcher.stop()

    assert completed == [1]
    assert not watcher.manual_import_running


def test_failed_sweep_preserves_the_existing_download_baseline(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = app_config.downloads_dir / "already-present.pdf"
    existing.write_bytes(b"existing download must stay put")
    ready: list[Path | ExistingDownload] = []
    watcher = DownloadWatcher(app_config, ready.append)
    baseline = watcher._snapshot()
    assert baseline is not None
    snapshots = iter((None, baseline))
    monkeypatch.setattr(watcher, "_snapshot", lambda: next(snapshots))
    monkeypatch.setattr("organizador.watcher.wait_until_stable", lambda *_args, **_kwargs: True)
    watcher.start(observe=False)
    try:
        watcher._known = set(baseline)
        watcher._sweep_once()
        watcher._sweep_once()
        sleep(0.1)

        assert ready == []
        assert existing.read_bytes() == b"existing download must stay put"
    finally:
        watcher.stop()


def test_stopping_watcher_suppresses_a_late_successful_stabilization(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    stabilization_started = Event()
    ready = Event()

    def finish_after_stop(*_args: object, **kwargs: object) -> bool:
        stabilization_started.set()
        stop_event = kwargs["stop_event"]
        assert isinstance(stop_event, Event)
        stop_event.wait(2.0)
        return True

    monkeypatch.setattr("organizador.watcher.wait_until_stable", finish_after_stop)
    candidate = app_config.downloads_dir / "late-success.pdf"
    candidate.write_bytes(b"late stabilization result")
    watcher = DownloadWatcher(app_config, lambda _path: ready.set())
    watcher.start(observe=False)
    watcher.enqueue(candidate)
    assert stabilization_started.wait(1.0)

    watcher.stop()

    assert not ready.is_set()
    assert candidate.exists()


def test_exhausted_retry_budget_resets_only_after_file_identity_changes(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0
    attempted = Event()

    def never_stable(*_args: object, **_kwargs: object) -> bool:
        nonlocal attempts
        attempts += 1
        attempted.set()
        return False

    monkeypatch.setattr("organizador.watcher.wait_until_stable", never_stable)
    candidate = app_config.downloads_dir / "never-stable.pdf"
    candidate.write_bytes(b"unchanged exhausted candidate")
    watcher = DownloadWatcher(app_config, lambda _path: None, retry_delays=())
    watcher.start(observe=False)
    try:
        watcher.enqueue(candidate)
        assert attempted.wait(1.0)
        attempted.clear()
        watcher.enqueue(candidate)
        assert not attempted.wait(0.2)
        assert attempts == 1

        candidate.write_bytes(b"replacement candidate with a new identity and size")
        watcher.enqueue(candidate)
        assert attempted.wait(1.0)
        assert attempts == 2
    finally:
        watcher.stop()


def test_requeue_schedules_bounded_ingest_retries(
    app_config: AppConfig,
) -> None:
    candidate = app_config.downloads_dir / "transient.pdf"
    candidate.write_bytes(b"delivered but unmoved")
    watcher = DownloadWatcher(app_config, lambda _path: None, retry_delays=(60.0, 60.0))
    try:
        watcher.requeue(candidate)
        assert len(watcher._retry_after) == 1
        key = next(iter(watcher._retry_after))
        assert watcher._retry_attempts[key] == 1

        watcher.requeue(candidate)
        assert watcher._retry_attempts[key] == 2

        watcher.requeue(candidate)
        assert key not in watcher._retry_after
        assert key not in watcher._retry_attempts
        assert key in watcher._retry_exhausted
    finally:
        watcher.stop()


def test_delivery_does_not_reset_the_bounded_retry_budget(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = app_config.downloads_dir / "delivered-then-failed.pdf"
    candidate.write_bytes(b"delivered but never moved")
    delivered = Event()

    monkeypatch.setattr("organizador.watcher.wait_until_stable", lambda *_args, **_kwargs: True)
    watcher = DownloadWatcher(app_config, lambda _path: delivered.set(), retry_delays=(0.0, 0.0))
    watcher.start(observe=False)

    def wait_worker_idle(value: str) -> None:
        deadline = monotonic() + 1.0
        while value in watcher._pending and monotonic() < deadline:
            sleep(0.01)

    try:
        watcher.enqueue(candidate)
        assert delivered.wait(1.0)
        delivered.clear()
        key = next(iter(watcher._known))
        wait_worker_idle(key)

        watcher.requeue(candidate)
        assert watcher._retry_attempts[key] == 1
        watcher._retry_after[key] = 0.0
        watcher._sweep_once()
        assert delivered.wait(1.0)
        delivered.clear()
        wait_worker_idle(key)

        watcher.requeue(candidate)
        assert watcher._retry_attempts[key] == 2
        watcher._retry_after[key] = 0.0
        watcher._sweep_once()
        assert delivered.wait(1.0)
        delivered.clear()
        wait_worker_idle(key)

        watcher.requeue(candidate)
        assert key not in watcher._retry_attempts
        assert key in watcher._retry_exhausted

        watcher.enqueue(candidate)
        assert not delivered.wait(0.2)
        assert watcher._queue.empty()
    finally:
        watcher.stop()


def test_expired_requeue_reaches_pending_through_the_sweep(
    app_config: AppConfig,
) -> None:
    candidate = app_config.downloads_dir / "retry-me.pdf"
    candidate.write_bytes(b"delivered but unmoved")
    watcher = DownloadWatcher(app_config, lambda _path: None, retry_delays=(60.0,))
    try:
        watcher.requeue(candidate)
        key = next(iter(watcher._retry_after))
        watcher._retry_after[key] = 0.0

        watcher._sweep_once()

        assert key in watcher._pending
        assert not watcher._queue.empty()
    finally:
        watcher.stop()


def test_ingest_failure_requeues_the_path_for_another_attempt(
    qt_app: QApplication,
    app_config: AppConfig,
    database: Database,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from organizador.controller import AppController
    from organizador.filer import FilingError
    from organizador.ui.tray import TrayIcon

    del subject
    controller = AppController(app_config)
    notices: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        controller.tray, "notify", lambda *args, **kwargs: notices.append((args, kwargs))
    )
    monkeypatch.setattr(TrayIcon, "available", property(lambda self: True))
    requeued: list[Path] = []
    controller.watcher = SimpleNamespace(requeue=requeued.append)  # type: ignore[assignment]

    def fail_ingest(path: Path, expected: object = None) -> None:
        raise FilingError("disco temporariamente indisponível")

    monkeypatch.setattr(controller.filer, "ingest", fail_ingest)
    path = app_config.downloads_dir / "falha.pdf"
    path.write_bytes(b"temporary ingestion failure")
    qt_app.processEvents()
    try:
        controller._ingest_download(controller._watcher_generation, path)

        deadline = monotonic() + 10.0
        while not requeued or not notices:
            if monotonic() >= deadline:
                raise AssertionError("timed out waiting for the ingest outcome")
            qt_app.processEvents()
            sleep(0.01)

        assert requeued == [path]
        assert notices and notices[0][0][0] == "Não foi possível recolher o ficheiro"
    finally:
        controller._shutdown_transfers()
        controller.indexer.shutdown()
        controller.tray.hide()
        controller.main_window.allow_close = True
        controller.main_window.close()


def test_confirmed_existing_batch_bypasses_pause_and_enforces_cap(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidates: list[ExistingDownload] = []
    for index in range(30):
        path = app_config.downloads_dir / f"existing_{index:02}.pdf"
        path.write_bytes(b"completed existing download")
        candidate = ExistingDownload.capture(path)
        assert candidate is not None
        candidates.append(candidate)
    ready: list[Path | ExistingDownload] = []
    completed = Event()
    skipped: list[int] = []

    def import_completed(count: int) -> None:
        skipped.append(count)
        completed.set()

    monkeypatch.setattr("organizador.watcher.wait_until_stable", lambda *_args, **_kwargs: True)
    watcher = DownloadWatcher(app_config, ready.append, import_completed)
    snapshot_calls: list[bool] = []
    monkeypatch.setattr(watcher, "_snapshot", lambda: snapshot_calls.append(True) or set())
    watcher.start(observe=False)
    watcher.set_paused(True)
    try:
        assert watcher.enqueue_existing(candidates) == 25
        assert completed.wait(3.0), "manual import batch did not complete"
        assert len(ready) == 25
        assert all(isinstance(item, ExistingDownload) for item in ready)
        assert skipped == [0]
        assert not watcher.running
        assert snapshot_calls == []
    finally:
        watcher.stop()


def test_text_and_notebook_indexing_is_searchable(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    text_path = tmp_path / "cadeia.txt"
    text_path.write_text("A regra da cadeia deriva funções compostas.", encoding="utf-8")
    text_id = _file_record(database, subject, text_path)
    notebook_path = tmp_path / "analise.ipynb"
    notebook_path.write_text(
        json.dumps({"cells": [{"cell_type": "markdown", "source": ["Integrais impróprios"]}]}),
        encoding="utf-8",
    )
    notebook_id = _file_record(database, subject, notebook_path)
    indexer = DocumentIndexer(database)

    text_document = database.get_file(text_id)
    notebook_document = database.get_file(notebook_id)
    assert text_document is not None
    assert notebook_document is not None
    indexer.index_document(text_document)
    indexer.index_document(notebook_document)
    indexer.shutdown()

    assert database.search("composta")[0].file_id == text_id
    assert database.search("improprio")[0].file_id == notebook_id


def test_indexer_rejects_new_work_after_shutdown(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "por_indexar.txt"
    path.write_text("conteúdo", encoding="utf-8")
    file_id = _file_record(database, subject, path)
    document = database.get_file(file_id)
    assert document is not None
    indexer = DocumentIndexer(database)

    indexer.shutdown()
    indexer.submit(document)

    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.indexed_at is None


def test_edited_document_is_reconsidered_for_search(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "editado.txt"
    path.write_text("fotossintese original", encoding="utf-8")
    file_id = _file_record(database, subject, path)
    indexer = DocumentIndexer(database)
    try:
        document = database.get_file(file_id)
        assert document is not None
        indexer.index_document(document)
        assert database.search("fotossintese")
        assert not database.search("respiracao")

        path.write_text("respiracao revista", encoding="utf-8")
        assert database.reset_stale_index_fingerprints() == 1

        reconsidered = database.get_file(file_id)
        assert reconsidered is not None
        indexer.index_document(reconsidered)
        assert database.search("respiracao")
        assert not database.search("fotossintese")
    finally:
        indexer.shutdown()


def test_missing_document_remains_pending_for_future_indexing(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "temporariamente-ausente.txt"
    path.write_text("conteúdo recuperável", encoding="utf-8")
    file_id = _file_record(database, subject, path)
    document = database.get_file(file_id)
    assert document is not None
    path.unlink()
    indexer = DocumentIndexer(database)

    indexer.index_document(document)
    indexer.shutdown()

    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.indexed_at is None


def test_missing_documents_do_not_starve_later_indexing_work(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    for index in range(51):
        missing = tmp_path / f"missing-{index:02}.txt"
        missing.write_text("temporarily missing", encoding="utf-8")
        _file_record(database, subject, missing)
        missing.unlink()
    healthy = tmp_path / "healthy.txt"
    healthy.write_text("ready to index", encoding="utf-8")
    healthy_id = _file_record(database, subject, healthy)

    pending = database.list_unindexed_documents(limit=50)

    assert [document.id for document in pending] == [healthy_id]


def test_failed_indexing_batch_does_not_starve_later_documents(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    for index in range(50):
        malformed = tmp_path / f"malformed-{index:02}.ipynb"
        malformed.write_text("not valid JSON", encoding="utf-8")
        _file_record(database, subject, malformed)
    healthy = tmp_path / "after-malformed.txt"
    healthy.write_text("healthy document after malformed batch", encoding="utf-8")
    healthy_id = _file_record(database, subject, healthy)
    indexer: DocumentIndexer

    def refill(_file_id: int, _error: str) -> None:
        indexer.submit_pending()

    indexer = DocumentIndexer(database, refill)
    try:
        indexer.submit_pending()
        deadline = monotonic() + 20.0
        while not database.search("healthy") and monotonic() < deadline:
            sleep(0.01)

        results = database.search("healthy")
        assert results
        assert results[0].file_id == healthy_id
    finally:
        indexer.shutdown()


def test_reindex_reports_when_the_queue_is_full(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "fila.txt"
    path.write_text("conteudo para reindexar", encoding="utf-8")
    file_id = _file_record(database, subject, path)
    document = database.get_file(file_id)
    assert document is not None
    indexer = DocumentIndexer(database)
    try:
        indexer._active = {(index, "") for index in range(MAX_PENDING_INDEX_JOBS)}

        assert indexer.reindex(document) is False

        indexer._active.clear()
        assert indexer.reindex(document) is True
    finally:
        indexer.shutdown()


def test_moving_a_queued_document_requeues_indexing_on_the_new_path(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    source = tmp_path / "antes.txt"
    source.write_text("conteudo movido para indexar", encoding="utf-8")
    file_id = _file_record(database, subject, source)
    stale = database.get_file(file_id)
    assert stale is not None
    other = database.add_subject("Outra", "OUT", "#123456", (), "OUT - Outra")
    destination = tmp_path / "depois.txt"
    pending = database.begin_document_move(file_id, other.id, "Outros", destination)
    source.replace(destination)
    database.complete_document_move(pending.id, destination, subject_id=other.id, kind="Outros")

    indexer = DocumentIndexer(database)
    try:
        indexer._attempted.add((file_id, stale.record_token))

        indexer.index_document(stale)

        assert (file_id, stale.record_token) not in indexer._attempted
        indexer.submit_pending()
        deadline = monotonic() + 10.0
        while not database.search("movido") and monotonic() < deadline:
            sleep(0.01)
        assert database.search("movido")
        stored = database.get_file(file_id)
        assert stored is not None
        assert stored.indexed_at is not None
    finally:
        indexer.shutdown()


def test_index_refill_keeps_a_fixed_outstanding_work_cap(
    database: Database,
    subject: Subject,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for index in range(MAX_PENDING_INDEX_JOBS + 10):
        path = tmp_path / f"queued-{index:02}.txt"
        path.write_text("queued document", encoding="utf-8")
        _file_record(database, subject, path)
    started = Event()
    release = Event()
    indexer = DocumentIndexer(database)

    def block_indexing(_document: object) -> None:
        started.set()
        release.wait(2.0)

    monkeypatch.setattr(indexer, "index_document", block_indexing)
    try:
        indexer.submit_pending()
        assert started.wait(1.0)
        for _ in range(5):
            indexer.submit_pending()

        assert len(indexer._active) == MAX_PENDING_INDEX_JOBS
    finally:
        release.set()
        indexer.shutdown()


def test_symlinked_document_is_never_selected_or_indexed(
    database: Database,
    subject: Subject,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "filed-link.txt"
    path.write_text("original document", encoding="utf-8")
    file_id = _file_record(database, subject, path)
    document = database.get_file(file_id)
    assert document is not None
    original_lstat = Path.lstat
    details = list(path.lstat())
    details[0] = S_IFLNK | 0o777
    symlink_details = os.stat_result(details)

    def report_symlink(candidate: Path) -> os.stat_result:
        return symlink_details if candidate == path else original_lstat(candidate)

    monkeypatch.setattr(Path, "lstat", report_symlink)
    indexer = DocumentIndexer(database)

    assert database.list_unindexed_documents() == []
    indexer.index_document(document)
    indexer.shutdown()

    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.indexed_at is None


def test_cap_pages_truncates_at_the_character_limit() -> None:
    kept, truncated = _cap_pages(["ab", "cdef", "gh"], limit=5)

    assert kept == ["ab", "cde"]
    assert truncated is True

    kept, truncated = _cap_pages(["ab", "cd"], limit=4)

    assert kept == ["ab", "cd"]
    assert truncated is False

    with pytest.raises(ValueError):
        _cap_pages(["ab"], limit=0)


def test_changed_file_size_refreshes_the_record_and_defers_indexing(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "editado.txt"
    path.write_bytes(b"x")
    file_id = _file_record(database, subject, path)
    path.write_bytes(b"y" * 5000)
    indexer = DocumentIndexer(database)

    indexer.index_document(database.get_file(file_id))
    indexer.shutdown()

    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.size == 5000
    assert refreshed.indexed_at is None

    indexer = DocumentIndexer(database)
    indexer.index_document(refreshed)
    indexer.shutdown()

    indexed = database.get_file(file_id)
    assert indexed is not None
    assert indexed.indexed_at is not None


def test_indexed_text_is_capped_but_head_terms_stay_searchable(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    from organizador.indexer import MAX_INDEX_CHARS

    head = "cabecalho-marcador-unico"
    tail = "cauda-marcador-unico"
    path = tmp_path / "longo.txt"
    path.write_text(head + "\n" + ("texto de enchimento\n" * 60000) + tail + "\n", encoding="utf-8")
    assert path.stat().st_size > MAX_INDEX_CHARS
    file_id = _file_record(database, subject, path)
    indexer = DocumentIndexer(database)

    indexer.index_document(database.get_file(file_id))
    indexer.shutdown()

    assert database.search("cabecalho-marcador-unico")
    assert database.search("cauda-marcador-unico") == []
    assert database.search("indexed") == []


def test_document_without_extractable_text_stays_findable_by_final_name(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "apontamento-vazio.txt"
    path.write_text("", encoding="utf-8")
    file_id = _file_record(database, subject, path)
    document = database.get_file(file_id)
    assert document is not None
    indexer = DocumentIndexer(database)

    indexer.index_document(document)
    indexer.shutdown()

    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.indexed_at is not None
    assert refreshed.index_state == ""
    results = database.search("apontamento-vazio")
    assert [result.file_id for result in results] == [file_id]
    assert results[0].title == "apontamento-vazio.txt"


def test_failed_extraction_can_be_fixed_and_reindexed(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    from docx import Document

    path = tmp_path / "quebrado.docx"
    path.write_bytes(b"not an OOXML archive")
    file_id = _file_record(database, subject, path)
    document = database.get_file(file_id)
    assert document is not None
    indexer = DocumentIndexer(database)

    indexer.index_document(document)
    indexer.shutdown()

    failed = database.get_file(file_id)
    assert failed is not None
    assert failed.indexed_at is not None
    assert failed.index_state == "failed"
    assert [document.id for document in database.list_failed_index_documents()] == [file_id]
    assert database.search("quebrado")

    repaired = Document()
    repaired.add_paragraph("conteúdo recuperado de testes")
    repaired.save(path)

    indexer = DocumentIndexer(database)
    indexer.reindex(failed)
    indexer.shutdown()
    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.indexed_at is None
    assert refreshed.index_state == ""

    for _ in range(3):
        current = database.get_file(file_id)
        assert current is not None
        if current.indexed_at is not None:
            break
        worker = DocumentIndexer(database)
        worker.index_document(current)
        worker.shutdown()

    assert database.search("recuperado")
    assert database.list_failed_index_documents() == []


def test_stabilizer_treats_a_zero_byte_finished_file_as_stable(tmp_path: Path) -> None:
    empty = tmp_path / "vazio.pdf"
    empty.write_bytes(b"")

    assert wait_until_stable(empty, interval=0.01, stable_samples=1, timeout=0.5)


def test_below_minimum_download_is_rejected_without_retrying(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready: list[Path | ExistingDownload] = []
    watcher = DownloadWatcher(app_config, ready.append, retry_delays=(0.0,))
    monkeypatch.setattr(
        "organizador.watcher.wait_until_stable",
        lambda path, **kwargs: wait_until_stable(
            path, interval=0.01, stable_samples=1, timeout=1.0, **kwargs
        ),
    )
    watcher.start(observe=False)
    try:
        tiny = app_config.downloads_dir / "abaixo-do-minimo.pdf"
        tiny.write_bytes(b"x" * 2)
        normalised = watcher._normalise_candidate(tiny)
        assert normalised is not None
        _, key = normalised
        watcher.enqueue(tiny)

        deadline = monotonic() + 5.0
        while key not in watcher._retry_exhausted and monotonic() < deadline:
            sleep(0.01)

        assert key in watcher._retry_exhausted
        assert watcher._retry_attempts == {}
        assert ready == []
    finally:
        watcher.stop()


def test_below_minimum_rejection_reconsiders_after_identity_change(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready: list[Path | ExistingDownload] = []
    watcher = DownloadWatcher(app_config, ready.append, retry_delays=(0.0,))
    monkeypatch.setattr(
        "organizador.watcher.wait_until_stable",
        lambda path, **kwargs: wait_until_stable(
            path, interval=0.01, stable_samples=1, timeout=1.0, **kwargs
        ),
    )
    watcher.start(observe=False)
    try:
        path = app_config.downloads_dir / "redownload.pdf"
        path.write_bytes(b"x" * 2)
        normalised = watcher._normalise_candidate(path)
        assert normalised is not None
        _, key = normalised
        watcher.enqueue(path)

        deadline = monotonic() + 5.0
        while key not in watcher._retry_exhausted and monotonic() < deadline:
            sleep(0.01)
        assert key in watcher._retry_exhausted

        sleep(0.01)
        path.write_bytes(b"x" * 400)
        watcher.enqueue(path)

        deadline = monotonic() + 5.0
        while not ready and monotonic() < deadline:
            sleep(0.01)

        assert ready == [path]
    finally:
        watcher.stop()


def test_tiny_download_does_not_starve_the_next_arrival(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready: list[Path | ExistingDownload] = []
    watcher = DownloadWatcher(app_config, ready.append, retry_delays=(0.0,))
    monkeypatch.setattr(
        "organizador.watcher.wait_until_stable",
        lambda path, **kwargs: wait_until_stable(
            path, interval=0.01, stable_samples=1, timeout=1.0, **kwargs
        ),
    )
    watcher.start(observe=False)
    try:
        tiny = app_config.downloads_dir / "pequeno.pdf"
        tiny.write_bytes(b"x" * 2)
        good = app_config.downloads_dir / "seguinte.pdf"
        good.write_bytes(b"x" * 400)
        watcher.enqueue(tiny)
        watcher.enqueue(good)

        deadline = monotonic() + 5.0
        while not ready and monotonic() < deadline:
            sleep(0.01)

        assert ready == [good]
    finally:
        watcher.stop()


def test_take_undelivered_returns_queued_candidates_and_clears(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Event()

    def blocked(*_args: object, **kwargs: object) -> bool:
        started.set()
        stop_event = kwargs["stop_event"]
        assert isinstance(stop_event, Event)
        stop_event.wait(2.0)
        return False

    monkeypatch.setattr("organizador.watcher.wait_until_stable", blocked)
    watcher = DownloadWatcher(app_config, lambda _path: None)
    watcher.start(observe=False)
    try:
        path = app_config.downloads_dir / "em-curso.pdf"
        path.write_bytes(b"still arriving")
        watcher.enqueue(path)
        assert started.wait(1.0)

        taken = watcher.take_undelivered()

        assert taken == [path]
        assert watcher.take_undelivered() == []
    finally:
        watcher.stop()


def test_restarted_watcher_delivers_a_stuck_download(
    app_config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Event()

    def blocked(*_args: object, **kwargs: object) -> bool:
        started.set()
        stop_event = kwargs["stop_event"]
        assert isinstance(stop_event, Event)
        stop_event.wait(2.0)
        return False

    monkeypatch.setattr("organizador.watcher.wait_until_stable", blocked)
    old = DownloadWatcher(app_config, lambda _path: None)
    old.start(observe=False)
    path = app_config.downloads_dir / "resgatado.pdf"
    path.write_bytes(b"queued in the old watcher")
    old.enqueue(path)
    assert started.wait(1.0)
    undelivered = old.take_undelivered()
    old.stop()

    monkeypatch.setattr("organizador.watcher.wait_until_stable", lambda *_args, **_kwargs: True)
    delivered: list[Path | ExistingDownload] = []
    replacement = DownloadWatcher(app_config, delivered.append)
    replacement.start(observe=False)
    try:
        # Simulate the observe=True baseline that strands the file.
        baseline = replacement._snapshot()
        assert baseline is not None
        replacement._known = set(baseline)

        replacement.adopt(undelivered)

        deadline = monotonic() + 3.0
        while not delivered and monotonic() < deadline:
            sleep(0.01)

        assert delivered == [path]
    finally:
        replacement.stop()


def test_settings_restart_keeps_a_stabilizing_download(
    qt_app: QApplication,
    app_config: AppConfig,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from organizador.controller import AppController

    del subject
    calls = 0
    started = Event()

    def stabilize(*_args: object, **kwargs: object) -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            stop_event = kwargs["stop_event"]
            assert isinstance(stop_event, Event)
            stop_event.wait(2.0)
            return False
        return True

    monkeypatch.setattr("organizador.watcher.wait_until_stable", stabilize)
    controller = AppController(app_config)
    app_config.watch_enabled = False
    try:
        controller._restart_watcher()
        first_watcher = controller.watcher
        assert first_watcher is not None
        path = app_config.downloads_dir / "a-caminho.pdf"
        path.write_bytes(b"stabilizing download" * 10)
        first_watcher.enqueue(path)
        assert started.wait(1.0)

        # A settings save restarts the watcher while the file stabilizes.
        controller._restart_watcher()

        deadline = monotonic() + 10.0
        while controller.database.count_inbox_items() == 0 and monotonic() < deadline:
            qt_app.processEvents()
            sleep(0.01)

        assert controller.database.count_inbox_items() == 1
    finally:
        controller._shutdown_transfers()
        controller.indexer.shutdown()
        controller.tray.hide()
        controller.main_window.allow_close = True
        controller.main_window.close()
