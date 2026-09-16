"""Content-fingerprint duplicate detection across intake and catalog."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from organizador.db import Database
from organizador.models import FiledDocument, InboxItem

LOGGER = logging.getLogger(__name__)
CHUNK_SIZE = 1024 * 1024


def file_sha256(path: Path) -> str:
    """Return the content fingerprint, or ``""`` when the file cannot be read."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(CHUNK_SIZE):
                digest.update(chunk)
    except OSError:
        LOGGER.debug("Could not fingerprint %s", path, exc_info=True)
        return ""
    return digest.hexdigest()


def file_fingerprint(path: Path) -> str:
    """Return a cheap change detector based on size and modification time."""

    try:
        details = path.stat()
    except OSError:
        LOGGER.debug("Could not stat %s", path, exc_info=True)
        return ""
    return f"{details.st_size}:{details.st_mtime_ns}"


def fingerprint_size(value: str) -> int | None:
    """Return the byte size recorded in a fingerprint, when valid."""

    size, separator, _modified = value.partition(":")
    if not separator or not size.isdigit():
        return None
    return int(size)


def _hash_is_fresh(content_sha256: str, stored: str, current: str) -> bool:
    """Return whether a cached hash still matches the file's stat fingerprint."""

    return bool(content_sha256) and bool(stored) and stored == current


def find_duplicate(database: Database, item: InboxItem) -> FiledDocument | None:
    """Return the newest active document with the same content, if any.

    Candidates are filtered by their *current* on-disk size — stored sizes lag
    behind edits — and cached hashes are revalidated against the file's size
    and modification time, so edited documents are re-hashed instead of
    matching an outdated fingerprint.
    """

    item_fingerprint = file_fingerprint(item.path)
    item_size = fingerprint_size(item_fingerprint)
    if item_size is None:
        return None
    fingerprint = item.content_sha256
    if not _hash_is_fresh(fingerprint, item.hash_fingerprint, item_fingerprint):
        fingerprint = file_sha256(item.path)
        if not fingerprint:
            return None
        database.set_inbox_hash(item.id, fingerprint, file_fingerprint(item.path))
    candidates = sorted(
        database.list_files(),
        key=lambda document: (document.filed_at, document.id),
        reverse=True,
    )
    for document in candidates:
        current = file_fingerprint(document.current_path)
        if fingerprint_size(current) != item_size:
            continue
        if _hash_is_fresh(document.content_sha256, document.hash_fingerprint, current):
            candidate_hash = document.content_sha256
        else:
            candidate_hash = file_sha256(document.current_path)
            if not candidate_hash:
                continue
            database.set_file_hash(
                document.id, candidate_hash, file_fingerprint(document.current_path)
            )
        if candidate_hash == fingerprint:
            return document
    return None
