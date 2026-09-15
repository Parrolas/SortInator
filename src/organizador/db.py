"""SQLite persistence with page-level FTS5 document search."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable, Collection, Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from organizador.models import (
    FILE_KINDS,
    ActivitySummary,
    ExistingDownload,
    FiledDocument,
    FilingHint,
    HistoryEvent,
    InboxItem,
    SearchResult,
    StudyTask,
    Subject,
)
from organizador.paths import normalise_path_key, windows_folder_key

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 6

METRIC_COLLISIONS_RENAMED = "collisions_renamed"
METRIC_OPERATIONS_RECOVERED = "operations_recovered"


class NewerDatabaseError(RuntimeError):
    """The database was created or migrated by a newer application version."""


class DatabaseHealthError(RuntimeError):
    """A database failed an explicit SQLite health check."""


@dataclass(frozen=True, slots=True)
class SchemaInspection:
    """Read-only summary of the schema state relevant to migrations."""

    database_exists: bool
    user_version: int | None
    missing_additions: tuple[str, ...] = ()

    @property
    def requires_migration(self) -> bool:
        """Return whether this application can and should update the schema."""

        return bool(
            self.database_exists
            and self.user_version is not None
            and (
                self.user_version < SCHEMA_VERSION
                or (self.user_version == SCHEMA_VERSION and self.missing_additions)
            )
        )

    @property
    def is_current(self) -> bool:
        """Return whether the schema is complete for this application version."""

        return (
            self.database_exists
            and self.user_version == SCHEMA_VERSION
            and not self.missing_additions
        )


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    """Result of opening a database read-only and running ``quick_check``."""

    database_exists: bool
    quick_check: tuple[str, ...]
    error: str | None = None

    @property
    def healthy(self) -> bool:
        """Return whether SQLite reported a structurally healthy database."""

        return self.database_exists and self.error is None and self.quick_check == ("ok",)

    def require_healthy(self) -> None:
        """Raise a stable application error when the health check failed."""

        if self.healthy:
            return
        detail = self.error or "; ".join(self.quick_check) or "database is missing"
        raise DatabaseHealthError(f"SQLite database is not healthy: {detail}")


SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_actions (
    token TEXT PRIMARY KEY,
    expires_at REAL NOT NULL,
    documents_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    code TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '#2D7A78',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    folder_name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inbox (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    original_path TEXT NOT NULL,
    original_name TEXT NOT NULL,
    size INTEGER NOT NULL,
    detected_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    suggested_subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
    suggested_kind TEXT NOT NULL DEFAULT 'Outros',
    last_error TEXT NOT NULL DEFAULT '',
    content_sha256 TEXT NOT NULL DEFAULT '',
    hash_fingerprint TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_active_path
ON inbox(path) WHERE status IN ('pending', 'error', 'filing', 'returning');

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    inbox_id INTEGER REFERENCES inbox(id),
    kind TEXT NOT NULL,
    original_name TEXT NOT NULL,
    current_path TEXT NOT NULL UNIQUE,
    original_path TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL DEFAULT 0,
    filed_at TEXT NOT NULL,
    indexed_at TEXT,
    origin TEXT NOT NULL DEFAULT 'filed' CHECK (origin IN ('filed', 'adopted')),
    record_token TEXT NOT NULL DEFAULT '',
    catalog_state TEXT NOT NULL DEFAULT 'active'
        CHECK (catalog_state IN ('active', 'dropped')),
    index_state TEXT NOT NULL DEFAULT '',
    index_error TEXT NOT NULL DEFAULT '',
    content_sha256 TEXT NOT NULL DEFAULT '',
    hash_fingerprint TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    source_path TEXT NOT NULL,
    destination_path TEXT NOT NULL,
    file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
    inbox_id INTEGER REFERENCES inbox(id) ON DELETE SET NULL,
    subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
    kind TEXT NOT NULL DEFAULT '',
    related_event_id INTEGER,
    created_at TEXT NOT NULL,
    undone_at TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
    file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
    due_date TEXT,
    completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
    created_at TEXT NOT NULL,
    reminder_lead_days INTEGER,
    last_notified_on TEXT
);

CREATE TABLE IF NOT EXISTS reviewed_findings (
    normalized_path TEXT NOT NULL,
    reason TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    PRIMARY KEY (normalized_path, reason)
);

CREATE TABLE IF NOT EXISTS activity_counters (
    kind TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS document_pages USING fts5(
    file_id UNINDEXED,
    page UNINDEXED,
    subject UNINDEXED,
    title,
    content,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE INDEX IF NOT EXISTS idx_inbox_status_detected ON inbox(status, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_filed_at ON files(filed_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(completed, due_date);
CREATE INDEX IF NOT EXISTS idx_events_undo ON events(undone_at, created_at DESC);
"""

_EXPECTED_TABLES = (
    "notification_actions",
    "subjects",
    "inbox",
    "files",
    "events",
    "tasks",
    "reviewed_findings",
    "activity_counters",
    "document_pages",
)
_EXPECTED_INDEXES = (
    "idx_inbox_active_path",
    "idx_inbox_status_detected",
    "idx_files_filed_at",
    "idx_tasks_due_date",
    "idx_events_undo",
)
_ADDITIVE_COLUMNS = {
    "events": ("subject_id", "kind", "related_event_id"),
    "files": (
        "origin",
        "record_token",
        "catalog_state",
        "index_state",
        "index_error",
        "mtime_ns",
        "content_sha256",
        "hash_fingerprint",
    ),
    "inbox": ("content_sha256", "hash_fingerprint"),
    "tasks": ("reminder_lead_days", "last_notified_on"),
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class Database:
    """Small connection-per-operation SQLite repository.

    Background workers may call this class safely because connections are never
    shared across threads.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Open a configured database connection."""

        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
        finally:
            connection.close()

    def inspect_schema(self) -> SchemaInspection:
        """Inspect migration state without creating or writing the database."""

        if not self.path.is_file():
            return SchemaInspection(database_exists=False, user_version=None)
        with self._connect_read_only() as connection:
            version_row = connection.execute("PRAGMA user_version").fetchone()
            user_version = int(version_row[0]) if version_row is not None else 0
            rows = connection.execute(
                "SELECT type, name, sql FROM sqlite_master WHERE type IN ('table', 'index')"
            ).fetchall()
            objects = {(str(row["type"]), str(row["name"])): row["sql"] for row in rows}
            missing: list[str] = []
            for table in _EXPECTED_TABLES:
                if ("table", table) not in objects:
                    missing.append(f"table:{table}")
            for index in _EXPECTED_INDEXES:
                if ("index", index) not in objects:
                    missing.append(f"index:{index}")
            active_index_sql = objects.get(("index", "idx_inbox_active_path"))
            if (
                active_index_sql is not None
                and "'returning'" not in str(active_index_sql).casefold()
            ):
                missing.append("index:idx_inbox_active_path:returning")
            for table, expected_columns in _ADDITIVE_COLUMNS.items():
                if ("table", table) not in objects:
                    continue
                columns = {
                    str(row["name"])
                    for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
                }
                missing.extend(
                    f"{table}.{column}" for column in expected_columns if column not in columns
                )
        return SchemaInspection(
            database_exists=True,
            user_version=user_version,
            missing_additions=tuple(sorted(missing)),
        )

    def validate_health(self) -> DatabaseHealth:
        """Run SQLite ``quick_check`` read-only without creating a missing file."""

        if not self.path.is_file():
            return DatabaseHealth(
                database_exists=False,
                quick_check=(),
                error="database does not exist",
            )
        try:
            with self._connect_read_only() as connection:
                rows = connection.execute("PRAGMA quick_check").fetchall()
        except (OSError, sqlite3.Error) as exc:
            return DatabaseHealth(
                database_exists=True,
                quick_check=(),
                error=str(exc),
            )
        return DatabaseHealth(
            database_exists=True,
            quick_check=tuple(str(row[0]) for row in rows),
        )

    def backup_to(self, destination: Path) -> DatabaseHealth:
        """Create and validate a standalone snapshot, including committed WAL data."""

        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with (
                self._connect_read_only() as source,
                closing(sqlite3.connect(destination, timeout=10.0)) as target,
            ):
                source.backup(target)
                target.commit()
                target.execute("PRAGMA journal_mode = DELETE")
            health = Database(destination).validate_health()
            health.require_healthy()
        except BaseException:
            destination.unlink(missing_ok=True)
            Path(f"{destination}-wal").unlink(missing_ok=True)
            Path(f"{destination}-shm").unlink(missing_ok=True)
            raise
        return health

    @contextmanager
    def _connect_read_only(self) -> Iterator[sqlite3.Connection]:
        uri = f"{self.path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the database and all current schema objects."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version_row = connection.execute("PRAGMA user_version").fetchone()
            previous_version = int(version_row[0]) if version_row is not None else 0
            if previous_version > SCHEMA_VERSION:
                raise NewerDatabaseError(
                    f"A base de dados pertence a uma versão mais recente ({previous_version})."
                )
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._execute_schema(connection)
                if previous_version < 2:
                    self._prepare_office_reindex(connection)
                # Additive reconciliation is deliberately version-independent.
                # It repairs interrupted/same-version additions without a bump.
                self._prepare_operation_journal(connection)
                self._prepare_reconciliation_actions(connection)
                self._prepare_task_reminders(connection)
                self._prepare_search_metadata(connection)
                self._prepare_content_hashes(connection)
                if previous_version < 6:
                    self._prepare_search_reindex(connection)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @staticmethod
    def _execute_schema(connection: sqlite3.Connection) -> None:
        """Execute the schema without ``executescript``'s implicit commit."""

        pending = ""
        for line in SCHEMA.splitlines(keepends=True):
            pending += line
            if not sqlite3.complete_statement(pending):
                continue
            statement = pending.strip()
            pending = ""
            if statement:
                connection.execute(statement)
        if pending.strip():  # pragma: no cover - guarded by the static schema constant
            raise RuntimeError("The SQLite schema contains an incomplete statement.")

    @staticmethod
    def _prepare_office_reindex(connection: sqlite3.Connection) -> None:
        """Queue Office files handled before text extraction was supported."""

        office_files = """
            SELECT id FROM files
            WHERE LOWER(current_path) LIKE '%.docx'
               OR LOWER(current_path) LIKE '%.pptx'
               OR LOWER(current_path) LIKE '%.xlsx'
        """
        connection.execute(
            f"""DELETE FROM document_pages
                 WHERE CAST(file_id AS INTEGER) IN ({office_files})"""
        )
        connection.execute(
            f"""UPDATE files SET indexed_at = NULL
                 WHERE id IN ({office_files})"""
        )

    @staticmethod
    def _prepare_operation_journal(connection: sqlite3.Connection) -> None:
        """Add pending-operation metadata and protect every active inbox path."""

        columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(events)").fetchall()
        }
        if "subject_id" not in columns:
            connection.execute(
                "ALTER TABLE events ADD COLUMN subject_id INTEGER REFERENCES subjects(id)"
            )
        if "kind" not in columns:
            connection.execute("ALTER TABLE events ADD COLUMN kind TEXT NOT NULL DEFAULT ''")
        if "related_event_id" not in columns:
            connection.execute("ALTER TABLE events ADD COLUMN related_event_id INTEGER")
        index_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'idx_inbox_active_path'"
        ).fetchone()
        if index_row is None or "'returning'" not in str(index_row["sql"]).casefold():
            connection.execute("DROP INDEX IF EXISTS idx_inbox_active_path")
            connection.execute(
                """
                CREATE UNIQUE INDEX idx_inbox_active_path
                ON inbox(path) WHERE status IN ('pending', 'error', 'filing', 'returning')
                """
            )

    @staticmethod
    def _prepare_reconciliation_actions(connection: sqlite3.Connection) -> None:
        """Add file provenance and persisted finding-review state."""

        columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(files)").fetchall()
        }
        if "origin" not in columns:
            connection.execute(
                """
                ALTER TABLE files ADD COLUMN origin TEXT NOT NULL DEFAULT 'filed'
                CHECK (origin IN ('filed', 'adopted'))
                """
            )
        if "record_token" not in columns:
            connection.execute("ALTER TABLE files ADD COLUMN record_token TEXT NOT NULL DEFAULT ''")
        if "catalog_state" not in columns:
            connection.execute(
                """
                ALTER TABLE files ADD COLUMN catalog_state TEXT NOT NULL DEFAULT 'active'
                CHECK (catalog_state IN ('active', 'dropped'))
                """
            )
        rows = connection.execute("SELECT id FROM files WHERE record_token = ''").fetchall()
        connection.executemany(
            "UPDATE files SET record_token = ? WHERE id = ? AND record_token = ''",
            ((uuid4().hex, int(row["id"])) for row in rows),
        )

    @staticmethod
    def _prepare_task_reminders(connection: sqlite3.Connection) -> None:
        """Ensure the additive reminder columns exist on the tasks table."""

        columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "reminder_lead_days" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN reminder_lead_days INTEGER")
        if "last_notified_on" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN last_notified_on TEXT")

    @staticmethod
    def _prepare_search_metadata(connection: sqlite3.Connection) -> None:
        """Ensure the additive index-state columns exist on the files table."""

        columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(files)").fetchall()
        }
        if "index_state" not in columns:
            connection.execute("ALTER TABLE files ADD COLUMN index_state TEXT NOT NULL DEFAULT ''")
        if "index_error" not in columns:
            connection.execute("ALTER TABLE files ADD COLUMN index_error TEXT NOT NULL DEFAULT ''")
        if "mtime_ns" not in columns:
            connection.execute("ALTER TABLE files ADD COLUMN mtime_ns INTEGER NOT NULL DEFAULT 0")

    @staticmethod
    def _prepare_content_hashes(connection: sqlite3.Connection) -> None:
        """Ensure the additive duplicate-detection columns exist."""

        additions = {
            "inbox": (
                ("content_sha256", "TEXT NOT NULL DEFAULT ''"),
                ("hash_fingerprint", "TEXT NOT NULL DEFAULT ''"),
            ),
            "files": (
                ("content_sha256", "TEXT NOT NULL DEFAULT ''"),
                ("hash_fingerprint", "TEXT NOT NULL DEFAULT ''"),
            ),
        }
        for table, columns_to_add in additions.items():
            columns = {
                str(row["name"])
                for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for name, declaration in columns_to_add:
                if name not in columns:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    @staticmethod
    def _prepare_search_reindex(connection: sqlite3.Connection) -> None:
        """Rebuild search rows once so every document gains final-name titles."""

        connection.execute("DELETE FROM document_pages")
        connection.execute("UPDATE files SET indexed_at = NULL, index_state = '', index_error = ''")

    def add_subject(
        self,
        name: str,
        code: str,
        color: str,
        keywords: Sequence[str],
        folder_name: str,
    ) -> Subject:
        """Create and return a subject."""

        cleaned_keywords = tuple(dict.fromkeys(item.strip() for item in keywords if item.strip()))
        conflicts = self.find_subject_folder_conflicts(folder_name)
        if conflicts:
            raise ValueError(
                "A pasta desta disciplina já pertence a outra disciplina no Windows: "
                f"{', '.join(conflicts)}. Escolhe um nome ou código que dê outra pasta."
            )
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO subjects(name, code, color, keywords_json, folder_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    code.strip(),
                    color,
                    json.dumps(cleaned_keywords, ensure_ascii=False),
                    folder_name,
                    _now(),
                ),
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("A base de dados não devolveu o id da disciplina.")
            subject_id = cursor.lastrowid
        subject = self.get_subject(subject_id)
        if subject is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError("A disciplina foi criada mas não pôde ser lida.")
        return subject

    def find_subject_folder_conflicts(
        self,
        folder_name: str,
        *,
        exclude_id: int | None = None,
        active_only: bool = False,
    ) -> tuple[str, ...]:
        """Return subject names whose folder resolves like ``folder_name`` on Windows.

        SQLite uniqueness is ASCII-only, but NTFS folds accents with case, so
        ``Cálculo`` and ``CÁLCULO`` would share one directory. Archived
        subjects still reserve their folders because their documents keep
        living in them.
        """

        candidate = windows_folder_key(folder_name)
        query = "SELECT id, name, folder_name FROM subjects"
        if active_only:
            query += " WHERE active = 1"
        conflicts: list[str] = []
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
        for row in rows:
            if exclude_id is not None and int(row["id"]) == exclude_id:
                continue
            if windows_folder_key(str(row["folder_name"])) == candidate:
                conflicts.append(str(row["name"]))
        return tuple(sorted(conflicts))

    def update_subject(
        self,
        subject_id: int,
        name: str,
        code: str,
        color: str,
        keywords: Sequence[str],
        folder_name: str,
    ) -> Subject:
        """Update an existing subject."""

        cleaned_keywords = tuple(dict.fromkeys(item.strip() for item in keywords if item.strip()))
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE subjects
                SET name = ?, code = ?, color = ?, keywords_json = ?, folder_name = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    code.strip(),
                    color,
                    json.dumps(cleaned_keywords, ensure_ascii=False),
                    folder_name,
                    subject_id,
                ),
            )
            connection.commit()
        subject = self.get_subject(subject_id)
        if subject is None:
            raise LookupError(f"Disciplina inexistente: {subject_id}")
        return subject

    def archive_subject(self, subject_id: int) -> None:
        """Hide a subject without deleting documents linked to it."""

        with self.connect() as connection:
            connection.execute("UPDATE subjects SET active = 0 WHERE id = ?", (subject_id,))
            connection.commit()

    def set_subject_active(self, subject_id: int, active: bool) -> Subject:
        """Show or hide a subject without touching its documents."""

        with self.connect() as connection:
            connection.execute(
                "UPDATE subjects SET active = ? WHERE id = ?", (int(active), subject_id)
            )
            connection.commit()
        subject = self.get_subject(subject_id)
        if subject is None:
            raise LookupError(f"Disciplina inexistente: {subject_id}")
        return subject

    def find_active_subject_conflicts(self, subject_id: int) -> tuple[str, ...]:
        """Return active subjects claiming the same name or folder as this one."""

        subject = self.get_subject(subject_id)
        if subject is None:
            raise LookupError(f"Disciplina inexistente: {subject_id}")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT name FROM subjects
                WHERE id != ? AND active = 1
                  AND (name = ? COLLATE NOCASE OR folder_name = ?)
                """,
                (subject_id, subject.name, subject.folder_name),
            ).fetchall()
        conflicts = {str(row["name"]) for row in rows}
        conflicts.update(
            self.find_subject_folder_conflicts(
                subject.folder_name, exclude_id=subject_id, active_only=True
            )
        )
        return tuple(sorted(conflicts))

    def delete_subject(self, subject_id: int) -> None:
        """Delete an unused subject while rolling back failed first-run setup."""

        with self.connect() as connection:
            connection.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
            connection.commit()

    def get_subject(self, subject_id: int) -> Subject | None:
        """Return a subject by id."""

        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM subjects WHERE id = ?", (subject_id,)
            ).fetchone()
        return self._subject(row) if row else None

    def list_subjects(self, *, active_only: bool = True) -> list[Subject]:
        """List subjects alphabetically."""

        query = "SELECT * FROM subjects"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name COLLATE NOCASE"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
        return [self._subject(row) for row in rows]

    def count_subjects(self) -> int:
        """Return the number of active subjects."""

        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM subjects WHERE active = 1"
            ).fetchone()
        return int(row["total"])

    def add_inbox_item(
        self,
        path: Path,
        original_path: Path,
        original_name: str,
        size: int,
    ) -> InboxItem:
        """Record a file moved into the university inbox."""

        now = _now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO inbox(path, original_path, original_name, size, detected_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(path), str(original_path), original_name, size, now),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("A base de dados não devolveu o id do ficheiro recebido.")
            inbox_id = cursor.lastrowid
            connection.execute(
                """
                INSERT INTO events(action, source_path, destination_path, inbox_id, created_at)
                VALUES ('ingest', ?, ?, ?, ?)
                """,
                (str(original_path), str(path), inbox_id, now),
            )
            connection.commit()
        item = self.get_inbox_item(inbox_id)
        if item is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError("O ficheiro entrou na caixa mas não pôde ser lido.")
        return item

    def get_inbox_item(self, inbox_id: int) -> InboxItem | None:
        """Return an inbox item by id."""

        with self.connect() as connection:
            row = connection.execute("SELECT * FROM inbox WHERE id = ?", (inbox_id,)).fetchone()
        return self._inbox(row) if row else None

    def begin_ingest(self, source: Path, destination: Path, size: int) -> HistoryEvent:
        """Reserve a recovery-only inbox row before touching a downloaded file."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pending = connection.execute(
                "SELECT source_path FROM events WHERE action = 'ingest_pending'"
            ).fetchall()
            source_key = normalise_path_key(source)
            if any(normalise_path_key(Path(row["source_path"])) == source_key for row in pending):
                raise LookupError("Este download já tem uma recolha por concluir.")
            now = _now()
            cursor = connection.execute(
                """
                INSERT INTO inbox(path, original_path, original_name, size, detected_at, status)
                VALUES (?, ?, ?, ?, ?, 'recovery')
                """,
                (str(destination), str(source), source.name, size, now),
            )
            inbox_id = cursor.lastrowid
            event = connection.execute(
                """
                INSERT INTO events(action, source_path, destination_path, inbox_id, created_at)
                VALUES ('ingest_pending', ?, ?, ?, ?)
                """,
                (str(source), str(destination), inbox_id, now),
            )
            row = connection.execute(
                "SELECT * FROM events WHERE id = ?", (event.lastrowid,)
            ).fetchone()
            connection.commit()
        return self._event(row)

    def complete_ingest(self, event_id: int, content_sha256: str = "") -> InboxItem:
        """Publish an ingested file only after its move has completed."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = connection.execute(
                "SELECT inbox_id FROM events WHERE id = ? AND action = 'ingest_pending'",
                (event_id,),
            ).fetchone()
            if event is None:
                raise LookupError("A recolha pendente já não existe.")
            inbox_id = int(event["inbox_id"])
            connection.execute(
                """
                UPDATE inbox
                SET status = 'pending', last_error = '', content_sha256 = ?
                WHERE id = ?
                """,
                (content_sha256, inbox_id),
            )
            connection.execute("UPDATE events SET action = 'ingest' WHERE id = ?", (event_id,))
            row = connection.execute("SELECT * FROM inbox WHERE id = ?", (inbox_id,)).fetchone()
            if row is None:
                raise LookupError("O ficheiro recolhido já não existe no catálogo.")
            item = self._inbox(row)
            connection.commit()
        return item

    def set_inbox_hash(self, inbox_id: int, content_sha256: str, fingerprint: str) -> None:
        """Cache a content fingerprint and the stat fingerprint it was read from."""

        with self.connect() as connection:
            connection.execute(
                "UPDATE inbox SET content_sha256 = ?, hash_fingerprint = ? WHERE id = ?",
                (content_sha256, fingerprint, inbox_id),
            )
            connection.commit()

    def set_file_hash(self, file_id: int, content_sha256: str, fingerprint: str) -> None:
        """Cache a content fingerprint and the stat fingerprint it was read from."""

        with self.connect() as connection:
            connection.execute(
                "UPDATE files SET content_sha256 = ?, hash_fingerprint = ? WHERE id = ?",
                (content_sha256, fingerprint, file_id),
            )
            connection.commit()

    def cancel_ingest(self, event_id: int) -> None:
        """Discard a reservation after verifying that its move did not persist."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = connection.execute(
                "SELECT inbox_id FROM events WHERE id = ? AND action = 'ingest_pending'",
                (event_id,),
            ).fetchone()
            if event is not None:
                connection.execute("DELETE FROM events WHERE id = ?", (event_id,))
                connection.execute(
                    "DELETE FROM inbox WHERE id = ? AND status = 'recovery'", (event["inbox_id"],)
                )
            connection.commit()

    def list_pending_ingests(self) -> list[HistoryEvent]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE action = 'ingest_pending' ORDER BY id"
            ).fetchall()
        return [self._event(row) for row in rows]

    def find_active_inbox_by_path(self, path: Path) -> InboxItem | None:
        """Find an existing active inbox record for a path."""

        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM inbox
                WHERE path = ? AND status IN ('pending', 'error', 'filing', 'returning')
                ORDER BY id DESC LIMIT 1
                """,
                (str(path),),
            ).fetchone()
        return self._inbox(row) if row else None

    def register_recovered_inbox_file(self, path: Path, size: int) -> InboxItem | None:
        """Register an untracked inbox file or reactivate its recovery record."""

        now = _now()
        with self.connect() as connection:
            active = connection.execute(
                """
                SELECT id FROM inbox
                WHERE path = ? AND status IN ('pending', 'error', 'filing', 'returning')
                LIMIT 1
                """,
                (str(path),),
            ).fetchone()
            if active is not None:
                return None

            recovery = connection.execute(
                """
                SELECT id FROM inbox
                WHERE path = ? AND status = 'recovery'
                ORDER BY id DESC LIMIT 1
                """,
                (str(path),),
            ).fetchone()
            if recovery is None:
                cursor = connection.execute(
                    """
                    INSERT INTO inbox(
                        path, original_path, original_name, size, detected_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (str(path), str(path), path.name, size, now),
                )
                if cursor.lastrowid is None:
                    raise RuntimeError("A base de dados não devolveu o id do ficheiro recuperado.")
                inbox_id = cursor.lastrowid
            else:
                inbox_id = int(recovery["id"])
                updated = connection.execute(
                    """
                    UPDATE inbox
                    SET status = 'pending', size = ?, detected_at = ?, last_error = ''
                    WHERE id = ? AND status = 'recovery'
                    """,
                    (size, now, inbox_id),
                )
                if updated.rowcount != 1:
                    connection.rollback()
                    return None
            connection.execute(
                """
                INSERT INTO events(action, source_path, destination_path, inbox_id, created_at)
                VALUES ('recover', ?, ?, ?, ?)
                """,
                (str(path), str(path), inbox_id, now),
            )
            connection.commit()
        return self.get_inbox_item(inbox_id)

    def list_inbox_for_reconciliation(self) -> list[InboxItem]:
        """List current inbox records that may need startup recovery."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM inbox
                WHERE status IN ('pending', 'error', 'filing', 'returning', 'recovery')
                ORDER BY detected_at ASC
                """
            ).fetchall()
        return [self._inbox(row) for row in rows]

    def list_inbox_items(self) -> list[InboxItem]:
        """List files still requiring attention."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM inbox
                WHERE status IN ('pending', 'error', 'recovery')
                ORDER BY detected_at DESC
                """
            ).fetchall()
        return [self._inbox(row) for row in rows]

    def count_inbox_items(self) -> int:
        """Return the current inbox count."""

        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total FROM inbox
                WHERE status IN ('pending', 'error', 'recovery')
                """
            ).fetchone()
        return int(row["total"])

    def update_inbox_suggestion(self, inbox_id: int, subject_id: int | None, kind: str) -> None:
        """Store the classifier proposal shown to the user."""

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE inbox
                SET suggested_subject_id = ?, suggested_kind = ?, last_error = ''
                WHERE id = ?
                """,
                (subject_id, kind, inbox_id),
            )
            connection.commit()

    def set_inbox_status(self, inbox_id: int, status: str, error: str = "") -> None:
        """Change processing state for an inbox item."""

        with self.connect() as connection:
            connection.execute(
                "UPDATE inbox SET status = ?, last_error = ? WHERE id = ?",
                (status, error, inbox_id),
            )
            connection.commit()

    def begin_document_filing(
        self,
        inbox_id: int,
        subject_id: int,
        kind: str,
        destination_path: Path,
        *,
        related_event_id: int | None = None,
    ) -> HistoryEvent:
        """Persist a filing destination before its filesystem move."""

        return self._begin_inbox_operation(
            "file_pending",
            inbox_id,
            destination_path,
            "filing",
            subject_id=subject_id,
            kind=kind,
            related_event_id=related_event_id,
        )

    def begin_return(self, inbox_id: int, destination_path: Path) -> HistoryEvent:
        """Persist a Downloads return destination before its filesystem move."""

        return self._begin_inbox_operation(
            "return_pending",
            inbox_id,
            destination_path,
            "returning",
        )

    def _begin_inbox_operation(
        self,
        action: str,
        inbox_id: int,
        destination_path: Path,
        status: str,
        *,
        subject_id: int | None = None,
        kind: str = "",
        related_event_id: int | None = None,
    ) -> HistoryEvent:
        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM events
                WHERE action = ? AND inbox_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (action, inbox_id),
            ).fetchone()
            if existing is not None:
                pending = self._event(existing)
                if pending.destination_path != destination_path:
                    raise RuntimeError("Já existe uma operação pendente para este ficheiro.")
                return pending
            item = connection.execute(
                """
                SELECT path FROM inbox
                WHERE id = ? AND status IN ('pending', 'error')
                """,
                (inbox_id,),
            ).fetchone()
            if item is None:
                raise LookupError(f"Ficheiro da caixa indisponível: {inbox_id}")
            now = _now()
            connection.execute(
                "UPDATE inbox SET status = ?, last_error = '' WHERE id = ?",
                (status, inbox_id),
            )
            cursor = connection.execute(
                """
                INSERT INTO events(
                    action, source_path, destination_path, inbox_id,
                    subject_id, kind, related_event_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action,
                    str(item["path"]),
                    str(destination_path),
                    inbox_id,
                    subject_id,
                    kind,
                    related_event_id,
                    now,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("A base de dados não devolveu o id da operação pendente.")
            event_id = cursor.lastrowid
            connection.commit()
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError("A operação pendente foi criada mas não pôde ser lida.")
        return self._event(row)

    def cancel_pending_inbox_operation(
        self,
        event_id: int,
        *,
        status: str = "pending",
        error: str = "",
        current_path: Path | None = None,
    ) -> bool:
        """Cancel an operation whose source file never left the inbox."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = connection.execute(
                """
                SELECT inbox_id FROM events
                WHERE id = ? AND action IN ('file_pending', 'return_pending')
                """,
                (event_id,),
            ).fetchone()
            if event is None or event["inbox_id"] is None:
                return False
            connection.execute("DELETE FROM events WHERE id = ?", (event_id,))
            if current_path is None:
                connection.execute(
                    """
                    UPDATE inbox SET status = ?, last_error = ?
                    WHERE id = ? AND status IN ('filing', 'returning')
                    """,
                    (status, error, int(event["inbox_id"])),
                )
            else:
                connection.execute(
                    """
                    UPDATE inbox SET status = ?, last_error = ?, path = ?
                    WHERE id = ? AND status IN ('filing', 'returning')
                    """,
                    (status, error, str(current_path), int(event["inbox_id"])),
                )
            connection.commit()
        return True

    def reset_interrupted_filing(self, inbox_id: int) -> bool:
        """Return an interrupted filing to pending if it is still transient."""

        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE inbox SET status = 'pending', last_error = ''
                WHERE id = ? AND status = 'filing'
                """,
                (inbox_id,),
            )
            connection.commit()
        return cursor.rowcount == 1

    def mark_inbox_recovery_required(self, inbox_id: int, error: str) -> bool:
        """Expose a missing inbox file without retaining a blocking active path."""

        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE inbox SET status = 'recovery', last_error = ?
                WHERE id = ? AND status IN ('pending', 'error', 'filing', 'returning')
                """,
                (error, inbox_id),
            )
            connection.commit()
        return cursor.rowcount == 1

    def record_filing(
        self,
        inbox_id: int,
        subject_id: int,
        kind: str,
        destination_path: Path,
        *,
        pending_event_id: int | None = None,
    ) -> FiledDocument:
        """Atomically record a successful inbox-to-subject move."""

        now = _now()
        pending_related: int | None = None
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if pending_event_id is not None:
                marker = connection.execute(
                    """
                    SELECT id, related_event_id FROM events
                    WHERE id = ? AND action = 'file_pending' AND inbox_id = ?
                      AND destination_path = ? AND subject_id = ? AND kind = ?
                    """,
                    (
                        pending_event_id,
                        inbox_id,
                        str(destination_path),
                        subject_id,
                        kind,
                    ),
                ).fetchone()
                if marker is None:
                    raise LookupError("A organização pendente já foi concluída ou cancelada.")
                pending_related = (
                    int(marker["related_event_id"])
                    if marker["related_event_id"] is not None
                    else None
                )
                item_row = connection.execute(
                    "SELECT * FROM inbox WHERE id = ? AND status = 'filing'",
                    (inbox_id,),
                ).fetchone()
            else:
                item_row = connection.execute(
                    "SELECT * FROM inbox WHERE id = ?", (inbox_id,)
                ).fetchone()
            if item_row is None:
                raise LookupError(f"Ficheiro da caixa inexistente: {inbox_id}")
            item = self._inbox(item_row)
            destination_key = normalise_path_key(destination_path)
            catalog_rows = connection.execute(
                "SELECT id, current_path, catalog_state FROM files"
            ).fetchall()
            matching = [
                row
                for row in catalog_rows
                if normalise_path_key(Path(str(row["current_path"]))) == destination_key
            ]
            if any(str(row["catalog_state"]) == "active" for row in matching):
                raise LookupError("O destino já pertence a outro registo do catálogo.")
            token = uuid4().hex
            if matching:
                if len(matching) != 1:
                    raise LookupError("Existem vários registos antigos para o mesmo destino.")
                file_id = int(matching[0]["id"])
                connection.execute(
                    """
                    UPDATE files
                    SET subject_id = ?, inbox_id = ?, kind = ?, original_name = ?,
                        current_path = ?, original_path = ?, size = ?, filed_at = ?,
                        indexed_at = NULL, origin = 'filed', record_token = ?,
                        catalog_state = 'active', content_sha256 = ?
                    WHERE id = ? AND catalog_state = 'dropped'
                    """,
                    (
                        subject_id,
                        inbox_id,
                        kind,
                        item.original_name,
                        str(destination_path),
                        str(item.original_path),
                        item.size,
                        now,
                        token,
                        item.content_sha256,
                        file_id,
                    ),
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO files(
                        subject_id, inbox_id, kind, original_name, current_path,
                        original_path, size, filed_at, record_token, content_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        subject_id,
                        inbox_id,
                        kind,
                        item.original_name,
                        str(destination_path),
                        str(item.original_path),
                        item.size,
                        now,
                        token,
                        item.content_sha256,
                    ),
                )
                if cursor.lastrowid is None:
                    raise RuntimeError("A base de dados não devolveu o id do documento.")
                file_id = cursor.lastrowid
            connection.execute(
                "UPDATE inbox SET status = 'filed', path = ?, last_error = '' WHERE id = ?",
                (str(destination_path), inbox_id),
            )
            connection.execute(
                """
                INSERT INTO events(
                    action, source_path, destination_path, file_id, inbox_id,
                    related_event_id, created_at
                ) VALUES ('file', ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(item.path),
                    str(destination_path),
                    file_id,
                    inbox_id,
                    pending_related,
                    now,
                ),
            )
            if pending_event_id is None:
                connection.execute(
                    """
                    DELETE FROM events
                    WHERE action = 'file_pending' AND inbox_id = ? AND destination_path = ?
                    """,
                    (inbox_id, str(destination_path)),
                )
            else:
                connection.execute("DELETE FROM events WHERE id = ?", (pending_event_id,))
            row = connection.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
            if row is None:  # pragma: no cover - defensive database invariant
                raise RuntimeError("O ficheiro foi organizado mas não pôde ser lido.")
            document = self._file(row)
            connection.commit()
        return document

    def adopt_subject_file(
        self,
        candidate: ExistingDownload,
        subject_id: int,
        kind: str,
    ) -> FiledDocument:
        """Catalog an unchanged file in place without creating move history."""

        if kind not in FILE_KINDS:
            raise ValueError(f"Tipo de documento inválido: {kind}")
        if not candidate.still_matches():
            raise LookupError("O ficheiro mudou antes de poder ser adotado.")
        now = _now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            subject = connection.execute(
                "SELECT id FROM subjects WHERE id = ?", (subject_id,)
            ).fetchone()
            if subject is None:
                raise LookupError("A disciplina já não existe.")
            if not candidate.still_matches():
                raise LookupError("O ficheiro mudou antes de poder ser adotado.")
            candidate_key = normalise_path_key(candidate.path)
            catalog_rows = connection.execute(
                "SELECT id, current_path, catalog_state FROM files"
            ).fetchall()
            matching = [
                row
                for row in catalog_rows
                if normalise_path_key(Path(str(row["current_path"]))) == candidate_key
            ]
            if any(str(row["catalog_state"]) == "active" for row in matching):
                raise LookupError("O ficheiro já existe no catálogo através de outro caminho.")
            token = uuid4().hex
            if matching:
                if len(matching) != 1:
                    raise LookupError("Existem vários registos antigos para o mesmo ficheiro.")
                file_id = int(matching[0]["id"])
                cursor = connection.execute(
                    """
                    UPDATE files
                    SET subject_id = ?, inbox_id = NULL, kind = ?, original_name = ?,
                        current_path = ?, original_path = ?, size = ?, filed_at = ?,
                        indexed_at = NULL, origin = 'adopted', record_token = ?,
                        catalog_state = 'active'
                    WHERE id = ? AND catalog_state = 'dropped'
                    """,
                    (
                        subject_id,
                        kind,
                        candidate.path.name,
                        str(candidate.path),
                        str(candidate.path),
                        candidate.size,
                        now,
                        token,
                        file_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise LookupError("O registo antigo mudou antes de poder ser adotado.")
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO files(
                        subject_id, inbox_id, kind, original_name, current_path,
                        original_path, size, filed_at, origin, record_token
                    ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, 'adopted', ?)
                    """,
                    (
                        subject_id,
                        kind,
                        candidate.path.name,
                        str(candidate.path),
                        str(candidate.path),
                        candidate.size,
                        now,
                        token,
                    ),
                )
                if cursor.lastrowid is None:
                    raise RuntimeError("A base de dados não devolveu o id do documento adotado.")
                file_id = cursor.lastrowid
            connection.commit()
        document = self.get_file(file_id)
        if document is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError("O documento foi adotado mas não pôde ser lido.")
        return document

    def unregister_adopted_file(
        self,
        file_id: int,
        *,
        expected_path: Path,
        expected_record_token: str,
        reviewed_reason: str,
    ) -> bool:
        """Remove only an adopted catalog row while leaving its file untouched."""

        normalized_path = normalise_path_key(expected_path)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pending = connection.execute(
                "SELECT 1 FROM events WHERE action = 'undo_pending' AND file_id = ?",
                (file_id,),
            ).fetchone()
            if pending is not None:
                return False
            cursor = connection.execute(
                """
                DELETE FROM files
                WHERE id = ? AND current_path = ? AND record_token = ?
                  AND origin = 'adopted' AND catalog_state = 'active'
                """,
                (file_id, str(expected_path), expected_record_token),
            )
            if cursor.rowcount != 1:
                return False
            connection.execute("DELETE FROM document_pages WHERE file_id = ?", (str(file_id),))
            connection.execute(
                """
                INSERT INTO reviewed_findings(normalized_path, reason, reviewed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(normalized_path, reason)
                DO UPDATE SET reviewed_at = excluded.reviewed_at
                """,
                (normalized_path, reviewed_reason, _now()),
            )
            connection.commit()
        return True

    def drop_file_record(
        self,
        file_id: int,
        *,
        expected_path: Path,
        expected_origin: str,
        expected_record_token: str,
        verify_missing: Callable[[], bool],
    ) -> bool:
        """Drop a stale catalog row after its caller proves the file is missing."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pending = connection.execute(
                "SELECT 1 FROM events WHERE action = 'undo_pending' AND file_id = ?",
                (file_id,),
            ).fetchone()
            if pending is not None:
                return False
            current = connection.execute(
                """
                SELECT id FROM files
                WHERE id = ? AND current_path = ? AND origin = ? AND record_token = ?
                  AND catalog_state = 'active'
                """,
                (
                    file_id,
                    str(expected_path),
                    expected_origin,
                    expected_record_token,
                ),
            ).fetchone()
            if current is None or not verify_missing():
                return False
            cursor = connection.execute(
                """
                UPDATE files
                SET catalog_state = 'dropped', indexed_at = NULL, record_token = ?
                WHERE id = ? AND current_path = ? AND origin = ? AND record_token = ?
                  AND catalog_state = 'active'
                """,
                (
                    uuid4().hex,
                    file_id,
                    str(expected_path),
                    expected_origin,
                    expected_record_token,
                ),
            )
            if cursor.rowcount != 1:
                return False
            connection.execute(
                """
                UPDATE events SET undone_at = COALESCE(undone_at, ?)
                WHERE action = 'file' AND file_id = ?
                """,
                (_now(), file_id),
            )
            connection.execute("DELETE FROM document_pages WHERE file_id = ?", (str(file_id),))
            connection.execute("UPDATE tasks SET file_id = NULL WHERE file_id = ?", (file_id,))
            connection.commit()
        return cursor.rowcount == 1

    def mark_finding_reviewed(self, path: Path, reason: str) -> None:
        """Persist an idempotent human review decision for one path/reason pair."""

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO reviewed_findings(normalized_path, reason, reviewed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(normalized_path, reason)
                DO UPDATE SET reviewed_at = excluded.reviewed_at
                """,
                (normalise_path_key(path), reason, _now()),
            )
            connection.commit()

    def list_reviewed_finding_keys(self) -> set[tuple[str, str]]:
        """Return all persisted review keys in one query."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT normalized_path, reason FROM reviewed_findings"
            ).fetchall()
        return {(str(row["normalized_path"]), str(row["reason"])) for row in rows}

    def prune_reviewed_findings(self, live_keys: set[tuple[str, str]]) -> int:
        """Forget reviews whose underlying finding disappeared after a complete scan."""

        stale = self.list_reviewed_finding_keys() - live_keys
        if not stale:
            return 0
        with self.connect() as connection:
            connection.executemany(
                "DELETE FROM reviewed_findings WHERE normalized_path = ? AND reason = ?",
                sorted(stale),
            )
            connection.commit()
        return len(stale)

    def record_return(
        self,
        inbox_id: int,
        destination_path: Path,
        *,
        pending_event_id: int | None = None,
    ) -> None:
        """Record an inbox file returned to Downloads as non-university material."""

        now = _now()
        with self.connect() as connection:
            if pending_event_id is not None:
                connection.execute("BEGIN IMMEDIATE")
                marker = connection.execute(
                    """
                    SELECT id FROM events
                    WHERE id = ? AND action = 'return_pending' AND inbox_id = ?
                      AND destination_path = ?
                    """,
                    (pending_event_id, inbox_id, str(destination_path)),
                ).fetchone()
                if marker is None:
                    raise LookupError("A devolução pendente já foi concluída ou cancelada.")
                item_row = connection.execute(
                    "SELECT * FROM inbox WHERE id = ? AND status = 'returning'",
                    (inbox_id,),
                ).fetchone()
            else:
                item_row = connection.execute(
                    "SELECT * FROM inbox WHERE id = ?", (inbox_id,)
                ).fetchone()
            if item_row is None:
                raise LookupError(f"Ficheiro da caixa inexistente: {inbox_id}")
            item = self._inbox(item_row)
            connection.execute(
                "UPDATE inbox SET status = 'returned', path = ?, last_error = '' WHERE id = ?",
                (str(destination_path), inbox_id),
            )
            connection.execute(
                """
                INSERT INTO events(action, source_path, destination_path, inbox_id, created_at)
                VALUES ('return', ?, ?, ?, ?)
                """,
                (str(item.path), str(destination_path), inbox_id, now),
            )
            if pending_event_id is None:
                connection.execute(
                    """
                    DELETE FROM events
                    WHERE action = 'return_pending' AND inbox_id = ? AND destination_path = ?
                    """,
                    (inbox_id, str(destination_path)),
                )
            else:
                connection.execute("DELETE FROM events WHERE id = ?", (pending_event_id,))
            connection.commit()

    def get_file(self, file_id: int) -> FiledDocument | None:
        """Return a filed document by id."""

        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM files WHERE id = ? AND catalog_state = 'active'",
                (file_id,),
            ).fetchone()
        return self._file(row) if row else None

    def list_recent_files(self, limit: int = 8) -> list[FiledDocument]:
        """List the latest filed documents."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM files
                WHERE catalog_state = 'active'
                ORDER BY filed_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._file(row) for row in rows]

    def list_files(self) -> list[FiledDocument]:
        """List every filed document for consistency checks."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM files WHERE catalog_state = 'active' ORDER BY id ASC"
            ).fetchall()
        return [self._file(row) for row in rows]

    def list_active_documents_by_size(self, size: int) -> list[FiledDocument]:
        """List active catalog documents that share a byte size."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM files
                WHERE catalog_state = 'active' AND size = ?
                ORDER BY filed_at DESC, id DESC
                """,
                (size,),
            ).fetchall()
        return [self._file(row) for row in rows]

    def list_adopted_files(self) -> list[FiledDocument]:
        """List files cataloged in place so the user can unregister them."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM files
                WHERE origin = 'adopted' AND catalog_state = 'active'
                ORDER BY filed_at DESC
                """
            ).fetchall()
        return [self._file(row) for row in rows]

    def count_files_by_subject(self) -> dict[int, tuple[int, int]]:
        """Return the active file count and total bytes for each subject."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT subject_id, COUNT(*) AS total, COALESCE(SUM(size), 0) AS bytes
                FROM files
                WHERE catalog_state = 'active'
                GROUP BY subject_id
                """
            ).fetchall()
        return {int(row["subject_id"]): (int(row["total"]), int(row["bytes"])) for row in rows}

    def list_subject_files(self, subject_id: int) -> list[FiledDocument]:
        """List a subject's active documents, grouped by kind and newest first."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM files
                WHERE subject_id = ? AND catalog_state = 'active'
                ORDER BY kind, filed_at DESC
                """,
                (subject_id,),
            ).fetchall()
        return [self._file(row) for row in rows]

    def increment_metric(self, kind: str, amount: int = 1) -> None:
        """Add to a lifetime safety counter used by the activity summary."""

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO activity_counters(kind, value) VALUES (?, ?)
                ON CONFLICT(kind) DO UPDATE SET value = value + excluded.value
                """,
                (kind, amount),
            )
            connection.commit()

    def activity_summary(self) -> ActivitySummary:
        """Summarise lifetime filing history and persisted safety counters."""

        with self.connect() as connection:
            organized = int(
                connection.execute("SELECT COUNT(*) FROM events WHERE action = 'file'").fetchone()[
                    0
                ]
            )
            adopted = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM files
                    WHERE origin = 'adopted' AND catalog_state = 'active'
                    """
                ).fetchone()[0]
            )
            returned = int(
                connection.execute(
                    "SELECT COUNT(*) FROM events WHERE action = 'return'"
                ).fetchone()[0]
            )
            undone = int(
                connection.execute(
                    "SELECT COUNT(*) FROM events WHERE action = 'file' AND undone_at IS NOT NULL"
                ).fetchone()[0]
            )
            counters = {
                str(row["kind"]): int(row["value"])
                for row in connection.execute(
                    "SELECT kind, value FROM activity_counters"
                ).fetchall()
            }
        return ActivitySummary(
            organized=organized,
            adopted=adopted,
            returned=returned,
            undone=undone,
            collisions_renamed=counters.get(METRIC_COLLISIONS_RENAMED, 0),
            operations_recovered=counters.get(METRIC_OPERATIONS_RECOVERED, 0),
        )

    def filing_hints(self) -> list[FilingHint]:
        """Return live, confirmed filing choices for conservative local learning."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT f.inbox_id, f.original_name, f.subject_id, f.kind, f.current_path
                FROM files AS f
                JOIN inbox AS i ON i.id = f.inbox_id
                JOIN subjects AS s ON s.id = f.subject_id
                WHERE i.status = 'filed'
                  AND f.origin = 'filed'
                  AND f.catalog_state = 'active'
                  AND s.active = 1
                  AND EXISTS (
                      SELECT 1 FROM events AS e
                      WHERE e.action = 'file'
                        AND e.file_id = f.id
                        AND e.inbox_id = f.inbox_id
                        AND e.undone_at IS NULL
                  )
                ORDER BY f.filed_at ASC, f.id ASC
                """
            ).fetchall()

        hints: list[FilingHint] = []
        seen_inbox_ids: set[int] = set()
        for row in rows:
            inbox_id = int(row["inbox_id"])
            kind = str(row["kind"])
            if inbox_id in seen_inbox_ids or kind not in FILE_KINDS:
                continue
            if not Path(str(row["current_path"])).is_file():
                continue
            seen_inbox_ids.add(inbox_id)
            hints.append(FilingHint(str(row["original_name"]), int(row["subject_id"]), kind))
        return hints

    def list_unindexed_documents(
        self,
        limit: int = 50,
        *,
        excluded_keys: Collection[tuple[int, str]] = (),
    ) -> list[FiledDocument]:
        """List supported files waiting for text extraction."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM files
                WHERE indexed_at IS NULL AND catalog_state = 'active'
                ORDER BY filed_at ASC
                """
            ).fetchall()
        result: list[FiledDocument] = []
        excluded = set(excluded_keys)
        for row in rows:
            document = self._file(row)
            if (document.id, document.record_token) in excluded:
                continue
            if ExistingDownload.capture(document.current_path) is None:
                continue
            result.append(document)
            if len(result) >= limit:
                break
        return result

    def latest_undoable_filing(self) -> HistoryEvent | None:
        """Return the most recent filing that has not been undone."""

        events = self.list_undoable_filings()
        return events[0] if events else None

    def list_undoable_filings(self) -> list[HistoryEvent]:
        """List filing events that have not been marked undone."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM events
                WHERE action = 'file' AND undone_at IS NULL
                ORDER BY id DESC
                """
            ).fetchall()
        return [self._event(row) for row in rows]

    def begin_filing_undo(
        self,
        event: HistoryEvent,
        restored_path: Path,
        *,
        source_path: Path | None = None,
    ) -> HistoryEvent:
        """Persist an undo destination before the document is moved.

        ``source_path`` is the document's current location, which differs from
        the filing destination when the document was moved after being filed.
        """

        if event.file_id is None or event.inbox_id is None:
            raise ValueError("O evento não contém os dados necessários para desfazer.")
        actual_source = source_path or event.destination_path
        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM events
                WHERE action = 'undo_pending' AND file_id = ? AND inbox_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (event.file_id, event.inbox_id),
            ).fetchone()
            if existing is not None:
                pending = self._event(existing)
                if pending.destination_path != restored_path:
                    raise RuntimeError("Já existe uma operação de desfazer pendente.")
                return pending
            cursor = connection.execute(
                """
                INSERT INTO events(
                    action, source_path, destination_path, file_id, inbox_id,
                    related_event_id, created_at
                ) VALUES ('undo_pending', ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(actual_source),
                    str(restored_path),
                    event.file_id,
                    event.inbox_id,
                    event.id,
                    _now(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("A base de dados não devolveu o id da operação de desfazer.")
            pending_id = cursor.lastrowid
            connection.commit()
            row = connection.execute("SELECT * FROM events WHERE id = ?", (pending_id,)).fetchone()
        if row is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError("A operação de desfazer foi criada mas não pôde ser lida.")
        return self._event(row)

    def list_pending_undos(self) -> list[HistoryEvent]:
        """List undo operations interrupted before their database commit."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE action = 'undo_pending' ORDER BY id ASC"
            ).fetchall()
        return [self._event(row) for row in rows]

    def list_pending_filings(self) -> list[HistoryEvent]:
        """List filings interrupted before their database commit."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE action = 'file_pending' ORDER BY id ASC"
            ).fetchall()
        return [self._event(row) for row in rows]

    def list_pending_returns(self) -> list[HistoryEvent]:
        """List Downloads returns interrupted before their database commit."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE action = 'return_pending' ORDER BY id ASC"
            ).fetchall()
        return [self._event(row) for row in rows]

    def begin_document_move(
        self,
        file_id: int,
        subject_id: int,
        kind: str,
        destination_path: Path,
    ) -> HistoryEvent:
        """Persist a catalogued document's new location before its move."""

        with self.connect() as connection:
            document = connection.execute(
                "SELECT current_path FROM files WHERE id = ? AND catalog_state = 'active'",
                (file_id,),
            ).fetchone()
            if document is None:
                raise LookupError("O documento já não está no catálogo.")
            existing = connection.execute(
                """
                SELECT * FROM events
                WHERE action = 'move_pending' AND file_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (file_id,),
            ).fetchone()
            if existing is not None:
                pending = self._event(existing)
                if pending.destination_path != destination_path:
                    raise RuntimeError("Já existe um movimento pendente para este documento.")
                return pending
            cursor = connection.execute(
                """
                INSERT INTO events(
                    action, source_path, destination_path, file_id,
                    subject_id, kind, created_at
                ) VALUES ('move_pending', ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(document["current_path"]),
                    str(destination_path),
                    file_id,
                    subject_id,
                    kind,
                    _now(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("A base de dados não devolveu o id do movimento.")
            event_id = cursor.lastrowid
            connection.commit()
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError("O movimento pendente foi criado mas não pôde ser lido.")
        return self._event(row)

    def complete_document_move(
        self,
        event_id: int,
        destination_path: Path,
        *,
        subject_id: int,
        kind: str,
    ) -> FiledDocument:
        """Atomically record a completed move between subject folders."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            marker = connection.execute(
                """
                SELECT file_id FROM events
                WHERE id = ? AND action = 'move_pending' AND destination_path = ?
                  AND subject_id = ? AND kind = ?
                """,
                (event_id, str(destination_path), subject_id, kind),
            ).fetchone()
            if marker is None or marker["file_id"] is None:
                raise LookupError("O movimento pendente já foi concluído ou cancelado.")
            file_id = int(marker["file_id"])
            updated = connection.execute(
                """
                UPDATE files
                SET subject_id = ?, kind = ?, current_path = ?
                WHERE id = ? AND catalog_state = 'active'
                """,
                (subject_id, kind, str(destination_path), file_id),
            )
            if updated.rowcount != 1:
                raise LookupError("O documento já não está no catálogo.")
            subject_row = connection.execute(
                "SELECT name FROM subjects WHERE id = ?", (subject_id,)
            ).fetchone()
            subject_name = str(subject_row["name"]) if subject_row is not None else ""
            connection.execute(
                "UPDATE document_pages SET subject = ?, title = ? WHERE file_id = ?",
                (subject_name, destination_path.name, str(file_id)),
            )
            connection.execute("UPDATE events SET action = 'move' WHERE id = ?", (event_id,))
            connection.commit()
        document = self.get_file(file_id)
        if document is None:  # pragma: no cover - defensive database invariant
            raise LookupError("O documento movido não pôde ser lido.")
        return document

    def cancel_document_move(self, event_id: int, *, new_path: Path | None = None) -> bool:
        """Discard a prepared move whose filesystem move never happened.

        When a rolled-back move left the document under a new name, ``new_path``
        re-points the catalog row before the marker is removed.
        """

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            marker = connection.execute(
                "SELECT file_id, source_path FROM events WHERE id = ? AND action = 'move_pending'",
                (event_id,),
            ).fetchone()
            if marker is None:
                return False
            if new_path is not None and marker["file_id"] is not None:
                connection.execute(
                    """
                    UPDATE files SET current_path = ?
                    WHERE id = ? AND current_path = ?
                    """,
                    (str(new_path), int(marker["file_id"]), str(marker["source_path"])),
                )
            connection.execute("DELETE FROM events WHERE id = ?", (event_id,))
            connection.commit()
        return True

    def list_pending_moves(self) -> list[HistoryEvent]:
        """List document moves interrupted before their database commit."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE action = 'move_pending' ORDER BY id ASC"
            ).fetchall()
        return [self._event(row) for row in rows]

    def begin_version_rename(self, file_id: int, destination_path: Path) -> HistoryEvent:
        """Persist a previous-version rename before its filesystem move."""

        with self.connect() as connection:
            document = connection.execute(
                """
                SELECT current_path FROM files
                WHERE id = ? AND catalog_state = 'active'
                """,
                (file_id,),
            ).fetchone()
            if document is None:
                raise LookupError("O documento anterior já não está no catálogo.")
            now = _now()
            cursor = connection.execute(
                """
                INSERT INTO events(
                    action, source_path, destination_path, file_id, created_at
                ) VALUES ('version_pending', ?, ?, ?, ?)
                """,
                (str(document["current_path"]), str(destination_path), file_id, now),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("A base de dados não devolveu o id da versão anterior.")
            event_id = cursor.lastrowid
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            connection.commit()
        if row is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError("A versão anterior foi preparada mas não pôde ser lida.")
        return self._event(row)

    def complete_version_rename(self, event_id: int, destination_path: Path) -> None:
        """Point the catalog at the renamed previous version."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = connection.execute(
                "SELECT file_id FROM events WHERE id = ? AND action = 'version_pending'",
                (event_id,),
            ).fetchone()
            if event is None or event["file_id"] is None:
                raise LookupError("A renomeação da versão anterior já não está pendente.")
            connection.execute(
                "UPDATE files SET current_path = ? WHERE id = ?",
                (str(destination_path), int(event["file_id"])),
            )
            connection.execute(
                "UPDATE events SET action = 'version', destination_path = ? WHERE id = ?",
                (str(destination_path), event_id),
            )
            connection.commit()

    def cancel_version_rename(self, event_id: int) -> bool:
        """Discard a prepared version rename whose move never happened."""

        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM events WHERE id = ? AND action = 'version_pending'",
                (event_id,),
            )
            connection.commit()
        return cursor.rowcount == 1

    def list_pending_versions(self) -> list[HistoryEvent]:
        """List previous-version renames interrupted before their commit."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE action = 'version_pending' ORDER BY id ASC"
            ).fetchall()
        return [self._event(row) for row in rows]

    def linked_version_event(self, filing_event: HistoryEvent) -> HistoryEvent | None:
        """Return the still-active version rename linked to a filing, if any."""

        if filing_event.related_event_id is None:
            return None
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM events
                WHERE id = ? AND action = 'version' AND undone_at IS NULL
                """,
                (filing_event.related_event_id,),
            ).fetchone()
        return self._event(row) if row is not None else None

    def cancel_pending_undo(self, event_id: int) -> bool:
        """Remove a prepared undo that did not move its source document."""

        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM events WHERE id = ? AND action = 'undo_pending'",
                (event_id,),
            )
            connection.commit()
        return cursor.rowcount == 1

    def redirect_filing_destination(
        self,
        event_id: int,
        file_id: int,
        previous_path: Path,
        new_path: Path,
        pending_event_id: int,
    ) -> bool:
        """Point the catalog and filing history at a rolled-back undo destination."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = connection.execute(
                """
                SELECT id FROM events
                WHERE id = ? AND action = 'file' AND undone_at IS NULL AND file_id = ?
                """,
                (event_id, file_id),
            ).fetchone()
            marker = connection.execute(
                "SELECT id FROM events WHERE id = ? AND action = 'undo_pending'",
                (pending_event_id,),
            ).fetchone()
            if event is None or marker is None:
                connection.rollback()
                return False
            updated = connection.execute(
                "UPDATE files SET current_path = ? WHERE id = ? AND current_path = ?",
                (str(new_path), file_id, str(previous_path)),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return False
            connection.execute(
                "UPDATE events SET destination_path = ? WHERE id = ?",
                (str(new_path), event_id),
            )
            connection.execute("DELETE FROM events WHERE id = ?", (pending_event_id,))
            connection.commit()
        return True

    def complete_pending_undo(self, pending: HistoryEvent) -> InboxItem | None:
        """Commit an undo whose prepared filesystem move already completed."""

        if pending.file_id is None or pending.inbox_id is None:
            return None
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event_row = None
            if pending.related_event_id is not None:
                event_row = connection.execute(
                    """
                    SELECT * FROM events
                    WHERE id = ? AND action = 'file' AND undone_at IS NULL
                    """,
                    (pending.related_event_id,),
                ).fetchone()
            if event_row is None:
                event_row = connection.execute(
                    """
                    SELECT * FROM events
                    WHERE action = 'file' AND file_id = ? AND inbox_id = ?
                      AND undone_at IS NULL AND destination_path = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (pending.file_id, pending.inbox_id, str(pending.source_path)),
                ).fetchone()
            if event_row is None:
                return None
            event = self._event(event_row)
            if not self._complete_filing_undo(
                connection,
                event,
                pending.destination_path,
                pending_event_id=pending.id,
                source_path=pending.source_path,
            ):
                return None
            connection.commit()
        return self.get_inbox_item(pending.inbox_id)

    def complete_legacy_interrupted_undo(
        self, event: HistoryEvent, restored_path: Path
    ) -> InboxItem | None:
        """Commit a pre-marker undo conservatively matched to its original path."""

        if event.inbox_id is None:
            return None
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not self._complete_filing_undo(connection, event, restored_path):
                return None
            connection.commit()
        return self.get_inbox_item(event.inbox_id)

    def mark_filing_undone(
        self,
        event: HistoryEvent,
        restored_path: Path,
        *,
        version_event: HistoryEvent | None = None,
        source_path: Path | None = None,
    ) -> None:
        """Update persistence after the filer restores a document to the inbox."""

        if event.file_id is None or event.inbox_id is None:
            raise ValueError("O evento não contém os dados necessários para desfazer.")
        with self.connect() as connection:
            if not self._complete_filing_undo(
                connection, event, restored_path, source_path=source_path
            ):
                raise LookupError("A organização já não está disponível para desfazer.")
            if version_event is not None:
                if version_event.file_id is None:
                    raise LookupError("A versão anterior não tem registo associado.")
                updated = connection.execute(
                    """
                    UPDATE files SET current_path = ?
                    WHERE id = ? AND current_path = ? AND catalog_state = 'active'
                    """,
                    (
                        str(version_event.source_path),
                        version_event.file_id,
                        str(version_event.destination_path),
                    ),
                )
                if updated.rowcount != 1:
                    raise LookupError("A versão anterior já não está disponível para desfazer.")
                connection.execute(
                    "UPDATE events SET undone_at = ? WHERE id = ? AND action = 'version'",
                    (_now(), version_event.id),
                )
            connection.commit()

    @staticmethod
    def _complete_filing_undo(
        connection: sqlite3.Connection,
        event: HistoryEvent,
        restored_path: Path,
        *,
        pending_event_id: int | None = None,
        source_path: Path | None = None,
    ) -> bool:
        """Apply the database half of a completed undo in one transaction."""

        if event.file_id is None or event.inbox_id is None:
            return False
        expected_source = source_path or event.destination_path
        current = connection.execute(
            """
            SELECT id FROM events
            WHERE id = ? AND action = 'file' AND undone_at IS NULL
            """,
            (event.id,),
        ).fetchone()
        document = connection.execute(
            """
            SELECT id FROM files
            WHERE id = ? AND inbox_id = ? AND current_path = ?
              AND origin = 'filed' AND catalog_state = 'active'
            """,
            (event.file_id, event.inbox_id, str(expected_source)),
        ).fetchone()
        inbox = connection.execute(
            "SELECT id FROM inbox WHERE id = ?", (event.inbox_id,)
        ).fetchone()
        if current is None or document is None or inbox is None:
            return False

        if pending_event_id is None:
            connection.execute(
                """
                DELETE FROM events
                WHERE action = 'undo_pending' AND file_id = ? AND inbox_id = ?
                  AND destination_path = ?
                """,
                (event.file_id, event.inbox_id, str(restored_path)),
            )
        else:
            connection.execute(
                "DELETE FROM events WHERE id = ? AND action = 'undo_pending'",
                (pending_event_id,),
            )
        connection.execute("DELETE FROM document_pages WHERE file_id = ?", (str(event.file_id),))
        connection.execute("DELETE FROM files WHERE id = ?", (event.file_id,))
        connection.execute(
            """
            UPDATE inbox
            SET status = 'pending', path = ?, last_error = ''
            WHERE id = ?
            """,
            (str(restored_path), event.inbox_id),
        )
        connection.execute("UPDATE events SET undone_at = ? WHERE id = ?", (_now(), event.id))
        return True

    def replace_document_pages(
        self,
        file_id: int,
        subject: str,
        title: str,
        pages: Sequence[str],
        *,
        expected_path: Path | None = None,
        expected_record_token: str | None = None,
        size: int | None = None,
        mtime_ns: int | None = None,
    ) -> None:
        """Replace all indexed pages for a document."""

        assignment = "indexed_at = ?, index_state = '', index_error = ''"
        values: list[object] = [_now()]
        if size is not None and mtime_ns is not None:
            assignment += ", size = ?, mtime_ns = ?"
            values += [size, mtime_ns]
        with self.connect() as connection:
            if expected_path is not None:
                token_clause = " AND record_token = ?" if expected_record_token is not None else ""
                values += [file_id, str(expected_path)]
                if expected_record_token is not None:
                    values.append(expected_record_token)
                updated = connection.execute(
                    f"""
                    UPDATE files SET {assignment}
                    WHERE id = ? AND current_path = ?{token_clause}
                      AND catalog_state = 'active'
                    """,
                    tuple(values),
                )
                if updated.rowcount != 1:
                    return
            else:
                values.append(file_id)
                connection.execute(
                    f"""
                    UPDATE files SET {assignment}
                    WHERE id = ? AND catalog_state = 'active'
                    """,
                    tuple(values),
                )
            connection.execute("DELETE FROM document_pages WHERE file_id = ?", (str(file_id),))
            connection.executemany(
                """
                INSERT INTO document_pages(file_id, page, subject, title, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (str(file_id), str(index), subject, title, content)
                    for index, content in enumerate(pages, start=1)
                    if content.strip()
                ],
            )
            connection.commit()

    def mark_document_indexed(
        self,
        file_id: int,
        *,
        expected_path: Path | None = None,
        expected_record_token: str | None = None,
        index_state: str = "",
        index_error: str = "",
        size: int | None = None,
        mtime_ns: int | None = None,
    ) -> None:
        """Mark a document handled even when it contains no extractable text."""

        assignment = "indexed_at = ?, index_state = ?, index_error = ?"
        values: list[object] = [_now(), index_state, index_error]
        if size is not None and mtime_ns is not None:
            assignment += ", size = ?, mtime_ns = ?"
            values += [size, mtime_ns]
        with self.connect() as connection:
            if expected_path is not None:
                token_clause = " AND record_token = ?" if expected_record_token is not None else ""
                values += [file_id, str(expected_path)]
                if expected_record_token is not None:
                    values.append(expected_record_token)
                connection.execute(
                    f"""
                    UPDATE files SET {assignment}
                    WHERE id = ? AND current_path = ?{token_clause}
                      AND catalog_state = 'active'
                    """,
                    tuple(values),
                )
            else:
                values.append(file_id)
                connection.execute(
                    f"""
                    UPDATE files SET {assignment}
                    WHERE id = ? AND catalog_state = 'active'
                    """,
                    tuple(values),
                )
            connection.commit()

    def clear_index_state(
        self,
        file_id: int,
        *,
        expected_path: Path | None = None,
        expected_record_token: str | None = None,
    ) -> None:
        """Reset index state so a document is queued for extraction again."""

        with self.connect() as connection:
            if expected_path is not None:
                token_clause = " AND record_token = ?" if expected_record_token is not None else ""
                parameters: tuple[object, ...] = (file_id, str(expected_path))
                if expected_record_token is not None:
                    parameters += (expected_record_token,)
                connection.execute(
                    f"""
                    UPDATE files SET indexed_at = NULL, index_state = '', index_error = ''
                    WHERE id = ? AND current_path = ?{token_clause}
                      AND catalog_state = 'active'
                    """,
                    parameters,
                )
            else:
                connection.execute(
                    """
                    UPDATE files SET indexed_at = NULL, index_state = '', index_error = ''
                    WHERE id = ? AND catalog_state = 'active'
                    """,
                    (file_id,),
                )
            connection.commit()

    def list_failed_index_documents(self, limit: int = 200) -> list[FiledDocument]:
        """Return indexed documents whose extraction failed and can be retried."""

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM files
                WHERE catalog_state = 'active' AND indexed_at IS NOT NULL
                  AND index_state = 'failed'
                ORDER BY id ASC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._file(row) for row in rows]

    def index_summary(self) -> tuple[int, int, int]:
        """Return ``(pending, failed, active)`` document counts for status display."""

        with self.connect() as connection:
            pending = int(
                connection.execute(
                    "SELECT COUNT(*) FROM files "
                    "WHERE catalog_state = 'active' AND indexed_at IS NULL"
                ).fetchone()[0]
            )
            failed = int(
                connection.execute(
                    "SELECT COUNT(*) FROM files "
                    "WHERE catalog_state = 'active' AND index_state = 'failed'"
                ).fetchone()[0]
            )
            active = int(
                connection.execute(
                    "SELECT COUNT(*) FROM files WHERE catalog_state = 'active'"
                ).fetchone()[0]
            )
        return pending, failed, active

    def refresh_file_size(
        self,
        file_id: int,
        size: int,
        *,
        expected_path: Path | None = None,
        expected_record_token: str | None = None,
        mtime_ns: int | None = None,
    ) -> None:
        """Record a new on-disk size and requeue the document for indexing."""

        assignment = "size = ?, indexed_at = NULL"
        values: list[object] = [size]
        if mtime_ns is not None:
            assignment += ", mtime_ns = ?"
            values.append(mtime_ns)
        with self.connect() as connection:
            if expected_path is not None:
                token_clause = " AND record_token = ?" if expected_record_token is not None else ""
                values += [file_id, str(expected_path)]
                if expected_record_token is not None:
                    values.append(expected_record_token)
                connection.execute(
                    f"""
                    UPDATE files SET {assignment}
                    WHERE id = ? AND current_path = ?{token_clause}
                      AND catalog_state = 'active'
                    """,
                    tuple(values),
                )
            else:
                values.append(file_id)
                connection.execute(
                    f"""
                    UPDATE files SET {assignment}
                    WHERE id = ? AND catalog_state = 'active'
                    """,
                    tuple(values),
                )
            connection.commit()

    def reset_stale_index_fingerprints(self) -> int:
        """Requeue indexed documents whose file changed since extraction.

        Startup calls this before the indexer refill pass so edited documents
        are reconsidered instead of serving stale search text forever.
        """

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, current_path, size, mtime_ns FROM files
                WHERE catalog_state = 'active' AND indexed_at IS NOT NULL
                """
            ).fetchall()
        reset = 0
        for row in rows:
            file_id = int(row["id"])
            path = Path(str(row["current_path"]))
            try:
                details = path.stat()
            except OSError:
                continue  # missing files belong to reconciliation, not here
            if int(details.st_size) == int(row["size"]) and int(details.st_mtime_ns) == int(
                row["mtime_ns"]
            ):
                continue
            with self.connect() as connection:
                connection.execute(
                    """
                    UPDATE files
                    SET size = ?, mtime_ns = ?, indexed_at = NULL,
                        index_state = '', index_error = ''
                    WHERE id = ? AND catalog_state = 'active'
                    """,
                    (int(details.st_size), int(details.st_mtime_ns), file_id),
                )
                connection.commit()
            reset += 1
        return reset

    def search(
        self,
        text: str,
        limit: int = 40,
        *,
        subject_id: int | None = None,
        kind: str | None = None,
    ) -> list[SearchResult]:
        """Search indexed pages using safe prefix terms, optionally filtered."""

        query = self._fts_query(text)
        if not query:
            return []
        conditions = ["document_pages MATCH ?", "f.catalog_state = 'active'"]
        parameters: list[object] = [query]
        if subject_id is not None:
            conditions.append("f.subject_id = ?")
            parameters.append(subject_id)
        if kind is not None:
            conditions.append("f.kind = ?")
            parameters.append(kind)
        parameters.append(limit)
        try:
            with self.connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT
                        f.id AS file_id,
                        f.current_path AS path,
                        s.name AS subject_name,
                        f.kind AS kind,
                        CAST(dp.page AS INTEGER) AS page,
                        snippet(document_pages, 4, '[', ']', ' … ', 20) AS excerpt
                    FROM document_pages AS dp
                    JOIN files AS f ON f.id = CAST(dp.file_id AS INTEGER)
                    JOIN subjects AS s ON s.id = f.subject_id
                    WHERE {" AND ".join(conditions)}
                    ORDER BY bm25(document_pages), f.filed_at DESC
                    LIMIT ?
                    """,
                    tuple(parameters),
                ).fetchall()
        except sqlite3.OperationalError:
            LOGGER.exception("FTS search failed for query %r", text)
            return []
        return [
            SearchResult(
                file_id=int(row["file_id"]),
                path=Path(str(row["path"])),
                title=Path(str(row["path"])).name,
                subject_name=str(row["subject_name"]),
                kind=str(row["kind"]),
                page=int(row["page"]),
                snippet=str(row["excerpt"]),
            )
            for row in rows
        ]

    def browse_documents(
        self,
        limit: int = 40,
        *,
        subject_id: int | None = None,
        kind: str | None = None,
    ) -> list[SearchResult]:
        """List recent documents by filter, without requiring search text."""

        conditions = ["f.catalog_state = 'active'"]
        parameters: list[object] = []
        if subject_id is not None:
            conditions.append("f.subject_id = ?")
            parameters.append(subject_id)
        if kind is not None:
            conditions.append("f.kind = ?")
            parameters.append(kind)
        parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    f.id AS file_id,
                    f.current_path AS path,
                    s.name AS subject_name,
                    f.kind AS kind
                FROM files AS f
                JOIN subjects AS s ON s.id = f.subject_id
                WHERE {" AND ".join(conditions)}
                ORDER BY f.filed_at DESC, f.id DESC
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
        return [
            SearchResult(
                file_id=int(row["file_id"]),
                path=Path(str(row["path"])),
                title=Path(str(row["path"])).name,
                subject_name=str(row["subject_name"]),
                kind=str(row["kind"]),
                page=0,
                snippet="",
            )
            for row in rows
        ]

    def add_task(
        self,
        title: str,
        subject_id: int | None,
        due_date: date | None,
        file_id: int | None = None,
        reminder_lead_days: int | None = None,
    ) -> StudyTask:
        """Create a study task."""

        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks(
                    title, subject_id, file_id, due_date, reminder_lead_days, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    title.strip(),
                    subject_id,
                    file_id,
                    due_date.isoformat() if due_date else None,
                    reminder_lead_days,
                    _now(),
                ),
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("A base de dados não devolveu o id da tarefa.")
            task_id = cursor.lastrowid
        task = self.get_task(task_id)
        if task is None:  # pragma: no cover - defensive database invariant
            raise RuntimeError("A tarefa foi criada mas não pôde ser lida.")
        return task

    def get_task(self, task_id: int) -> StudyTask | None:
        """Return a task by id."""

        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT t.*, COALESCE(s.name, '') AS subject_name
                FROM tasks AS t
                LEFT JOIN subjects AS s ON s.id = t.subject_id
                WHERE t.id = ?
                """,
                (task_id,),
            ).fetchone()
        return self._task(row) if row else None

    def list_tasks(self, *, include_completed: bool = True) -> list[StudyTask]:
        """List tasks with incomplete work first and nearest deadlines next."""

        where = "" if include_completed else "WHERE t.completed = 0"
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT t.*, COALESCE(s.name, '') AS subject_name
                FROM tasks AS t
                LEFT JOIN subjects AS s ON s.id = t.subject_id
                {where}
                ORDER BY t.completed, t.due_date IS NULL, t.due_date, t.created_at DESC
                """
            ).fetchall()
        return [self._task(row) for row in rows]

    def set_task_completed(self, task_id: int, completed: bool) -> None:
        """Mark a task complete or reopen it."""

        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET completed = ? WHERE id = ?", (int(completed), task_id)
            )
            connection.commit()

    def update_task(
        self,
        task_id: int,
        title: str,
        subject_id: int | None,
        due_date: date | None,
        reminder_lead_days: int | None = None,
    ) -> StudyTask:
        """Update a task's editable fields without touching its document link."""

        cleaned_title = title.strip()
        if not cleaned_title:
            raise ValueError("O título da tarefa não pode estar vazio.")
        new_due = due_date.isoformat() if due_date else None
        with self.connect() as connection:
            current = connection.execute(
                "SELECT due_date FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if current is None:
                raise LookupError(f"Tarefa inexistente: {task_id}")
            previous_due = str(current["due_date"]) if current["due_date"] is not None else None
            connection.execute(
                """
                UPDATE tasks
                SET title = ?, subject_id = ?, due_date = ?, reminder_lead_days = ?,
                    last_notified_on = CASE WHEN ? = 1 THEN NULL ELSE last_notified_on END
                WHERE id = ?
                """,
                (
                    cleaned_title,
                    subject_id,
                    new_due,
                    reminder_lead_days,
                    int(previous_due != new_due),
                    task_id,
                ),
            )
            connection.commit()
        task = self.get_task(task_id)
        if task is None:  # pragma: no cover - defensive database invariant
            raise LookupError(f"Tarefa inexistente: {task_id}")
        return task

    def mark_task_notified(self, task_id: int, on: date) -> None:
        """Record that a reminder was shown for a task on this calendar day."""

        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET last_notified_on = ? WHERE id = ?", (on.isoformat(), task_id)
            )
            connection.commit()

    def delete_task(self, task_id: int) -> None:
        """Delete a task explicitly selected by the user."""

        with self.connect() as connection:
            connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            connection.commit()

    @staticmethod
    def _fts_query(text: str) -> str:
        terms = [part.replace('"', '""') for part in text.split() if part.strip()]
        return " AND ".join(f'"{term}"*' for term in terms)

    @staticmethod
    def _subject(row: sqlite3.Row) -> Subject:
        return Subject(
            id=int(row["id"]),
            name=str(row["name"]),
            code=str(row["code"]),
            color=str(row["color"]),
            keywords=tuple(json.loads(str(row["keywords_json"]))),
            folder_name=str(row["folder_name"]),
            active=bool(row["active"]),
        )

    @staticmethod
    def _inbox(row: sqlite3.Row) -> InboxItem:
        return InboxItem(
            id=int(row["id"]),
            path=Path(str(row["path"])),
            original_path=Path(str(row["original_path"])),
            original_name=str(row["original_name"]),
            size=int(row["size"]),
            detected_at=datetime.fromisoformat(str(row["detected_at"])),
            status=str(row["status"]),
            suggested_subject_id=(
                int(row["suggested_subject_id"])
                if row["suggested_subject_id"] is not None
                else None
            ),
            suggested_kind=str(row["suggested_kind"]),
            last_error=str(row["last_error"]),
            content_sha256=str(row["content_sha256"]),
            hash_fingerprint=str(row["hash_fingerprint"]),
        )

    @staticmethod
    def _file(row: sqlite3.Row) -> FiledDocument:
        return FiledDocument(
            id=int(row["id"]),
            subject_id=int(row["subject_id"]),
            kind=str(row["kind"]),
            original_name=str(row["original_name"]),
            current_path=Path(str(row["current_path"])),
            original_path=Path(str(row["original_path"])),
            size=int(row["size"]),
            filed_at=datetime.fromisoformat(str(row["filed_at"])),
            indexed_at=_parse_datetime(
                str(row["indexed_at"]) if row["indexed_at"] is not None else None
            ),
            origin=str(row["origin"]),
            record_token=str(row["record_token"]),
            catalog_state=str(row["catalog_state"]),
            index_state=str(row["index_state"]),
            index_error=str(row["index_error"]),
            content_sha256=str(row["content_sha256"]),
            hash_fingerprint=str(row["hash_fingerprint"]),
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> HistoryEvent:
        return HistoryEvent(
            id=int(row["id"]),
            action=str(row["action"]),
            source_path=Path(str(row["source_path"])),
            destination_path=Path(str(row["destination_path"])),
            file_id=int(row["file_id"]) if row["file_id"] is not None else None,
            inbox_id=int(row["inbox_id"]) if row["inbox_id"] is not None else None,
            subject_id=(int(row["subject_id"]) if row["subject_id"] is not None else None),
            kind=str(row["kind"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            undone_at=_parse_datetime(
                str(row["undone_at"]) if row["undone_at"] is not None else None
            ),
            related_event_id=(
                int(row["related_event_id"]) if row["related_event_id"] is not None else None
            ),
        )

    @staticmethod
    def _task(row: sqlite3.Row) -> StudyTask:
        due = str(row["due_date"]) if row["due_date"] is not None else None
        notified = str(row["last_notified_on"]) if row["last_notified_on"] is not None else None
        return StudyTask(
            id=int(row["id"]),
            title=str(row["title"]),
            subject_id=int(row["subject_id"]) if row["subject_id"] is not None else None,
            subject_name=str(row["subject_name"]),
            file_id=int(row["file_id"]) if row["file_id"] is not None else None,
            due_date=date.fromisoformat(due) if due else None,
            completed=bool(row["completed"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            reminder_lead_days=(
                int(row["reminder_lead_days"]) if row["reminder_lead_days"] is not None else None
            ),
            last_notified_on=date.fromisoformat(notified) if notified else None,
        )
