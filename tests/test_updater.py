"""Transactional updater tests; every filesystem operation stays under pytest temp paths."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from contextlib import suppress
from pathlib import Path

import pytest

from organizador import __version__, updater
from organizador.updater import UpdaterError


class _FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._data) - self._pos
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _make_app_layout(path: Path, *, executable: bytes = b"app binary") -> Path:
    path.mkdir(parents=True)
    (path / "Organizador.exe").write_bytes(executable)
    (path / "_internal").mkdir()
    (path / "_internal" / "placeholder.txt").write_text("internal", encoding="utf-8")
    return path


def _make_zip_bytes(
    members: dict[str, bytes] | None = None,
    *,
    extra_infos: list[tuple[zipfile.ZipInfo, bytes]] | None = None,
) -> bytes:
    files = members or {
        "Organizador.exe": b"app binary",
        "_internal/placeholder.txt": b"internal data",
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        for info, data in extra_infos or []:
            archive.writestr(info, data)
    return buffer.getvalue()


def _fake_release(
    version: str,
    *,
    assets: list[dict[str, object]] | None = None,
) -> bytes:
    archive_name = f"Organizador-{version}-windows-x64.zip"
    release_assets = assets
    if release_assets is None:
        release_assets = [
            {
                "name": archive_name,
                "browser_download_url": f"https://example.invalid/{archive_name}",
            },
            {
                "name": f"{archive_name}.sha256",
                "browser_download_url": f"https://example.invalid/{archive_name}.sha256",
            },
        ]
    return json.dumps({"tag_name": f"v{version}", "assets": release_assets}).encode()


def _newer_version() -> str:
    current = updater.version_tuple(__version__)
    assert current is not None
    return f"{current[0]}.{current[1]}.{current[2] + 1}"


def _fake_urlopen_from(data: bytes) -> Callable[..., _FakeResponse]:
    def fake_urlopen(_request: object, **_kwargs: object) -> _FakeResponse:
        return _FakeResponse(data)

    return fake_urlopen


@pytest.fixture
def app_dir(tmp_path: Path) -> Iterator[Path]:
    path = _make_app_layout(tmp_path / "Renamed Install % ção")
    yield path
    updater.installation_lock_path(path).unlink(missing_ok=True)


def test_version_tuple_requires_exactly_three_numeric_parts() -> None:
    assert updater.version_tuple("v0.6.2") == (0, 6, 2)
    assert updater.version_tuple("10.20.30") == (10, 20, 30)
    for malformed in ("0.6", "0.6.2.1", "v0.6.2-alpha", "V0.6.2", " 0.6.2", "1..2"):
        assert updater.version_tuple(malformed) is None


def test_typed_check_result_returns_exact_versioned_asset_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = _newer_version()
    decoy = {
        "name": "Organizador-99.99.99-windows-x64.zip",
        "browser_download_url": "https://example.invalid/decoy.zip",
    }
    payload = json.loads(_fake_release(version))
    payload["assets"].insert(0, decoy)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        _fake_urlopen_from(json.dumps(payload).encode()),
    )

    result = updater.check_latest_release()

    assert result.status is updater.UpdateCheckStatus.UPDATE_AVAILABLE
    assert result.error is None
    assert result.update is not None
    assert result.info is result.update
    assert result.update.version == tuple(int(part) for part in version.split("."))
    assert result.update.zip_url.endswith(f"Organizador-{version}-windows-x64.zip")
    assert updater.fetch_latest_release() == result.update


def test_typed_check_result_distinguishes_no_update_from_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        _fake_urlopen_from(_fake_release(__version__)),
    )
    no_update = updater.check_latest_release()
    assert no_update == updater.UpdateCheckResult(updater.UpdateCheckStatus.NO_UPDATE)

    def raise_offline(_request: object, **_kwargs: object) -> _FakeResponse:
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", raise_offline)
    failed = updater.check_latest_release()
    assert failed.status is updater.UpdateCheckStatus.ERROR
    assert failed.update is None
    assert failed.error == "offline"
    assert updater.fetch_latest_release() is None


@pytest.mark.parametrize(
    "payload,error_fragment",
    [
        (b"[]", "not an object"),
        (b"{}", "tag_name"),
        (json.dumps({"tag_name": "v1.2", "assets": []}).encode(), "three-part"),
        (json.dumps({"tag_name": "v99.0.0", "assets": {}}).encode(), "assets"),
        (_fake_release("99.0.0", assets=[]), "exact ZIP/checksum pair"),
        (
            _fake_release(
                "99.0.0",
                assets=[
                    {
                        "name": "Organizador-v99.0.0-windows-x64.zip",
                        "browser_download_url": "https://example.invalid/wrong.zip",
                    },
                    {
                        "name": "Organizador-v99.0.0-windows-x64.zip.sha256",
                        "browser_download_url": "https://example.invalid/wrong.sha256",
                    },
                ],
            ),
            "exact ZIP/checksum pair",
        ),
    ],
)
def test_check_latest_release_reports_malformed_release_data(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    error_fragment: str,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_from(payload))
    result = updater.check_latest_release()
    assert result.status is updater.UpdateCheckStatus.ERROR
    assert result.error is not None and error_fragment in result.error


def test_check_result_rejects_inconsistent_typed_states() -> None:
    with pytest.raises(ValueError, match="requires update"):
        updater.UpdateCheckResult(updater.UpdateCheckStatus.UPDATE_AVAILABLE)
    with pytest.raises(ValueError, match="requires an error"):
        updater.UpdateCheckResult(updater.UpdateCheckStatus.ERROR)


def test_download_and_verify_accepts_matching_checksum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = _make_zip_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    bodies = {
        "https://example.invalid/app.zip": payload,
        "https://example.invalid/app.zip.sha256": f"{digest}  app.zip".encode(),
    }

    def fake_urlopen(request: object, **_kwargs: object) -> _FakeResponse:
        return _FakeResponse(bodies[str(getattr(request, "full_url", ""))])

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    zip_path = updater.download_and_verify(
        "https://example.invalid/app.zip",
        "https://example.invalid/app.zip.sha256",
        tmp_path,
    )
    assert zip_path.read_bytes() == payload


@pytest.mark.parametrize(
    "checksum",
    [
        b"0" * 64 + b"  app.zip",
        b"not-a-digest  app.zip",
        b"0" * 64 + b"  another.zip",
    ],
)
def test_download_and_verify_rejects_bad_or_mispaired_checksum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    checksum: bytes,
) -> None:
    payload = _make_zip_bytes()

    def fake_urlopen(request: object, **_kwargs: object) -> _FakeResponse:
        url = str(getattr(request, "full_url", ""))
        return _FakeResponse(checksum if url.endswith(".sha256") else payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(UpdaterError, match=r"verificação|verificar"):
        updater.download_and_verify(
            "https://example.invalid/app.zip",
            "https://example.invalid/app.zip.sha256",
            tmp_path,
        )
    assert not (tmp_path / "organizador-update.zip").exists()
    assert list(tmp_path.glob("*.part")) == []


def test_download_is_bounded_and_removes_partial_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(updater, "MAX_DOWNLOAD_BYTES", 3)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        _fake_urlopen_from(b"four"),
    )
    with pytest.raises(UpdaterError, match="limite"):
        updater.download_and_verify("https://example.invalid/app.zip", "unused", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_extract_to_staging_accepts_unicode_spaces_and_percent_paths(tmp_path: Path) -> None:
    zip_path = tmp_path / "pacote % ç.zip"
    zip_path.write_bytes(
        _make_zip_bytes(
            {
                "Organizador.exe": b"new app",
                "_internal/pasta % espaço/ação.txt": "conteúdo".encode(),
            }
        )
    )
    staging = tmp_path / "instalação temporária %"
    result = updater.extract_to_staging(zip_path, staging)
    assert result == staging.resolve()
    extracted = staging / "_internal" / "pasta % espaço" / "ação.txt"
    assert extracted.read_text(encoding="utf-8") == "conteúdo"
    assert not zip_path.exists()


@pytest.mark.parametrize(
    "member",
    [
        "../escape.txt",
        "folder/../../escape.txt",
        "..\\escape.txt",
        "/absolute.txt",
        "C:\\absolute.txt",
        "folder/unsafe:stream.txt",
        "folder/trailing. /file.txt",
    ],
)
def test_extract_rejects_archive_traversal_and_windows_unsafe_paths(
    tmp_path: Path,
    member: str,
) -> None:
    zip_path = tmp_path / "bad.zip"
    zip_path.write_bytes(_make_zip_bytes({member: b"escape"}))
    staging = tmp_path / "staging"
    with pytest.raises(UpdaterError, match="inseguro"):
        updater.extract_to_staging(zip_path, staging)
    assert not staging.exists()
    assert not zip_path.exists()
    assert not (tmp_path / "escape.txt").exists()


def test_extract_rejects_symlinks_and_case_collisions(tmp_path: Path) -> None:
    symlink = zipfile.ZipInfo("_internal/link")
    symlink.create_system = 3
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
    symlink_zip = tmp_path / "symlink.zip"
    symlink_zip.write_bytes(_make_zip_bytes(extra_infos=[(symlink, b"target")]))
    with pytest.raises(UpdaterError, match="tipo"):
        updater.extract_to_staging(symlink_zip, tmp_path / "symlink-staging")

    collision_zip = tmp_path / "collision.zip"
    collision_zip.write_bytes(
        _make_zip_bytes(
            {
                "Organizador.exe": b"app",
                "_internal/A.txt": b"first",
                "_internal/a.TXT": b"second",
            }
        )
    )
    with pytest.raises(UpdaterError, match="duplicados"):
        updater.extract_to_staging(collision_zip, tmp_path / "collision-staging")


@pytest.mark.parametrize(
    ("limits", "message"),
    [
        ({"max_members": 1}, "demasiados"),
        ({"max_file_size": 3}, "Um ficheiro"),
        ({"max_total_size": 5}, "extraída"),
    ],
)
def test_extract_enforces_member_file_and_total_limits(
    tmp_path: Path,
    limits: dict[str, int],
    message: str,
) -> None:
    zip_path = tmp_path / f"limited-{message}.zip"
    zip_path.write_bytes(_make_zip_bytes())
    with pytest.raises(UpdaterError, match=message):
        updater.extract_to_staging(zip_path, tmp_path / f"stage-{message}", **limits)


def test_extract_removes_invalid_layout(tmp_path: Path) -> None:
    zip_path = tmp_path / "incomplete.zip"
    zip_path.write_bytes(_make_zip_bytes({"Organizador.exe": b"app"}))
    staging = tmp_path / "staging"
    with pytest.raises(UpdaterError, match="instalação completa"):
        updater.extract_to_staging(zip_path, staging)
    assert not staging.exists()


def test_app_directory_validates_layout_without_requiring_folder_name(
    monkeypatch: pytest.MonkeyPatch,
    app_dir: Path,
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app_dir / "Organizador.exe"))
    assert updater.app_directory() == app_dir.resolve()
    assert updater.validate_app_directory(app_dir) == app_dir.resolve()

    (app_dir / "Organizador.exe").unlink()
    assert updater.app_directory() is None
    with pytest.raises(UpdaterError, match="instalação completa"):
        updater.validate_app_directory(app_dir)


def test_create_transaction_uses_unique_siblings_and_persists_optional_receipt(
    app_dir: Path,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "dados com espaço % ç"
    receipt = data_dir / "recovery-receipt.json"
    first = updater.create_update_transaction(
        app_dir,
        "v0.6.2",
        data_dir=data_dir,
        recovery_receipt_path=receipt,
    )
    assert first.version == (0, 6, 2)
    assert first.staging_dir.parent == app_dir.parent
    assert first.rollback_dir.parent == app_dir.parent
    assert first.staging_dir != first.rollback_dir
    assert first.state_dir not in {first.staging_dir, first.rollback_dir, first.app_dir}
    assert first.recovery_receipt_path == receipt.resolve()
    assert updater.read_update_transaction(first.manifest_path) == first
    assert list(first.state_dir.glob("*.tmp")) == []

    updater.release_installation_lock(first)
    second = updater.create_update_transaction(app_dir, (0, 6, 2))
    try:
        assert second.transaction_id != first.transaction_id
        assert second.staging_dir != first.staging_dir
        assert second.rollback_dir != first.rollback_dir
    finally:
        updater.release_installation_lock(second)


def test_installation_lock_records_owner_and_rejects_contention(app_dir: Path) -> None:
    live_pid = os.getpid()
    first = updater.acquire_installation_lock(
        app_dir,
        transaction_id="tx-one",
        token="secret-one",
        manifest_path=app_dir.parent / "state" / "transaction.json",
        pid=live_pid,
    )
    stored = updater.read_installation_lock(first.path)
    assert stored == first
    assert stored is not None and stored.pid == live_pid

    with pytest.raises(UpdaterError, match=rf"tx-one.*{live_pid}"):
        updater.acquire_installation_lock(app_dir, transaction_id="tx-two")

    impostor = updater.InstallationLock(
        path=first.path,
        transaction_id=first.transaction_id,
        token="wrong-token",
        pid=first.pid,
        created_at=first.created_at,
        app_dir=first.app_dir,
        manifest_path=first.manifest_path,
    )
    assert updater.release_installation_lock(impostor) is False
    assert first.path.exists()
    assert updater.release_installation_lock(first) is True


def test_installation_lock_takes_over_stale_or_malformed_locks(app_dir: Path) -> None:
    dead = updater.acquire_installation_lock(
        app_dir,
        transaction_id="tx-dead",
        token="secret-dead",
        manifest_path=app_dir.parent / "state" / "transaction.json",
        pid=2_147_483_647,
    )
    try:
        assert updater.is_lock_stale(updater.read_installation_lock(dead.path)) is True
        taken = updater.acquire_installation_lock(app_dir, transaction_id="tx-live")
        try:
            assert taken.transaction_id == "tx-live"
            assert updater.read_installation_lock(taken.path) == taken
        finally:
            updater.release_installation_lock(taken)
    finally:
        updater.release_installation_lock(dead)

    first = updater.acquire_installation_lock(app_dir, transaction_id="tx-fresh")
    try:
        assert updater.is_lock_stale(updater.read_installation_lock(first.path)) is False
    finally:
        updater.release_installation_lock(first)

    malformed = updater.installation_lock_path(app_dir.resolve())
    malformed.write_text("not json", encoding="utf-8")
    recovered = updater.acquire_installation_lock(app_dir, transaction_id="tx-recovered")
    try:
        assert recovered.transaction_id == "tx-recovered"
    finally:
        updater.release_installation_lock(recovered)


def _sample_result(transaction: updater.UpdateTransaction) -> updater.UpdateResult:
    return updater.UpdateResult(
        transaction_id=transaction.transaction_id,
        status=updater.UpdateResultStatus.ROLLED_BACK,
        phase="wait_ready",
        committed=False,
        rollback_succeeded=True,
        error="ready timeout",
        old_pid=transaction.old_pid,
        new_pid=4321,
        started_at="2026-09-03T00:00:00+00:00",
        finished_at="2026-09-03T00:00:01+00:00",
        app_dir=transaction.app_dir,
        rollback_dir=transaction.rollback_dir,
        recovery_receipt_path=transaction.recovery_receipt_path,
    )


def test_result_round_trip_and_seen_timestamp_are_atomic(app_dir: Path) -> None:
    transaction = updater.create_update_transaction(app_dir, "0.6.2")
    try:
        assert updater.read_update_result(transaction) is None
        expected = _sample_result(transaction)
        updater.write_update_result(transaction.result_path, expected)
        assert updater.read_result(transaction.result_path) == expected

        seen = updater.mark_result_seen(transaction)
        assert seen is not None and seen.seen_at is not None
        assert updater.read_update_result(transaction) == seen
        assert updater.mark_update_result_seen(transaction) == seen
        assert list(transaction.state_dir.glob("*.tmp")) == []
    finally:
        updater.release_installation_lock(transaction)


def test_marker_functions_require_token_and_complete_protocol(app_dir: Path) -> None:
    transaction = updater.create_update_transaction(app_dir, "0.6.2")
    try:
        with pytest.raises(UpdaterError, match="token"):
            updater.mark_update_ready(transaction.manifest_path, "wrong")
        ready = updater.mark_update_ready(transaction.manifest_path, transaction.token, pid=77)
        ready_payload = json.loads(ready.read_text(encoding="utf-8"))
        assert ready_payload["pid"] == 77
        assert not updater.wait_for_update_commit(
            transaction.manifest_path,
            transaction.token,
            timeout_seconds=0.01,
            poll_seconds=0.001,
        )

        commit_payload = {
            "schema_version": 1,
            "transaction_id": transaction.transaction_id,
            "token": transaction.token,
        }
        transaction.commit_path.write_text(json.dumps(commit_payload), encoding="utf-8")
        assert updater.wait_for_update_commit(transaction.manifest_path, transaction.token)
        assert updater.mark_update_healthy(
            transaction.manifest_path,
            transaction.token,
            pid=88,
        ).is_file()
    finally:
        updater.release_installation_lock(transaction)


def test_helper_is_transaction_specific_and_utf8_bom_encoded(app_dir: Path) -> None:
    transaction = updater.create_update_transaction(app_dir, "0.6.2")
    try:
        helper = updater.write_update_helper(transaction)
        raw = helper.read_bytes()
        content = raw.decode("utf-8-sig")
        assert raw.startswith(b"\xef\xbb\xbf")
        assert helper.parent == transaction.state_dir
        assert str(transaction.manifest_path).replace("'", "''") in content
        assert "Get-Process -Id ([int]$script:Transaction.old_pid)" in content
        assert "Stop-Process -Id $script:NewProcess.Id" in content
        assert "--data-dir" in content
        assert "--update-manifest" in content
        assert "--update-token" in content
        assert "Move-DirectoryWithRetry" in content
        assert "Wait-ForMarker" in content
        assert "failed_after_commit" in content
        assert b"\r\n" in raw
    finally:
        updater.release_installation_lock(transaction)


def test_launch_helper_uses_required_powershell_flags_and_safe_cwd(
    monkeypatch: pytest.MonkeyPatch,
    app_dir: Path,
) -> None:
    transaction = updater.create_update_transaction(app_dir, "0.6.2")
    updater.write_update_helper(transaction)
    captured: dict[str, object] = {}
    waited: dict[str, object] = {}

    class _Process:
        pass

    def fake_popen(arguments: list[str], **kwargs: object) -> _Process:
        captured["arguments"] = arguments
        captured.update(kwargs)
        return _Process()

    def fake_wait(
        waited_transaction: updater.UpdateTransaction, *, timeout_seconds: float = 0.0
    ) -> bool:
        waited["transaction"] = waited_transaction
        waited["timeout_seconds"] = timeout_seconds
        return True

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(updater, "wait_for_helper_ready", fake_wait)
    try:
        updater.launch_update_helper(transaction, powershell_executable="Power Shell.exe")
    finally:
        updater.release_installation_lock(transaction)

    arguments = captured["arguments"]
    assert isinstance(arguments, list)
    assert arguments[:7] == [
        "Power Shell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(transaction.helper_path),
    ]
    assert arguments[-4:] == [
        "-ManifestPath",
        str(transaction.manifest_path),
        "-Token",
        transaction.token,
    ]
    assert captured["cwd"] == transaction.state_dir
    assert waited["transaction"] is transaction
    assert waited["timeout_seconds"] == 30.0
    assert transaction.state_dir not in {
        transaction.app_dir,
        transaction.staging_dir,
        transaction.rollback_dir,
    }


def test_legacy_controller_wrappers_remain_callable(
    monkeypatch: pytest.MonkeyPatch,
    app_dir: Path,
    tmp_path: Path,
) -> None:
    legacy_staging = _make_app_layout(app_dir.parent / "Organizador.update", executable=b"new")
    data_dir = tmp_path / "Dados % ç com espaços"
    monkeypatch.setattr(sys, "argv", ["Organizador.exe", "--data-dir", str(data_dir)])
    helper = updater.write_swap_script(app_dir, legacy_staging)
    transaction = updater.read_update_transaction(helper.parent / "transaction.json")
    try:
        assert helper.suffix == ".ps1"
        assert transaction.staging_dir == legacy_staging.resolve()
        assert transaction.data_dir == data_dir.resolve()
    finally:
        updater.release_installation_lock(transaction)


def test_cleanup_previous_version_only_removes_legacy_rollback(tmp_path: Path) -> None:
    app = _make_app_layout(tmp_path / "Any Name")
    old_dir = _make_app_layout(tmp_path / "Organizador.old", executable=b"old")
    transaction_rollback = _make_app_layout(tmp_path / ".Any Name.update-id.rollback")
    updater.cleanup_previous_version(app)
    assert not old_dir.exists()
    assert transaction_rollback.exists()


def test_prune_completed_rollback_directories_removes_only_healthy_leftovers(
    tmp_path: Path,
) -> None:
    app = _make_app_layout(tmp_path / "App")
    data_dir = tmp_path / "dados"
    healthy_id = "a" * 32
    failed_id = "b" * 32
    orphan_id = "c" * 32
    healthy = _make_app_layout(tmp_path / f".App.update-{healthy_id}.rollback")
    failed = _make_app_layout(tmp_path / f".App.update-{failed_id}.rollback")
    orphan = _make_app_layout(tmp_path / f".App.update-{orphan_id}.rollback")
    for transaction_id, status in (
        (healthy_id, "succeeded"),
        (failed_id, "failed_after_commit"),
    ):
        state = data_dir / "updates" / transaction_id
        state.mkdir(parents=True)
        (state / "result.json").write_text(
            json.dumps({"transaction_id": transaction_id, "status": status}),
            encoding="utf-8",
        )

    removed = updater.prune_completed_rollback_directories(app, data_dir)

    assert removed == (healthy,)
    assert not healthy.exists()
    assert failed.exists()
    assert orphan.exists()
    assert updater.prune_completed_rollback_directories(app, data_dir) == ()


def test_prune_completed_rollback_directories_ignores_unknown_names(tmp_path: Path) -> None:
    app = _make_app_layout(tmp_path / "App")
    intruder = _make_app_layout(tmp_path / ".App.update-not-a-transaction.rollback")
    legacy = _make_app_layout(tmp_path / "Organizador.old")

    assert updater.prune_completed_rollback_directories(app, tmp_path / "dados") == ()
    assert intruder.exists()
    assert legacy.exists()


def test_update_result_preserves_cleanup_deferred(app_dir: Path) -> None:
    transaction = updater.create_update_transaction(app_dir, "0.6.2")
    try:
        result = updater.UpdateResult(
            transaction_id=transaction.transaction_id,
            status=updater.UpdateResultStatus.SUCCEEDED,
            phase="complete",
            committed=True,
            rollback_succeeded=None,
            error=None,
            old_pid=transaction.old_pid,
            new_pid=None,
            started_at=updater._utc_now(),
            finished_at=updater._utc_now(),
            app_dir=transaction.app_dir,
            rollback_dir=transaction.rollback_dir,
            cleanup_deferred=True,
        )
        updater.write_update_result(transaction.result_path, result)

        restored = updater.read_update_result(transaction)
        assert restored is not None
        assert restored.cleanup_deferred is True
        assert updater.mark_update_result_seen(transaction) is not None
        reloaded = updater.read_update_result(transaction)
        assert reloaded is not None
        assert reloaded.cleanup_deferred is True
    finally:
        updater.release_installation_lock(transaction)


def _powershell_path() -> str | None:
    if sys.platform != "win32":
        return None
    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(candidate) if candidate.is_file() else shutil.which("powershell.exe")


@pytest.fixture(scope="session")
def sleeping_executable(tmp_path_factory: pytest.TempPathFactory) -> Path:
    powershell = _powershell_path()
    if powershell is None:
        pytest.skip("Windows PowerShell is required for the helper integration tests")
    build_dir = tmp_path_factory.mktemp("updater-helper-target")
    source = build_dir / "Target.cs"
    executable = build_dir / "Organizador.exe"
    source.write_text(
        """
using System;
using System.IO;
using System.Threading;
public static class Program {
    public static int Main(string[] args) {
        for (int i = 0; i + 1 < args.Length; i++) {
            if (args[i] == "--data-dir") {
                Directory.CreateDirectory(args[i + 1]);
                File.WriteAllLines(Path.Combine(args[i + 1], "launched-args.txt"), args);
            }
        }
        Thread.Sleep(15000);
        return 0;
    }
}
""".strip(),
        encoding="utf-8",
    )
    command = (
        "Add-Type -Path "
        + "'"
        + str(source).replace("'", "''")
        + "' -OutputAssembly '"
        + str(executable).replace("'", "''")
        + "' -OutputType WindowsApplication"
    )
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0 or not executable.is_file():
        pytest.skip(f"could not compile isolated helper target: {completed.stderr.strip()}")
    return executable


def _start_old_process(powershell: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", "Start-Sleep -Seconds 15"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _terminate_exact_pid(pid: int | None) -> None:
    if pid is None:
        return
    with suppress(OSError):
        os.kill(pid, signal.SIGTERM)


def _wait_until(predicate: Callable[[], bool], timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("timed out waiting for updater integration condition")
        time.sleep(0.025)


def _wait_helper(
    helper: subprocess.Popen[bytes], transaction: updater.UpdateTransaction, timeout: float = 60.0
) -> int:
    """Wait for the helper, dumping transaction state when endpoint holds strike."""

    try:
        result = helper.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if transaction.state_dir.is_dir():
            state = sorted(path.name for path in transaction.state_dir.iterdir())
        else:
            state = ["<state dir missing>"]
        result_path = transaction.result_path
        recorded = (
            result_path.read_text(encoding="utf-8") if result_path.is_file() else "<no result>"
        )
        raise AssertionError(
            f"helper timed out after {timeout}s; state={state}; result={recorded}"
        ) from None
    assert result is not None
    return result


def test_real_powershell_helper_waits_exact_pid_and_completes_handshake(
    tmp_path: Path,
    sleeping_executable: Path,
) -> None:
    powershell = _powershell_path()
    assert powershell is not None
    root = tmp_path / "pai ç % com espaços"
    app = _make_app_layout(root / "Minha App", executable=b"old executable")
    data_dir = root / "dados ç % com espaços"
    old_process = _start_old_process(powershell)
    transaction = updater.create_update_transaction(
        app,
        "0.6.2",
        data_dir=data_dir,
        old_pid=old_process.pid,
        old_process_timeout_seconds=10,
        ready_timeout_seconds=10,
        healthy_timeout_seconds=10,
        move_retry_seconds=0.05,
    )
    _make_app_layout(transaction.staging_dir, executable=sleeping_executable.read_bytes())
    updater.write_update_helper(transaction)
    helper = updater.launch_update_helper(transaction, powershell_executable=powershell)
    result: updater.UpdateResult | None = None
    try:
        time.sleep(0.25)
        assert app.is_dir(), "the helper must not move the app before the captured PID exits"
        assert transaction.staging_dir.is_dir()
        old_process.terminate()
        old_process.wait(timeout=5)
        _wait_until(
            lambda: transaction.rollback_dir.is_dir() and not transaction.staging_dir.exists()
        )
        updater.mark_update_ready(transaction.manifest_path, transaction.token, pid=555)
        assert updater.wait_for_update_commit(
            transaction.manifest_path,
            transaction.token,
            timeout_seconds=30,
        )
        updater.mark_update_healthy(transaction.manifest_path, transaction.token, pid=555)
        assert _wait_helper(helper, transaction) == 0
        result = updater.read_update_result(transaction)
        assert result is not None
        assert result.status is updater.UpdateResultStatus.SUCCEEDED
        assert result.committed is True
        assert result.rollback_succeeded is None
        assert not transaction.rollback_dir.exists()
        assert not transaction.lock_path.exists()
        args_path = data_dir / "launched-args.txt"
        _wait_until(args_path.is_file)
        launched_args = args_path.read_text(encoding="utf-8-sig").splitlines()
        assert launched_args == [
            "--background",
            "--data-dir",
            str(data_dir),
            "--update-manifest",
            str(transaction.manifest_path),
            "--update-token",
            transaction.token,
        ]
    finally:
        if old_process.poll() is None:
            old_process.terminate()
        if helper.poll() is None:
            helper.terminate()
        _terminate_exact_pid(result.new_pid if result is not None else None)
        updater.release_installation_lock(transaction)


def test_real_powershell_helper_rolls_back_when_ready_never_arrives(
    tmp_path: Path,
    sleeping_executable: Path,
) -> None:
    powershell = _powershell_path()
    assert powershell is not None
    app = _make_app_layout(tmp_path / "rollback % ç" / "App", executable=b"old executable")
    transaction = updater.create_update_transaction(
        app,
        "0.6.2",
        data_dir=tmp_path / "relaunch-data",
        old_pid=2_147_483_647,
        ready_timeout_seconds=0.35,
        healthy_timeout_seconds=1,
        move_retry_seconds=0.05,
    )
    _make_app_layout(transaction.staging_dir, executable=sleeping_executable.read_bytes())
    updater.write_update_helper(transaction)
    helper = updater.launch_update_helper(transaction, powershell_executable=powershell)
    try:
        assert _wait_helper(helper, transaction) == 10
        result = updater.read_update_result(transaction)
        assert result is not None
        assert result.status is updater.UpdateResultStatus.ROLLED_BACK
        assert result.phase == "wait_ready"
        assert result.committed is False
        assert result.rollback_succeeded is True
        assert "ready" in (result.error or "")
        assert (app / "Organizador.exe").read_bytes() == b"old executable"
        assert transaction.staging_dir.is_dir()
        assert not transaction.rollback_dir.exists()
        assert not transaction.lock_path.exists()

        aged = time.time() - 8 * 86400.0
        os.utime(transaction.state_dir, (aged, aged))
        removed = updater.prune_abandoned_update_state(tmp_path / "relaunch-data")
        assert transaction.staging_dir in removed
        assert not transaction.staging_dir.exists()
        assert (app / "Organizador.exe").read_bytes() == b"old executable"
    finally:
        if helper.poll() is None:
            helper.terminate()
        updater.release_installation_lock(transaction)


def test_real_powershell_helper_rolls_back_after_commit_failure(
    tmp_path: Path,
    sleeping_executable: Path,
) -> None:
    powershell = _powershell_path()
    assert powershell is not None
    # The restored previous version is itself runnable here, so the helper's
    # relaunch can be observed through its argument log. The relaunched
    # sleeper exits alone after 15 seconds; nothing else in the test needs it.
    app = _make_app_layout(
        tmp_path / "post commit % ç" / "App",
        executable=sleeping_executable.read_bytes(),
    )
    data_dir = tmp_path / "relaunch % ç data"
    transaction = updater.create_update_transaction(
        app,
        "0.6.2",
        data_dir=data_dir,
        old_pid=2_147_483_647,
        ready_timeout_seconds=5,
        healthy_timeout_seconds=0.35,
        move_retry_seconds=0.05,
    )
    _make_app_layout(transaction.staging_dir, executable=sleeping_executable.read_bytes())
    updater.write_update_helper(transaction)
    helper = updater.launch_update_helper(transaction, powershell_executable=powershell)
    result: updater.UpdateResult | None = None
    try:
        _wait_until(
            lambda: transaction.rollback_dir.is_dir() and not transaction.staging_dir.exists()
        )
        updater.mark_update_ready(transaction.manifest_path, transaction.token)
        assert updater.wait_for_update_commit(
            transaction.manifest_path,
            transaction.token,
            timeout_seconds=30,
        )
        assert _wait_helper(helper, transaction) == 10
        result = updater.read_update_result(transaction)
        assert result is not None
        assert result.status is updater.UpdateResultStatus.ROLLED_BACK
        assert result.phase == "wait_healthy"
        assert result.committed is True
        assert result.rollback_succeeded is True
        assert (app / "Organizador.exe").read_bytes() == sleeping_executable.read_bytes()
        assert transaction.staging_dir.is_dir()
        assert not transaction.rollback_dir.exists()
        assert not transaction.lock_path.exists()
        args_path = data_dir / "launched-args.txt"
        _wait_until(args_path.is_file, timeout=30.0)
        assert args_path.read_text(encoding="utf-8-sig").splitlines() == [
            "--background",
            "--data-dir",
            str(data_dir),
        ]
    finally:
        if helper.poll() is None:
            helper.terminate()
        _terminate_exact_pid(result.new_pid if result is not None else None)
        updater.release_installation_lock(transaction)


def test_real_powershell_helper_keeps_healthy_install_when_cleanup_fails(
    tmp_path: Path,
    sleeping_executable: Path,
) -> None:
    powershell = _powershell_path()
    assert powershell is not None
    app = _make_app_layout(tmp_path / "deferred % ç" / "App", executable=b"old executable")
    data_dir = tmp_path / "deferred % ç data"
    transaction = updater.create_update_transaction(
        app,
        "0.6.2",
        data_dir=data_dir,
        old_pid=2_147_483_647,
        ready_timeout_seconds=5,
        healthy_timeout_seconds=5,
        move_attempts=2,
        move_retry_seconds=0.05,
    )
    _make_app_layout(transaction.staging_dir, executable=sleeping_executable.read_bytes())
    updater.write_update_helper(transaction)
    helper = updater.launch_update_helper(transaction, powershell_executable=powershell)
    folder_holder: subprocess.Popen[bytes] | None = None
    result: updater.UpdateResult | None = None
    try:
        _wait_until(
            lambda: transaction.rollback_dir.is_dir() and not transaction.staging_dir.exists()
        )
        # A process with its working directory inside the rollback folder
        # keeps Windows from deleting it, simulating a locked old file.
        folder_holder = subprocess.Popen(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", "Start-Sleep -Seconds 20"],
            cwd=str(transaction.rollback_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        updater.mark_update_ready(transaction.manifest_path, transaction.token)
        assert updater.wait_for_update_commit(
            transaction.manifest_path,
            transaction.token,
            timeout_seconds=30,
        )
        updater.mark_update_healthy(transaction.manifest_path, transaction.token)
        assert _wait_helper(helper, transaction) == 0
        result = updater.read_update_result(transaction)
        assert result is not None
        assert result.status is updater.UpdateResultStatus.SUCCEEDED
        assert result.phase == "complete"
        assert result.committed is True
        assert result.cleanup_deferred is True
        # The healthy new installation stays in place and the retained old
        # copy is swept by a later launch.
        assert (app / "Organizador.exe").read_bytes() == sleeping_executable.read_bytes()
        assert transaction.rollback_dir.is_dir()
        assert not transaction.lock_path.exists()
        assert updater.prune_completed_rollback_directories(app, data_dir) == ()
        folder_holder.terminate()
        folder_holder.wait(timeout=10)
        folder_holder = None
        _wait_until(
            lambda: (
                updater.prune_completed_rollback_directories(app, data_dir)
                == (transaction.rollback_dir,)
            ),
            timeout=10.0,
        )
        assert not transaction.rollback_dir.exists()
    finally:
        if helper.poll() is None:
            helper.terminate()
        if folder_holder is not None and folder_holder.poll() is None:
            folder_holder.terminate()
        _terminate_exact_pid(result.new_pid if result is not None else None)
        updater.release_installation_lock(transaction)


def test_real_powershell_helper_keeps_healthy_install_when_receipt_write_fails(
    tmp_path: Path,
    sleeping_executable: Path,
) -> None:
    powershell = _powershell_path()
    assert powershell is not None
    app = _make_app_layout(tmp_path / "receipt % ç" / "App", executable=b"old executable")
    data_dir = tmp_path / "receipt % ç data"
    transaction = updater.create_update_transaction(
        app,
        "0.6.2",
        data_dir=data_dir,
        old_pid=2_147_483_647,
        ready_timeout_seconds=10,
        healthy_timeout_seconds=10,
        move_retry_seconds=0.05,
    )
    _make_app_layout(transaction.staging_dir, executable=sleeping_executable.read_bytes())
    updater.write_update_helper(transaction)
    # A directory at the result path makes every receipt write fail.
    transaction.result_path.mkdir()
    helper = updater.launch_update_helper(transaction, powershell_executable=powershell)
    try:
        _wait_until(
            lambda: transaction.rollback_dir.is_dir() and not transaction.staging_dir.exists()
        )
        updater.mark_update_ready(transaction.manifest_path, transaction.token, pid=555)
        assert updater.wait_for_update_commit(
            transaction.manifest_path,
            transaction.token,
            timeout_seconds=30,
        )
        updater.mark_update_healthy(transaction.manifest_path, transaction.token, pid=555)
        assert _wait_helper(helper, transaction) == 0
        assert (app / "Organizador.exe").read_bytes() == sleeping_executable.read_bytes()
        assert not transaction.rollback_dir.exists()
        assert not transaction.lock_path.exists()
        assert transaction.result_path.is_dir()
    finally:
        if helper.poll() is None:
            helper.terminate()
        updater.release_installation_lock(transaction)


def test_abort_update_transaction_discards_lock_staging_and_state(app_dir: Path) -> None:
    transaction = updater.create_update_transaction(app_dir, "0.6.2")
    transaction.staging_dir.mkdir(parents=True)
    (transaction.staging_dir / "Organizador.exe").write_bytes(b"staged")
    assert transaction.lock_path.is_file()

    updater.abort_update_transaction(transaction)

    assert not transaction.lock_path.exists()
    assert not transaction.staging_dir.exists()
    assert not transaction.state_dir.exists()


def test_read_staged_release_version(tmp_path: Path) -> None:
    assert updater.read_staged_release_version(tmp_path) is None

    (tmp_path / "update-manifest.json").write_text('{"version": "0.6.2"}', encoding="utf-8")
    assert updater.read_staged_release_version(tmp_path) == (0, 6, 2)

    (tmp_path / "update-manifest.json").write_text('{"version": "soon"}', encoding="utf-8")
    with pytest.raises(UpdaterError):
        updater.read_staged_release_version(tmp_path)


def test_helper_ready_markers_round_trip(app_dir: Path) -> None:
    transaction = updater.create_update_transaction(app_dir, "0.6.2")
    try:
        assert updater.helper_ready_received(transaction) is False
        assert updater.wait_for_helper_ready(transaction, timeout_seconds=0.05) is False

        transaction.helper_ready_path.write_text(
            json.dumps({"transaction_id": transaction.transaction_id, "token": "wrong"}),
            encoding="utf-8",
        )
        assert updater.helper_ready_received(transaction) is False

        transaction.helper_ready_path.write_text(
            json.dumps({"transaction_id": transaction.transaction_id, "token": transaction.token}),
            encoding="utf-8",
        )
        assert updater.helper_ready_received(transaction) is True
        assert updater.wait_for_helper_ready(transaction, timeout_seconds=5.0) is True
    finally:
        updater.release_installation_lock(transaction)


def test_launch_update_helper_reports_an_unready_helper(
    app_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transaction = updater.create_update_transaction(app_dir, "0.6.2")
    updater.write_update_helper(transaction)
    terminated: list[bool] = []

    class _Process:
        def terminate(self) -> None:
            terminated.append(True)

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: _Process())
    try:
        with pytest.raises(UpdaterError, match="assistente"):
            updater.launch_update_helper(transaction, ready_timeout_seconds=0.05)
        assert terminated == [True]
    finally:
        updater.release_installation_lock(transaction)


def test_prune_abandoned_update_state(tmp_path: Path) -> None:
    app = _make_app_layout(tmp_path / "Prune App")
    data_dir = tmp_path / "data"

    old = updater.create_update_transaction(app, "0.6.2", data_dir=data_dir)
    old.staging_dir.mkdir(parents=True)
    updater.release_installation_lock(old)
    aged = time.time() - 8 * 86400.0
    os.utime(old.state_dir, (aged, aged))

    fresh = updater.create_update_transaction(app, "0.6.2", data_dir=data_dir)
    updater.release_installation_lock(fresh)

    finished = updater.create_update_transaction(app, "0.6.2", data_dir=data_dir)
    updater.write_update_result(
        finished.result_path,
        updater.UpdateResult(
            transaction_id=finished.transaction_id,
            status=updater.UpdateResultStatus.SUCCEEDED,
            phase="complete",
            committed=True,
            rollback_succeeded=None,
            error=None,
            old_pid=1,
            new_pid=2,
            started_at="2026-09-03T00:00:00+00:00",
            finished_at="2026-09-03T00:00:01+00:00",
            app_dir=finished.app_dir,
            rollback_dir=finished.rollback_dir,
        ),
    )
    updater.release_installation_lock(finished)

    removed = updater.prune_abandoned_update_state(data_dir)

    assert old.state_dir in removed
    assert old.staging_dir in removed
    assert not old.state_dir.exists()
    assert not old.staging_dir.exists()
    assert fresh.state_dir.is_dir()
    assert finished.state_dir.is_dir()


def _write_rolled_back_result(transaction: updater.UpdateTransaction, **overrides: object) -> None:
    payload: dict[str, object] = {
        "transaction_id": transaction.transaction_id,
        "status": updater.UpdateResultStatus.ROLLED_BACK,
        "phase": "wait_ready",
        "committed": False,
        "rollback_succeeded": True,
        "error": "helper error",
        "old_pid": 1,
        "new_pid": None,
        "started_at": "2026-09-03T00:00:00+00:00",
        "finished_at": "2026-09-03T00:00:01+00:00",
        "app_dir": transaction.app_dir,
        "rollback_dir": transaction.rollback_dir,
    }
    payload.update(overrides)
    updater.write_update_result(
        transaction.result_path,
        updater.UpdateResult(**payload),  # type: ignore[arg-type]
    )


def test_prune_reclaims_an_aged_rolled_back_staging_copy(tmp_path: Path) -> None:
    app = _make_app_layout(tmp_path / "Rolled App")
    data_dir = tmp_path / "data"
    rolled = updater.create_update_transaction(app, "0.6.2", data_dir=data_dir)
    _make_app_layout(rolled.staging_dir, executable=b"new executable")
    _write_rolled_back_result(rolled)
    updater.release_installation_lock(rolled)
    aged = time.time() - 8 * 86400.0
    os.utime(rolled.state_dir, (aged, aged))

    removed = updater.prune_abandoned_update_state(data_dir)

    assert rolled.state_dir in removed
    assert rolled.staging_dir in removed
    assert not rolled.state_dir.exists()
    assert not rolled.staging_dir.exists()
    assert (app / "Organizador.exe").read_bytes() == b"app binary"


def test_prune_keeps_a_fresh_rolled_back_result_for_the_notification(
    tmp_path: Path,
) -> None:
    app = _make_app_layout(tmp_path / "Rolled Fresh App")
    data_dir = tmp_path / "data"
    rolled = updater.create_update_transaction(app, "0.6.2", data_dir=data_dir)
    _make_app_layout(rolled.staging_dir)
    _write_rolled_back_result(rolled)
    updater.release_installation_lock(rolled)

    removed = updater.prune_abandoned_update_state(data_dir)

    assert removed == ()
    assert rolled.state_dir.is_dir()
    assert rolled.staging_dir.is_dir()


def test_prune_keeps_failed_and_partial_rollback_state(tmp_path: Path) -> None:
    app = _make_app_layout(tmp_path / "Failed App")
    data_dir = tmp_path / "data"
    after_commit = updater.create_update_transaction(app, "0.6.2", data_dir=data_dir)
    _make_app_layout(after_commit.staging_dir)
    _write_rolled_back_result(
        after_commit,
        status=updater.UpdateResultStatus.FAILED_AFTER_COMMIT,
        committed=True,
    )
    updater.release_installation_lock(after_commit)
    partial = updater.create_update_transaction(app, "0.6.2", data_dir=data_dir)
    _make_app_layout(partial.staging_dir)
    _write_rolled_back_result(
        partial,
        status=updater.UpdateResultStatus.FAILED,
        rollback_succeeded=False,
    )
    updater.release_installation_lock(partial)
    aged = time.time() - 8 * 86400.0
    os.utime(after_commit.state_dir, (aged, aged))
    os.utime(partial.state_dir, (aged, aged))

    removed = updater.prune_abandoned_update_state(data_dir)

    assert removed == ()
    assert after_commit.state_dir.is_dir()
    assert after_commit.staging_dir.is_dir()
    assert partial.state_dir.is_dir()
    assert partial.staging_dir.is_dir()
