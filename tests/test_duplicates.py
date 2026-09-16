"""Content-fingerprint duplicate detection tests."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from organizador.db import Database
from organizador.duplicates import file_fingerprint, file_sha256, find_duplicate
from organizador.models import FiledDocument, Subject


def _touch(path: Path) -> None:
    """Advance the modification time without changing the file size."""

    details = path.stat()
    os.utime(path, ns=(details.st_atime_ns, details.st_mtime_ns + 1_000_000))


def _filed_document(
    database: Database, subject: Subject, tmp_path: Path, name: str, content: bytes
) -> FiledDocument:
    path = tmp_path / name
    path.write_bytes(content)
    item = database.add_inbox_item(path, tmp_path / "dl" / name, name, path.stat().st_size)
    return database.record_filing(item.id, subject.id, "Outros", path)


def _inbox_item(
    database: Database, subject: Subject, tmp_path: Path, name: str, content: bytes
) -> int:
    del subject
    path = tmp_path / name
    path.write_bytes(content)
    item = database.add_inbox_item(path, tmp_path / "dl" / name, name, path.stat().st_size)
    return item.id


def test_file_sha256_reads_content_and_tolerates_missing_files(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes(b"conteudo")

    assert file_sha256(path) == hashlib.sha256(b"conteudo").hexdigest()
    assert file_sha256(tmp_path / "ausente.txt") == ""


def test_file_fingerprint_tracks_size_and_modification(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes(b"conteudo")
    first = file_fingerprint(path)

    assert first.startswith(f"{len(b'conteudo')}:")
    _touch(path)
    assert file_fingerprint(path) != first
    assert file_fingerprint(tmp_path / "ausente.txt") == ""


def test_find_duplicate_matches_content_and_caches_fingerprints(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    document = _filed_document(database, subject, tmp_path, "aula.txt", b"igual" * 30)
    item_id = _inbox_item(database, subject, tmp_path, "aula-copia.txt", b"igual" * 30)
    item = database.get_inbox_item(item_id)
    assert item is not None

    match = find_duplicate(database, item)

    assert match is not None
    assert match.id == document.id
    refreshed = database.get_inbox_item(item_id)
    assert refreshed is not None
    assert refreshed.content_sha256 == hashlib.sha256(b"igual" * 30).hexdigest()
    assert refreshed.hash_fingerprint
    stored = database.get_file(document.id)
    assert stored is not None
    assert stored.content_sha256 == hashlib.sha256(b"igual" * 30).hexdigest()
    assert stored.hash_fingerprint


def test_find_duplicate_refreshes_a_same_size_edit_of_the_filed_document(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    original = b"A" * 64
    edited = b"B" * 64
    document = _filed_document(database, subject, tmp_path, "aula.txt", original)
    first_id = _inbox_item(database, subject, tmp_path, "copia.txt", original)
    first = database.get_inbox_item(first_id)
    assert first is not None
    assert find_duplicate(database, first) is not None

    document.current_path.write_bytes(edited)
    _touch(document.current_path)

    stale_id = _inbox_item(database, subject, tmp_path, "original.txt", original)
    stale = database.get_inbox_item(stale_id)
    assert stale is not None
    assert find_duplicate(database, stale) is None

    edited_id = _inbox_item(database, subject, tmp_path, "editado.txt", edited)
    edited_item = database.get_inbox_item(edited_id)
    assert edited_item is not None
    match = find_duplicate(database, edited_item)

    assert match is not None
    assert match.id == document.id
    stored = database.get_file(document.id)
    assert stored is not None
    assert stored.content_sha256 == hashlib.sha256(edited).hexdigest()
    assert stored.hash_fingerprint


def test_find_duplicate_rehashes_an_edited_inbox_item(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    content = b"C" * 64
    edited = b"D" * 64
    document = _filed_document(database, subject, tmp_path, "aula.txt", content)
    item_id = _inbox_item(database, subject, tmp_path, "copia.txt", content)
    item = database.get_inbox_item(item_id)
    assert item is not None
    match = find_duplicate(database, item)
    assert match is not None
    assert match.id == document.id

    item.path.write_bytes(edited)
    _touch(item.path)

    refreshed = database.get_inbox_item(item_id)
    assert refreshed is not None
    assert find_duplicate(database, refreshed) is None
    stored = database.get_inbox_item(item_id)
    assert stored is not None
    assert stored.content_sha256 == hashlib.sha256(edited).hexdigest()
    assert stored.hash_fingerprint


def test_find_duplicate_refreshes_a_legacy_cache_without_a_fingerprint(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    content = b"E" * 64
    document = _filed_document(database, subject, tmp_path, "aula.txt", content)
    with database.connect() as connection:
        connection.execute(
            "UPDATE files SET content_sha256 = ?, hash_fingerprint = '' WHERE id = ?",
            (hashlib.sha256(content).hexdigest(), document.id),
        )
        connection.commit()
    item_id = _inbox_item(database, subject, tmp_path, "copia.txt", content)
    item = database.get_inbox_item(item_id)
    assert item is not None

    match = find_duplicate(database, item)

    assert match is not None
    stored = database.get_file(document.id)
    assert stored is not None
    assert stored.hash_fingerprint


def test_find_duplicate_matches_a_size_changed_edit(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    original = b"curto"
    edited = b"conteudo bem maior depois da edicao"
    document = _filed_document(database, subject, tmp_path, "aula.txt", original)
    document.current_path.write_bytes(edited)
    _touch(document.current_path)

    item_id = _inbox_item(database, subject, tmp_path, "copia.txt", edited)
    item = database.get_inbox_item(item_id)
    assert item is not None

    match = find_duplicate(database, item)

    assert match is not None
    assert match.id == document.id


def test_find_duplicate_ignores_same_size_different_content(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    _filed_document(database, subject, tmp_path, "a.txt", b"AAAA")
    item_id = _inbox_item(database, subject, tmp_path, "b.txt", b"BBBB")
    item = database.get_inbox_item(item_id)
    assert item is not None

    assert find_duplicate(database, item) is None


def test_find_duplicate_ignores_different_sizes(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    _filed_document(database, subject, tmp_path, "a.txt", b"conteudo maior")
    item_id = _inbox_item(database, subject, tmp_path, "b.txt", b"curto")
    item = database.get_inbox_item(item_id)
    assert item is not None

    assert find_duplicate(database, item) is None


def test_find_duplicate_ignores_dropped_documents(
    database: Database, subject: Subject, tmp_path: Path
) -> None:
    document = _filed_document(database, subject, tmp_path, "a.txt", b"igual")
    with database.connect() as connection:
        connection.execute(
            "UPDATE files SET catalog_state = 'dropped' WHERE id = ?", (document.id,)
        )
        connection.commit()
    item_id = _inbox_item(database, subject, tmp_path, "b.txt", b"igual")
    item = database.get_inbox_item(item_id)
    assert item is not None

    assert find_duplicate(database, item) is None
