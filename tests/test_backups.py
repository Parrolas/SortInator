"""User snapshot, retention, portable archive and restore-request tests."""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import organizador.recovery as recovery_module
from organizador.db import Database, DatabaseHealth, DatabaseHealthError
from organizador.recovery import (
    DATABASE_BACKUP_NAME,
    MANIFEST_NAME,
    PRE_RESTORE_MARKER,
    RESTORE_REQUEST_FAILED_NAME,
    RESTORE_REQUEST_NAME,
    SETTINGS_ABSENT_NAME,
    SETTINGS_BACKUP_NAME,
    USER_MARKER,
    RecoveryCoordinator,
    RecoveryError,
)


def _prepared_data(tmp_path: Path, name: str = "data") -> tuple[Path, Database]:
    data_dir = tmp_path / name
    data_dir.mkdir()
    database = Database(data_dir / "organizador.db")
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO subjects(name, code, color, keywords_json, folder_name, created_at)
            VALUES ('Cálculo I', 'MAT101', '#087A74', '[]', 'MAT101 - Cálculo I', '2026-01-01')
            """
        )
        connection.commit()
    (data_dir / "settings.json").write_text('{"language": "pt"}', encoding="utf-8")
    return data_dir, database


def _subject_count(database_path: Path) -> int:
    with Database(database_path).connect() as connection:
        row = connection.execute("SELECT COUNT(*) FROM subjects").fetchone()
    return int(row[0])


def test_create_snapshot_publishes_a_user_bundle(tmp_path: Path) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)

    bundle = coordinator.create_snapshot()

    assert (bundle.path / USER_MARKER).is_file()
    assert (bundle.path / DATABASE_BACKUP_NAME).is_file()
    assert (bundle.path / SETTINGS_BACKUP_NAME).is_file()
    assert (bundle.path / MANIFEST_NAME).is_file()
    inventory = coordinator.list_bundles()
    assert [info.path for info in inventory] == [bundle.path]
    assert inventory[0].kind == USER_MARKER
    assert inventory[0].settings_present is True
    assert inventory[0].size_bytes > 0


def test_create_snapshot_without_settings_records_absence(tmp_path: Path) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    (data_dir / "settings.json").unlink()
    coordinator = RecoveryCoordinator(data_dir)

    bundle = coordinator.create_snapshot(marker=PRE_RESTORE_MARKER)

    assert (bundle.path / PRE_RESTORE_MARKER).is_file()
    assert (bundle.path / SETTINGS_ABSENT_NAME).is_file()
    assert not (bundle.path / SETTINGS_BACKUP_NAME).exists()
    assert bundle.settings_present is False


def test_prune_never_touches_user_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    monkeypatch.setattr(recovery_module, "_utc_now", lambda: now - timedelta(days=90))
    old_user = coordinator.create_snapshot()
    monkeypatch.setattr(recovery_module, "_utc_now", lambda: now)
    new_user = coordinator.create_snapshot()

    removed = coordinator.prune_automatic_backups()

    assert removed == ()
    assert old_user.path.is_dir()
    assert new_user.path.is_dir()


def test_prune_keeps_two_recent_pre_restore_bundles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    stamps = [
        now - timedelta(days=1),
        now - timedelta(days=2),
        now - timedelta(days=3),
        now - timedelta(days=31),
    ]
    bundles = []
    for stamp in stamps:
        monkeypatch.setattr(recovery_module, "_utc_now", lambda value=stamp: value)
        bundles.append(coordinator.create_snapshot(PRE_RESTORE_MARKER))
    monkeypatch.setattr(recovery_module, "_utc_now", lambda: now)

    removed = coordinator.prune_automatic_backups()

    assert set(removed) == {bundles[2].path, bundles[3].path}
    assert bundles[0].path.is_dir()
    assert bundles[1].path.is_dir()


def test_restore_bundle_replaces_current_data(tmp_path: Path) -> None:
    data_dir, database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()
    assert _subject_count(data_dir / "organizador.db") == 0

    restored = coordinator.restore_bundle(bundle.path)

    assert restored.path == bundle.path
    assert _subject_count(data_dir / "organizador.db") == 1


def test_delete_refuses_non_user_bundles(tmp_path: Path) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    pre_restore = coordinator.create_snapshot(PRE_RESTORE_MARKER)
    user = coordinator.create_snapshot()

    coordinator.delete_bundle(user.path)

    assert not user.path.exists()
    with pytest.raises(RecoveryError):
        coordinator.delete_bundle(pre_restore.path)
    assert pre_restore.path.is_dir()


def test_zip_export_import_roundtrip(tmp_path: Path) -> None:
    data_dir, database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    export_dir = tmp_path / "exports"

    archive = coordinator.export_bundle_zip(bundle.path, export_dir)

    assert archive.suffix == ".zip"
    assert archive.is_file()
    imported = coordinator.import_bundle_zip(archive)
    assert imported.path != bundle.path
    assert (imported.path / USER_MARKER).is_file()
    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()

    coordinator.restore_bundle(imported.path)

    assert _subject_count(data_dir / "organizador.db") == 1


def test_zip_import_rejects_foreign_members(tmp_path: Path) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    archive = coordinator.export_bundle_zip(bundle.path, tmp_path / "exports")
    with zipfile.ZipFile(archive, "a") as handle:
        handle.writestr("extra.txt", b"nope")

    with pytest.raises(RecoveryError):
        coordinator.import_bundle_zip(archive)

    assert not any(path.name.startswith("import-") for path in coordinator.backups_dir.iterdir())


def test_zip_import_rejects_traversal_members(tmp_path: Path) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    archive = coordinator.export_bundle_zip(bundle.path, tmp_path / "exports")
    with zipfile.ZipFile(archive, "a") as handle:
        handle.writestr("../escape.txt", b"nope")

    with pytest.raises(RecoveryError):
        coordinator.import_bundle_zip(archive)

    assert not (tmp_path / "escape.txt").exists()


def test_zip_import_rejects_a_tampered_database(tmp_path: Path) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    archive = tmp_path / "exports" / "tampered.zip"
    archive.parent.mkdir()
    database_bytes = (bundle.path / DATABASE_BACKUP_NAME).read_bytes()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(bundle.path / MANIFEST_NAME, MANIFEST_NAME)
        handle.writestr(DATABASE_BACKUP_NAME, database_bytes[:-16])
        handle.write(bundle.path / SETTINGS_BACKUP_NAME, SETTINGS_BACKUP_NAME)

    with pytest.raises(RecoveryError):
        coordinator.import_bundle_zip(archive)


def test_failed_restore_keeps_the_current_database_and_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, database = _prepared_data(tmp_path)
    (data_dir / "settings.json").write_text(
        '{"language": "pt", "marker": "atual"}', encoding="utf-8"
    )
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()
    current_database_sha = recovery_module._sha256_file(data_dir / "organizador.db")
    current_settings = (data_dir / "settings.json").read_bytes()
    original_replace = Path.replace

    def failing_replace(self: Path, target: Path) -> Path:
        if self.name.startswith(".organizador.db.restore-"):
            raise OSError("disco cheio")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_replace)

    with pytest.raises(OSError):
        coordinator.restore_bundle(bundle.path)

    assert recovery_module._sha256_file(data_dir / "organizador.db") == current_database_sha
    assert (data_dir / "settings.json").read_bytes() == current_settings
    assert _subject_count(data_dir / "organizador.db") == 0
    assert not any(path.name.endswith(".tmp") for path in data_dir.iterdir())


def test_restore_rolls_back_when_verification_fails_after_the_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, database = _prepared_data(tmp_path)
    (data_dir / "settings.json").write_text(
        '{"language": "pt", "marker": "atual"}', encoding="utf-8"
    )
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()
    current_database_sha = recovery_module._sha256_file(data_dir / "organizador.db")
    current_settings = (data_dir / "settings.json").read_bytes()
    original_validate = Database.validate_health

    def failing_validate(self: Database) -> DatabaseHealth:
        if self.path == data_dir / "organizador.db":
            raise DatabaseHealthError("quick_check falhou")
        return original_validate(self)

    monkeypatch.setattr(Database, "validate_health", failing_validate)

    with pytest.raises(DatabaseHealthError):
        coordinator.restore_bundle(bundle.path)

    assert recovery_module._sha256_file(data_dir / "organizador.db") == current_database_sha
    assert (data_dir / "settings.json").read_bytes() == current_settings
    assert not any(path.name.endswith(".tmp") for path in data_dir.iterdir())


def test_restore_request_roundtrip_creates_pre_restore_snapshot(tmp_path: Path) -> None:
    data_dir, database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()

    request_path = coordinator.request_restore(bundle.path)
    assert request_path.name == RESTORE_REQUEST_NAME
    assert coordinator.has_restore_request()

    outcome = coordinator.consume_restore_request()

    assert outcome is not None
    assert outcome.restored_from == bundle.created_at
    assert _subject_count(data_dir / "organizador.db") == 1
    assert not coordinator.has_restore_request()
    kinds = [info.kind for info in coordinator.list_bundles()]
    assert PRE_RESTORE_MARKER in kinds


def test_tampered_restore_request_is_quarantined(tmp_path: Path) -> None:
    data_dir, database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    request_path = coordinator.request_restore(bundle.path)
    payload = json.loads(request_path.read_bytes())
    payload["manifest_sha256"] = "0" * 64
    request_path.write_text(json.dumps(payload), encoding="utf-8")
    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()

    with pytest.raises(RecoveryError):
        coordinator.consume_restore_request()

    assert not (data_dir / RESTORE_REQUEST_NAME).exists()
    failed = json.loads((data_dir / RESTORE_REQUEST_FAILED_NAME).read_bytes())
    assert "changed since the request" in failed["error"]
    assert _subject_count(data_dir / "organizador.db") == 0
