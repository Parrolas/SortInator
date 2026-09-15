"""Crash-safe backup coordination for migrations and user snapshots."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import shutil
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from uuid import uuid4

from organizador.db import (
    SCHEMA_VERSION,
    Database,
    DatabaseHealthError,
    NewerDatabaseError,
)

LOGGER = logging.getLogger(__name__)

BUNDLE_FORMAT_VERSION = 1
DATABASE_BACKUP_NAME = "database.sqlite3"
SETTINGS_BACKUP_NAME = "settings.bin"
SETTINGS_ABSENT_NAME = "settings.absent"
MANIFEST_NAME = "manifest.json"
PENDING_MARKER = "pending"
HEALTHY_MARKER = "healthy"
FAILED_MARKER = "failed"
QUARANTINED_MARKER = "quarantined"
USER_MARKER = "user"
PRE_RESTORE_MARKER = "pre_restore"
RESTORE_REQUEST_NAME = "restore-request.json"
RESTORE_REQUEST_FAILED_NAME = "restore-request-failed.json"
REQUEST_FORMAT_VERSION = 1
_PROTECTED_MARKERS = (PENDING_MARKER, FAILED_MARKER, QUARANTINED_MARKER)
_AUTOMATIC_KINDS = ("migration", "pre_restore")
_MAX_MANIFEST_BYTES = 1024 * 1024


class RecoveryError(RuntimeError):
    """A backup could not be trusted, restored or exported safely."""


@dataclass(frozen=True, slots=True)
class RecoveryBundle:
    """A validated snapshot and its on-disk state directory."""

    path: Path
    created_at: datetime
    database_user_version: int
    settings_present: bool


@dataclass(frozen=True, slots=True)
class BundleInfo:
    """Lightweight inventory entry that never re-hashes the database."""

    path: Path
    created_at: datetime
    database_user_version: int
    settings_present: bool
    kind: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class RestoreOutcome:
    """A staged restore that was applied at startup."""

    restored_from: datetime
    bundle_path: Path


@dataclass(frozen=True, slots=True)
class _Manifest:
    created_at: datetime
    user_version: int
    settings_present: bool
    database_entry: dict[Any, Any]
    settings_entry: dict[Any, Any]


@dataclass(frozen=True, slots=True)
class _ValidatedBundle:
    bundle: RecoveryBundle
    database_path: Path
    database_sha256: str
    settings_path: Path
    settings_sha256: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RecoveryCoordinator:
    """Create, publish, restore, and retain migration recovery bundles."""

    def __init__(
        self,
        data_dir: Path,
        *,
        database_name: str = "organizador.db",
        settings_name: str = "settings.json",
    ) -> None:
        self.data_dir = data_dir
        self.database_path = data_dir / database_name
        self.settings_path = data_dir / settings_name
        self.backups_dir = data_dir / "backups"

    def prepare_migration(self) -> RecoveryBundle | None:
        """Publish a validated pending backup only when migration is required."""

        database = Database(self.database_path)
        if self.database_path.is_symlink():
            raise RecoveryError("The database path must not be a symbolic link.")
        if not self.database_path.is_file():
            return None
        database.validate_health().require_healthy()
        inspection = database.inspect_schema()
        if inspection.user_version is not None and inspection.user_version > SCHEMA_VERSION:
            raise NewerDatabaseError(
                f"A base de dados pertence a uma versão mais recente ({inspection.user_version})."
            )
        if not inspection.requires_migration:
            return None
        if self._pending_bundle_paths():
            raise RecoveryError("A pending migration backup already exists.")
        if self.settings_path.is_symlink():
            raise RecoveryError("The settings path must not be a symbolic link.")
        if self.settings_path.exists() and not self.settings_path.is_file():
            raise RecoveryError("The settings path is not a regular file.")

        self.backups_dir.mkdir(parents=True, exist_ok=True)
        created_at = _utc_now()
        bundle_path = self.backups_dir / (f"migration-{created_at:%Y%m%dT%H%M%S%fZ}-{uuid4().hex}")
        bundle_path.mkdir()
        try:
            database_backup = bundle_path / DATABASE_BACKUP_NAME
            database.backup_to(database_backup)
            settings_present = self.settings_path.is_file()
            settings_backup = bundle_path / (
                SETTINGS_BACKUP_NAME if settings_present else SETTINGS_ABSENT_NAME
            )
            settings_bytes = self.settings_path.read_bytes() if settings_present else b""
            _write_atomic(settings_backup, settings_bytes)
            manifest = {
                "format_version": BUNDLE_FORMAT_VERSION,
                "created_at": created_at.isoformat(),
                "schema": {
                    "user_version": inspection.user_version,
                    "missing_additions": list(inspection.missing_additions),
                },
                "files": {
                    "database": {
                        "path": DATABASE_BACKUP_NAME,
                        "sha256": _sha256_file(database_backup),
                    },
                    "settings": {
                        "path": settings_backup.name,
                        "sha256": _sha256_bytes(settings_bytes),
                        "present": settings_present,
                    },
                },
            }
            manifest_bytes = (
                json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            _write_atomic(bundle_path / MANIFEST_NAME, manifest_bytes)
            validated = self._validate_bundle(bundle_path)
            self._publish_pending(bundle_path)
            return validated.bundle
        except BaseException:
            if bundle_path.exists() and not (bundle_path / PENDING_MARKER).exists():
                with suppress(OSError):
                    _write_atomic(bundle_path / FAILED_MARKER, b"")
            raise

    def create_snapshot(self, marker: str = USER_MARKER) -> RecoveryBundle:
        """Publish a validated on-demand snapshot of the current data.

        ``marker`` names the bundle kind (``user`` or ``pre_restore``); the
        marker file makes the bundle visible to retention and deletion rules.
        """

        marker = marker.strip()
        if not marker or not marker.replace("_", "").isalnum() or not marker.isascii():
            raise RecoveryError("The snapshot marker is invalid.")
        if self.database_path.is_symlink():
            raise RecoveryError("The database path must not be a symbolic link.")
        if not self.database_path.is_file():
            raise RecoveryError("There is no database to back up.")
        database = Database(self.database_path)
        database.validate_health().require_healthy()
        inspection = database.inspect_schema()
        if inspection.user_version is not None and inspection.user_version > SCHEMA_VERSION:
            raise NewerDatabaseError(
                f"A base de dados pertence a uma versão mais recente ({inspection.user_version})."
            )
        if self.settings_path.is_symlink():
            raise RecoveryError("The settings path must not be a symbolic link.")
        if self.settings_path.exists() and not self.settings_path.is_file():
            raise RecoveryError("The settings path is not a regular file.")

        self.backups_dir.mkdir(parents=True, exist_ok=True)
        created_at = _utc_now()
        bundle_path = self.backups_dir / f"{marker}-{created_at:%Y%m%dT%H%M%S%fZ}-{uuid4().hex}"
        bundle_path.mkdir()
        try:
            database_backup = bundle_path / DATABASE_BACKUP_NAME
            database.backup_to(database_backup)
            settings_present = self.settings_path.is_file()
            settings_backup = bundle_path / (
                SETTINGS_BACKUP_NAME if settings_present else SETTINGS_ABSENT_NAME
            )
            settings_bytes = self.settings_path.read_bytes() if settings_present else b""
            _write_atomic(settings_backup, settings_bytes)
            manifest = {
                "format_version": BUNDLE_FORMAT_VERSION,
                "created_at": created_at.isoformat(),
                "schema": {
                    "user_version": inspection.user_version,
                    "missing_additions": list(inspection.missing_additions),
                },
                "files": {
                    "database": {
                        "path": DATABASE_BACKUP_NAME,
                        "sha256": _sha256_file(database_backup),
                    },
                    "settings": {
                        "path": settings_backup.name,
                        "sha256": _sha256_bytes(settings_bytes),
                        "present": settings_present,
                    },
                },
            }
            manifest_bytes = (
                json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            _write_atomic(bundle_path / MANIFEST_NAME, manifest_bytes)
            validated = self._validate_bundle(bundle_path)
            _write_atomic(bundle_path / marker, b"")
            return validated.bundle
        except BaseException:
            if bundle_path.exists() and not any(
                (bundle_path / state).exists() for state in (USER_MARKER, PRE_RESTORE_MARKER)
            ):
                with suppress(OSError):
                    _write_atomic(bundle_path / FAILED_MARKER, b"")
            raise

    def restore_pending(self) -> RecoveryBundle | None:
        """Restore the sole migration that never reached its health point."""

        pending = self._pending_bundle_paths()
        if not pending:
            return None
        if len(pending) != 1:
            raise RecoveryError("Multiple pending migration backups require manual review.")
        bundle_path = pending[0]
        conflicting_states = (HEALTHY_MARKER, FAILED_MARKER, QUARANTINED_MARKER)
        if any(
            (bundle_path / state).exists() or (bundle_path / state).is_symlink()
            for state in conflicting_states
        ):
            raise RecoveryError("A pending migration backup has conflicting state markers.")
        try:
            validated = self._validate_bundle(bundle_path)
        except (DatabaseHealthError, OSError, RecoveryError, ValueError) as exc:
            self._transition(bundle_path, PENDING_MARKER, QUARANTINED_MARKER)
            raise RecoveryError(f"The pending recovery bundle is not trustworthy: {exc}") from exc

        self._restore_bundle(validated)
        self._transition(bundle_path, PENDING_MARKER, FAILED_MARKER)
        return validated.bundle

    def validate_migrated(self, bundle: RecoveryBundle) -> None:
        """Verify the migrated data without closing the restoration window."""

        bundle_path = self._owned_bundle_path(bundle.path)
        pending = bundle_path / PENDING_MARKER
        healthy = bundle_path / HEALTHY_MARKER
        if healthy.is_file() and not (pending.exists() or pending.is_symlink()):
            return
        if not pending.is_file() or pending.is_symlink():
            raise RecoveryError("The migration backup is no longer pending.")
        try:
            self._validate_bundle(bundle_path)
        except (DatabaseHealthError, OSError, RecoveryError, ValueError) as exc:
            self._transition(bundle_path, PENDING_MARKER, QUARANTINED_MARKER)
            raise RecoveryError(f"The migration backup is not trustworthy: {exc}") from exc

        Database(self.database_path).validate_health().require_healthy()
        inspection = Database(self.database_path).inspect_schema()
        if not inspection.is_current:
            raise RecoveryError("The migrated database has not reached the current healthy schema.")

    def mark_healthy(self, bundle: RecoveryBundle) -> None:
        """Atomically prevent restoration after the application health point."""

        bundle_path = self._owned_bundle_path(bundle.path)
        pending = bundle_path / PENDING_MARKER
        healthy = bundle_path / HEALTHY_MARKER
        if healthy.is_file() and not (pending.exists() or pending.is_symlink()):
            return
        self.validate_migrated(bundle)
        self._transition(bundle_path, PENDING_MARKER, HEALTHY_MARKER)

    def prune_automatic_backups(self) -> tuple[Path, ...]:
        """Keep the newest two automatic bundles per kind, never beyond 30 days.

        User snapshots and protected recovery states are never pruned.
        """

        if not self.backups_dir.is_dir():
            return ()
        cutoff = _utc_now() - timedelta(days=30)
        buckets: dict[str, list[tuple[datetime, Path]]] = {kind: [] for kind in _AUTOMATIC_KINDS}
        for path in self.backups_dir.iterdir():
            if not path.is_dir() or path.is_symlink():
                continue
            kind = self._bundle_kind(path)
            if kind not in buckets:
                continue
            if any(
                (path / marker).exists() or (path / marker).is_symlink()
                for marker in _PROTECTED_MARKERS
            ):
                continue
            try:
                manifest = self._decode_manifest(path)
            except (OSError, RecoveryError, ValueError):
                continue
            buckets[kind].append((manifest.created_at, path))

        removed: list[Path] = []
        for entries in buckets.values():
            entries.sort(key=lambda item: (item[0], item[1].name), reverse=True)
            for index, (created_at, path) in enumerate(entries):
                if index < 2 and created_at >= cutoff:
                    continue
                shutil.rmtree(path)
                removed.append(path)
        return tuple(removed)

    def list_bundles(self) -> tuple[BundleInfo, ...]:
        """Return a lightweight inventory, newest first, without re-hashing."""

        if not self.backups_dir.is_dir():
            return ()
        found: list[BundleInfo] = []
        for path in self.backups_dir.iterdir():
            if not path.is_dir() or path.is_symlink():
                continue
            manifest_path = path / MANIFEST_NAME
            if not manifest_path.is_file() or manifest_path.is_symlink():
                continue
            try:
                manifest = self._decode_manifest(path)
                size_bytes = (path / DATABASE_BACKUP_NAME).stat().st_size
            except (OSError, RecoveryError, ValueError):
                continue
            found.append(
                BundleInfo(
                    path=path,
                    created_at=manifest.created_at,
                    database_user_version=manifest.user_version,
                    settings_present=manifest.settings_present,
                    kind=self._bundle_kind(path),
                    size_bytes=size_bytes,
                )
            )
        found.sort(key=lambda item: (item.created_at, item.path.name), reverse=True)
        return tuple(found)

    def validate_bundle(self, bundle_path: Path) -> RecoveryBundle:
        """Fully validate a bundle, including every hash and the database health."""

        return self._validate_bundle(bundle_path).bundle

    def restore_bundle(self, bundle_path: Path) -> RecoveryBundle:
        """Replace the live data with a fully validated bundle."""

        validated = self._validate_bundle(bundle_path)
        self._restore_bundle(validated)
        return validated.bundle

    def delete_bundle(self, bundle_path: Path) -> None:
        """Delete one user snapshot; automatic and protected bundles stay."""

        path = self._owned_bundle_path(bundle_path)
        if self._bundle_kind(path) != USER_MARKER:
            raise RecoveryError("Only user backups can be deleted.")
        shutil.rmtree(path)

    def export_bundle_zip(self, bundle_path: Path, destination: Path) -> Path:
        """Write a portable archive of a validated bundle, returning its path."""

        validated = self._validate_bundle(bundle_path)
        archive = destination
        if archive.suffix.casefold() != ".zip":
            stamp = f"{validated.bundle.created_at:%Y-%m-%d-%H%M%S}"
            archive = destination / f"Organizador-backup-{stamp}.zip"
        if archive.is_symlink():
            raise RecoveryError("The export destination must not be a symbolic link.")
        archive.parent.mkdir(parents=True, exist_ok=True)
        temporary = archive.parent / f".{archive.name}-{uuid4().hex}.tmp"
        settings_name = (
            SETTINGS_BACKUP_NAME if validated.bundle.settings_present else SETTINGS_ABSENT_NAME
        )
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive_file:
                archive_file.write(validated.bundle.path / MANIFEST_NAME, MANIFEST_NAME)
                archive_file.write(validated.database_path, DATABASE_BACKUP_NAME)
                archive_file.write(validated.settings_path, settings_name)
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
        return archive

    def import_bundle_zip(self, zip_path: Path) -> RecoveryBundle:
        """Stage a portable archive as a validated user snapshot."""

        archive = zip_path
        if archive.is_symlink() or not archive.is_file():
            raise RecoveryError("The backup archive is missing or unsafe.")
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        staging = self.backups_dir / f"import-{uuid4().hex}"
        staging.mkdir()
        try:
            with zipfile.ZipFile(archive) as archive_file:
                try:
                    manifest_bytes = _read_zip_member(
                        archive_file, MANIFEST_NAME, limit=_MAX_MANIFEST_BYTES
                    )
                except (KeyError, zipfile.BadZipFile) as exc:
                    raise RecoveryError("The backup archive is not a valid bundle.") from exc
                _write_atomic(staging / MANIFEST_NAME, manifest_bytes)
                manifest = self._decode_manifest(staging)
                settings_name = (
                    SETTINGS_BACKUP_NAME if manifest.settings_present else SETTINGS_ABSENT_NAME
                )
                expected = {MANIFEST_NAME, DATABASE_BACKUP_NAME, settings_name}
                if set(archive_file.namelist()) != expected:
                    raise RecoveryError("The backup archive has unexpected contents.")
                _copy_zip_member(archive_file, DATABASE_BACKUP_NAME, staging / DATABASE_BACKUP_NAME)
                _copy_zip_member(archive_file, settings_name, staging / settings_name)
            validated = self._validate_bundle(staging)
        except BaseException as exc:
            shutil.rmtree(staging, ignore_errors=True)
            if isinstance(exc, zipfile.BadZipFile):
                raise RecoveryError("The backup archive is not a valid bundle.") from exc
            raise
        stamp = f"{validated.bundle.created_at:%Y%m%dT%H%M%S%fZ}"
        final = self.backups_dir / f"{USER_MARKER}-{stamp}-{uuid4().hex}"
        staging.replace(final)
        _write_atomic(final / USER_MARKER, b"")
        return RecoveryBundle(
            path=final,
            created_at=validated.bundle.created_at,
            database_user_version=validated.bundle.database_user_version,
            settings_present=validated.bundle.settings_present,
        )

    def has_restore_request(self) -> bool:
        """Return whether a staged restore is waiting for the next launch."""

        request_path = self.data_dir / RESTORE_REQUEST_NAME
        return request_path.is_file() and not request_path.is_symlink()

    def request_restore(self, bundle_path: Path) -> Path:
        """Stage a validated bundle for restoration on the next launch."""

        validated = self._validate_bundle(bundle_path)
        payload = {
            "format_version": REQUEST_FORMAT_VERSION,
            "created_at": _utc_now().isoformat(),
            "bundle": str(validated.bundle.path),
            "bundle_created_at": validated.bundle.created_at.isoformat(),
            "manifest_sha256": _sha256_file(validated.bundle.path / MANIFEST_NAME),
        }
        request_path = self.data_dir / RESTORE_REQUEST_NAME
        _write_atomic(
            request_path,
            (json.dumps(payload, ensure_ascii=True, indent=2) + "\n").encode("utf-8"),
        )
        return request_path

    def consume_restore_request(self) -> RestoreOutcome | None:
        """Apply a staged restore before the application opens its data."""

        request_path = self.data_dir / RESTORE_REQUEST_NAME
        if not request_path.is_file() or request_path.is_symlink():
            return None
        try:
            payload = self._decode_restore_request(request_path)
            bundle_path = Path(str(payload["bundle"]))
            validated = self._validate_bundle(bundle_path)
            expected = str(payload["manifest_sha256"]).casefold()
            actual = _sha256_file(validated.bundle.path / MANIFEST_NAME)
            if not hmac.compare_digest(actual, expected):
                raise RecoveryError("The requested backup changed since the request.")
            self._snapshot_before_restore()
            self._restore_bundle(validated)
        except Exception as exc:
            self._quarantine_restore_request(request_path, exc)
            raise
        request_path.unlink(missing_ok=True)
        return RestoreOutcome(
            restored_from=validated.bundle.created_at,
            bundle_path=validated.bundle.path,
        )

    def _decode_restore_request(self, request_path: Path) -> dict[str, Any]:
        try:
            decoded: Any = json.loads(request_path.read_bytes())
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RecoveryError("The restore request is unreadable.") from exc
        if not isinstance(decoded, dict) or decoded.get("format_version") != REQUEST_FORMAT_VERSION:
            raise RecoveryError("The restore request format is unsupported.")
        bundle = decoded.get("bundle")
        manifest_sha256 = decoded.get("manifest_sha256")
        created_at = decoded.get("created_at")
        if (
            not isinstance(bundle, str)
            or not isinstance(manifest_sha256, str)
            or len(manifest_sha256) != 64
            or not isinstance(created_at, str)
        ):
            raise RecoveryError("The restore request is malformed.")
        return decoded

    def _snapshot_before_restore(self) -> None:
        """Protect the current data unless it is already unusable."""

        try:
            self.create_snapshot(PRE_RESTORE_MARKER)
        except Exception:
            LOGGER.warning("Could not snapshot the current data before restoring", exc_info=True)

    def _quarantine_restore_request(self, request_path: Path, error: Exception) -> None:
        payload = {"failed_at": _utc_now().isoformat(), "error": str(error)}
        with suppress(OSError):
            _write_atomic(
                self.data_dir / RESTORE_REQUEST_FAILED_NAME,
                (json.dumps(payload, ensure_ascii=True, indent=2) + "\n").encode("utf-8"),
            )
        with suppress(OSError):
            request_path.unlink(missing_ok=True)

    @staticmethod
    def _bundle_kind(bundle_path: Path) -> str:
        if (bundle_path / USER_MARKER).is_file():
            return USER_MARKER
        if (bundle_path / PRE_RESTORE_MARKER).is_file():
            return PRE_RESTORE_MARKER
        if (bundle_path / HEALTHY_MARKER).is_file():
            return "migration"
        if (bundle_path / PENDING_MARKER).is_file():
            return "pending"
        if (bundle_path / FAILED_MARKER).is_file():
            return "failed_recovery"
        if (bundle_path / QUARANTINED_MARKER).is_file():
            return "quarantined"
        return "unmarked"

    def _publish_pending(self, bundle_path: Path) -> None:
        _write_atomic(bundle_path / PENDING_MARKER, b"")

    def _pending_bundle_paths(self) -> tuple[Path, ...]:
        if not self.backups_dir.is_dir():
            return ()
        pending: list[Path] = []
        for path in self.backups_dir.iterdir():
            marker = path / PENDING_MARKER
            if (
                path.is_dir()
                and not path.is_symlink()
                and marker.is_file()
                and not marker.is_symlink()
            ):
                pending.append(path)
        return tuple(sorted(pending))

    def _decode_manifest(self, bundle_path: Path) -> _Manifest:
        manifest_path = bundle_path / MANIFEST_NAME
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise RecoveryError("The recovery manifest is missing or unsafe.")
        try:
            decoded: Any = json.loads(manifest_path.read_bytes())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RecoveryError("The recovery manifest is malformed.") from exc
        if not isinstance(decoded, dict) or decoded.get("format_version") != BUNDLE_FORMAT_VERSION:
            raise RecoveryError("The recovery manifest format is unsupported.")

        created_raw = decoded.get("created_at")
        if not isinstance(created_raw, str):
            raise RecoveryError("The recovery manifest has no creation time.")
        try:
            created_at = datetime.fromisoformat(created_raw)
        except ValueError as exc:
            raise RecoveryError("The recovery manifest creation time is invalid.") from exc
        if created_at.tzinfo is None:
            raise RecoveryError("The recovery manifest creation time has no timezone.")
        created_at = created_at.astimezone(UTC)

        schema = decoded.get("schema")
        if not isinstance(schema, dict) or type(schema.get("user_version")) is not int:
            raise RecoveryError("The recovery manifest schema version is invalid.")
        user_version = int(schema["user_version"])
        files = decoded.get("files")
        if not isinstance(files, dict):
            raise RecoveryError("The recovery manifest file list is invalid.")
        database_entry = files.get("database")
        settings_entry = files.get("settings")
        if not isinstance(database_entry, dict) or not isinstance(settings_entry, dict):
            raise RecoveryError("The recovery manifest file entries are invalid.")
        settings_present = settings_entry.get("present")
        if not isinstance(settings_present, bool):
            raise RecoveryError("The settings presence marker is invalid.")
        return _Manifest(
            created_at=created_at,
            user_version=user_version,
            settings_present=settings_present,
            database_entry=database_entry,
            settings_entry=settings_entry,
        )

    def _validate_bundle(self, bundle_path: Path) -> _ValidatedBundle:
        bundle_path = self._owned_bundle_path(bundle_path)
        manifest = self._decode_manifest(bundle_path)
        database_path, database_sha256 = self._manifest_file(
            bundle_path, manifest.database_entry, expected_name=DATABASE_BACKUP_NAME
        )
        expected_settings_name = (
            SETTINGS_BACKUP_NAME if manifest.settings_present else SETTINGS_ABSENT_NAME
        )
        settings_path, settings_sha256 = self._manifest_file(
            bundle_path, manifest.settings_entry, expected_name=expected_settings_name
        )
        if not manifest.settings_present and settings_path.stat().st_size != 0:
            raise RecoveryError("The settings absence marker is not empty.")
        database_sidecars = (Path(f"{database_path}-wal"), Path(f"{database_path}-shm"))
        if any(path.exists() or path.is_symlink() for path in database_sidecars):
            raise RecoveryError("The database backup is not standalone.")
        Database(database_path).validate_health().require_healthy()
        return _ValidatedBundle(
            bundle=RecoveryBundle(
                path=bundle_path,
                created_at=manifest.created_at,
                database_user_version=manifest.user_version,
                settings_present=manifest.settings_present,
            ),
            database_path=database_path,
            database_sha256=database_sha256,
            settings_path=settings_path,
            settings_sha256=settings_sha256,
        )

    def _manifest_file(
        self,
        bundle_path: Path,
        entry: dict[Any, Any],
        *,
        expected_name: str,
    ) -> tuple[Path, str]:
        relative = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise RecoveryError("A recovery manifest file entry is malformed.")
        if relative != expected_name:
            raise RecoveryError("A recovery manifest path is unexpected.")
        candidate = _safe_relative_path(bundle_path, relative)
        if not candidate.is_file() or candidate.is_symlink():
            raise RecoveryError("A recovery bundle file is missing or unsafe.")
        actual = _sha256_file(candidate)
        if len(digest) != 64 or not hmac.compare_digest(actual, digest.casefold()):
            raise RecoveryError(f"Hash mismatch for {relative}.")
        return candidate, digest.casefold()

    def _restore_bundle(self, validated: _ValidatedBundle) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        database_stage = self.data_dir / (f".{self.database_path.name}.restore-{uuid4().hex}.tmp")
        settings_stage = self.data_dir / (f".{self.settings_path.name}.restore-{uuid4().hex}.tmp")
        saved_originals: list[tuple[Path, Path]] = []
        try:
            _copy_durable(validated.database_path, database_stage)
            if _sha256_file(database_stage) != validated.database_sha256:
                raise RecoveryError("The staged database hash does not match its manifest.")
            Database(database_stage).validate_health().require_healthy()
            if validated.bundle.settings_present:
                _copy_durable(validated.settings_path, settings_stage)
                if _sha256_file(settings_stage) != validated.settings_sha256:
                    raise RecoveryError("The staged settings hash does not match its manifest.")
            try:
                originals = (
                    self.settings_path,
                    *self._database_sidecars(),
                    self.database_path,
                )
                for original in originals:
                    if not original.exists() and not original.is_symlink():
                        continue
                    saved = self.data_dir / f".{original.name}.replaced-{uuid4().hex}.tmp"
                    original.replace(saved)
                    saved_originals.append((original, saved))
                database_stage.replace(self.database_path)
                if validated.bundle.settings_present:
                    settings_stage.replace(self.settings_path)

                if _sha256_file(self.database_path) != validated.database_sha256:
                    raise RecoveryError("The restored database hash does not match its manifest.")
                Database(self.database_path).validate_health().require_healthy()
                if validated.bundle.settings_present:
                    if _sha256_file(self.settings_path) != validated.settings_sha256:
                        raise RecoveryError(
                            "The restored settings hash does not match its manifest."
                        )
                elif self.settings_path.exists() or self.settings_path.is_symlink():
                    raise RecoveryError("Settings should be absent after recovery.")
            except BaseException:
                for installed in (
                    self.database_path,
                    self.settings_path,
                    *self._database_sidecars(),
                ):
                    installed.unlink(missing_ok=True)
                for original, saved in reversed(saved_originals):
                    if saved.exists() or saved.is_symlink():
                        saved.replace(original)
                raise
            for _, saved in saved_originals:
                with suppress(OSError):
                    saved.unlink(missing_ok=True)
        finally:
            database_stage.unlink(missing_ok=True)
            settings_stage.unlink(missing_ok=True)

    def _database_sidecars(self) -> tuple[Path, Path]:
        return (Path(f"{self.database_path}-wal"), Path(f"{self.database_path}-shm"))

    def _owned_bundle_path(self, path: Path) -> Path:
        if path.is_symlink() or not path.is_dir():
            raise RecoveryError("The recovery bundle path is missing or unsafe.")
        try:
            resolved_backups = self.backups_dir.resolve()
            if path.resolve().parent != resolved_backups:
                raise RecoveryError("The recovery bundle is outside the backup directory.")
        except OSError as exc:
            raise RecoveryError("The recovery bundle path could not be resolved.") from exc
        return path

    @staticmethod
    def _transition(bundle_path: Path, old_state: str, new_state: str) -> None:
        source = bundle_path / old_state
        destination = bundle_path / new_state
        if (
            not source.is_file()
            or source.is_symlink()
            or destination.exists()
            or destination.is_symlink()
        ):
            raise RecoveryError(
                f"Cannot transition recovery state from {old_state} to {new_state}."
            )
        source.replace(destination)


def _safe_relative_path(bundle_path: Path, value: str) -> Path:
    normalised = value.replace("\\", "/")
    posix = PurePosixPath(normalised)
    windows = PureWindowsPath(value)
    if (
        not value
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise RecoveryError("A recovery manifest path is unsafe.")
    candidate = bundle_path.joinpath(*posix.parts)
    try:
        candidate.resolve(strict=False).relative_to(bundle_path.resolve())
    except (OSError, ValueError) as exc:
        raise RecoveryError("A recovery manifest path escapes its bundle.") from exc
    return candidate


def _read_zip_member(archive: zipfile.ZipFile, name: str, *, limit: int) -> bytes:
    info = archive.getinfo(name)
    if info.is_dir() or info.file_size > limit:
        raise RecoveryError("A backup archive member is too large.")
    return archive.read(name)


def _copy_zip_member(archive: zipfile.ZipFile, name: str, destination: Path) -> None:
    info = archive.getinfo(name)
    if info.is_dir():
        raise RecoveryError("A backup archive member is not a file.")
    try:
        with archive.open(name) as source, destination.open("xb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _copy_durable(source: Path, destination: Path) -> None:
    with source.open("rb") as input_file, destination.open("xb") as output_file:
        shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
        output_file.flush()
        os.fsync(output_file.fileno())


def _write_atomic(path: Path, value: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
