"""Download-completion detection with an exclusive Windows file check."""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path
from threading import Event

from organizador.config import TEMPORARY_SUFFIXES

GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


def can_open_exclusively(path: Path) -> bool:
    """Return whether no other process holds a conflicting file handle."""

    if os.name != "nt":  # pragma: no cover - development fallback
        try:
            with path.open("rb"):
                return True
        except OSError:
            return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    handle = create_file(
        str(path),
        GENERIC_READ,
        0,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        return False
    close_handle(handle)
    return True


def wait_until_stable(
    path: Path,
    *,
    timeout: float = 120.0,
    interval: float = 0.5,
    stable_samples: int = 3,
    stop_event: Event | None = None,
) -> bool:
    """Wait until a file stops changing and is no longer locked.

    Stability is purely "size and mtime unchanged"; size policy (such as the
    configured minimum) belongs to the caller, so a below-minimum file must
    not keep the shared stabilization worker busy for the whole timeout.

    Args:
        path: Candidate final download path.
        timeout: Maximum wait before leaving the file untouched.
        interval: Delay between stat samples.
        stable_samples: Number of identical consecutive samples required.
        stop_event: Optional application shutdown signal.

    Returns:
        True only when the file is stable and exclusively openable.
    """

    lowered = path.name.casefold()
    if any(lowered.endswith(suffix) for suffix in TEMPORARY_SUFFIXES):
        return False

    deadline = time.monotonic() + timeout
    previous: tuple[int, int] | None = None
    unchanged = 0
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            return False
        try:
            stat = path.stat()
        except (FileNotFoundError, PermissionError, OSError):
            unchanged = 0
            previous = None
        else:
            signature = (stat.st_size, stat.st_mtime_ns)
            if signature == previous:
                unchanged += 1
            else:
                unchanged = 0
            previous = signature
            if unchanged >= stable_samples and can_open_exclusively(path):
                return True
        if stop_event is not None:
            stop_event.wait(interval)
        else:
            time.sleep(interval)
    return False
