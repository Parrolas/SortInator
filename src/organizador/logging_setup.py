"""Early rotating logging and frozen-safe uncaught exception handling."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

LOGGER = logging.getLogger(__name__)
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(data_dir: Path) -> None:
    """Configure one rotating log handler for the selected application data folder."""

    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = (data_dir / "sortinator.log").resolve()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for existing in root.handlers:
        if not isinstance(existing, RotatingFileHandler):
            continue
        try:
            existing_path = Path(existing.baseFilename).resolve()
        except OSError:
            continue
        if existing_path == log_path:
            return

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_500_000,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)


def log_uncaught_exception(
    exception_type: type[BaseException],
    exception: BaseException,
    traceback: TracebackType | None,
) -> None:
    """Persist otherwise invisible exceptions from a windowed executable."""

    LOGGER.critical(
        "Unhandled exception",
        exc_info=(exception_type, exception, traceback),
    )
    if sys.stderr is not None:
        sys.__excepthook__(exception_type, exception, traceback)
