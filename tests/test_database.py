"""SQLite repository and FTS behavior tests."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

from organizador.db import (
    METRIC_COLLISIONS_RENAMED,
    Database,
    NewerDatabaseError,
)
from organizador.models import (
    ActivitySummary,
    ExistingDownload,
    FilingHint,
    FindingReason,
    Subject,
)
from organizador.paths import normalise_path_key


def _file_record(database: Database, subject: Subject, tmp_path: Path) -> int:
    inbox_path = tmp_path / "inbox" / "aula.txt"
    original_path = tmp_path / "downloads" / "aula.txt"
    inbox_path.parent.mkdir(parents=True)
    inbox_path.write_text("Derivadas e integrais", encoding="utf-8")
    item = database.add_inbox_item(inbox_path, original_path, "aula.txt", inbox_path.stat().st_size)
    destination = tmp_path / "subject" / "aula.txt"
    destination.parent.mkdir()
    inbox_path.replace(destination)
    return database.record_filing(item.id, subject.id, "Slides", destination).id


def test_subject_update_and_archive(database: Database, subject: Subject) -> None:
    updated = database.update_subject(
        subject.id,
        "Cálculo Diferencial",
        "MAT101",
        "#123456",
        ("limites", "derivadas"),
        subject.folder_name,
    )
    assert updated.name == "Cálculo Diferencial"
    assert updated.keywords == ("limites", "derivadas")

    database.archive_subject(subject.id)

    assert database.count_subjects() == 0
    assert database.get_subject(subject.id) is not None

    restored = database.set_subject_active(subject.id, True)

    assert restored.active
    assert database.count_subjects() == 1
    assert database.find_active_subject_conflicts(subject.id) == ()


def test_legacy_database_gains_index_fingerprint_column(
    database: Database,
) -> None:
    with database.connect() as connection:
        connection.execute("ALTER TABLE files DROP COLUMN mtime_ns")
        connection.commit()

    assert "files.mtime_ns" in database.inspect_schema().missing_additions
    database.initialize()

    with database.connect() as connection:
        columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(files)").fetchall()
        }
    assert "mtime_ns" in columns
    assert database.inspect_schema().missing_additions == ()


def _indexed_text_file(database: Database, subject: Subject, path: Path, text: str) -> int:
    path.write_text(text, encoding="utf-8")
    item = database.add_inbox_item(
        path, path.parent / "dl" / path.name, path.name, path.stat().st_size
    )
    filed = database.record_filing(item.id, subject.id, "Outros", path)
    details = path.stat()
    database.replace_document_pages(
        filed.id,
        subject.name,
        path.name,
        [text],
        expected_path=path,
        size=details.st_size,
        mtime_ns=details.st_mtime_ns,
    )
    return filed.id


def test_reset_stale_index_fingerprints_detects_edited_files(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "notas.txt"
    file_id = _indexed_text_file(database, subject, path, "versão original")

    assert database.reset_stale_index_fingerprints() == 0

    path.write_text("versão original revista e alargada", encoding="utf-8")

    assert database.reset_stale_index_fingerprints() == 1
    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.indexed_at is None
    assert refreshed.index_state == ""
    assert database.reset_stale_index_fingerprints() == 0


def test_reset_stale_index_fingerprints_detects_same_size_edits(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    import os

    path = tmp_path / "constante.txt"
    file_id = _indexed_text_file(database, subject, path, "abcdefgh")

    path.write_text("ABCDEFGH", encoding="utf-8")
    os.utime(path, ns=(0, 0))

    assert database.reset_stale_index_fingerprints() == 1
    assert database.get_file(file_id) is not None


def test_reset_stale_index_fingerprints_ignores_missing_files(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "sumido.txt"
    file_id = _indexed_text_file(database, subject, path, "texto")
    path.unlink()

    assert database.reset_stale_index_fingerprints() == 0
    assert database.get_file(file_id) is not None


def test_add_subject_rejects_windows_folder_collision(database: Database, subject: Subject) -> None:
    with pytest.raises(ValueError, match="já pertence"):
        database.add_subject("Cópia", "MAT101", "#123456", (), "MAT101 - CÁLCULO I")

    distinct = database.add_subject("Álgebra", "ALG101", "#123456", (), "ALG101 - Álgebra")

    assert distinct.folder_name == "ALG101 - Álgebra"
    assert database.count_subjects() == 2


def test_subject_folder_conflicts_support_exclusion_and_restore_checks(
    database: Database, subject: Subject
) -> None:
    own = database.find_subject_folder_conflicts(subject.folder_name)
    assert own == (subject.name,)
    assert database.find_subject_folder_conflicts(subject.folder_name, exclude_id=subject.id) == ()
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
        clone_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    try:
        active_conflicts = database.find_subject_folder_conflicts(
            subject.folder_name, active_only=True
        )
        assert sorted(active_conflicts) == sorted((subject.name, "CÁLCULO CLONE"))
        assert database.find_active_subject_conflicts(clone_id) == (subject.name,)
        database.archive_subject(clone_id)
        assert database.find_active_subject_conflicts(clone_id) == (subject.name,)
    finally:
        database.delete_subject(clone_id)


def test_unused_subject_can_be_deleted_during_setup_rollback(
    database: Database, subject: Subject
) -> None:
    database.delete_subject(subject.id)

    assert database.get_subject(subject.id) is None


def test_fts_search_returns_page_and_prefix_match(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    file_id = _file_record(database, subject, tmp_path)
    database.replace_document_pages(
        file_id,
        subject.name,
        "aula.txt",
        ("A regra da cadeia calcula derivadas compostas.", "Integrais definidas."),
    )

    results = database.search("deriv")

    assert len(results) == 1
    assert results[0].page == 1
    assert "[derivadas]" in results[0].snippet.casefold()
    assert database.search("") == []


def test_tasks_order_completion_and_delete(database: Database, subject: Subject) -> None:
    later = database.add_task("Entrega final", subject.id, date(2026, 9, 20))
    sooner = database.add_task("Ficha 2", subject.id, date(2026, 9, 10))

    assert [task.id for task in database.list_tasks()] == [sooner.id, later.id]

    database.set_task_completed(sooner.id, True)
    tasks = database.list_tasks()
    assert tasks[-1].completed

    database.delete_task(later.id)
    assert database.get_task(later.id) is None


def test_mark_filing_undone_restores_inbox_state(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    file_id = _file_record(database, subject, tmp_path)
    event = database.latest_undoable_filing()
    assert event is not None
    restored = tmp_path / "inbox" / "restored.txt"

    assert database.filing_hints() == [FilingHint("aula.txt", subject.id, "Slides")]

    database.mark_filing_undone(event, restored)

    assert database.get_file(file_id) is None
    item = database.get_inbox_item(event.inbox_id or -1)
    assert item is not None
    assert item.status == "pending"
    assert item.path == restored
    assert database.filing_hints() == []


def test_filing_hints_exclude_missing_files_and_archived_subjects(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    file_id = _file_record(database, subject, tmp_path)
    document = database.get_file(file_id)
    assert document is not None
    assert database.filing_hints() == [FilingHint("aula.txt", subject.id, "Slides")]

    document.current_path.unlink()
    assert database.filing_hints() == []

    document.current_path.write_text("restored", encoding="utf-8")
    database.archive_subject(subject.id)
    assert database.filing_hints() == []


def test_stale_index_job_cannot_write_to_a_reused_file_id(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    old_file_id = _file_record(database, subject, tmp_path / "old")
    old_document = database.get_file(old_file_id)
    assert old_document is not None
    old_path = old_document.current_path
    event = database.latest_undoable_filing()
    assert event is not None
    database.mark_filing_undone(event, tmp_path / "restored.txt")

    new_file_id = _file_record(database, subject, tmp_path / "new")
    assert new_file_id == old_file_id

    database.mark_document_indexed(old_file_id, expected_path=old_path)
    replacement = database.get_file(new_file_id)
    assert replacement is not None
    assert replacement.indexed_at is None

    database.replace_document_pages(
        old_file_id,
        subject.name,
        "old.txt",
        ("stale searchable text",),
        expected_path=old_path,
    )

    replacement = database.get_file(new_file_id)
    assert replacement is not None
    assert replacement.indexed_at is None
    assert database.search("stale") == []


def test_schema_migration_queues_existing_office_files_once(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "slides.pptx"
    path.write_bytes(b"legacy presentation")
    item = database.add_inbox_item(
        path, tmp_path / "Downloads" / path.name, path.name, path.stat().st_size
    )
    document = database.record_filing(item.id, subject.id, "Slides", path)
    database.replace_document_pages(
        document.id,
        subject.name,
        document.original_name,
        ("legacy searchable slide",),
        expected_path=path,
    )
    assert database.search("legacy")
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 1")
        connection.commit()

    database.initialize()

    pending = database.get_file(document.id)
    assert pending is not None
    assert pending.indexed_at is None
    assert database.search("legacy") == []

    database.replace_document_pages(
        document.id,
        subject.name,
        document.original_name,
        ("reindexed presentation",),
        expected_path=path,
    )
    database.initialize()

    retained = database.get_file(document.id)
    assert retained is not None
    assert retained.indexed_at is not None
    assert database.search("reindexed")


def test_schema_v3_adds_operation_journal_metadata(database: Database) -> None:
    with database.connect() as connection:
        connection.execute("ALTER TABLE events DROP COLUMN subject_id")
        connection.execute("ALTER TABLE events DROP COLUMN kind")
        connection.execute("DROP INDEX idx_inbox_active_path")
        connection.execute(
            """
            CREATE UNIQUE INDEX idx_inbox_active_path
            ON inbox(path) WHERE status IN ('pending', 'error', 'filing')
            """
        )
        connection.execute("PRAGMA user_version = 2")
        connection.commit()

    database.initialize()

    with database.connect() as connection:
        columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(events)").fetchall()
        }
        index_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'idx_inbox_active_path'"
        ).fetchone()
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    assert {"subject_id", "kind"} <= columns
    assert index_row is not None
    assert "'returning'" in str(index_row["sql"])
    assert version == 6


def test_schema_v4_adds_file_origin_and_persisted_reviews(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    file_id = _file_record(database, subject, tmp_path)
    with database.connect() as connection:
        connection.execute("DROP TABLE reviewed_findings")
        connection.execute("ALTER TABLE files DROP COLUMN origin")
        connection.execute("ALTER TABLE files DROP COLUMN record_token")
        connection.execute("ALTER TABLE files DROP COLUMN catalog_state")
        connection.execute("PRAGMA user_version = 3")
        connection.commit()

    database.initialize()

    migrated = database.get_file(file_id)
    assert migrated is not None
    assert migrated.origin == "filed"
    assert migrated.record_token
    database.mark_finding_reviewed(
        migrated.current_path,
        FindingReason.MISSING_DOCUMENT.value,
    )
    database.initialize()
    with database.connect() as connection:
        columns = {
            str(row["name"]): row
            for row in connection.execute("PRAGMA table_info(files)").fetchall()
        }
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    assert columns["origin"]["dflt_value"] == "'filed'"
    assert columns["origin"]["notnull"] == 1
    assert columns["record_token"]["dflt_value"] == "''"
    assert columns["record_token"]["notnull"] == 1
    assert columns["catalog_state"]["dflt_value"] == "'active'"
    assert columns["catalog_state"]["notnull"] == 1
    assert version == 6
    assert database.list_reviewed_finding_keys() == {
        (
            normalise_path_key(migrated.current_path),
            FindingReason.MISSING_DOCUMENT.value,
        )
    }


def test_schema_v6_adds_search_state_and_rebuilds_titles(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    from organizador.indexer import DocumentIndexer

    inbox_path = tmp_path / "inbox" / "original.txt"
    inbox_path.parent.mkdir(parents=True)
    inbox_path.write_text("texto para pesquisa", encoding="utf-8")
    item = database.add_inbox_item(
        inbox_path,
        tmp_path / "downloads" / "original.txt",
        "original.txt",
        inbox_path.stat().st_size,
    )
    destination = tmp_path / "subject" / "relatorio-final.txt"
    destination.parent.mkdir()
    inbox_path.replace(destination)
    filed = database.record_filing(item.id, subject.id, "Outros", destination)
    document = database.get_file(filed.id)
    assert document is not None
    indexer = DocumentIndexer(database)
    indexer.index_document(document)
    indexer.shutdown()
    assert database.search("relatorio")

    with database.connect() as connection:
        connection.execute("ALTER TABLE files DROP COLUMN index_state")
        connection.execute("ALTER TABLE files DROP COLUMN index_error")
        connection.execute(
            "UPDATE document_pages SET title = 'original.txt' WHERE CAST(file_id AS INTEGER) = ?",
            (filed.id,),
        )
        connection.execute("PRAGMA user_version = 5")
        connection.commit()
    assert database.search("original")
    assert database.search("relatorio") == []

    inspection = database.inspect_schema()
    assert inspection.user_version == 5
    assert inspection.requires_migration
    assert set(inspection.missing_additions) >= {"files.index_state", "files.index_error"}

    database.initialize()

    with database.connect() as connection:
        columns = {
            str(row["name"]): row
            for row in connection.execute("PRAGMA table_info(files)").fetchall()
        }
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        pages = connection.execute("SELECT COUNT(*) FROM document_pages").fetchone()[0]
    assert columns["index_state"]["dflt_value"] == "''"
    assert columns["index_state"]["notnull"] == 1
    assert columns["index_error"]["dflt_value"] == "''"
    assert columns["index_error"]["notnull"] == 1
    assert version == 6
    assert int(pages) == 0
    reset = database.get_file(filed.id)
    assert reset is not None
    assert reset.indexed_at is None
    assert database.search("original") == []
    assert database.inspect_schema().is_current

    refreshed = database.get_file(filed.id)
    assert refreshed is not None
    indexer = DocumentIndexer(database)
    indexer.index_document(refreshed)
    indexer.shutdown()

    assert database.search("relatorio")


def test_adopted_file_has_no_inbox_history_or_filing_hint(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "adopted.txt"
    path.write_text("cataloged in place", encoding="utf-8")
    candidate = ExistingDownload.capture(path)
    assert candidate is not None

    document = database.adopt_subject_file(candidate, subject.id, "Outros")

    assert document.origin == "adopted"
    assert document.current_path == path.absolute()
    assert database.filing_hints() == []
    with database.connect() as connection:
        row = connection.execute(
            "SELECT inbox_id FROM files WHERE id = ?", (document.id,)
        ).fetchone()
        event_count = int(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
    assert row is not None
    assert row["inbox_id"] is None
    assert event_count == 0


def test_unregister_adopted_file_preserves_disk_and_clears_catalog_data(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "adopted.txt"
    contents = b"searchable adopted document"
    path.write_bytes(contents)
    candidate = ExistingDownload.capture(path)
    assert candidate is not None
    document = database.adopt_subject_file(candidate, subject.id, "Outros")
    task = database.add_task("Review adopted", subject.id, None, document.id)
    database.replace_document_pages(
        document.id,
        subject.name,
        document.original_name,
        ("searchable adopted document",),
        expected_path=document.current_path,
        expected_record_token=document.record_token,
    )

    removed = database.unregister_adopted_file(
        document.id,
        expected_path=document.current_path,
        expected_record_token=document.record_token,
        reviewed_reason=FindingReason.UNTRACKED_SUBJECT_FILE.value,
    )

    assert removed
    assert path.read_bytes() == contents
    assert database.get_file(document.id) is None
    assert database.search("searchable") == []
    detached_task = database.get_task(task.id)
    assert detached_task is not None
    assert detached_task.file_id is None
    assert (
        normalise_path_key(path),
        FindingReason.UNTRACKED_SUBJECT_FILE.value,
    ) in database.list_reviewed_finding_keys()


def test_unregister_rejects_a_normally_filed_document(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    file_id = _file_record(database, subject, tmp_path)
    document = database.get_file(file_id)
    assert document is not None

    assert not database.unregister_adopted_file(
        document.id,
        expected_path=document.current_path,
        expected_record_token=document.record_token,
        reviewed_reason=FindingReason.UNTRACKED_SUBJECT_FILE.value,
    )
    assert database.get_file(document.id) == document


def test_reviewed_finding_keys_are_reason_specific_and_idempotent(
    database: Database, tmp_path: Path
) -> None:
    path = tmp_path / "finding.pdf"
    database.mark_finding_reviewed(path, FindingReason.MISSING_DOCUMENT.value)
    database.mark_finding_reviewed(path, FindingReason.MISSING_DOCUMENT.value)
    database.mark_finding_reviewed(path, FindingReason.BROKEN_UNDO_EVENT.value)

    keys = database.list_reviewed_finding_keys()

    assert len(keys) == 2
    assert {reason for _, reason in keys} == {
        FindingReason.MISSING_DOCUMENT.value,
        FindingReason.BROKEN_UNDO_EVENT.value,
    }


def test_stale_index_job_cannot_write_after_same_path_is_readopted(
    database: Database,
    subject: Subject,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("organizador.db._now", lambda: "2026-08-31T12:00:00+00:00")
    path = tmp_path / "same-path.txt"
    path.write_text("cataloged twice", encoding="utf-8")
    candidate = ExistingDownload.capture(path)
    assert candidate is not None
    original = database.adopt_subject_file(candidate, subject.id, "Outros")
    assert database.unregister_adopted_file(
        original.id,
        expected_path=original.current_path,
        expected_record_token=original.record_token,
        reviewed_reason=FindingReason.UNTRACKED_SUBJECT_FILE.value,
    )
    replacement = database.adopt_subject_file(candidate, subject.id, "Outros")
    assert replacement.id == original.id
    assert replacement.record_token != original.record_token

    database.replace_document_pages(
        original.id,
        subject.name,
        original.original_name,
        ("stale same-path contents",),
        expected_path=original.current_path,
        expected_record_token=original.record_token,
    )

    refreshed = database.get_file(replacement.id)
    assert refreshed is not None
    assert refreshed.indexed_at is None
    assert database.search("stale") == []


def test_newer_database_version_is_refused_without_downgrade(database: Database) -> None:
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 7")
        connection.commit()

    with pytest.raises(NewerDatabaseError, match="versão mais recente"):
        database.initialize()

    with database.connect() as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    assert version == 7


def test_normal_filing_reuses_a_dropped_path_tombstone(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    file_id = _file_record(database, subject, tmp_path / "first")
    original = database.get_file(file_id)
    assert original is not None
    original.current_path.unlink()
    assert database.drop_file_record(
        original.id,
        expected_path=original.current_path,
        expected_origin=original.origin,
        expected_record_token=original.record_token,
        verify_missing=lambda: True,
    )
    new_inbox_path = tmp_path / "second" / "inbox" / "aula.txt"
    new_inbox_path.parent.mkdir(parents=True)
    new_inbox_path.write_text("new document at the same path", encoding="utf-8")
    new_item = database.add_inbox_item(
        new_inbox_path,
        tmp_path / "second" / "downloads" / "aula.txt",
        new_inbox_path.name,
        new_inbox_path.stat().st_size,
    )
    original.current_path.write_text("new document at the same path", encoding="utf-8")

    replacement = database.record_filing(
        new_item.id,
        subject.id,
        "Slides",
        original.current_path,
    )

    assert replacement.id == original.id
    assert replacement.catalog_state == "active"
    assert replacement.record_token != original.record_token
    assert database.latest_undoable_filing() is not None


def test_activity_summary_tracks_lifetime_history(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    assert database.activity_summary() == ActivitySummary(0, 0, 0, 0, 0, 0)

    file_id = _file_record(database, subject, tmp_path)
    document = database.get_file(file_id)
    assert document is not None
    event = database.latest_undoable_filing()
    assert event is not None
    database.mark_filing_undone(event, tmp_path / "restored.txt")
    adopted_path = tmp_path / "adotado.txt"
    adopted_path.write_text("cataloged in place", encoding="utf-8")
    candidate = ExistingDownload.capture(adopted_path)
    assert candidate is not None
    database.adopt_subject_file(candidate, subject.id, "Outros")
    return_path = tmp_path / "devolvido.txt"
    item = database.add_inbox_item(
        return_path,
        tmp_path / "downloads" / "devolvido.txt",
        return_path.name,
        10,
    )
    database.record_return(item.id, tmp_path / "Downloads" / "devolvido.txt")
    database.increment_metric(METRIC_COLLISIONS_RENAMED)
    database.increment_metric(METRIC_COLLISIONS_RENAMED)

    summary = database.activity_summary()

    assert summary.organized == 1
    assert summary.undone == 1
    assert summary.adopted == 1
    assert summary.returned == 1
    assert summary.collisions_renamed == 2
    assert summary.operations_recovered == 0


def test_task_reminder_columns_are_added_additively(database: Database) -> None:
    with database.connect() as connection:
        connection.execute("ALTER TABLE tasks DROP COLUMN reminder_lead_days")
        connection.execute("ALTER TABLE tasks DROP COLUMN last_notified_on")
        connection.commit()

    database.initialize()

    with database.connect() as connection:
        columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    assert {"reminder_lead_days", "last_notified_on"} <= columns
    assert version == 6
    task = database.add_task("Ainda funciona", None, None)
    assert task.last_notified_on is None
    assert task.reminder_lead_days is None


def test_task_update_changes_fields_and_keeps_the_document_link(
    database: Database, subject: Subject
) -> None:
    earlier = database.add_task("Primeira", subject.id, date(2026, 9, 20), file_id=None)
    later = database.add_task("Segunda", subject.id, date(2026, 10, 20))
    database.mark_task_notified(later.id, date(2026, 9, 1))

    updated = database.update_task(
        later.id, "Segunda revista", subject.id, date(2026, 9, 5), reminder_lead_days=7
    )

    assert updated.title == "Segunda revista"
    assert updated.due_date == date(2026, 9, 5)
    assert updated.reminder_lead_days == 7
    assert updated.last_notified_on is None
    assert [task.id for task in database.list_tasks()] == [updated.id, earlier.id]

    renamed = database.update_task(earlier.id, "Primeira editada", None, None)

    assert renamed.subject_id is None
    assert renamed.due_date is None
    assert database.get_task(earlier.id) is not None

    with pytest.raises(LookupError):
        database.update_task(9999, "Fantasma", None, None)
    with pytest.raises(ValueError):
        database.update_task(earlier.id, "   ", None, None)


def test_archived_subject_has_no_active_conflicts_and_restores_cleanly(
    database: Database, subject: Subject
) -> None:
    database.archive_subject(subject.id)
    database.add_subject("Cálculo I bis", "MAT102", "#123456", (), "MAT102 - Cálculo I")

    conflicts = database.find_active_subject_conflicts(subject.id)

    assert conflicts == ()
    restored = database.set_subject_active(subject.id, True)
    assert restored.active
    assert database.count_subjects() == 2


def test_subject_file_summaries_and_listings_ignore_dropped_records(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    slides_id = _file_record(database, subject, tmp_path / "slides")
    other = database.add_subject("História", "HIS1", "#111111", (), "HIS1 - História")

    exercise_inbox = tmp_path / "exercicios" / "ficha.txt"
    exercise_inbox.parent.mkdir(parents=True)
    exercise_inbox.write_text("lista de problemas longa", encoding="utf-8")
    item = database.add_inbox_item(
        exercise_inbox,
        tmp_path / "downloads" / "ficha.txt",
        exercise_inbox.name,
        exercise_inbox.stat().st_size,
    )
    exercise_destination = tmp_path / "subject" / "ficha.txt"
    exercise_destination.parent.mkdir(parents=True)
    exercise_inbox.replace(exercise_destination)
    exercise_id = database.record_filing(item.id, subject.id, "Exercícios", exercise_destination).id

    adopted_path = tmp_path / "adopted.txt"
    adopted_path.write_text("adotado", encoding="utf-8")
    candidate = ExistingDownload.capture(adopted_path)
    assert candidate is not None
    adopted = database.adopt_subject_file(candidate, subject.id, "Outros")

    his_inbox = tmp_path / "his" / "aula.txt"
    his_inbox.parent.mkdir(parents=True)
    his_inbox.write_text("revolução industrial", encoding="utf-8")
    his_item = database.add_inbox_item(
        his_inbox,
        tmp_path / "downloads" / "aula.txt",
        his_inbox.name,
        his_inbox.stat().st_size,
    )
    his_destination = tmp_path / "his" / "organizada.txt"
    his_inbox.replace(his_destination)
    other_document = database.record_filing(his_item.id, other.id, "Slides", his_destination)

    dropped_id = _file_record(database, subject, tmp_path / "dropped")
    dropped_document = database.get_file(dropped_id)
    assert dropped_document is not None
    dropped_document.current_path.unlink()
    assert database.drop_file_record(
        dropped_id,
        expected_path=dropped_document.current_path,
        expected_origin=dropped_document.origin,
        expected_record_token=dropped_document.record_token,
        verify_missing=lambda: True,
    )

    files = database.list_subject_files(subject.id)
    summaries = database.count_files_by_subject()

    assert [document.id for document in files] == [exercise_id, adopted.id, slides_id]
    assert summaries[subject.id] == (3, sum(document.size for document in files))
    assert summaries[other.id] == (1, other_document.size)
    assert dropped_id not in {document.id for document in files}


def test_schema_inspection_does_not_create_a_missing_database(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "organizador.db"

    inspection = Database(path).inspect_schema()
    health = Database(path).validate_health()

    assert not inspection.database_exists
    assert inspection.user_version is None
    assert not inspection.requires_migration
    assert not health.healthy
    assert not path.exists()
    assert not path.parent.exists()


def test_schema_inspection_detects_same_version_additive_drift(database: Database) -> None:
    with database.connect() as connection:
        connection.execute("ALTER TABLE tasks DROP COLUMN reminder_lead_days")
        connection.execute("ALTER TABLE tasks DROP COLUMN last_notified_on")
        connection.commit()

    inspection = database.inspect_schema()

    assert inspection.user_version == 6
    assert inspection.requires_migration
    assert set(inspection.missing_additions) >= {
        "tasks.reminder_lead_days",
        "tasks.last_notified_on",
    }

    database.initialize()

    assert database.inspect_schema().is_current


def test_schema_migration_rolls_back_schema_and_version_together(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 4")
        connection.commit()

    def fail_after_schema_write(connection: sqlite3.Connection) -> None:
        connection.execute("ALTER TABLE tasks ADD COLUMN migration_probe TEXT")
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(
        Database,
        "_prepare_task_reminders",
        staticmethod(fail_after_schema_write),
    )

    with pytest.raises(RuntimeError, match="injected migration failure"):
        database.initialize()

    with database.connect() as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
    assert version == 4
    assert "migration_probe" not in columns


def test_backup_includes_committed_rows_still_resident_in_wal(
    database: Database, tmp_path: Path
) -> None:
    snapshot = tmp_path / "snapshot.sqlite3"
    with database.connect() as writer:
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute(
            """
            INSERT INTO subjects(name, code, folder_name, created_at)
            VALUES ('WAL subject', 'WAL', 'WAL subject', '2026-09-03T00:00:00+00:00')
            """
        )
        writer.commit()
        assert Path(f"{database.path}-wal").is_file()

        health = database.backup_to(snapshot)

    assert health.healthy
    with closing(sqlite3.connect(snapshot)) as connection:
        count = int(
            connection.execute("SELECT COUNT(*) FROM subjects WHERE code = 'WAL'").fetchone()[0]
        )
    assert count == 1
    assert not Path(f"{snapshot}-wal").exists()
    assert not Path(f"{snapshot}-shm").exists()


def test_backup_excludes_uncommitted_rows(database: Database, tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.sqlite3"
    with database.connect() as writer:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            """
            INSERT INTO subjects(name, code, folder_name, created_at)
            VALUES ('Uncommitted', 'NOPE', 'Uncommitted', '2026-09-03T00:00:00+00:00')
            """
        )

        database.backup_to(snapshot)

        writer.rollback()
    with closing(sqlite3.connect(snapshot)) as connection:
        count = int(
            connection.execute("SELECT COUNT(*) FROM subjects WHERE code = 'NOPE'").fetchone()[0]
        )
    assert count == 0


def test_database_health_reports_corruption_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.db"
    contents = b"this is not sqlite"
    path.write_bytes(contents)

    health = Database(path).validate_health()

    assert not health.healthy
    assert health.error
    assert path.read_bytes() == contents


def _searchable_record(
    database: Database, subject: Subject, tmp_path: Path, name: str, kind: str, text: str
) -> int:
    inbox_path = tmp_path / "inbox" / name
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(text, encoding="utf-8")
    item = database.add_inbox_item(
        inbox_path, tmp_path / "downloads" / name, name, inbox_path.stat().st_size
    )
    destination = tmp_path / "subject" / subject.folder_name / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.replace(destination)
    filed = database.record_filing(item.id, subject.id, kind, destination)
    database.replace_document_pages(
        filed.id, subject.name, name, (text,), expected_path=destination
    )
    return filed.id


def test_search_accepts_subject_and_kind_filters(database: Database, tmp_path: Path) -> None:
    first = database.add_subject("Cálculo I", "MAT101", "#000000", (), "MAT101")
    second = database.add_subject("Física I", "FIS101", "#000000", (), "FIS101")
    derivadas = _searchable_record(
        database, first, tmp_path, "derivadas.txt", "Slides", "derivadas"
    )
    integral = _searchable_record(database, first, tmp_path, "integral.txt", "Testes", "derivadas")
    cinematica = _searchable_record(
        database, second, tmp_path, "cinematica.txt", "Slides", "derivadas"
    )

    assert {result.file_id for result in database.search("derivadas")} == {
        derivadas,
        integral,
        cinematica,
    }
    assert {result.file_id for result in database.search("derivadas", subject_id=first.id)} == {
        derivadas,
        integral,
    }
    assert {result.file_id for result in database.search("derivadas", kind="Slides")} == {
        derivadas,
        cinematica,
    }
    assert [
        result.file_id
        for result in database.search("derivadas", subject_id=second.id, kind="Testes")
    ] == []


def test_browse_documents_lists_by_filter_without_query(database: Database, tmp_path: Path) -> None:
    first = database.add_subject("Cálculo I", "MAT101", "#000000", (), "MAT101")
    second = database.add_subject("Física I", "FIS101", "#000000", (), "FIS101")
    derivadas = _searchable_record(
        database, first, tmp_path, "derivadas.txt", "Slides", "derivadas"
    )
    integral = _searchable_record(database, first, tmp_path, "integral.txt", "Testes", "derivadas")
    cinematica = _searchable_record(
        database, second, tmp_path, "cinematica.txt", "Slides", "derivadas"
    )

    assert {result.file_id for result in database.browse_documents()} == {
        derivadas,
        integral,
        cinematica,
    }
    assert {result.file_id for result in database.browse_documents(subject_id=first.id)} == {
        derivadas,
        integral,
    }
    assert {result.file_id for result in database.browse_documents(kind="Testes")} == {integral}
    browsed = database.browse_documents(subject_id=second.id, kind="Slides")
    assert [result.file_id for result in browsed] == [cinematica]
    assert browsed[0].title == "cinematica.txt"
    assert browsed[0].page == 0
    assert browsed[0].snippet == ""


def test_redirect_filing_destination_requires_the_pending_marker(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    file_id = _file_record(database, subject, tmp_path)
    event = database.latest_undoable_filing()
    assert event is not None
    new_path = tmp_path / "subject" / "renomeado.txt"

    assert (
        database.redirect_filing_destination(
            event.id, file_id, event.destination_path, new_path, 999_999
        )
        is False
    )

    stored = database.get_file(file_id)
    assert stored is not None
    assert stored.current_path == event.destination_path
    assert database.list_undoable_filings() == [event]


def test_legacy_database_gains_duplicate_columns(database: Database) -> None:
    with database.connect() as connection:
        connection.execute("ALTER TABLE inbox DROP COLUMN content_sha256")
        connection.execute("ALTER TABLE inbox DROP COLUMN hash_fingerprint")
        connection.execute("ALTER TABLE files DROP COLUMN content_sha256")
        connection.execute("ALTER TABLE files DROP COLUMN hash_fingerprint")
        connection.execute("ALTER TABLE events DROP COLUMN related_event_id")
        connection.commit()

    missing = database.inspect_schema().missing_additions
    assert "inbox.content_sha256" in missing
    assert "inbox.hash_fingerprint" in missing
    assert "files.content_sha256" in missing
    assert "files.hash_fingerprint" in missing
    assert "events.related_event_id" in missing

    database.initialize()

    assert database.inspect_schema().missing_additions == ()


def test_version_rename_lifecycle_updates_the_catalog(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    file_id = _file_record(database, subject, tmp_path)
    document = database.get_file(file_id)
    assert document is not None
    versioned = document.current_path.parent / "aula (versao anterior).txt"

    event = database.begin_version_rename(file_id, versioned)

    assert database.list_pending_versions() == [event]

    document.current_path.replace(versioned)
    database.complete_version_rename(event.id, versioned)

    stored = database.get_file(file_id)
    assert stored is not None
    assert stored.current_path == versioned
    assert database.list_pending_versions() == []

    pending = database.begin_version_rename(file_id, document.current_path.parent / "outro.txt")
    assert database.cancel_version_rename(pending.id) is True
    assert database.list_pending_versions() == []
