"""Startup consistency checks that never mutate user documents."""

from __future__ import annotations

from pathlib import Path

import pytest

from organizador import reconcile
from organizador.config import AppConfig
from organizador.db import Database
from organizador.filer import FilingService
from organizador.models import FindingReason, ReconciliationFinding, Subject
from organizador.reconcile import (
    adopt_untracked_subject_file,
    apply,
    dismiss_finding,
    drop_missing_document,
    findings,
    scan,
    unregister_adopted_document,
    visible_findings,
)


def test_scan_reports_subjects_sharing_one_windows_folder(
    app_config: AppConfig, database: Database, subject: Subject
) -> None:
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO subjects(name, code, color, keywords_json, folder_name, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                "CÁLCULO CLONE",
                "CAL101",
                "#123456",
                "[]",
                "MAT101 - CÁLCULO I",
                "2026-01-01T00:00:00",
            ),
        )
        connection.commit()

    report = scan(app_config, database)

    assert len(report.subject_folder_collisions) == 1
    finding = report.subject_folder_collisions[0]
    assert finding.reason is FindingReason.SUBJECT_FOLDER_COLLISION
    assert finding in findings(report)
    assert finding in visible_findings(database, report)
    assert dismiss_finding(database, finding) is True
    assert finding not in visible_findings(database, scan(app_config, database))


def _snapshot(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_scan_and_apply_recover_only_safe_database_states(
    app_config: AppConfig,
    database: Database,
    subject: Subject,
) -> None:
    orphan = app_config.inbox_dir / "MAT101_recuperado.pdf"
    orphan.write_bytes(b"untracked inbox document")

    interrupted_path = app_config.inbox_dir / "interrompido.pdf"
    interrupted_path.write_bytes(b"interrupted filing document")
    interrupted = database.add_inbox_item(
        interrupted_path,
        app_config.downloads_dir / interrupted_path.name,
        interrupted_path.name,
        interrupted_path.stat().st_size,
    )
    database.set_inbox_status(interrupted.id, "filing")

    missing_path = app_config.inbox_dir / "desaparecido.pdf"
    missing = database.add_inbox_item(
        missing_path,
        app_config.downloads_dir / missing_path.name,
        missing_path.name,
        200,
    )

    subject_folder = app_config.university_root / subject.folder_name / "Slides"
    untracked_subject = subject_folder / "sem-registo.pdf"
    untracked_subject.write_bytes(b"untracked subject document")

    filed_source = app_config.inbox_dir / "organizado.pdf"
    filed_source.write_bytes(b"filed document")
    filed_item = database.add_inbox_item(
        filed_source,
        app_config.downloads_dir / filed_source.name,
        filed_source.name,
        filed_source.stat().st_size,
    )
    filed_destination = subject_folder / "organizado.pdf"
    filed_source.replace(filed_destination)
    missing_document = database.record_filing(
        filed_item.id,
        subject.id,
        "Slides",
        filed_destination,
    )
    filed_destination.unlink()

    downloads_file = app_config.downloads_dir / "nunca-analisar.pdf"
    downloads_file.write_bytes(b"Downloads remains outside reconciliation")
    before = _snapshot(app_config.university_root)

    report = scan(app_config, database)

    assert _snapshot(app_config.university_root) == before
    assert [candidate.path for candidate in report.inbox_orphans] == [orphan]
    assert [item.id for item in report.interrupted_filings] == [interrupted.id]
    assert report.missing_inbox_items == (missing,)
    assert report.untracked_subject_files == (untracked_subject,)
    assert report.missing_documents == (missing_document,)
    assert len(report.broken_undo_events) == 1
    assert report.broken_undo_events[0].destination_path == filed_destination
    assert downloads_file not in {
        *(candidate.path for candidate in report.inbox_orphans),
        *report.untracked_subject_files,
    }

    outcome = apply(database, report)

    assert _snapshot(app_config.university_root) == before
    assert [item.path for item in outcome.recovered_items] == [orphan]
    assert outcome.reset_filing_ids == (interrupted.id,)
    assert outcome.recovery_required_ids == (missing.id,)
    recovered_interrupted = database.get_inbox_item(interrupted.id)
    assert recovered_interrupted is not None
    assert recovered_interrupted.status == "pending"
    recovered_missing = database.get_inbox_item(missing.id)
    assert recovered_missing is not None
    assert recovered_missing.status == "recovery"
    assert "Recuperação necessária" in recovered_missing.last_error
    assert database.get_file(missing_document.id) == missing_document
    assert untracked_subject.read_bytes() == b"untracked subject document"
    assert downloads_file.read_bytes() == b"Downloads remains outside reconciliation"

    second_outcome = apply(database, scan(app_config, database))

    assert second_outcome.change_count == 0
    assert _snapshot(app_config.university_root) == before


def test_recovery_record_is_reactivated_if_the_file_returns_to_inbox(
    app_config: AppConfig,
    database: Database,
) -> None:
    path = app_config.inbox_dir / "restaurado.pdf"
    item = database.add_inbox_item(
        path,
        app_config.downloads_dir / path.name,
        path.name,
        100,
    )
    first_outcome = apply(database, scan(app_config, database))
    assert first_outcome.recovery_required_ids == (item.id,)

    path.write_bytes(b"manually restored file")
    report = scan(app_config, database)
    assert [candidate.path for candidate in report.inbox_orphans] == [path]

    second_outcome = apply(database, report)

    assert [recovered.id for recovered in second_outcome.recovered_items] == [item.id]
    restored = database.get_inbox_item(item.id)
    assert restored is not None
    assert restored.status == "pending"
    assert restored.size == path.stat().st_size
    assert restored.last_error == ""


def test_changed_orphan_is_not_registered_from_a_stale_scan(
    app_config: AppConfig,
    database: Database,
) -> None:
    path = app_config.inbox_dir / "mudou.pdf"
    path.write_bytes(b"original orphan file")
    report = scan(app_config, database)
    path.write_bytes(b"changed after the read-only scan")

    outcome = apply(database, report)

    assert outcome.change_count == 0
    assert database.find_active_inbox_by_path(path) is None
    assert path.read_bytes() == b"changed after the read-only scan"


def test_unreadable_file_is_never_persisted_as_missing(
    app_config: AppConfig,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = app_config.inbox_dir / "temporariamente-inacessivel.pdf"
    path.write_bytes(b"still present")
    item = database.add_inbox_item(
        path,
        app_config.downloads_dir / path.name,
        path.name,
        path.stat().st_size,
    )
    original_lstat = Path.lstat

    def deny_target(candidate: Path) -> object:
        if candidate == path:
            raise PermissionError("temporarily unavailable")
        return original_lstat(candidate)

    monkeypatch.setattr(Path, "lstat", deny_target)

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert report.incomplete
    assert report.missing_inbox_items == ()
    assert outcome.change_count == 0
    unchanged = database.get_inbox_item(item.id)
    assert unchanged is not None
    assert unchanged.status == "pending"


def test_unreadable_directory_marks_scan_incomplete_without_registering_files(
    app_config: AppConfig,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orphan = app_config.inbox_dir / "nao-observado.pdf"
    orphan.write_bytes(b"must remain unregistered")
    original_iterdir = Path.iterdir

    def deny_inbox(candidate: Path) -> object:
        if candidate == app_config.inbox_dir:
            raise PermissionError("directory temporarily unavailable")
        return original_iterdir(candidate)

    monkeypatch.setattr(Path, "iterdir", deny_inbox)

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert report.incomplete
    assert report.inbox_orphans == ()
    assert outcome.change_count == 0
    assert database.find_active_inbox_by_path(orphan) is None
    assert orphan.read_bytes() == b"must remain unregistered"


def test_prepared_undo_is_completed_after_a_crash_between_move_and_commit(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "desfazer-interrompido.pdf"
    source.write_bytes(b"undo crash boundary" * 20)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", source.name)
    event = database.latest_undoable_filing()
    assert event is not None
    document.current_path.write_bytes(b"edited after filing" * 20)
    restored_path = event.source_path
    pending = database.begin_filing_undo(event, restored_path)
    document.current_path.replace(restored_path)
    before = _snapshot(app_config.university_root)

    report = scan(app_config, database)

    assert report.pending_undo_events == (pending,)
    assert report.inbox_orphans == ()
    assert report.missing_documents == ()
    assert report.broken_undo_events == ()

    outcome = apply(database, report)

    assert _snapshot(app_config.university_root) == before
    assert outcome.completed_undo_event_ids == (pending.id,)
    assert [recovered.id for recovered in outcome.recovered_items] == [item.id]
    restored = database.get_inbox_item(item.id)
    assert restored is not None
    assert restored.status == "pending"
    assert restored.path == restored_path
    assert database.get_file(document.id) is None
    assert database.list_pending_undos() == []
    assert database.latest_undoable_filing() is None
    assert database.activity_summary().operations_recovered == 1


def test_interrupted_replacement_undo_restores_the_previous_version_path(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    first_source = app_config.downloads_dir / "aula.pdf"
    first_source.write_bytes(b"versao antiga " * 20)
    first_item = filer.ingest(first_source)
    assert first_item is not None
    old = filer.file_document(first_item.id, subject.id, "Slides", "Aula.pdf")

    second_source = app_config.downloads_dir / "aula-copia.pdf"
    second_source.write_bytes(b"versao nova " * 20)
    second_item = filer.ingest(second_source)
    assert second_item is not None
    new_document = filer.file_document(
        second_item.id, subject.id, "Slides", "Aula.pdf", replace_document_id=old.id
    )
    event = database.latest_undoable_filing()
    assert event is not None
    version_event = database.linked_version_event(event)
    assert version_event is not None
    assert version_event.source_path.is_file()
    restored_path = app_config.inbox_dir / "Aula.pdf"

    pending = database.begin_filing_undo(
        event, restored_path, source_path=new_document.current_path
    )
    new_document.current_path.replace(restored_path)
    version_event.destination_path.replace(version_event.source_path)

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert outcome.completed_undo_event_ids == (pending.id,)
    assert database.get_file(new_document.id) is None
    stored_old = database.get_file(old.id)
    assert stored_old is not None
    assert stored_old.current_path == version_event.source_path
    assert stored_old.current_path.is_file()
    assert database.list_pending_undos() == []
    with database.connect() as connection:
        undone_at = connection.execute(
            "SELECT undone_at FROM events WHERE id = ?", (version_event.id,)
        ).fetchone()[0]
    assert undone_at is not None
    remaining = scan(app_config, database)
    assert remaining.missing_documents == ()
    assert remaining.pending_undo_events == ()


def test_prepared_undo_is_cancelled_when_the_move_never_started(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "desfazer-nao-iniciado.pdf"
    source.write_bytes(b"undo did not start" * 20)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", source.name)
    event = database.latest_undoable_filing()
    assert event is not None
    pending = database.begin_filing_undo(event, event.source_path)

    outcome = apply(database, scan(app_config, database))

    assert outcome.cancelled_undo_event_ids == (pending.id,)
    assert database.list_pending_undos() == []
    assert document.current_path.exists()
    assert database.get_file(document.id) == document
    assert database.latest_undoable_filing() == event


def test_legacy_interrupted_undo_reuses_the_original_inbox_record(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "desfazer-antigo.pdf"
    source.write_bytes(b"legacy interrupted undo" * 20)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", source.name)
    event = database.latest_undoable_filing()
    assert event is not None
    document.current_path.replace(event.source_path)

    report = scan(app_config, database)

    assert [undo.event.id for undo in report.legacy_interrupted_undos] == [event.id]
    assert report.inbox_orphans == ()
    assert report.broken_undo_events == ()

    outcome = apply(database, report)

    assert outcome.completed_undo_event_ids == (event.id,)
    assert [recovered.id for recovered in outcome.recovered_items] == [item.id]
    assert database.get_file(document.id) is None
    assert database.count_inbox_items() == 1


def test_prepared_filing_is_completed_after_a_post_move_crash(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "arquivo-interrompido.pdf"
    source.write_bytes(b"pending filing" * 20)
    item = filer.ingest(source)
    assert item is not None
    destination = app_config.university_root / subject.folder_name / "Slides" / source.name
    pending = database.begin_document_filing(item.id, subject.id, "Slides", destination)
    item.path.replace(destination)
    before = _snapshot(app_config.university_root)

    report = scan(app_config, database)

    assert report.pending_filing_events == (pending,)
    assert report.untracked_subject_files == ()
    assert report.missing_inbox_items == ()

    outcome = apply(database, report)

    assert _snapshot(app_config.university_root) == before
    assert outcome.completed_operation_event_ids == (pending.id,)
    document = database.list_files()[0]
    assert document.current_path == destination
    filed_item = database.get_inbox_item(item.id)
    assert filed_item is not None
    assert filed_item.status == "filed"
    assert database.list_pending_filings() == []

    repeated = apply(database, report)
    assert repeated.change_count == 0
    assert len(database.list_files()) == 1
    assert database.activity_summary().operations_recovered == 1


def test_prepared_filing_with_a_size_mismatch_is_left_for_review(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "arquivo-tamanho.pdf"
    source.write_bytes(b"pending filing" * 20)
    item = filer.ingest(source)
    assert item is not None
    destination = app_config.university_root / subject.folder_name / "Slides" / source.name
    pending = database.begin_document_filing(item.id, subject.id, "Slides", destination)
    item.path.replace(destination)
    destination.write_bytes(b"tiny")

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert outcome.completed_operation_event_ids == ()
    assert database.list_pending_filings() == [pending]
    assert database.list_files() == []
    reasons = {finding.reason for finding in findings(report)}
    assert FindingReason.PENDING_FILING_SOURCE in reasons
    assert FindingReason.PENDING_FILING_DESTINATION in reasons


def test_prepared_move_is_completed_after_a_post_move_crash(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "mover-interrompido.pdf"
    source.write_bytes(b"pending move" * 20)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", "Aula.pdf")
    other = database.add_subject("Outra", "OUT", "#123456", (), "OUT - Outra")
    filer.ensure_subject_structure(other)
    destination = app_config.university_root / other.folder_name / "Outros" / "Aula.pdf"
    pending = database.begin_document_move(document.id, other.id, "Outros", destination)
    document.current_path.replace(destination)
    before = _snapshot(app_config.university_root)

    report = scan(app_config, database)

    assert report.pending_move_events == (pending,)
    assert report.untracked_subject_files == ()
    assert report.missing_documents == ()

    outcome = apply(database, report)

    assert _snapshot(app_config.university_root) == before
    assert outcome.completed_operation_event_ids == (pending.id,)
    stored = database.get_file(document.id)
    assert stored is not None
    assert stored.current_path == destination
    assert stored.subject_id == other.id
    assert stored.kind == "Outros"
    assert database.list_pending_moves() == []
    assert database.activity_summary().operations_recovered == 1


def test_prepared_move_with_a_size_mismatch_is_left_for_review(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "mover-tamanho.pdf"
    source.write_bytes(b"pending move" * 20)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", "Aula.pdf")
    other = database.add_subject("Outra", "OUT", "#123456", (), "OUT - Outra")
    filer.ensure_subject_structure(other)
    destination = app_config.university_root / other.folder_name / "Outros" / "Aula.pdf"
    pending = database.begin_document_move(document.id, other.id, "Outros", destination)
    document.current_path.replace(destination)
    destination.write_bytes(b"tiny")

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert outcome.completed_operation_event_ids == ()
    assert database.list_pending_moves() == [pending]
    reasons = {finding.reason for finding in findings(report)}
    assert FindingReason.PENDING_MOVE_SOURCE in reasons
    assert FindingReason.PENDING_MOVE_DESTINATION in reasons


def test_prepared_move_is_cancelled_when_the_file_never_left(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "mover-cancelado.pdf"
    source.write_bytes(b"pending move" * 20)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", "Aula.pdf")
    other = database.add_subject("Outra", "OUT", "#123456", (), "OUT - Outra")
    filer.ensure_subject_structure(other)
    destination = app_config.university_root / other.folder_name / "Outros" / "Aula.pdf"
    pending = database.begin_document_move(document.id, other.id, "Outros", destination)

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert outcome.cancelled_operation_event_ids == (pending.id,)
    assert database.list_pending_moves() == []
    stored = database.get_file(document.id)
    assert stored is not None
    assert stored.current_path == document.current_path
    assert stored.subject_id == subject.id


def test_prepared_undo_with_a_size_mismatch_is_left_for_review(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "desfazer-tamanho.pdf"
    source.write_bytes(b"undo size mismatch" * 20)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", source.name)
    event = database.latest_undoable_filing()
    assert event is not None
    pending = database.begin_filing_undo(event, event.source_path)
    document.current_path.unlink()
    event.source_path.write_bytes(b"x")

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert outcome.completed_undo_event_ids == ()
    assert database.list_pending_undos() == [pending]
    stored = database.get_file(document.id)
    assert stored is not None
    assert stored.current_path == document.current_path


def test_prepared_return_with_a_size_mismatch_is_left_for_review(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
) -> None:
    source = app_config.downloads_dir / "devolucao-tamanho.pdf"
    source.write_bytes(b"pending return" * 20)
    item = filer.ingest(source)
    assert item is not None
    destination = app_config.downloads_dir / source.name
    pending = database.begin_return(item.id, destination)
    item.path.replace(destination)
    destination.write_bytes(b"tiny")

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert outcome.completed_operation_event_ids == ()
    assert database.list_pending_returns() == [pending]


def test_prepared_return_is_completed_after_a_post_move_crash(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
) -> None:
    source = app_config.downloads_dir / "devolucao-interrompida.pdf"
    source.write_bytes(b"pending return" * 20)
    item = filer.ingest(source)
    assert item is not None
    destination = app_config.downloads_dir / source.name
    pending = database.begin_return(item.id, destination)
    item.path.replace(destination)
    before = destination.read_bytes()

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert report.pending_return_events == (pending,)
    assert outcome.completed_operation_event_ids == (pending.id,)
    assert destination.read_bytes() == before
    returned = database.get_inbox_item(item.id)
    assert returned is not None
    assert returned.status == "returned"
    assert database.list_pending_returns() == []

    repeated = apply(database, report)
    assert repeated.change_count == 0
    with database.connect() as connection:
        return_events = int(
            connection.execute("SELECT COUNT(*) FROM events WHERE action = 'return'").fetchone()[0]
        )
    assert return_events == 1


def test_non_regular_tracked_path_requires_manual_review(
    app_config: AppConfig,
    database: Database,
) -> None:
    path = app_config.inbox_dir / "substituido.pdf"
    item = database.add_inbox_item(
        path,
        app_config.downloads_dir / path.name,
        path.name,
        100,
    )
    path.mkdir()

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert report.unsafe_paths == (path,)
    assert report.missing_inbox_items == ()
    assert outcome.change_count == 0
    unchanged = database.get_inbox_item(item.id)
    assert unchanged is not None
    assert unchanged.status == "pending"
    assert path.is_dir()


def test_scan_limit_bounds_directory_work(
    app_config: AppConfig,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = app_config.inbox_dir / "primeiro.pdf"
    second = app_config.inbox_dir / "segundo.pdf"
    first.write_bytes(b"first orphan file")
    second.write_bytes(b"second orphan file")
    monkeypatch.setattr(reconcile, "SCAN_LIMIT", 1)

    report = scan(app_config, database)

    assert report.truncated
    assert len(report.inbox_orphans) == 1
    assert first.exists()
    assert second.exists()


def test_untracked_subject_file_can_be_adopted_and_unregistered_without_disk_changes(
    app_config: AppConfig,
    database: Database,
    subject: Subject,
) -> None:
    path = app_config.university_root / subject.folder_name / "Slides" / "legacy.pdf"
    path.write_bytes(b"existing study document")
    before = _snapshot(app_config.university_root)
    report = scan(app_config, database)
    finding = next(
        item for item in findings(report) if item.reason is FindingReason.UNTRACKED_SUBJECT_FILE
    )

    document = adopt_untracked_subject_file(app_config, database, finding)

    assert document.origin == "adopted"
    assert document.current_path == path
    assert _snapshot(app_config.university_root) == before
    assert scan(app_config, database).untracked_subject_files == ()

    assert unregister_adopted_document(database, document)
    assert _snapshot(app_config.university_root) == before
    untracked_again = scan(app_config, database)
    assert untracked_again.untracked_subject_files == (path,)
    assert visible_findings(database, untracked_again) == ()


def test_adoption_rejects_a_file_changed_since_the_scan(
    app_config: AppConfig,
    database: Database,
    subject: Subject,
) -> None:
    path = app_config.university_root / subject.folder_name / "Slides" / "changed.pdf"
    path.write_bytes(b"original contents")
    finding = next(
        item
        for item in findings(scan(app_config, database))
        if item.reason is FindingReason.UNTRACKED_SUBJECT_FILE
    )
    path.write_bytes(b"replacement contents with a different size")

    with pytest.raises(LookupError, match="mudou"):
        adopt_untracked_subject_file(app_config, database, finding)

    assert database.list_files() == []
    assert path.read_bytes() == b"replacement contents with a different size"


def test_missing_record_is_dropped_only_while_the_file_remains_absent(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "missing.pdf"
    contents = b"missing catalog document" * 20
    source.write_bytes(contents)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", source.name)
    document.current_path.unlink()
    missing_finding = next(
        item
        for item in findings(scan(app_config, database))
        if item.reason is FindingReason.MISSING_DOCUMENT
    )
    assert missing_finding.document is not None

    document.current_path.write_bytes(contents)
    assert not drop_missing_document(database, missing_finding.document)
    assert database.get_file(document.id) is not None

    document.current_path.unlink()
    current_finding = next(
        item
        for item in findings(scan(app_config, database))
        if item.reason is FindingReason.MISSING_DOCUMENT
    )
    assert current_finding.document is not None
    assert drop_missing_document(database, current_finding.document)
    assert database.get_file(document.id) is None
    assert database.latest_undoable_filing() is None
    assert not document.current_path.exists()
    with database.connect() as connection:
        tombstone = connection.execute(
            "SELECT catalog_state FROM files WHERE id = ?", (document.id,)
        ).fetchone()
    assert tombstone is not None
    assert tombstone["catalog_state"] == "dropped"

    document.current_path.write_bytes(contents)
    returned_finding = next(
        item
        for item in findings(scan(app_config, database))
        if item.reason is FindingReason.UNTRACKED_SUBJECT_FILE
    )
    readopted = adopt_untracked_subject_file(app_config, database, returned_finding)
    assert readopted.id == document.id
    assert readopted.catalog_state == "active"
    assert document.current_path.read_bytes() == contents


def test_reviewing_one_reason_does_not_hide_another_at_the_same_path(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = app_config.downloads_dir / "two-reasons.pdf"
    source.write_bytes(b"two reconciliation reasons" * 20)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", source.name)
    document.current_path.unlink()
    report = scan(app_config, database)
    initial = visible_findings(database, report)
    reasons = {finding.reason for finding in initial if finding.path == document.current_path}
    assert reasons == {
        FindingReason.MISSING_DOCUMENT,
        FindingReason.BROKEN_UNDO_EVENT,
    }
    missing = next(
        finding for finding in initial if finding.reason is FindingReason.MISSING_DOCUMENT
    )

    assert dismiss_finding(database, missing)

    reopened = Database(database.path)
    remaining = visible_findings(reopened, report)
    assert [finding.reason for finding in remaining] == [FindingReason.BROKEN_UNDO_EVENT]

    document.current_path.write_bytes(b"restored")
    assert visible_findings(database, scan(app_config, database)) == ()
    assert database.list_reviewed_finding_keys() == set()


def test_pending_operation_finding_cannot_be_dismissed(database: Database, tmp_path: Path) -> None:
    finding = ReconciliationFinding(
        tmp_path / "pending.pdf",
        FindingReason.PENDING_FILING_DESTINATION,
    )

    assert not dismiss_finding(database, finding)
    assert database.list_reviewed_finding_keys() == set()


def test_missing_record_rechecks_absence_inside_the_database_operation(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = app_config.downloads_dir / "restored-during-drop.txt"
    contents = b"restored while catalog removal is starting"
    source.write_bytes(contents)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Outros", source.name)
    document.current_path.unlink()
    original_probe = reconcile._probe
    probes = 0

    def restore_on_second_probe(path: Path, state: object = None) -> object:
        nonlocal probes
        if path == document.current_path:
            probes += 1
            if probes == 2:
                path.write_bytes(contents)
        return original_probe(path, state)  # type: ignore[arg-type]

    monkeypatch.setattr(reconcile, "_probe", restore_on_second_probe)

    assert not drop_missing_document(database, document)
    assert database.get_file(document.id) == document
    assert document.current_path.read_bytes() == contents


def test_drop_tombstone_recovers_a_file_appearing_after_the_last_probe(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = app_config.downloads_dir / "late-restored.txt"
    contents = b"restored immediately after the final absence result"
    source.write_bytes(contents)
    item = filer.ingest(source)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Outros", source.name)
    document.current_path.unlink()
    original_probe = reconcile._probe
    probes = 0

    def recreate_after_result(path: Path, state: object = None) -> object:
        nonlocal probes
        if path == document.current_path:
            probes += 1
            if probes == 2:
                path.write_bytes(contents)
                return reconcile._ProbeState.MISSING
        return original_probe(path, state)  # type: ignore[arg-type]

    monkeypatch.setattr(reconcile, "_probe", recreate_after_result)

    assert drop_missing_document(database, document)
    assert document.current_path.read_bytes() == contents
    assert database.get_file(document.id) is None
    with database.connect() as connection:
        tombstone = connection.execute(
            "SELECT catalog_state FROM files WHERE id = ?", (document.id,)
        ).fetchone()
    assert tombstone is not None
    assert tombstone["catalog_state"] == "dropped"

    monkeypatch.setattr(reconcile, "_probe", original_probe)
    finding = next(
        item
        for item in findings(scan(app_config, database))
        if item.reason is FindingReason.UNTRACKED_SUBJECT_FILE
    )
    recovered = adopt_untracked_subject_file(app_config, database, finding)
    assert recovered.id == document.id
    assert recovered.record_token != document.record_token
    assert recovered.current_path.read_bytes() == contents


def test_reconciliation_and_adoption_compare_canonical_paths(
    app_config: AppConfig,
    database: Database,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual = app_config.university_root / subject.folder_name / "Slides" / "aliased.pdf"
    actual.write_bytes(b"one physical document")
    inbox_path = app_config.inbox_dir / "catalog-row.pdf"
    inbox_path.write_bytes(b"catalog metadata source")
    item = database.add_inbox_item(
        inbox_path,
        app_config.downloads_dir / inbox_path.name,
        inbox_path.name,
        inbox_path.stat().st_size,
    )
    alias = app_config.university_root / "directory-alias" / actual.name
    database.record_filing(item.id, subject.id, "Slides", alias)
    original_key = reconcile.normalise_path_key

    def alias_key(path: Path) -> str:
        if path.name == actual.name and path.parent.name in {"Slides", "directory-alias"}:
            return "same-physical-file"
        return original_key(path)

    monkeypatch.setattr(reconcile, "normalise_path_key", alias_key)
    monkeypatch.setattr("organizador.db.normalise_path_key", alias_key)

    report = scan(app_config, database)
    candidate = reconcile.ExistingDownload.capture(actual)
    assert candidate is not None
    assert report.untracked_subject_files == ()
    with pytest.raises(LookupError, match="outro caminho"):
        database.adopt_subject_file(candidate, subject.id, "Slides")


def test_conflicted_ingest_pending_does_not_abort_the_reconciliation(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    destination = app_config.inbox_dir / "conflito.pdf"
    destination.write_bytes(b"interrupted ingest" * 10)
    stale = database.add_inbox_item(
        destination,
        app_config.downloads_dir / destination.name,
        destination.name,
        destination.stat().st_size,
    )
    source = app_config.downloads_dir / "conflito.pdf"
    with database.connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO inbox(path, original_path, original_name, size, detected_at, status)
            VALUES (?, ?, ?, ?, '2026-09-03T00:00:00+00:00', 'recovery')
            """,
            (str(destination), str(source), source.name, destination.stat().st_size),
        )
        recovery_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO events(action, source_path, destination_path, inbox_id, created_at)
            VALUES ('ingest_pending', ?, ?, ?, '2026-09-03T00:00:00+00:00')
            """,
            (str(source), str(destination), recovery_id),
        )
        connection.commit()

    movers = app_config.downloads_dir / "mover-combinado.pdf"
    movers.write_bytes(b"pending move" * 20)
    item = filer.ingest(movers)
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", "Combinado.pdf")
    other = database.add_subject("Outra", "OUT", "#123456", (), "OUT - Outra")
    filer.ensure_subject_structure(other)
    move_destination = app_config.university_root / other.folder_name / "Outros" / "Combinado.pdf"
    move = database.begin_document_move(document.id, other.id, "Outros", move_destination)
    document.current_path.replace(move_destination)

    report = scan(app_config, database)
    outcome = apply(database, report)

    assert move.id in outcome.completed_operation_event_ids
    assert [event.inbox_id for event in database.list_pending_ingests()] == [recovery_id]
    with database.connect() as connection:
        stale_row = connection.execute(
            "SELECT status FROM inbox WHERE id = ?", (stale.id,)
        ).fetchone()
    assert stale_row is not None and stale_row["status"] == "pending"
    reasons = {finding.reason for finding in findings(report)}
    assert FindingReason.PENDING_INGEST_DESTINATION in reasons

    second = apply(database, scan(app_config, database))
    assert second.completed_operation_event_ids == ()
    assert len(database.list_pending_ingests()) == 1


def test_completed_ingest_lookup_failure_is_isolated_per_item(
    app_config: AppConfig,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_ids: list[int] = []
    for name in ("primeiro.pdf", "segundo.pdf"):
        destination = app_config.inbox_dir / name
        destination.write_bytes(b"recolha pendente" * 10)
        source = app_config.downloads_dir / name
        with database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO inbox(path, original_path, original_name, size, detected_at, status)
                VALUES (?, ?, ?, ?, '2026-09-03T00:00:00+00:00', 'recovery')
                """,
                (str(destination), str(source), name, destination.stat().st_size),
            )
            inbox_id = int(cursor.lastrowid)
            event = connection.execute(
                """
                INSERT INTO events(action, source_path, destination_path, inbox_id, created_at)
                VALUES ('ingest_pending', ?, ?, ?, '2026-09-03T00:00:00+00:00')
                """,
                (str(source), str(destination), inbox_id),
            )
            event_ids.append(int(event.lastrowid))
            connection.commit()

    original = Database.complete_ingest
    failing_event = event_ids[0]

    def flaky_complete(self: Database, event_id: int, content_sha256: str = "") -> object:
        if event_id == failing_event:
            raise LookupError("A recolha pendente já não existe.")
        return original(self, event_id, content_sha256)

    monkeypatch.setattr(Database, "complete_ingest", flaky_complete)

    outcome = apply(database, scan(app_config, database))

    assert [event.id for event in database.list_pending_ingests()] == [failing_event]
    assert len(outcome.recovered_items) == 1
    with database.connect() as connection:
        statuses = {
            str(row["status"]) for row in connection.execute("SELECT status FROM inbox").fetchall()
        }
    assert statuses == {"pending", "recovery"}
