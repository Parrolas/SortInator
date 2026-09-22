"""Migration backup publication, restoration, and retention tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import organizador.recovery as recovery_module
from organizador.db import Database
from organizador.recovery import (
    FAILED_MARKER,
    HEALTHY_MARKER,
    MANIFEST_NAME,
    PENDING_MARKER,
    QUARANTINED_MARKER,
    RecoveryBundle,
    RecoveryCoordinator,
    RecoveryError,
)


def _old_database(data_dir: Path) -> Database:
    data_dir.mkdir(parents=True)
    database = Database(data_dir / "sortinator.db")
    database.initialize()
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 4")
        connection.commit()
    return database


def _healthy_bundle_at(
    coordinator: RecoveryCoordinator,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
    created_at: datetime,
) -> RecoveryBundle:
    monkeypatch.setattr(recovery_module, "_utc_now", lambda: created_at)
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 4")
        connection.commit()
    bundle = coordinator.prepare_migration()
    assert bundle is not None
    database.initialize()
    coordinator.mark_healthy(bundle)
    return bundle


def test_pending_marker_is_published_only_after_bundle_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    _old_database(data_dir)
    coordinator = RecoveryCoordinator(data_dir)
    order: list[str] = []
    original_validate = coordinator._validate_bundle
    original_publish = coordinator._publish_pending

    def validate(bundle_path: Path) -> Any:
        assert not (bundle_path / PENDING_MARKER).exists()
        result = original_validate(bundle_path)
        order.append("validated")
        return result

    def publish(bundle_path: Path) -> None:
        assert order == ["validated"]
        assert (bundle_path / MANIFEST_NAME).is_file()
        order.append("published")
        original_publish(bundle_path)

    monkeypatch.setattr(coordinator, "_validate_bundle", validate)
    monkeypatch.setattr(coordinator, "_publish_pending", publish)

    bundle = coordinator.prepare_migration()

    assert bundle is not None
    assert order == ["validated", "published"]
    assert (bundle.path / PENDING_MARKER).is_file()


def test_restore_roundtrips_malformed_settings_and_is_idempotent(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    database = _old_database(data_dir)
    original_settings = b"\xff{malformed-json}\r\n\x00"
    (data_dir / "settings.json").write_bytes(original_settings)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.prepare_migration()
    assert bundle is not None

    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO subjects(name, code, folder_name, created_at)
            VALUES ('After backup', 'NEW', 'After backup', '2026-09-03T00:00:00+00:00')
            """
        )
        connection.commit()
    (data_dir / "settings.json").write_bytes(b'{"replacement": true}\n')
    Path(f"{database.path}-wal").write_bytes(b"stale wal")
    Path(f"{database.path}-shm").write_bytes(b"stale shm")

    restored = coordinator.restore_pending()

    assert restored == bundle
    assert (data_dir / "settings.json").read_bytes() == original_settings
    assert not Path(f"{database.path}-wal").exists()
    assert not Path(f"{database.path}-shm").exists()
    with database.connect() as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        new_rows = int(
            connection.execute("SELECT COUNT(*) FROM subjects WHERE code = 'NEW'").fetchone()[0]
        )
    assert version == 4
    assert new_rows == 0
    assert (bundle.path / FAILED_MARKER).is_file()
    assert not (bundle.path / PENDING_MARKER).exists()

    assert coordinator.restore_pending() is None
    assert (data_dir / "settings.json").read_bytes() == original_settings


def test_restore_removes_settings_when_the_original_was_absent(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    _old_database(data_dir)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.prepare_migration()
    assert bundle is not None
    assert not bundle.settings_present

    (data_dir / "settings.json").write_bytes(b"created after backup")

    coordinator.restore_pending()

    assert not (data_dir / "settings.json").exists()


@pytest.mark.parametrize("tamper", ["database", "path-traversal"])
def test_restore_quarantines_tampered_or_unsafe_bundles(tmp_path: Path, tamper: str) -> None:
    data_dir = tmp_path / "data"
    database = _old_database(data_dir)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.prepare_migration()
    assert bundle is not None
    database.initialize()
    outside = coordinator.backups_dir / "outside.db"
    outside.write_bytes(b"outside sentinel")

    if tamper == "database":
        (bundle.path / "database.sqlite3").write_bytes(b"tampered")
    else:
        manifest_path = bundle.path / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["database"]["path"] = "../outside.db"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RecoveryError, match="not trustworthy"):
        coordinator.restore_pending()

    assert outside.read_bytes() == b"outside sentinel"
    assert database.inspect_schema().is_current
    assert (bundle.path / QUARANTINED_MARKER).is_file()
    assert not (bundle.path / PENDING_MARKER).exists()


def test_transient_bundle_validation_retries_before_quarantine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    database = _old_database(data_dir)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.prepare_migration()
    assert bundle is not None
    database.initialize()

    attempts: list[int] = []
    original_validate = coordinator._validate_bundle

    def flaky(bundle_path: Path) -> Any:
        attempts.append(1)
        if len(attempts) <= 2:
            raise PermissionError("locked by antivirus")
        return original_validate(bundle_path)

    monkeypatch.setattr(coordinator, "_validate_bundle", flaky)
    monkeypatch.setattr(recovery_module.time, "sleep", lambda _seconds: None)

    coordinator.validate_migrated(bundle)

    assert len(attempts) == 3
    assert (bundle.path / PENDING_MARKER).is_file()
    assert not (bundle.path / QUARANTINED_MARKER).exists()


def test_persistent_transient_failure_still_quarantines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    database = _old_database(data_dir)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.prepare_migration()
    assert bundle is not None
    database.initialize()

    def locked(bundle_path: Path) -> Any:
        raise PermissionError("locked by antivirus")

    monkeypatch.setattr(coordinator, "_validate_bundle", locked)
    monkeypatch.setattr(recovery_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RecoveryError, match="not trustworthy"):
        coordinator.validate_migrated(bundle)

    assert (bundle.path / QUARANTINED_MARKER).is_file()
    assert not (bundle.path / PENDING_MARKER).exists()


def test_restore_update_rollback_restores_a_quarantined_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    database = _old_database(data_dir)
    original_settings = b'{"language": "pt"}\n'
    (data_dir / "settings.json").write_bytes(original_settings)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.prepare_migration()
    assert bundle is not None

    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO subjects(name, code, folder_name, created_at)
            VALUES ('After backup', 'NEW', 'After backup', '2026-09-03T00:00:00+00:00')
            """
        )
        connection.commit()
    (data_dir / "settings.json").write_bytes(b'{"replacement": true}\n')

    def locked(bundle_path: Path) -> Any:
        raise PermissionError("locked by antivirus")

    original_validate = coordinator._validate_bundle
    monkeypatch.setattr(coordinator, "_validate_bundle", locked)
    monkeypatch.setattr(recovery_module.time, "sleep", lambda _seconds: None)
    with pytest.raises(RecoveryError):
        coordinator.validate_migrated(bundle)
    assert (bundle.path / QUARANTINED_MARKER).is_file()

    # The antivirus lock clears before the helper rolls the binaries back.
    monkeypatch.setattr(coordinator, "_validate_bundle", original_validate)

    restored = coordinator.restore_update_rollback(bundle)

    assert restored == bundle
    assert (data_dir / "settings.json").read_bytes() == original_settings
    with database.connect() as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        new_rows = int(
            connection.execute("SELECT COUNT(*) FROM subjects WHERE code = 'NEW'").fetchone()[0]
        )
    assert version == 4
    assert new_rows == 0
    assert (bundle.path / FAILED_MARKER).is_file()
    assert not (bundle.path / QUARANTINED_MARKER).exists()

    with pytest.raises(RecoveryError):
        coordinator.restore_update_rollback(bundle)


def test_restore_update_rollback_refuses_healthy_or_broken_bundles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    database = _old_database(data_dir)
    coordinator = RecoveryCoordinator(data_dir)
    healthy = coordinator.prepare_migration()
    assert healthy is not None
    database.initialize()
    coordinator.mark_healthy(healthy)

    with pytest.raises(RecoveryError, match="healthy"):
        coordinator.restore_update_rollback(healthy)

    tampered_dir = tmp_path / "tampered"
    tampered_database = _old_database(tampered_dir)
    tampered_coordinator = RecoveryCoordinator(tampered_dir)
    tampered = tampered_coordinator.prepare_migration()
    assert tampered is not None
    tampered_database.initialize()
    (tampered.path / "database.sqlite3").write_bytes(b"tampered")

    with pytest.raises(RecoveryError):
        tampered_coordinator.restore_pending()
    assert (tampered.path / QUARANTINED_MARKER).is_file()

    with pytest.raises(RecoveryError):
        tampered_coordinator.restore_update_rollback(tampered)
    assert (tampered.path / QUARANTINED_MARKER).is_file()
    assert not (tampered.path / FAILED_MARKER).exists()


def test_healthy_marker_prevents_a_later_restore(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    database = _old_database(data_dir)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.prepare_migration()
    assert bundle is not None

    database.initialize()
    coordinator.mark_healthy(bundle)
    coordinator.mark_healthy(bundle)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO subjects(name, code, folder_name, created_at)
            VALUES ('Healthy data', 'SAFE', 'Healthy data', '2026-09-03T00:00:00+00:00')
            """
        )
        connection.commit()

    assert coordinator.restore_pending() is None
    with database.connect() as connection:
        count = int(
            connection.execute("SELECT COUNT(*) FROM subjects WHERE code = 'SAFE'").fetchone()[0]
        )
    assert count == 1
    assert (bundle.path / HEALTHY_MARKER).is_file()
    assert not (bundle.path / PENDING_MARKER).exists()


def test_retention_keeps_two_recent_healthy_bundles_and_all_protected_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    database = _old_database(data_dir)
    coordinator = RecoveryCoordinator(data_dir)
    now = datetime(2026, 9, 3, 12, tzinfo=UTC)

    recent_one = _healthy_bundle_at(coordinator, database, monkeypatch, now - timedelta(days=1))
    recent_two = _healthy_bundle_at(coordinator, database, monkeypatch, now - timedelta(days=2))
    excess_recent = _healthy_bundle_at(coordinator, database, monkeypatch, now - timedelta(days=3))
    expired = _healthy_bundle_at(coordinator, database, monkeypatch, now - timedelta(days=31))
    protected_failed = _healthy_bundle_at(
        coordinator, database, monkeypatch, now - timedelta(days=40)
    )
    (protected_failed.path / HEALTHY_MARKER).replace(protected_failed.path / FAILED_MARKER)
    protected_quarantined = _healthy_bundle_at(
        coordinator, database, monkeypatch, now - timedelta(days=41)
    )
    (protected_quarantined.path / HEALTHY_MARKER).replace(
        protected_quarantined.path / QUARANTINED_MARKER
    )
    protected_pending = _healthy_bundle_at(
        coordinator, database, monkeypatch, now - timedelta(days=42)
    )
    (protected_pending.path / HEALTHY_MARKER).replace(protected_pending.path / PENDING_MARKER)
    monkeypatch.setattr(recovery_module, "_utc_now", lambda: now)

    removed = coordinator.prune_automatic_backups()

    assert set(removed) == {excess_recent.path, expired.path}
    assert recent_one.path.is_dir()
    assert recent_two.path.is_dir()
    assert protected_failed.path.is_dir()
    assert protected_quarantined.path.is_dir()
    assert protected_pending.path.is_dir()
