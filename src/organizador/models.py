"""Domain models shared by the application layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from stat import S_ISREG

FILE_KINDS: tuple[str, ...] = (
    "Slides",
    "Exercícios",
    "Testes",
    "Trabalhos",
    "Outros",
)


@dataclass(frozen=True, slots=True)
class Subject:
    """A university subject and its filing rules."""

    id: int
    name: str
    code: str
    color: str
    keywords: tuple[str, ...]
    folder_name: str
    active: bool = True


@dataclass(frozen=True, slots=True)
class InboxItem:
    """A downloaded file waiting for a filing decision."""

    id: int
    path: Path
    original_path: Path
    original_name: str
    size: int
    detected_at: datetime
    status: str
    suggested_subject_id: int | None
    suggested_kind: str
    last_error: str
    content_sha256: str = ""
    hash_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class FiledDocument:
    """A document filed into a subject folder."""

    id: int
    subject_id: int
    kind: str
    original_name: str
    current_path: Path
    original_path: Path
    size: int
    filed_at: datetime
    indexed_at: datetime | None
    origin: str = "filed"
    record_token: str = ""
    catalog_state: str = "active"
    index_state: str = ""
    index_error: str = ""
    content_sha256: str = ""
    hash_fingerprint: str = ""


class FindingReason(StrEnum):
    """Stable persistence keys for findings that require a human decision."""

    UNTRACKED_SUBJECT_FILE = "untracked_subject_file"
    PENDING_INGEST_SOURCE = "pending_ingest_source"
    PENDING_INGEST_DESTINATION = "pending_ingest_destination"
    PENDING_VERSION_SOURCE = "pending_version_source"
    PENDING_VERSION_DESTINATION = "pending_version_destination"
    PENDING_MOVE_SOURCE = "pending_move_source"
    PENDING_MOVE_DESTINATION = "pending_move_destination"
    MISSING_DOCUMENT = "missing_document"
    BROKEN_UNDO_EVENT = "broken_undo_event"
    PENDING_FILING_SOURCE = "pending_filing_source"
    PENDING_FILING_DESTINATION = "pending_filing_destination"
    PENDING_RETURN_SOURCE = "pending_return_source"
    PENDING_RETURN_DESTINATION = "pending_return_destination"
    PENDING_UNDO_SOURCE = "pending_undo_source"
    PENDING_UNDO_DESTINATION = "pending_undo_destination"
    LEGACY_INTERRUPTED_UNDO = "legacy_interrupted_undo"
    UNSAFE_PATH = "unsafe_path"
    SUBJECT_FOLDER_COLLISION = "subject_folder_collision"


@dataclass(frozen=True, slots=True)
class ReconciliationFinding:
    """One independently reviewable path/reason pair from a consistency scan."""

    path: Path
    reason: FindingReason
    reference_id: int | None = None
    candidate: ExistingDownload | None = None
    document: FiledDocument | None = None


@dataclass(frozen=True, slots=True)
class HistoryEvent:
    """A reversible file-system event."""

    id: int
    action: str
    source_path: Path
    destination_path: Path
    file_id: int | None
    inbox_id: int | None
    subject_id: int | None
    kind: str
    created_at: datetime
    undone_at: datetime | None
    related_event_id: int | None = None


@dataclass(frozen=True, slots=True)
class StudyTask:
    """A subject-linked task or deadline."""

    id: int
    title: str
    subject_id: int | None
    subject_name: str
    file_id: int | None
    due_date: date | None
    completed: bool
    created_at: datetime
    reminder_lead_days: int | None = None
    last_notified_on: date | None = None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A page, slide or worksheet-level local search result."""

    file_id: int
    path: Path
    title: str
    subject_name: str
    kind: str
    page: int
    snippet: str


@dataclass(frozen=True, slots=True)
class FilingHint:
    """A confirmed filing choice available to the local classifier."""

    original_name: str
    subject_id: int
    kind: str


@dataclass(frozen=True, slots=True)
class ActivitySummary:
    """Lifetime counts shown on the home page as reassurance."""

    organized: int
    adopted: int
    returned: int
    undone: int
    collisions_renamed: int
    operations_recovered: int


@dataclass(frozen=True, slots=True)
class ExistingDownload:
    """A top-level Downloads file captured before manual import confirmation."""

    path: Path
    size: int
    modified_ns: int
    device: int
    inode: int

    @classmethod
    def capture(cls, path: Path) -> ExistingDownload | None:
        """Capture a regular non-link file without following filesystem links."""

        try:
            return cls.capture_strict(path)
        except OSError:
            return None

    @classmethod
    def capture_strict(cls, path: Path) -> ExistingDownload | None:
        """Capture a file while preserving indeterminate filesystem errors."""

        candidate = path.absolute()
        try:
            details = candidate.lstat()
        except FileNotFoundError:
            return None
        if not S_ISREG(details.st_mode):
            return None
        return cls(
            candidate,
            details.st_size,
            details.st_mtime_ns,
            details.st_dev,
            details.st_ino,
        )

    def still_matches(self) -> bool:
        """Return whether the same unchanged regular file is still present."""

        return ExistingDownload.capture(self.path) == self


@dataclass(frozen=True, slots=True)
class ExistingDownloadsPlan:
    """A read-only, capped plan awaiting explicit user confirmation."""

    total: int
    selected: tuple[ExistingDownload, ...]


@dataclass(frozen=True, slots=True)
class InterruptedUndo:
    """A legacy undo move completed on disk but not in persistence."""

    event: HistoryEvent
    restored_file: ExistingDownload


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Read-only filesystem and database consistency findings."""

    inbox_orphans: tuple[ExistingDownload, ...]
    interrupted_filings: tuple[InboxItem, ...]
    missing_inbox_items: tuple[InboxItem, ...]
    untracked_subject_files: tuple[Path, ...]
    missing_documents: tuple[FiledDocument, ...]
    broken_undo_events: tuple[HistoryEvent, ...]
    pending_filing_events: tuple[HistoryEvent, ...]
    pending_return_events: tuple[HistoryEvent, ...]
    pending_undo_events: tuple[HistoryEvent, ...]
    legacy_interrupted_undos: tuple[InterruptedUndo, ...]
    unsafe_paths: tuple[Path, ...]
    untracked_subject_candidates: tuple[ExistingDownload, ...] = ()
    subject_folder_collisions: tuple[ReconciliationFinding, ...] = ()
    truncated: bool = False
    incomplete: bool = False
    pending_ingest_events: tuple[HistoryEvent, ...] = ()
    pending_version_events: tuple[HistoryEvent, ...] = ()
    pending_move_events: tuple[HistoryEvent, ...] = ()

    @property
    def finding_count(self) -> int:
        """Return the number of findings before database-only recovery."""

        return (
            len(self.inbox_orphans)
            + len(self.interrupted_filings)
            + len(self.missing_inbox_items)
            + len(self.untracked_subject_files)
            + len(self.missing_documents)
            + len(self.broken_undo_events)
            + len(self.pending_filing_events)
            + len(self.pending_return_events)
            + len(self.pending_undo_events)
            + len(self.legacy_interrupted_undos)
            + len(self.unsafe_paths)
            + len(self.subject_folder_collisions)
            + len(self.pending_ingest_events)
            + len(self.pending_version_events)
            + len(self.pending_move_events)
        )


@dataclass(frozen=True, slots=True)
class ReconciliationOutcome:
    """Database changes made from a reconciliation report."""

    recovered_items: tuple[InboxItem, ...]
    reset_filing_ids: tuple[int, ...]
    recovery_required_ids: tuple[int, ...]
    completed_undo_event_ids: tuple[int, ...]
    cancelled_undo_event_ids: tuple[int, ...]
    completed_operation_event_ids: tuple[int, ...]
    cancelled_operation_event_ids: tuple[int, ...]

    @property
    def change_count(self) -> int:
        """Return the number of database records recovered or repaired."""

        return (
            len(self.recovered_items)
            + len(self.reset_filing_ids)
            + len(self.recovery_required_ids)
            + len(self.cancelled_undo_event_ids)
            + len(self.completed_operation_event_ids)
            + len(self.cancelled_operation_event_ids)
        )


@dataclass(frozen=True, slots=True)
class FilingGuess:
    """The classifier's best subject and file-kind proposal."""

    subject_id: int | None
    kind: str
    confidence: int
