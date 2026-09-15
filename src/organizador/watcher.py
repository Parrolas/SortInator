"""Non-blocking Downloads observer with a polling safety net."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from time import monotonic

from watchdog.events import (
    DirCreatedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from organizador.config import MANUAL_IMPORT_BATCH_LIMIT, AppConfig
from organizador.models import ExistingDownload
from organizador.stabilizer import wait_until_stable

LOGGER = logging.getLogger(__name__)
DownloadCandidate = Path | ExistingDownload
PathCandidateCallback = Callable[[Path], None]
CandidateCallback = Callable[[DownloadCandidate], None]
ImportCompleteCallback = Callable[[int], None]
PathKey = tuple[str, str]
DEFAULT_STABILIZATION_RETRY_DELAYS = (30.0, 120.0, 300.0)


def _directory_key(path: Path) -> str:
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        resolved = path.absolute()
    return os.path.normcase(os.fspath(resolved))


def _path_key(path: Path) -> PathKey:
    absolute = path.absolute()
    return (_directory_key(absolute.parent), os.path.normcase(absolute.name))


class DownloadEventHandler(FileSystemEventHandler):
    """Convert watchdog events into final-path candidates."""

    def __init__(self, enqueue: PathCandidateCallback) -> None:
        super().__init__()
        self.enqueue = enqueue

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        if not event.is_directory:
            self.enqueue(Path(os.fsdecode(event.src_path)))

    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
        if not event.is_directory:
            self.enqueue(Path(os.fsdecode(event.dest_path)))


class DownloadWatcher:
    """Observe final download names without blocking watchdog's event thread."""

    def __init__(
        self,
        config: AppConfig,
        on_ready: CandidateCallback,
        on_import_complete: ImportCompleteCallback | None = None,
        *,
        retry_delays: Sequence[float] = DEFAULT_STABILIZATION_RETRY_DELAYS,
    ) -> None:
        self.config = config
        self.on_ready = on_ready
        self.on_import_complete = on_import_complete
        if any(delay < 0 for delay in retry_delays):
            raise ValueError("Retry delays must not be negative")
        self._retry_delays = tuple(float(delay) for delay in retry_delays)
        self._queue: Queue[tuple[PathKey, DownloadCandidate] | None] = Queue()
        self._pending: set[PathKey] = set()
        self._known: set[PathKey] = set()
        self._manual_pending: set[PathKey] = set()
        self._manual_skipped = 0
        self._ignored_until: dict[PathKey, float] = {}
        self._retry_after: dict[PathKey, float] = {}
        self._retry_attempts: dict[PathKey, int] = {}
        self._retry_exhausted: dict[PathKey, ExistingDownload | None] = {}
        self._paused_seen: set[PathKey] = set()
        self._lock = Lock()
        self._stop = Event()
        self._paused = Event()
        self._observer: BaseObserver | None = None
        self._worker: Thread | None = None
        self._sweeper: Thread | None = None
        self._downloads_key = _directory_key(config.downloads_dir)

    @property
    def running(self) -> bool:
        """Return whether the native observer is active."""

        return self._observer is not None and self._observer.is_alive()

    @property
    def active(self) -> bool:
        """Return whether the shared stabilization worker is active."""

        return self._worker is not None and self._worker.is_alive()

    @property
    def manual_import_running(self) -> bool:
        """Return whether a confirmed existing-file batch is still being checked."""

        with self._lock:
            return bool(self._manual_pending)

    @property
    def paused(self) -> bool:
        """Return whether new candidates are temporarily ignored."""

        return self._paused.is_set()

    def start(self, *, observe: bool = True) -> None:
        """Start the worker and optionally native observation and its safety net."""

        if self.active:
            return
        self.config.downloads_dir.mkdir(parents=True, exist_ok=True)
        self._downloads_key = _directory_key(self.config.downloads_dir)
        self._stop.clear()
        snapshot = self._snapshot() if observe else {}
        if snapshot is None:
            raise OSError("Não foi possível estabelecer uma base segura de Downloads.")
        self._known = set(snapshot)
        self._worker = Thread(target=self._work, name="download-stabilizer", daemon=True)
        self._worker.start()
        if observe:
            self._observer = Observer()
            self._observer.schedule(
                DownloadEventHandler(self.enqueue), str(self.config.downloads_dir), recursive=False
            )
            self._observer.start()
            self._sweeper = Thread(target=self._sweep, name="download-sweeper", daemon=True)
            self._sweeper.start()
            LOGGER.info("Watching Downloads at %s", self.config.downloads_dir)
        else:
            LOGGER.info("Manual Downloads import ready at %s", self.config.downloads_dir)

    def stop(self) -> None:
        """Stop all watcher threads cleanly."""

        self._stop.set()
        self._queue.put(None)
        if self._observer is not None and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=3)
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=3)
        if self._sweeper is not None and self._sweeper.is_alive():
            self._sweeper.join(timeout=3)
        self._observer = None
        self._worker = None
        self._sweeper = None
        completed_skips: int | None = None
        with self._lock:
            if self._manual_pending:
                completed_skips = self._manual_skipped + len(self._manual_pending)
            self._pending.clear()
            self._manual_pending.clear()
            self._manual_skipped = 0
            self._retry_after.clear()
            self._retry_attempts.clear()
            self._retry_exhausted.clear()
            self._paused_seen.clear()
        if completed_skips is not None and self.on_import_complete is not None:
            self.on_import_complete(completed_skips)

    def set_paused(self, paused: bool) -> None:
        """Pause or resume candidate intake."""

        if paused:
            self._paused.set()
            return
        with self._lock:
            released = self._paused_seen
            self._paused_seen = set()
            self._known.difference_update(released)
        self._paused.clear()
        if released and self.active:
            Thread(
                target=self._sweep_once,
                name="download-sweep-resume",
                daemon=True,
            ).start()

    def ignore_self_move(self, path: Path, *, seconds: float = 30.0) -> None:
        """Prevent a file returned by this app from being ingested again."""

        normalised = self._normalise_candidate(path)
        if normalised is None:
            return
        _, key = normalised
        with self._lock:
            self._known.add(key)
            self._ignored_until[key] = monotonic() + seconds

    def enqueue(self, path: Path) -> None:
        """Queue one eligible final filename for stabilization."""

        if self._stop.is_set() or not self.config.accepts(path):
            return
        normalised = self._normalise_candidate(path)
        if normalised is None:
            return
        candidate, key = normalised
        with self._lock:
            if self._paused.is_set():
                self._known.add(key)
                self._paused_seen.add(key)
                return
            now = monotonic()
            ignored_until = self._ignored_until.get(key)
            if ignored_until is not None and ignored_until >= now:
                self._known.add(key)
                return
            self._ignored_until.pop(key, None)
            if key in self._retry_exhausted:
                current = ExistingDownload.capture(candidate)
                if current == self._retry_exhausted[key]:
                    self._known.add(key)
                    return
                self._retry_exhausted.pop(key, None)
                self._retry_attempts.pop(key, None)
            retry_after = self._retry_after.get(key)
            if retry_after is not None and retry_after > now:
                self._known.add(key)
                return
            self._retry_after.pop(key, None)
            self._known.add(key)
            if key in self._pending:
                return
            self._pending.add(key)
        self._queue.put((key, candidate))

    def requeue(self, path: Path) -> None:
        """Return a delivered-but-unmoved file to the stabilizer with backoff.

        The worker marks a candidate done when it emits the ready signal,
        before the controller actually moves the file. When that move fails,
        the path stays known and sweeps ignore it; requeueing registers a
        bounded retry so a transient failure is attempted again.
        """

        normalised = self._normalise_candidate(path)
        if normalised is None:
            return
        _, key = normalised
        with self._lock:
            if key in self._pending:
                return
            self._known.add(key)
            attempt = self._retry_attempts.get(key, 0)
            if attempt < len(self._retry_delays):
                self._retry_attempts[key] = attempt + 1
                self._retry_after[key] = monotonic() + self._retry_delays[attempt]
            else:
                # No attempts left: hand over to the exhausted path so a later
                # sweep notices when the file actually changes.
                self._retry_after.pop(key, None)
                self._retry_attempts.pop(key, None)
                self._retry_exhausted[key] = ExistingDownload.capture(path)

    def enqueue_existing(self, candidates: Sequence[ExistingDownload]) -> int:
        """Queue one explicitly confirmed batch while enforcing the fixed safety cap."""

        if self._stop.is_set() or not self.active:
            return 0
        selected = candidates[:MANUAL_IMPORT_BATCH_LIMIT]
        queued: list[tuple[PathKey, ExistingDownload]] = []
        skipped = 0
        with self._lock:
            if self._manual_pending:
                return 0
            for candidate in selected:
                path = candidate.path
                normalised = self._normalise_candidate(path)
                try:
                    eligible = (
                        normalised is not None
                        and self.config.accepts(path)
                        and candidate.still_matches()
                    )
                except OSError:
                    eligible = False
                if normalised is None:
                    eligible = False
                    key = _path_key(path)
                else:
                    _, key = normalised
                if not eligible or key in self._pending:
                    skipped += 1
                    continue
                self._pending.add(key)
                self._manual_pending.add(key)
                queued.append((key, candidate))
            self._manual_skipped = skipped
            if not queued:
                self._manual_skipped = 0
        for key, candidate in queued:
            self._queue.put((key, candidate))
        return len(queued)

    def _work(self) -> None:
        while not self._stop.is_set():
            try:
                queued = self._queue.get(timeout=0.5)
            except Empty:
                continue
            if queued is None:
                self._queue.task_done()
                return
            key, candidate = queued
            if isinstance(candidate, ExistingDownload):
                manual_candidate = candidate
                path = candidate.path
            else:
                manual_candidate = None
                path = candidate
            delivered = False
            retry = False
            paused_interrupted = False
            try:
                unchanged_before = manual_candidate is None or manual_candidate.still_matches()
                stable = unchanged_before and wait_until_stable(
                    path, minimum_size=self.config.minimum_file_size, stop_event=self._stop
                )
                unchanged_after = manual_candidate is None or manual_candidate.still_matches()
                if (
                    stable
                    and unchanged_after
                    and not self._stop.is_set()
                    and (manual_candidate is not None or not self._paused.is_set())
                ):
                    self.on_ready(candidate)
                    delivered = True
                elif (
                    manual_candidate is None
                    and not self._stop.is_set()
                    and not self._paused.is_set()
                ):
                    retry = True
                elif manual_candidate is None and not self._stop.is_set() and self._paused.is_set():
                    paused_interrupted = True
            except Exception:
                LOGGER.exception("Failed while handling download candidate %s", path)
            finally:
                completed_skips: int | None = None
                retries_exhausted = False
                with self._lock:
                    self._pending.discard(key)
                    # A successful hand-off is not a successful move: the
                    # controller can still fail and requeue the path, so the
                    # bounded retry budget is only cleared once the sweep sees
                    # the file gone (or its identity changed).
                    if paused_interrupted:
                        self._known.add(key)
                        self._paused_seen.add(key)
                    elif retry:
                        attempt = self._retry_attempts.get(key, 0)
                        if attempt < len(self._retry_delays):
                            self._retry_attempts[key] = attempt + 1
                            self._retry_after[key] = monotonic() + self._retry_delays[attempt]
                        else:
                            self._retry_after.pop(key, None)
                            self._retry_attempts.pop(key, None)
                            self._retry_exhausted[key] = ExistingDownload.capture(path)
                            retries_exhausted = True
                    if manual_candidate is not None:
                        was_pending = key in self._manual_pending
                        if was_pending:
                            if not delivered:
                                self._manual_skipped += 1
                            self._manual_pending.discard(key)
                            if not self._manual_pending:
                                completed_skips = self._manual_skipped
                                self._manual_skipped = 0
                self._queue.task_done()
                if retries_exhausted:
                    LOGGER.warning("Download did not stabilize after bounded retries: %s", path)
                if completed_skips is not None and self.on_import_complete is not None:
                    self.on_import_complete(completed_skips)

    def _sweep(self) -> None:
        while not self._stop.wait(20.0):
            self._sweep_once()

    def _sweep_once(self) -> None:
        current = self._snapshot()
        if current is None:
            return
        current_keys = set(current)
        with self._lock:
            now = monotonic()
            self._ignored_until = {
                key: deadline for key, deadline in self._ignored_until.items() if deadline >= now
            }
            expired_retries = {
                key
                for key, deadline in self._retry_after.items()
                if deadline <= now and key in current_keys and key not in self._pending
            }
            for key in expired_retries:
                self._retry_after.pop(key, None)
            changed_exhausted = {
                key
                for key, snapshot in self._retry_exhausted.items()
                if key in current and current[key] != snapshot and key not in self._pending
            }
            for key in changed_exhausted:
                self._retry_exhausted.pop(key, None)
                self._retry_attempts.pop(key, None)
            absent = (set(self._retry_attempts) | set(self._retry_exhausted)) - current_keys
            for key in absent:
                self._retry_after.pop(key, None)
                self._retry_attempts.pop(key, None)
                self._retry_exhausted.pop(key, None)
            new_keys = (current_keys - self._known) | expired_retries | changed_exhausted
            self._known = current_keys | self._pending
        for key in new_keys:
            self.enqueue(current[key].path)

    def _snapshot(self) -> dict[PathKey, ExistingDownload] | None:
        try:
            result: dict[PathKey, ExistingDownload] = {}
            for path in self.config.downloads_dir.iterdir():
                candidate = ExistingDownload.capture_strict(path)
                if candidate is not None:
                    result[_path_key(candidate.path)] = candidate
            return result
        except OSError:
            LOGGER.exception("Could not scan Downloads")
            return None

    def _normalise_candidate(self, path: Path) -> tuple[Path, PathKey] | None:
        try:
            candidate = path.absolute()
            key = _path_key(candidate)
        except (OSError, RuntimeError):
            return None
        if key[0] != self._downloads_key:
            return None
        return candidate, key
