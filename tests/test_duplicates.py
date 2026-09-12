"""Content-fingerprint duplicate detection tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from organizador.db import Database
from organizador.duplicates import file_sha256, find_duplicate
from organizador.models import FiledDocument, Subject


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
    stored = database.get_file(document.id)
    assert stored is not None
    assert stored.content_sha256 == hashlib.sha256(b"igual" * 30).hexdigest()


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
