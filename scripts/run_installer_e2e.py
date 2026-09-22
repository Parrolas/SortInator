"""Exercise the exact Setup artifact in an explicitly disposable Windows account.

This intentionally refuses an account with SortInator data or an installation.
Run on a clean Windows CI runner/VM, never the developer's daily-use account.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import winreg
from collections.abc import Callable
from pathlib import Path

import organizador.updater as updater
from organizador import __version__
from organizador.config import LEGACY_APP_NAME, AppConfig, default_data_dir
from organizador.db import Database
from organizador.filer import FilingService
from organizador.windows_shell import UNINSTALL_KEY


def payload_executable(app_dir: Path) -> Path:
    """Resolve the installed payload executable, preferring its manifest."""

    manifest = app_dir / "update-manifest.json"
    if manifest.is_file():
        try:
            name = json.loads(manifest.read_text(encoding="utf-8")).get("executable")
        except (OSError, ValueError):
            name = None
        if isinstance(name, str) and name:
            candidate = app_dir / name
            if candidate.is_file():
                return candidate
    fallback = app_dir / "SortInator.exe"
    if fallback.is_file():
        return fallback
    raise AssertionError("installed payload has no executable")


def run(executable: Path, *arguments: str, expected: int = 0) -> None:
    result = subprocess.run(
        [str(executable), *arguments], creationflags=subprocess.CREATE_NO_WINDOW, timeout=180
    )
    if result.returncode != expected:
        raise RuntimeError(f"{executable.name} exited {result.returncode}")


def _wait_until(predicate: Callable[[], bool], timeout: float = 60.0) -> None:
    """Inno uninstallers may hand off to a second phase that outlives the first process."""

    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("timed out waiting for the uninstaller to finish")
        time.sleep(0.1)


def verify_artifact(path: Path) -> None:
    expected = Path(str(path) + ".sha256").read_text(encoding="utf-8").split()[0]
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--disposable-account", action="store_true")
    args = parser.parse_args()
    data = default_data_dir()
    if not args.disposable_account:
        parser.error("This test requires --disposable-account on a clean Windows VM/CI runner")
    for candidate in (data, data.parent / LEGACY_APP_NAME):
        if candidate.exists():
            parser.error("Refusing to test in an account with existing SortInator data")
    for key_name in (
        UNINSTALL_KEY,
        r"Software\Classes\sortinator",
        r"Software\Classes\organizador",
    ):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name):
                parser.error("Refusing to replace an existing SortInator installation/registration")
        except FileNotFoundError:
            pass
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
        ) as key:
            for value_name in ("SortInator", "Organizador"):
                try:
                    winreg.QueryValueEx(key, value_name)
                except FileNotFoundError:
                    continue
                parser.error("Refusing to replace an existing SortInator login entry")
    except FileNotFoundError:
        pass
    verify_artifact(args.installer)
    verify_artifact(args.zip)
    root = Path(tempfile.mkdtemp(prefix="sortinator-install-e2e-"))
    install = root / "installed"
    downloads = root / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    # Extraction consumes its input archive; preserve the release artifact.
    update_archive = root / args.zip.name
    shutil.copy2(args.zip.resolve(), update_archive)
    config = AppConfig(
        data_dir=data,
        downloads_dir=downloads,
        university_root=root / "coursework",
        initialized=True,
        check_updates_on_launch=False,
        watch_enabled=False,
    )
    config.ensure_directories()
    config.save()
    database = Database(config.database_path)
    database.initialize()
    filer = FilingService(config, database)
    subject = database.add_subject("Test subject", "TEST", "#087A74", (), "TEST")
    filer.ensure_subject_structure(subject)
    original = config.downloads_dir / "protected.txt"
    original.write_bytes(b"preserve coursework contents" * 20)
    inbox = filer.ingest(original)
    assert inbox is not None
    document = filer.file_document(inbox.id, subject.id, "Outros", original.name)
    original_bytes = document.current_path.read_bytes()
    # Simulate the additive migration from the prior portable catalog.
    with database.connect() as connection:
        connection.execute("DROP TABLE notification_actions")
        connection.commit()
    print(f"Evidence sandbox: {root}", flush=True)
    parameters = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", f"/DIR={install}")
    run(args.installer.resolve(), *parameters, f"/LOG={root / 'install.log'}")
    uninstaller = install / "unins000.exe"
    assert uninstaller.is_file()
    executable = payload_executable(install / "app")
    run(executable, "--smoke-test", "--data-dir", str(data))
    assert database.inspect_schema().is_current
    run(args.installer.resolve(), *parameters, f"/LOG={root / 'reinstall.log'}")
    assert document.current_path.read_bytes() == original_bytes

    transaction = updater.create_update_transaction(
        executable.parent,
        __version__,
        data_dir=data,
        old_pid=2_147_483_647,
    )
    updater.extract_to_staging(update_archive, transaction.staging_dir)
    marker = transaction.staging_dir / "added-by-update.txt"
    marker.write_text("managed update file", encoding="utf-8")
    with (transaction.staging_dir / "runtime-files.txt").open("a", encoding="utf-8") as stream:
        stream.write("added-by-update.txt\n")
    updater.write_update_helper(transaction)
    helper = updater.launch_update_helper(transaction)
    new_pid: int | None = None
    try:
        assert helper.wait(timeout=180) == 0
        result = updater.read_update_result(transaction)
        assert result is not None
        new_pid = result.new_pid
        assert result.status is updater.UpdateResultStatus.SUCCEEDED
        assert uninstaller.is_file()
        assert (executable.parent / marker.name).is_file()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            assert winreg.QueryValueEx(key, "DisplayVersion")[0] == __version__
    finally:
        if helper.poll() is None:
            helper.terminate()
        if new_pid is not None:
            # Only the idle fixture app launched by this transaction; no transfers pending.
            subprocess.run(
                ["taskkill.exe", "/PID", str(new_pid), "/F"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True,
                check=False,
            )
            time.sleep(1)
    run(
        uninstaller,
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        f"/LOG={root / 'uninstall.log'}",
    )
    _wait_until(lambda: not (executable.parent / marker.name).exists())
    assert not executable.exists()
    assert document.current_path.read_bytes() == original_bytes
    assert config.database_path.is_file()
    assert AppConfig.load(data).university_root == config.university_root
    run(args.installer.resolve(), *parameters, f"/LOG={root / 'restore-install.log'}")
    run(executable, "--smoke-test", "--data-dir", str(data))
    assert database.get_file(document.id) is not None
    run(uninstaller, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
    _wait_until(lambda: not executable.exists())
    print("PASS: install, migration, reinstall, real update, uninstall and data reuse", flush=True)
    print(f"Fixture data and logs retained in disposable account: {root}", flush=True)


if __name__ == "__main__":
    main()
