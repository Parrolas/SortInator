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


def find_duplicate(database: Database, item: InboxItem) -> FiledDocument | None:
    """Return the newest active document with the same content, if any.

    Catalog fingerprints are computed lazily once per document and cached, so
    pre-existing installations pay the cost only for same-size candidates.
    """

    fingerprint = item.content_sha256 or file_sha256(item.path)
    if not fingerprint:
        return None
    if not item.content_sha256:
        database.set_inbox_hash(item.id, fingerprint)
    for document in database.list_active_documents_by_size(item.size):
        candidate_hash = document.content_sha256 or file_sha256(document.current_path)
        if not candidate_hash:
            continue
        if not document.content_sha256:
            database.set_file_hash(document.id, candidate_hash)
        if candidate_hash == fingerprint:
            return document
    return None
