# ruff: noqa: E501  # Long lines inside the embedded PowerShell remain readable as commands.
"""Transactional self-update support for the packaged Windows application.

Release discovery and download remain synchronous because callers already run
them on worker threads.  Installation is represented by an on-disk manifest;
an external PowerShell process performs the directory swap after the exact old
process exits and records an atomic result for the relaunched application.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from organizador import __version__
from organizador.i18n import _

LOGGER = logging.getLogger(__name__)

RELEASES_API = "https://api.github.com/repos/Parrolas/SortInator/releases/latest"
REQUEST_TIMEOUT = 10.0
DOWNLOAD_TIMEOUT = 60.0
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_FILE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
TRANSACTION_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 1
STAGED_MANIFEST_NAME = "update-manifest.json"
LOCK_STALE_AFTER_SECONDS = 3600.0
_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")

Version = tuple[int, int, int]


class UpdaterError(RuntimeError):
    """A recoverable update failure suitable for display to the user."""


class UpdateCheckStatus(StrEnum):
    """Outcome categories for release discovery."""

    UPDATE_AVAILABLE = "update_available"
    NO_UPDATE = "no_update"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    """One newer published release ready to download."""

    version: Version
    tag_name: str
    zip_url: str
    sha256_url: str


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    """A typed release check result that does not hide operational errors."""

    status: UpdateCheckStatus
    update: UpdateInfo | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status is UpdateCheckStatus.UPDATE_AVAILABLE and self.update is None:
            raise ValueError("an available result requires update metadata")
        if self.status is not UpdateCheckStatus.UPDATE_AVAILABLE and self.update is not None:
            raise ValueError("only an available result may contain update metadata")
        if self.status is UpdateCheckStatus.ERROR and not self.error:
            raise ValueError("an error result requires an error message")
        if self.status is not UpdateCheckStatus.ERROR and self.error is not None:
            raise ValueError("only an error result may contain an error message")

    @property
    def info(self) -> UpdateInfo | None:
        """Alias used by callers that refer to release information as ``info``."""

        return self.update


class UpdateResultStatus(StrEnum):
    """Terminal outcomes written by the external helper."""

    SUCCEEDED = "succeeded"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    FAILED_AFTER_COMMIT = "failed_after_commit"


@dataclass(frozen=True, slots=True)
class InstallationLock:
    """Ownership metadata stored in the process-independent installation lock."""

    path: Path
    transaction_id: str
    token: str
    pid: int
    created_at: str
    app_dir: Path
    manifest_path: Path

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON representation of this lock."""

        return {
            "schema_version": TRANSACTION_SCHEMA_VERSION,
            "transaction_id": self.transaction_id,
            "token": self.token,
            "pid": self.pid,
            "created_at": self.created_at,
            "app_dir": str(self.app_dir),
            "manifest_path": str(self.manifest_path),
        }


@dataclass(frozen=True, slots=True)
class UpdateTransaction:
    """All paths and handshake settings needed for one installation attempt."""

    transaction_id: str
    token: str
    version: Version
    app_dir: Path
    staging_dir: Path
    rollback_dir: Path
    state_dir: Path
    manifest_path: Path
    result_path: Path
    helper_path: Path
    helper_ready_path: Path
    ready_path: Path
    commit_path: Path
    healthy_path: Path
    lock_path: Path
    old_pid: int
    created_at: str
    data_dir: Path | None = None
    recovery_receipt_path: Path | None = None
    old_process_timeout_seconds: float = 120.0
    ready_timeout_seconds: float = 60.0
    healthy_timeout_seconds: float = 60.0
    move_attempts: int = 20
    move_retry_seconds: float = 0.25

    def to_dict(self) -> dict[str, object]:
        """Return the manifest representation consumed by PowerShell."""

        return {
            "schema_version": TRANSACTION_SCHEMA_VERSION,
            "transaction_id": self.transaction_id,
            "token": self.token,
            "version": list(self.version),
            "app_dir": str(self.app_dir),
            "staging_dir": str(self.staging_dir),
            "rollback_dir": str(self.rollback_dir),
            "state_dir": str(self.state_dir),
            "manifest_path": str(self.manifest_path),
            "result_path": str(self.result_path),
            "helper_path": str(self.helper_path),
            "helper_ready_path": str(self.helper_ready_path),
            "ready_path": str(self.ready_path),
            "commit_path": str(self.commit_path),
            "healthy_path": str(self.healthy_path),
            "lock_path": str(self.lock_path),
            "old_pid": self.old_pid,
            "created_at": self.created_at,
            "data_dir": str(self.data_dir) if self.data_dir is not None else None,
            "recovery_receipt_path": (
                str(self.recovery_receipt_path) if self.recovery_receipt_path is not None else None
            ),
            "old_process_timeout_seconds": self.old_process_timeout_seconds,
            "ready_timeout_seconds": self.ready_timeout_seconds,
            "healthy_timeout_seconds": self.healthy_timeout_seconds,
            "move_attempts": self.move_attempts,
            "move_retry_seconds": self.move_retry_seconds,
        }

    @property
    def download_dir(self) -> Path:
        """Return this transaction's private download directory."""

        return self.state_dir / "download"


@dataclass(frozen=True, slots=True)
class UpdateResult:
    """Persistent, user-visible outcome of one update transaction."""

    transaction_id: str
    status: UpdateResultStatus
    phase: str
    committed: bool
    rollback_succeeded: bool | None
    error: str | None
    old_pid: int
    new_pid: int | None
    started_at: str
    finished_at: str
    app_dir: Path
    rollback_dir: Path
    recovery_receipt_path: Path | None = None
    cleanup_deferred: bool = False
    seen_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON representation of the helper result."""

        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "transaction_id": self.transaction_id,
            "status": self.status.value,
            "phase": self.phase,
            "committed": self.committed,
            "rollback_succeeded": self.rollback_succeeded,
            "error": self.error,
            "old_pid": self.old_pid,
            "new_pid": self.new_pid,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "app_dir": str(self.app_dir),
            "rollback_dir": str(self.rollback_dir),
            "recovery_receipt_path": (
                str(self.recovery_receipt_path) if self.recovery_receipt_path is not None else None
            ),
            "cleanup_deferred": self.cleanup_deferred,
            "seen_at": self.seen_at,
        }


# Short aliases make the typed discovery API convenient without breaking UpdateInfo imports.
CheckStatus = UpdateCheckStatus
CheckResult = UpdateCheckResult


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def is_frozen() -> bool:
    """Return whether the app runs from the packaged executable."""

    return bool(getattr(sys, "frozen", False))


def version_tuple(tag: str) -> Version | None:
    """Parse exactly three numeric version components, with an optional ``v``."""

    match = _VERSION_PATTERN.fullmatch(tag)
    if match is None:
        return None
    try:
        major, minor, patch = (int(part) for part in match.groups())
    except ValueError:
        return None
    return major, minor, patch


def _packaged_executable(app_dir: Path) -> Path | None:
    """Resolve the packaged executable, preferring the update manifest.

    The manifest records the executable name for the payload, so a renamed
    build keeps updating correctly instead of relying on a hardcoded name.
    """

    manifest_path = app_dir / "update-manifest.json"
    if manifest_path.is_file():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = None
        if isinstance(payload, dict):
            name = payload.get("executable")
            if isinstance(name, str) and name:
                candidate = app_dir / name
                if candidate.is_file():
                    return candidate
    fallback = app_dir / "SortInator.exe"
    if fallback.is_file():
        return fallback
    return None


def validate_app_directory(candidate: Path) -> Path:
    """Validate a complete packaged app without constraining its folder name."""

    resolved = candidate.resolve()
    if _packaged_executable(resolved) is None or not (resolved / "_internal").is_dir():
        raise UpdaterError(_("A pasta não contém uma instalação completa do SortInator."))
    return resolved


def app_directory() -> Path | None:
    """Return the packaged application folder, or ``None`` when it is invalid."""

    if not is_frozen():
        return None
    try:
        return validate_app_directory(Path(sys.executable).resolve().parent)
    except UpdaterError:
        return None


def staging_directory(app_dir: Path) -> Path:
    """Return the legacy staging path used by the current controller.

    New code should use :func:`create_update_transaction`, whose staging and
    rollback paths are unique for every attempt.
    """

    return app_dir.parent / "Organizador.update"


def _release_error(message: str) -> UpdateCheckResult:
    LOGGER.info("Update check failed: %s", message)
    return UpdateCheckResult(UpdateCheckStatus.ERROR, error=message)


def check_latest_release(*, current_version: str = __version__) -> UpdateCheckResult:
    """Check GitHub and distinguish no update from malformed or failed checks."""

    current = version_tuple(current_version)
    if current is None:
        return _release_error(f"invalid current version: {current_version!r}")

    request = urllib.request.Request(
        RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "SortInator",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload: Any = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return _release_error(str(exc) or type(exc).__name__)

    if not isinstance(payload, dict):
        return _release_error("release response is not an object")
    tag_name = payload.get("tag_name")
    if not isinstance(tag_name, str):
        return _release_error("release tag_name is missing or invalid")
    remote = version_tuple(tag_name)
    if remote is None:
        return _release_error(f"release tag is not a three-part version: {tag_name!r}")
    if remote <= current:
        return UpdateCheckResult(UpdateCheckStatus.NO_UPDATE)

    version_text = ".".join(str(part) for part in remote)
    zip_name = f"SortInator-{version_text}-windows-x64.zip"
    sha_name = f"{zip_name}.sha256"
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return _release_error("release assets are missing or invalid")

    matching: dict[str, str] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            return _release_error("release contains an invalid asset")
        name = asset.get("name")
        if name not in {zip_name, sha_name}:
            continue
        url = asset.get("browser_download_url")
        if not isinstance(url, str) or not url:
            return _release_error(f"release asset {name!r} has no download URL")
        if name in matching:
            return _release_error(f"release contains duplicate asset {name!r}")
        matching[name] = url
    if set(matching) != {zip_name, sha_name}:
        return _release_error(
            f"release v{version_text} does not contain the exact ZIP/checksum pair"
        )

    return UpdateCheckResult(
        UpdateCheckStatus.UPDATE_AVAILABLE,
        update=UpdateInfo(remote, tag_name, matching[zip_name], matching[sha_name]),
    )


def fetch_latest_release() -> UpdateInfo | None:
    """Compatibility wrapper returning only a newer release, as before v0.6.2."""

    return check_latest_release().update


def _download_to_path(url: str, path: Path, *, timeout: float, limit: int) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "SortInator"})
    written = 0
    with urllib.request.urlopen(request, timeout=timeout) as response, path.open("xb") as handle:
        while chunk := response.read(1024 * 1024):
            written += len(chunk)
            if written > limit:
                raise UpdaterError(_("O ficheiro da atualização excede o limite permitido."))
            handle.write(chunk)


def download_and_verify(download_url: str, sha256_url: str, destination_dir: Path) -> Path:
    """Download the release ZIP and discard it unless its SHA-256 matches."""

    destination_dir.mkdir(parents=True, exist_ok=True)
    zip_path = destination_dir / "sortinator-update.zip"
    part_path = destination_dir / f".{zip_path.name}.{uuid.uuid4().hex}.part"
    zip_path.unlink(missing_ok=True)
    try:
        _download_to_path(
            download_url,
            part_path,
            timeout=DOWNLOAD_TIMEOUT,
            limit=MAX_DOWNLOAD_BYTES,
        )
        os.replace(part_path, zip_path)
    except Exception as exc:
        part_path.unlink(missing_ok=True)
        zip_path.unlink(missing_ok=True)
        if isinstance(exc, UpdaterError):
            raise
        raise UpdaterError(
            _("A transferência da atualização falhou: {error}").format(error=exc)
        ) from exc

    try:
        request = urllib.request.Request(sha256_url, headers={"User-Agent": "SortInator"})
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            checksum_bytes = response.read(MAX_CHECKSUM_BYTES + 1)
        if len(checksum_bytes) > MAX_CHECKSUM_BYTES:
            raise ValueError("checksum response is too large")
        checksum_parts = checksum_bytes.decode("utf-8", errors="strict").strip().split()
        expected = checksum_parts[0] if checksum_parts else ""
        if not _SHA256_PATTERN.fullmatch(expected):
            raise ValueError("checksum is not a SHA-256 digest")
        if len(checksum_parts) > 1:
            published_name = checksum_parts[1].lstrip("*")
            archive_name = Path(urllib.parse.urlsplit(download_url).path).name
            if published_name != archive_name:
                raise ValueError("checksum names a different archive")
    except Exception as exc:
        zip_path.unlink(missing_ok=True)
        raise UpdaterError(
            _("Não foi possível verificar a atualização: {error}").format(error=exc)
        ) from exc

    digest = hashlib.sha256()
    with zip_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if not hmac.compare_digest(expected.lower(), digest.hexdigest().lower()):
        zip_path.unlink(missing_ok=True)
        raise UpdaterError(_("A verificação da atualização falhou; o ficheiro foi descartado."))
    return zip_path


def _validated_member_path(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename.replace("\\", "/")
    path = PurePosixPath(name)
    windows_path = PureWindowsPath(info.filename)
    if (
        not name
        or "\x00" in name
        or name.startswith("/")
        or windows_path.drive
        or windows_path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(":" in part or part.rstrip(" .") != part for part in path.parts)
    ):
        raise UpdaterError(_("A atualização contém um caminho de ficheiro inseguro."))

    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise UpdaterError(_("A atualização contém um tipo de ficheiro não permitido."))
    if info.flag_bits & 0x1:
        raise UpdaterError(_("A atualização contém um ficheiro encriptado não suportado."))
    return path


def extract_to_staging(
    zip_path: Path,
    staging_dir: Path,
    *,
    max_members: int = MAX_ARCHIVE_MEMBERS,
    max_file_size: int = MAX_ARCHIVE_FILE_BYTES,
    max_total_size: int = MAX_ARCHIVE_UNCOMPRESSED_BYTES,
) -> Path:
    """Safely extract a verified ZIP within explicit member and byte limits."""

    if min(max_members, max_file_size, max_total_size) < 1:
        raise ValueError("archive limits must be positive")
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            if len(members) > max_members:
                raise UpdaterError(_("A atualização contém demasiados ficheiros."))

            validated: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
            declared_total = 0
            destinations: dict[str, bool] = {}
            for info in members:
                relative = _validated_member_path(info)
                is_directory = info.is_dir()
                if info.file_size < 0 or info.file_size > max_file_size:
                    raise UpdaterError(_("Um ficheiro da atualização excede o limite permitido."))
                declared_total += info.file_size
                if declared_total > max_total_size:
                    raise UpdaterError(_("A atualização extraída excede o limite permitido."))

                key = relative.as_posix().casefold().rstrip("/")
                if not key or key in destinations:
                    raise UpdaterError(_("A atualização contém caminhos duplicados."))
                for parent in relative.parents:
                    parent_key = parent.as_posix().casefold()
                    if parent_key == ".":
                        break
                    if destinations.get(parent_key) is False:
                        raise UpdaterError(_("A atualização contém caminhos incompatíveis."))
                destinations[key] = is_directory
                validated.append((info, relative))

            extracted_total = 0
            for info, relative in validated:
                destination = staging_dir.joinpath(*relative.parts)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                member_size = 0
                with archive.open(info) as source, destination.open("xb") as target:
                    while chunk := source.read(1024 * 1024):
                        member_size += len(chunk)
                        extracted_total += len(chunk)
                        if member_size > max_file_size or extracted_total > max_total_size:
                            raise UpdaterError(
                                _("A atualização extraída excede o limite permitido.")
                            )
                        target.write(chunk)
                if member_size != info.file_size:
                    raise UpdaterError(_("O tamanho de um ficheiro da atualização é inválido."))

        return validate_app_directory(staging_dir)
    except UpdaterError:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise UpdaterError(_("A atualização descarregada está corrompida.")) from exc
    finally:
        zip_path.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def installation_lock_path(app_dir: Path) -> Path:
    """Return the stable sibling lock path for one installation directory."""

    return app_dir.parent / f".{app_dir.name}.update.lock"


def _pid_is_running(pid: int) -> bool:
    """Return whether a process identifier currently exists (fail-open)."""

    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:
        return True
    return True


def is_lock_stale(lock: InstallationLock | None) -> bool:
    """Return whether a lock can never complete and may be taken over."""

    if lock is None:
        return True
    try:
        created = datetime.fromisoformat(lock.created_at)
    except ValueError:
        created = None
    if created is not None:
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - created).total_seconds()
        if age > LOCK_STALE_AFTER_SECONDS:
            return True
    return not _pid_is_running(lock.pid)


def updates_directory(data_dir: Path) -> Path:
    """Return the canonical persistent update-state directory."""

    return data_dir.resolve() / "updates"


def acquire_installation_lock(
    app_dir: Path,
    *,
    transaction_id: str | None = None,
    token: str | None = None,
    manifest_path: Path | None = None,
    pid: int | None = None,
) -> InstallationLock:
    """Atomically acquire the app's update lock and persist owner metadata."""

    resolved_app = app_dir.resolve()
    lock_path = installation_lock_path(resolved_app)
    owner = InstallationLock(
        path=lock_path,
        transaction_id=transaction_id or uuid.uuid4().hex,
        token=token or uuid.uuid4().hex,
        pid=pid if pid is not None else os.getpid(),
        created_at=_utc_now(),
        app_dir=resolved_app,
        manifest_path=(manifest_path or lock_path.with_suffix(".json")).resolve(),
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except FileExistsError as exc:
        existing = read_installation_lock(lock_path)
        if existing is not None and not is_lock_stale(existing):
            detail = f"transaction {existing.transaction_id} (PID {existing.pid})"
            raise UpdaterError(
                _("Já existe uma instalação de atualização em curso: {owner}.").format(owner=detail)
            ) from exc
        # A malformed lock, or one whose owner is gone (or older than an hour),
        # can never complete; take it over instead of blocking updates forever.
        lock_path.unlink(missing_ok=True)
        try:
            descriptor = os.open(lock_path, flags, 0o600)
        except FileExistsError as retry_exc:
            raise UpdaterError(
                _("Já existe uma instalação de atualização em curso: {owner}.").format(
                    owner="unknown owner"
                )
            ) from retry_exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(owner.to_dict(), handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        lock_path.unlink(missing_ok=True)
        raise
    return owner


def read_installation_lock(lock_path: Path) -> InstallationLock | None:
    """Read lock metadata, returning ``None`` for a missing or malformed lock."""

    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return InstallationLock(
            path=lock_path,
            transaction_id=str(payload["transaction_id"]),
            token=str(payload["token"]),
            pid=int(payload["pid"]),
            created_at=str(payload["created_at"]),
            app_dir=Path(str(payload["app_dir"])),
            manifest_path=Path(str(payload["manifest_path"])),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def release_installation_lock(lock: InstallationLock | UpdateTransaction) -> bool:
    """Release a lock only when its on-disk token still belongs to the caller."""

    if isinstance(lock, UpdateTransaction):
        path = lock.lock_path
        token = lock.token
        transaction_id = lock.transaction_id
    else:
        path = lock.path
        token = lock.token
        transaction_id = lock.transaction_id
    existing = read_installation_lock(path)
    if (
        existing is None
        or not hmac.compare_digest(existing.token, token)
        or existing.transaction_id != transaction_id
    ):
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def abort_update_transaction(transaction: UpdateTransaction) -> None:
    """Release the lock and discard staging/state for a transaction never launched."""

    with suppress(Exception):
        release_installation_lock(transaction)
    for sibling in (transaction.staging_dir, transaction.state_dir):
        with suppress(OSError):
            if sibling.is_dir() and not sibling.is_symlink():
                shutil.rmtree(sibling, ignore_errors=True)


def read_staged_release_version(staging_dir: Path) -> Version | None:
    """Return the staged package manifest version, or ``None`` when absent."""

    manifest_path = staging_dir / STAGED_MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return None
    try:
        payload = _require_dict(
            json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path
        )
        raw_version = payload.get("version")
        version = version_tuple(raw_version) if isinstance(raw_version, str) else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise UpdaterError(f"invalid staged release manifest {manifest_path}: {exc}") from exc
    if version is None:
        raise UpdaterError(f"invalid staged release manifest {manifest_path}")
    return version


def prune_abandoned_update_state(data_dir: Path, *, max_age_days: float = 7.0) -> tuple[Path, ...]:
    """Remove old transaction state (and their staging) left by crashes.

    Result-bearing entries are kept for the notification window, except for
    completed rollbacks: they only leave a full staged copy of the new
    version behind, and by the time the rollback receipt exists the old
    version is verifiably back in place.
    """

    root = updates_directory(data_dir)
    if not root.is_dir() or root.is_symlink():
        return ()
    removed: list[Path] = []
    cutoff = time.time() - max_age_days * 86400.0
    for child in sorted(root.iterdir()):
        try:
            if not child.is_dir() or child.is_symlink():
                continue
            result_path = child / "result.json"
            if result_path.exists():
                try:
                    result = read_update_result(result_path)
                except (OSError, ValueError, KeyError, UpdaterError):
                    continue
                if result is None:
                    continue
                if not (
                    result.status is UpdateResultStatus.ROLLED_BACK
                    and result.rollback_succeeded is True
                    and result.app_dir.is_dir()
                ):
                    continue
            try:
                fresh = child.stat().st_mtime >= cutoff
            except OSError:
                continue
            if fresh:
                continue
            staging: Path | None = None
            try:
                payload = json.loads((child / "transaction.json").read_text(encoding="utf-8"))
                candidate = payload.get("staging_dir") if isinstance(payload, dict) else None
                if isinstance(candidate, str):
                    staging = Path(candidate)
            except (OSError, ValueError):
                staging = None
            shutil.rmtree(child, ignore_errors=True)
            removed.append(child)
            if (
                staging is not None
                and ".update-" in staging.name
                and staging.name.endswith(".staging")
                and staging.is_dir()
                and not staging.is_symlink()
            ):
                shutil.rmtree(staging, ignore_errors=True)
                removed.append(staging)
        except OSError:
            continue
    return tuple(removed)


def prune_completed_rollback_directories(
    app_dir: Path,
    data_dir: Path | None = None,
) -> tuple[Path, ...]:
    """Delete rollback folders retained by updates that finished healthy.

    When the helper cannot delete the previous version (a locked file, for
    instance) it keeps the folder rather than roll back a working install.
    Later launches sweep those folders once no process needs them.
    """

    resolved_app = app_dir.resolve()
    parent = resolved_app.parent
    prefix = f".{resolved_app.name}.update-"
    state_root = (
        updates_directory(data_dir)
        if data_dir is not None
        else parent / f".{resolved_app.name}.updates"
    )
    removed: list[Path] = []
    for child in sorted(parent.glob(f"{prefix}*.rollback")):
        try:
            if not child.is_dir() or child.is_symlink():
                continue
            remainder = child.name[len(prefix) : -len(".rollback")]
            if not remainder or set(remainder) - set("0123456789abcdef"):
                continue
            result_path = state_root / remainder / "result.json"
            if not result_path.is_file():
                continue
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("status") != "succeeded":
                continue
            shutil.rmtree(child, ignore_errors=True)
            if child.is_dir():
                continue
            removed.append(child)
        except (OSError, ValueError):
            continue
    return tuple(removed)


def _coerce_version(version: str | Version) -> Version:
    if isinstance(version, str):
        parsed = version_tuple(version)
        if parsed is None:
            raise ValueError("version must contain exactly three numeric components")
        return parsed
    if len(version) != 3 or any(part < 0 for part in version):
        raise ValueError("version must contain exactly three non-negative components")
    return version


def create_update_transaction(
    app_dir: Path,
    version: str | Version,
    *,
    data_dir: Path | None = None,
    old_pid: int | None = None,
    recovery_receipt_path: Path | None = None,
    old_process_timeout_seconds: float = 120.0,
    ready_timeout_seconds: float = 60.0,
    healthy_timeout_seconds: float = 60.0,
    move_attempts: int = 20,
    move_retry_seconds: float = 0.25,
    staging_dir: Path | None = None,
) -> UpdateTransaction:
    """Create, lock, and atomically persist one update transaction."""

    resolved_app = validate_app_directory(app_dir)
    parsed_version = _coerce_version(version)
    transaction_id = uuid.uuid4().hex
    token = uuid.uuid4().hex + uuid.uuid4().hex
    parent = resolved_app.parent
    prefix = f".{resolved_app.name}.update-{transaction_id}"
    resolved_staging = (staging_dir or (parent / f"{prefix}.staging")).resolve()
    rollback_dir = (parent / f"{prefix}.rollback").resolve()
    resolved_data_dir = data_dir.resolve() if data_dir is not None else None
    state_root = (
        updates_directory(resolved_data_dir)
        if resolved_data_dir is not None
        else parent / f".{resolved_app.name}.updates"
    )
    state_dir = (state_root / transaction_id).resolve()
    for sibling in (resolved_staging, rollback_dir):
        if sibling.parent != parent or sibling == resolved_app:
            raise ValueError("transaction paths must be distinct siblings of the app directory")
    if any(
        state_dir == moving or state_dir.is_relative_to(moving)
        for moving in (resolved_app, resolved_staging, rollback_dir)
    ):
        raise ValueError("transaction state must remain outside moving directories")
    if (
        min(
            old_process_timeout_seconds,
            ready_timeout_seconds,
            healthy_timeout_seconds,
            move_retry_seconds,
        )
        <= 0
        or move_attempts < 1
    ):
        raise ValueError("transaction timeouts and retry counts must be positive")
    owner_pid = old_pid if old_pid is not None else os.getpid()
    if owner_pid <= 0:
        raise ValueError("old_pid must be positive")

    state_dir.mkdir(parents=True)
    manifest_path = state_dir / "transaction.json"
    transaction = UpdateTransaction(
        transaction_id=transaction_id,
        token=token,
        version=parsed_version,
        app_dir=resolved_app,
        staging_dir=resolved_staging,
        rollback_dir=rollback_dir,
        state_dir=state_dir,
        manifest_path=manifest_path,
        result_path=state_dir / "result.json",
        helper_path=state_dir / "apply-update.ps1",
        helper_ready_path=state_dir / "helper-ready.json",
        ready_path=state_dir / "ready.json",
        commit_path=state_dir / "commit.json",
        healthy_path=state_dir / "healthy.json",
        lock_path=installation_lock_path(resolved_app),
        old_pid=owner_pid,
        created_at=_utc_now(),
        data_dir=resolved_data_dir,
        recovery_receipt_path=(
            recovery_receipt_path.resolve() if recovery_receipt_path is not None else None
        ),
        old_process_timeout_seconds=old_process_timeout_seconds,
        ready_timeout_seconds=ready_timeout_seconds,
        healthy_timeout_seconds=healthy_timeout_seconds,
        move_attempts=move_attempts,
        move_retry_seconds=move_retry_seconds,
    )
    try:
        acquire_installation_lock(
            resolved_app,
            transaction_id=transaction_id,
            token=token,
            manifest_path=manifest_path,
            pid=owner_pid,
        )
        write_update_transaction(transaction)
    except Exception:
        release_installation_lock(transaction)
        shutil.rmtree(state_dir, ignore_errors=True)
        raise
    return transaction


# A concise alias for callers that already use "transaction" in their update service.
create_transaction = create_update_transaction


def write_update_transaction(transaction: UpdateTransaction) -> Path:
    """Atomically write a transaction manifest and return its path."""

    _atomic_write_json(transaction.manifest_path, transaction.to_dict())
    return transaction.manifest_path


def _require_dict(payload: object, path: Path) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise UpdaterError(f"invalid JSON object in {path}")
    return payload


def read_update_transaction(manifest_path: Path) -> UpdateTransaction:
    """Read and validate a persisted transaction manifest."""

    try:
        payload = _require_dict(
            json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path
        )
        if int(payload["schema_version"]) != TRANSACTION_SCHEMA_VERSION:
            raise ValueError("unsupported transaction schema")
        version_payload = payload["version"]
        if not isinstance(version_payload, list) or len(version_payload) != 3:
            raise ValueError("invalid transaction version")
        version: Version = (
            int(version_payload[0]),
            int(version_payload[1]),
            int(version_payload[2]),
        )

        def optional_path(name: str) -> Path | None:
            value = payload.get(name)
            return Path(str(value)) if value is not None else None

        transaction = UpdateTransaction(
            transaction_id=str(payload["transaction_id"]),
            token=str(payload["token"]),
            version=_coerce_version(version),
            app_dir=Path(str(payload["app_dir"])),
            staging_dir=Path(str(payload["staging_dir"])),
            rollback_dir=Path(str(payload["rollback_dir"])),
            state_dir=Path(str(payload["state_dir"])),
            manifest_path=Path(str(payload["manifest_path"])),
            result_path=Path(str(payload["result_path"])),
            helper_path=Path(str(payload["helper_path"])),
            helper_ready_path=Path(str(payload["helper_ready_path"])),
            ready_path=Path(str(payload["ready_path"])),
            commit_path=Path(str(payload["commit_path"])),
            healthy_path=Path(str(payload["healthy_path"])),
            lock_path=Path(str(payload["lock_path"])),
            old_pid=int(payload["old_pid"]),
            created_at=str(payload["created_at"]),
            data_dir=optional_path("data_dir"),
            recovery_receipt_path=optional_path("recovery_receipt_path"),
            old_process_timeout_seconds=float(payload["old_process_timeout_seconds"]),
            ready_timeout_seconds=float(payload["ready_timeout_seconds"]),
            healthy_timeout_seconds=float(payload["healthy_timeout_seconds"]),
            move_attempts=int(payload["move_attempts"]),
            move_retry_seconds=float(payload["move_retry_seconds"]),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise UpdaterError(f"invalid update transaction {manifest_path}: {exc}") from exc
    if transaction.manifest_path.resolve() != manifest_path.resolve():
        raise UpdaterError("transaction manifest path does not match its location")
    control_paths = (
        transaction.manifest_path,
        transaction.result_path,
        transaction.helper_path,
        transaction.helper_ready_path,
        transaction.ready_path,
        transaction.commit_path,
        transaction.healthy_path,
    )
    if any(path.resolve().parent != transaction.state_dir.resolve() for path in control_paths):
        raise UpdaterError("transaction control path is outside its state directory")
    if any(
        transaction.state_dir.resolve() == moving.resolve()
        or transaction.state_dir.resolve().is_relative_to(moving.resolve())
        for moving in (
            transaction.app_dir,
            transaction.staging_dir,
            transaction.rollback_dir,
        )
    ):
        raise UpdaterError("transaction state is inside a moving directory")
    return transaction


def write_update_result(path: Path, result: UpdateResult) -> Path:
    """Atomically persist an update result."""

    _atomic_write_json(path, result.to_dict())
    return path


def read_update_result(path: Path | UpdateTransaction) -> UpdateResult | None:
    """Read a transaction result, returning ``None`` until one exists."""

    result_path = path.result_path if isinstance(path, UpdateTransaction) else path
    if not result_path.exists():
        return None
    try:
        payload = _require_dict(json.loads(result_path.read_text(encoding="utf-8")), result_path)
        if int(payload["schema_version"]) != RESULT_SCHEMA_VERSION:
            raise ValueError("unsupported result schema")

        def optional_string(name: str) -> str | None:
            value = payload.get(name)
            return str(value) if value is not None else None

        rollback_value = payload.get("rollback_succeeded")
        if rollback_value is not None and not isinstance(rollback_value, bool):
            raise ValueError("invalid rollback result")
        result = UpdateResult(
            transaction_id=str(payload["transaction_id"]),
            status=UpdateResultStatus(str(payload["status"])),
            phase=str(payload["phase"]),
            committed=bool(payload["committed"]),
            rollback_succeeded=rollback_value,
            error=optional_string("error"),
            old_pid=int(payload["old_pid"]),
            new_pid=int(payload["new_pid"]) if payload.get("new_pid") is not None else None,
            started_at=str(payload["started_at"]),
            finished_at=str(payload["finished_at"]),
            app_dir=Path(str(payload["app_dir"])),
            rollback_dir=Path(str(payload["rollback_dir"])),
            recovery_receipt_path=(
                Path(str(payload["recovery_receipt_path"]))
                if payload.get("recovery_receipt_path") is not None
                else None
            ),
            cleanup_deferred=bool(payload.get("cleanup_deferred", False)),
            seen_at=optional_string("seen_at"),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise UpdaterError(f"invalid update result {result_path}: {exc}") from exc
    return result


def mark_update_result_seen(path: Path | UpdateTransaction) -> UpdateResult | None:
    """Atomically timestamp a result as seen and return the updated value."""

    result_path = path.result_path if isinstance(path, UpdateTransaction) else path
    result = read_update_result(result_path)
    if result is None:
        return None
    if result.seen_at is None:
        result = replace(result, seen_at=_utc_now())
        write_update_result(result_path, result)
    return result


def scan_unseen_update_results(data_dir: Path) -> tuple[UpdateResult, ...]:
    """Return valid unseen results from the canonical update-state directory."""

    root = updates_directory(data_dir)
    if not root.is_dir() or root.is_symlink():
        return ()
    results: list[UpdateResult] = []
    for state_dir in root.iterdir():
        result_path = state_dir / "result.json"
        if (
            not state_dir.is_dir()
            or state_dir.is_symlink()
            or not result_path.is_file()
            or result_path.is_symlink()
        ):
            continue
        try:
            result = read_update_result(result_path)
        except UpdaterError:
            LOGGER.warning("Ignoring invalid update result %s", result_path, exc_info=True)
            continue
        if result is not None and result.seen_at is None:
            results.append(result)
    return tuple(sorted(results, key=lambda item: (item.finished_at, item.transaction_id)))


def mark_scanned_update_result_seen(data_dir: Path, transaction_id: str) -> UpdateResult | None:
    """Mark one canonically stored result seen by transaction identifier."""

    if not re.fullmatch(r"[0-9a-f]{32}", transaction_id):
        raise ValueError("invalid update transaction identifier")
    return mark_update_result_seen(updates_directory(data_dir) / transaction_id / "result.json")


read_result = read_update_result
mark_result_seen = mark_update_result_seen
unseen_update_results = scan_unseen_update_results


def _authorized_transaction(manifest_path: Path, token: str) -> UpdateTransaction:
    transaction = read_update_transaction(manifest_path)
    if not hmac.compare_digest(transaction.token, token):
        raise UpdaterError("update transaction token does not match")
    return transaction


def _target_executable(transaction: UpdateTransaction) -> Path:
    executable = _packaged_executable(transaction.app_dir)
    if executable is None:
        raise UpdaterError("the application executable is missing")
    return executable


def _expected_target_executables(transaction: UpdateTransaction) -> list[Path]:
    """Executables a relaunched target may legitimately run as.

    During the rename bridge the payload still ships the previous
    executable name as an alias, and pre-rename helpers launch through
    it; rejecting that identity would fail every update handshake from
    those versions. The alias retires itself once payloads stop
    shipping it.
    """

    expected = [_target_executable(transaction)]
    legacy = transaction.app_dir / "Organizador.exe"
    if legacy.is_file() and legacy not in expected:
        expected.append(legacy)
    return expected


def _write_marker(path: Path, transaction: UpdateTransaction, *, pid: int | None = None) -> None:
    _atomic_write_json(
        path,
        {
            "schema_version": TRANSACTION_SCHEMA_VERSION,
            "transaction_id": transaction.transaction_id,
            "token": transaction.token,
            "pid": pid,
            "version": list(transaction.version),
            "target_path": str(_target_executable(transaction)),
            "created_at": _utc_now(),
        },
    )


def validate_update_target(
    manifest_path: Path,
    token: str,
    *,
    data_dir: Path,
    executable: Path | None = None,
    version: str = __version__,
) -> UpdateTransaction:
    """Authorize a relaunched target against its lock, path, version, and profile."""

    transaction = _authorized_transaction(manifest_path, token)
    parsed_version = version_tuple(version)
    if parsed_version != transaction.version:
        raise UpdaterError("updated application version does not match the transaction")
    actual_executable = (executable or Path(sys.executable)).resolve()
    expected = [path.resolve() for path in _expected_target_executables(transaction)]
    if actual_executable not in expected:
        raise UpdaterError("updated application path does not match the transaction")
    if transaction.data_dir is None or transaction.data_dir.resolve() != data_dir.resolve():
        raise UpdaterError("updated application data directory does not match the transaction")
    lock = read_installation_lock(transaction.lock_path)
    if (
        lock is None
        or lock.transaction_id != transaction.transaction_id
        or not hmac.compare_digest(lock.token, transaction.token)
        or lock.manifest_path.resolve() != transaction.manifest_path.resolve()
        or lock.app_dir.resolve() != transaction.app_dir.resolve()
    ):
        raise UpdaterError("update installation lock ownership does not match")
    return transaction


def update_commit_received(transaction: UpdateTransaction) -> bool:
    """Check the helper commit marker once without blocking the Qt event loop."""

    try:
        payload = _require_dict(
            json.loads(transaction.commit_path.read_text(encoding="utf-8")),
            transaction.commit_path,
        )
        return bool(
            payload.get("transaction_id") == transaction.transaction_id
            and isinstance(payload.get("token"), str)
            and hmac.compare_digest(str(payload["token"]), transaction.token)
        )
    except (OSError, json.JSONDecodeError, UpdaterError):
        return False


def helper_ready_received(transaction: UpdateTransaction) -> bool:
    """Check the helper-ready marker once without blocking the Qt event loop."""

    try:
        payload = _require_dict(
            json.loads(transaction.helper_ready_path.read_text(encoding="utf-8")),
            transaction.helper_ready_path,
        )
        return bool(
            payload.get("transaction_id") == transaction.transaction_id
            and isinstance(payload.get("token"), str)
            and hmac.compare_digest(str(payload["token"]), transaction.token)
        )
    except (OSError, json.JSONDecodeError, UpdaterError):
        return False


def wait_for_helper_ready(
    transaction: UpdateTransaction,
    *,
    timeout_seconds: float = 30.0,
    poll_seconds: float = 0.05,
) -> bool:
    """Wait for the helper to confirm it loaded the manifest and is supervising."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if helper_ready_received(transaction):
            return True
        time.sleep(poll_seconds)
    return False


def mark_update_ready(manifest_path: Path, token: str, *, pid: int | None = None) -> Path:
    """Signal that the relaunched application completed basic startup."""

    transaction = _authorized_transaction(manifest_path, token)
    _write_marker(transaction.ready_path, transaction, pid=pid if pid is not None else os.getpid())
    return transaction.ready_path


def wait_for_update_commit(
    manifest_path: Path,
    token: str,
    *,
    timeout_seconds: float = 60.0,
    poll_seconds: float = 0.05,
) -> bool:
    """Wait for the helper's commit marker after signalling readiness."""

    transaction = _authorized_transaction(manifest_path, token)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if update_commit_received(transaction):
            return True
        time.sleep(poll_seconds)
    return False


def mark_update_healthy(manifest_path: Path, token: str, *, pid: int | None = None) -> Path:
    """Signal post-commit health after the new application is fully operational."""

    transaction = _authorized_transaction(manifest_path, token)
    _write_marker(
        transaction.healthy_path,
        transaction,
        pid=pid if pid is not None else os.getpid(),
    )
    return transaction.healthy_path


def complete_update_handshake(
    manifest_path: Path,
    token: str,
    *,
    commit_timeout_seconds: float = 60.0,
) -> bool:
    """Perform the ready/commit/healthy handshake from the relaunched app."""

    mark_update_ready(manifest_path, token)
    if not wait_for_update_commit(
        manifest_path,
        token,
        timeout_seconds=commit_timeout_seconds,
    ):
        return False
    mark_update_healthy(manifest_path, token)
    return True


_POWERSHELL_HELPER = r"""param(
    [string]$ManifestPath = __DEFAULT_MANIFEST__,
    [string]$Token = __DEFAULT_TOKEN__
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
    $script:Phase = 'load_manifest'
    $script:Committed = $false
    $script:AppMoved = $false
    $script:StagingMoved = $false
    $script:CleanupDeferred = $false
    $script:Healthy = $false
$script:NewProcess = $null
$script:StartedAt = [DateTime]::UtcNow.ToString('o')
$script:Transaction = $null

function Write-AtomicJson([string]$Path, [object]$Value) {
    $directory = [IO.Path]::GetDirectoryName($Path)
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $temporary = Join-Path $directory ('.' + [IO.Path]::GetFileName($Path) + '.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $json = $Value | ConvertTo-Json -Depth 8 -Compress
    $encoding = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($temporary, $json + "`n", $encoding)
    if ([IO.File]::Exists($Path)) {
        [IO.File]::Replace($temporary, $Path, $null)
    } else {
        [IO.File]::Move($temporary, $Path)
    }
}

function Test-SamePath([string]$Left, [string]$Right) {
    return [string]::Equals(
        [IO.Path]::GetFullPath($Left),
        [IO.Path]::GetFullPath($Right),
        [StringComparison]::OrdinalIgnoreCase
    )
}

function Move-DirectoryWithRetry([string]$Source, [string]$Destination) {
    $lastError = $null
    for ($attempt = 1; $attempt -le [int]$script:Transaction.move_attempts; $attempt++) {
        try {
            if (-not [IO.Directory]::Exists($Source)) { throw "source directory is missing: $Source" }
            if ([IO.Directory]::Exists($Destination) -or [IO.File]::Exists($Destination)) { throw "destination already exists: $Destination" }
            [IO.Directory]::Move($Source, $Destination)
            if ([IO.Directory]::Exists($Source) -or -not [IO.Directory]::Exists($Destination)) { throw 'directory move did not complete' }
            return
        } catch {
            $lastError = $_.Exception
            if ($attempt -lt [int]$script:Transaction.move_attempts) {
                Start-Sleep -Milliseconds ([int]([double]$script:Transaction.move_retry_seconds * 1000))
            }
        }
    }
    throw $lastError
}

function Remove-DirectoryWithRetry([string]$Path) {
    $lastError = $null
    for ($attempt = 1; $attempt -le [int]$script:Transaction.move_attempts; $attempt++) {
        try {
            if ([IO.Directory]::Exists($Path)) {
                [IO.Directory]::Delete($Path, $true)
            }
            if ([IO.Directory]::Exists($Path)) { throw "directory still exists: $Path" }
            return
        } catch {
            $lastError = $_.Exception
            if ($attempt -lt [int]$script:Transaction.move_attempts) {
                Start-Sleep -Milliseconds ([int]([double]$script:Transaction.move_retry_seconds * 1000))
            }
        }
    }
    throw $lastError
}

function Quote-WindowsArgument([string]$Argument) {
    if ($Argument.Length -eq 0) { return '""' }
    if ($Argument -notmatch '[\s"]') { return $Argument }
    $builder = New-Object Text.StringBuilder
    [void]$builder.Append('"')
    $slashes = 0
    foreach ($character in $Argument.ToCharArray()) {
        if ($character -eq '\') {
            $slashes++
        } elseif ($character -eq '"') {
            [void]$builder.Append(('\' * (($slashes * 2) + 1)))
            [void]$builder.Append('"')
            $slashes = 0
        } else {
            if ($slashes -gt 0) { [void]$builder.Append(('\' * $slashes)) }
            [void]$builder.Append($character)
            $slashes = 0
        }
    }
    if ($slashes -gt 0) { [void]$builder.Append(('\' * ($slashes * 2))) }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Test-AuthorizedMarker([string]$Path) {
    if (-not [IO.File]::Exists($Path)) { return $false }
    try {
        $marker = [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8) | ConvertFrom-Json
        return ([string]$marker.transaction_id -ceq [string]$script:Transaction.transaction_id) -and ([string]$marker.token -ceq $Token)
    } catch {
        return $false
    }
}

function Wait-ForMarker([string]$Path, [double]$TimeoutSeconds, [string]$Name) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-AuthorizedMarker $Path) { return }
        if ($null -ne $script:NewProcess -and $script:NewProcess.HasExited) {
            throw "new application exited before the $Name marker"
        }
        Start-Sleep -Milliseconds 50
    }
    throw "timed out waiting for the $Name marker"
}

function Stop-NewProcess {
    if ($null -eq $script:NewProcess -or $script:NewProcess.HasExited) { return }
    Stop-Process -Id $script:NewProcess.Id -Force -ErrorAction Stop
    if (-not $script:NewProcess.WaitForExit(10000)) {
        throw 'new application did not exit during rollback'
    }
}

function Restore-PreviousVersion {
    Stop-NewProcess
    if ($script:StagingMoved -and [IO.Directory]::Exists([string]$script:Transaction.app_dir)) {
        Move-DirectoryWithRetry ([string]$script:Transaction.app_dir) ([string]$script:Transaction.staging_dir)
    }
    if ($script:AppMoved -and [IO.Directory]::Exists([string]$script:Transaction.rollback_dir)) {
        Move-DirectoryWithRetry ([string]$script:Transaction.rollback_dir) ([string]$script:Transaction.app_dir)
    }
}

function Get-AppExecutable([string]$AppPath) {
    # Prefer the manifest so a renamed executable keeps working across updates.
    $manifestPath = Join-Path $AppPath 'update-manifest.json'
    if ([IO.File]::Exists($manifestPath)) {
        try {
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
            $name = [string]$manifest.executable
            if (-not [string]::IsNullOrEmpty($name)) {
                $candidate = Join-Path $AppPath $name
                if ([IO.File]::Exists($candidate)) { return $candidate }
            }
        } catch { }
    }
    $fallback = Join-Path $AppPath 'SortInator.exe'
    if ([IO.File]::Exists($fallback)) { return $fallback }
    throw 'application executable is missing'
}

function Start-RestoredApp {
    # Plain normal launch (no update arguments): the restored application
    # recovers its own pending migration bundle on startup, if one exists.
    $restoredExe = Get-AppExecutable ([string]$script:Transaction.app_dir)
    $relaunchArgs = New-Object Collections.Generic.List[string]
    [void]$relaunchArgs.Add('--background')
    if ($null -ne $script:Transaction.data_dir -and -not [string]::IsNullOrEmpty([string]$script:Transaction.data_dir)) {
        [void]$relaunchArgs.Add('--data-dir')
        [void]$relaunchArgs.Add([string]$script:Transaction.data_dir)
    }
    $quoted = (($relaunchArgs | ForEach-Object { Quote-WindowsArgument $_ }) -join ' ')
    $restored = Start-Process -FilePath $restoredExe -ArgumentList $quoted -WorkingDirectory ([string]$script:Transaction.app_dir) -PassThru
    if ($null -eq $restored) { throw 'could not relaunch the restored application' }
}

function Save-Result([string]$Status, [string]$ErrorMessage, [object]$RollbackSucceeded) {
    $newPid = $null
    if ($null -ne $script:NewProcess) { $newPid = $script:NewProcess.Id }
    $receipt = $null
    if ($null -ne $script:Transaction.recovery_receipt_path) { $receipt = [string]$script:Transaction.recovery_receipt_path }
    $result = [ordered]@{
        schema_version = 1
        transaction_id = [string]$script:Transaction.transaction_id
        status = $Status
        phase = $script:Phase
        committed = $script:Committed
        rollback_succeeded = $RollbackSucceeded
        error = $(if ([string]::IsNullOrEmpty($ErrorMessage)) { $null } else { $ErrorMessage })
        old_pid = [int]$script:Transaction.old_pid
        new_pid = $newPid
        started_at = $script:StartedAt
        finished_at = [DateTime]::UtcNow.ToString('o')
        app_dir = [string]$script:Transaction.app_dir
        rollback_dir = [string]$script:Transaction.rollback_dir
        recovery_receipt_path = $receipt
        cleanup_deferred = $script:CleanupDeferred
        seen_at = $null
    }
    Write-AtomicJson ([string]$script:Transaction.result_path) $result
}

function Release-Lock {
    $path = [string]$script:Transaction.lock_path
    if (-not [IO.File]::Exists($path)) { return }
    try {
        $owner = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) | ConvertFrom-Json
        if (([string]$owner.transaction_id -ceq [string]$script:Transaction.transaction_id) -and ([string]$owner.token -ceq $Token)) {
            [IO.File]::Delete($path)
        }
    } catch { }
}

try {
    $manifestFullPath = [IO.Path]::GetFullPath($ManifestPath)
    $script:Transaction = [IO.File]::ReadAllText($manifestFullPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
    if ([int]$script:Transaction.schema_version -ne 1) { throw 'unsupported transaction schema' }
    if ([string]$script:Transaction.token -cne $Token) { throw 'transaction token does not match' }
    if (-not (Test-SamePath ([string]$script:Transaction.manifest_path) $manifestFullPath)) { throw 'manifest path does not match transaction' }

    $appPath = [IO.Path]::GetFullPath([string]$script:Transaction.app_dir)
    $stagingPath = [IO.Path]::GetFullPath([string]$script:Transaction.staging_dir)
    $rollbackPath = [IO.Path]::GetFullPath([string]$script:Transaction.rollback_dir)
    $statePath = [IO.Path]::GetFullPath([string]$script:Transaction.state_dir)
    $parentPath = [IO.Directory]::GetParent($appPath).FullName
    foreach ($candidate in @($stagingPath, $rollbackPath)) {
        if (-not (Test-SamePath ([IO.Directory]::GetParent($candidate).FullName) $parentPath)) { throw 'transaction paths are not sibling directories' }
    }
    if ((Test-SamePath $appPath $stagingPath) -or (Test-SamePath $appPath $rollbackPath) -or (Test-SamePath $stagingPath $rollbackPath)) { throw 'transaction paths are not distinct' }
    foreach ($moving in @($appPath, $stagingPath, $rollbackPath)) {
        $prefix = $moving.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
        if ((Test-SamePath $statePath $moving) -or $statePath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'transaction state is inside a moving directory' }
    }
    if (-not [IO.Directory]::Exists($statePath)) { throw 'transaction state directory is missing' }
    foreach ($controlPath in @([string]$script:Transaction.manifest_path, [string]$script:Transaction.result_path, [string]$script:Transaction.helper_path, [string]$script:Transaction.helper_ready_path, [string]$script:Transaction.ready_path, [string]$script:Transaction.commit_path, [string]$script:Transaction.healthy_path)) {
        if (-not (Test-SamePath ([IO.Path]::GetDirectoryName($controlPath)) $statePath)) { throw 'transaction control path is outside the state directory' }
    }
    Set-Location -LiteralPath $statePath

    foreach ($markerPath in @([string]$script:Transaction.helper_ready_path, [string]$script:Transaction.ready_path, [string]$script:Transaction.commit_path, [string]$script:Transaction.healthy_path)) {
        if ([IO.File]::Exists($markerPath)) { [IO.File]::Delete($markerPath) }
    }

    $script:Phase = 'helper_ready'
    Write-AtomicJson ([string]$script:Transaction.helper_ready_path) ([ordered]@{
        schema_version = 1
        transaction_id = [string]$script:Transaction.transaction_id
        token = $Token
        created_at = [DateTime]::UtcNow.ToString('o')
    })

    $script:Phase = 'wait_old_process'
    $oldProcess = Get-Process -Id ([int]$script:Transaction.old_pid) -ErrorAction SilentlyContinue
    if ($null -ne $oldProcess) {
        $waitMilliseconds = [int]([double]$script:Transaction.old_process_timeout_seconds * 1000)
        if (-not $oldProcess.WaitForExit($waitMilliseconds)) { throw 'timed out waiting for the old application process' }
    }

    $script:Phase = 'move_current_to_rollback'
    Move-DirectoryWithRetry $appPath $rollbackPath
    $script:AppMoved = $true

    $script:Phase = 'move_staging_to_target'
    Move-DirectoryWithRetry $stagingPath $appPath
    $script:StagingMoved = $true

    $script:Phase = 'launch_target'
    $executable = Get-AppExecutable $appPath
    $arguments = New-Object Collections.Generic.List[string]
    [void]$arguments.Add('--background')
    if ($null -ne $script:Transaction.data_dir -and -not [string]::IsNullOrEmpty([string]$script:Transaction.data_dir)) {
        [void]$arguments.Add('--data-dir')
        [void]$arguments.Add([string]$script:Transaction.data_dir)
    }
    [void]$arguments.Add('--update-manifest')
    [void]$arguments.Add($manifestFullPath)
    [void]$arguments.Add('--update-token')
    [void]$arguments.Add($Token)
    $quotedArguments = (($arguments | ForEach-Object { Quote-WindowsArgument $_ }) -join ' ')
    $script:NewProcess = Start-Process -FilePath $executable -ArgumentList $quotedArguments -WorkingDirectory $appPath -PassThru
    if ($null -eq $script:NewProcess) { throw 'could not start the updated application' }

    $script:Phase = 'wait_ready'
    Wait-ForMarker ([string]$script:Transaction.ready_path) ([double]$script:Transaction.ready_timeout_seconds) 'ready'

    $script:Phase = 'commit'
    Write-AtomicJson ([string]$script:Transaction.commit_path) ([ordered]@{
        schema_version = 1
        transaction_id = [string]$script:Transaction.transaction_id
        token = $Token
        created_at = [DateTime]::UtcNow.ToString('o')
    })
    $script:Committed = $true

    $script:Phase = 'wait_healthy'
    Wait-ForMarker ([string]$script:Transaction.healthy_path) ([double]$script:Transaction.healthy_timeout_seconds) 'healthy'
    $script:Healthy = $true

    $script:Phase = 'cleanup_rollback'
    try {
        Remove-DirectoryWithRetry $rollbackPath
    } catch {
        # The update committed and the new version reported healthy. Deleting
        # the old copy must never undo a working installation; retain the
        # folder so a later launch can sweep it.
        $script:CleanupDeferred = $true
    }
    $script:Phase = 'complete'
    Save-Result 'succeeded' $null $null
    Release-Lock
    exit 0
} catch {
    $failure = $_.Exception.Message
    if ($script:Healthy) {
        # The new version is running healthy; nothing after this point may
        # roll it back. A receipt-write failure must leave the install alone.
        try { Save-Result 'succeeded' $failure $null } catch { }
        Release-Lock
        exit 0
    }
    $rollbackSucceeded = $null
    $status = 'failed'
    $needsRollback = ($null -ne $script:Transaction) -and ($script:AppMoved -or $script:StagingMoved)
    if ($needsRollback) {
        try {
            Restore-PreviousVersion
            $rollbackSucceeded = $true
            if ($script:AppMoved) { $status = 'rolled_back' }
            try {
                Start-RestoredApp
            } catch {
                $failure = $failure + '; relaunch failed: ' + $_.Exception.Message
            }
        } catch {
            $rollbackSucceeded = $false
            $failure = $failure + '; rollback failed: ' + $_.Exception.Message
            $status = 'failed'
        }
    }
    if ($status -eq 'failed' -and $script:Committed) {
        # The swap committed but neither success nor rollback completed.
        $status = 'failed_after_commit'
    }
    if ($null -ne $script:Transaction) {
        try { Save-Result $status $failure $rollbackSucceeded } catch { }
        Release-Lock
    }
    if ($status -eq 'rolled_back') { exit 10 }
    if ($status -eq 'failed_after_commit') { exit 20 }
    exit 30
}
"""


def _powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_update_helper(transaction: UpdateTransaction) -> Path:
    """Write a transaction-specific, Windows PowerShell 5.1-safe helper."""

    write_update_transaction(transaction)
    script = _POWERSHELL_HELPER.replace(
        "__DEFAULT_MANIFEST__", _powershell_literal(str(transaction.manifest_path))
    ).replace("__DEFAULT_TOKEN__", _powershell_literal(transaction.token))
    transaction.helper_path.write_text(script, encoding="utf-8-sig", newline="\r\n")
    return transaction.helper_path


def _current_data_dir_argument() -> Path | None:
    for index, argument in enumerate(sys.argv[1:]):
        if argument == "--data-dir" and index + 2 <= len(sys.argv) - 1:
            return Path(sys.argv[index + 2])
        if argument.startswith("--data-dir="):
            return Path(argument.partition("=")[2])
    return None


def write_swap_script(
    app_dir: Path | UpdateTransaction,
    staging_dir: Path | None = None,
) -> Path:
    """Compatibility wrapper for the v0.6 controller's two-argument API."""

    if isinstance(app_dir, UpdateTransaction):
        if staging_dir is not None:
            raise TypeError("staging_dir is not accepted with an UpdateTransaction")
        transaction = app_dir
    else:
        if staging_dir is None:
            raise TypeError("staging_dir is required")
        transaction = create_update_transaction(
            app_dir,
            __version__,
            data_dir=_current_data_dir_argument(),
            staging_dir=staging_dir,
        )
    return write_update_helper(transaction)


def _powershell_executable() -> str:
    system_root = os.environ.get("SYSTEMROOT")
    if system_root:
        candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("powershell.exe") or shutil.which("pwsh.exe") or "powershell.exe"


def _launch_helper(
    script_path: Path,
    *,
    cwd: Path,
    manifest_path: Path | None = None,
    token: str | None = None,
    powershell_executable: str | None = None,
) -> subprocess.Popen[bytes]:
    arguments = [
        powershell_executable or _powershell_executable(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]
    if manifest_path is not None and token is not None:
        arguments.extend(["-ManifestPath", str(manifest_path), "-Token", token])
    # DETACHED_PROCESS causes Windows PowerShell 5.1 to return without running a
    # file on some Windows builds. A hidden new process group survives its parent
    # while retaining reliable script execution.
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    return subprocess.Popen(
        arguments,
        cwd=cwd,
        creationflags=flags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def launch_update_helper(
    transaction: UpdateTransaction,
    *,
    powershell_executable: str | None = None,
    ready_timeout_seconds: float = 30.0,
    wait_ready: bool = True,
) -> subprocess.Popen[bytes]:
    """Launch the helper detached, from its stable transaction state directory.

    By default this waits for the helper-ready marker so callers only shut down
    after the helper confirmed it is supervising the transaction.
    """

    if transaction.helper_path.parent != transaction.state_dir:
        raise UpdaterError("the update helper must be outside all moving directories")
    process = _launch_helper(
        transaction.helper_path,
        cwd=transaction.state_dir,
        manifest_path=transaction.manifest_path,
        token=transaction.token,
        powershell_executable=powershell_executable,
    )
    if wait_ready and not wait_for_helper_ready(transaction, timeout_seconds=ready_timeout_seconds):
        with suppress(Exception):
            process.terminate()
        raise UpdaterError(_("Não foi possível iniciar o assistente de atualização."))
    return process


def launch_swap(script_path: Path) -> None:
    """Compatibility wrapper that launches a helper containing manifest defaults."""

    _launch_helper(script_path, cwd=script_path.parent)


def cleanup_previous_version(app_dir: Path) -> None:
    """Remove the deterministic rollback folder left by the pre-v0.6.2 updater."""

    old_dir = app_dir.parent / "Organizador.old"
    try:
        if old_dir.is_dir():
            shutil.rmtree(old_dir)
            LOGGER.info("Removed previous version folder %s", old_dir)
    except OSError:
        LOGGER.exception("Could not remove previous version folder %s", old_dir)


def download_temp_directory() -> Path:
    """Return the per-session folder used for the verified ZIP."""

    folder = Path(tempfile.gettempdir()) / "sortinator-update"
    folder.mkdir(parents=True, exist_ok=True)
    return folder
