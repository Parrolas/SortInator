"""User snapshot, retention, portable archive and restore-request tests."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import organizador.recovery as recovery_module
from organizador.db import Database, DatabaseHealth, DatabaseHealthError, NewerDatabaseError
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


def test_zip_import_rejects_a_database_member_over_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    database_bytes = (bundle.path / DATABASE_BACKUP_NAME).read_bytes()
    archive = tmp_path / "exports" / "grande.zip"
    archive.parent.mkdir()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(bundle.path / MANIFEST_NAME, MANIFEST_NAME)
        handle.writestr(DATABASE_BACKUP_NAME, database_bytes + b"0" * 4096)
        handle.write(bundle.path / SETTINGS_BACKUP_NAME, SETTINGS_BACKUP_NAME)

    monkeypatch.setattr(recovery_module, "_MAX_DATABASE_MEMBER_BYTES", 1024)

    with pytest.raises(RecoveryError, match="too large"):
        coordinator.import_bundle_zip(archive)

    assert not any(path.name.startswith("import-") for path in coordinator.backups_dir.iterdir())


def test_zip_import_rejects_a_settings_member_over_the_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    archive = tmp_path / "exports" / "grande.zip"
    archive.parent.mkdir()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(bundle.path / MANIFEST_NAME, MANIFEST_NAME)
        handle.write(bundle.path / DATABASE_BACKUP_NAME, DATABASE_BACKUP_NAME)
        handle.writestr(SETTINGS_BACKUP_NAME, b"x" * 4096)

    monkeypatch.setattr(recovery_module, "_MAX_SETTINGS_MEMBER_BYTES", 1024)

    with pytest.raises(RecoveryError, match="too large"):
        coordinator.import_bundle_zip(archive)

    assert not any(path.name.startswith("import-") for path in coordinator.backups_dir.iterdir())


def test_zip_import_enforces_the_total_member_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir, _database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    database_bytes = (bundle.path / DATABASE_BACKUP_NAME).read_bytes()
    archive = tmp_path / "exports" / "total.zip"
    archive.parent.mkdir()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(bundle.path / MANIFEST_NAME, MANIFEST_NAME)
        handle.writestr(DATABASE_BACKUP_NAME, database_bytes + b"0" * 2048)
        handle.writestr(SETTINGS_BACKUP_NAME, b"x" * 2048)

    monkeypatch.setattr(recovery_module, "_MAX_DATABASE_MEMBER_BYTES", 8192)
    monkeypatch.setattr(recovery_module, "_MAX_SETTINGS_MEMBER_BYTES", 8192)
    monkeypatch.setattr(recovery_module, "_MAX_BUNDLE_MEMBER_BYTES", 3000)

    with pytest.raises(RecoveryError, match="too large"):
        coordinator.import_bundle_zip(archive)

    assert not any(path.name.startswith("import-") for path in coordinator.backups_dir.iterdir())


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


def test_restore_failure_while_saving_settings_deletes_nothing(
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
        if self == data_dir / "settings.json":
            raise PermissionError("bloqueado")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_replace)
    coordinator.request_restore(bundle.path)

    with pytest.raises(PermissionError):
        coordinator.consume_restore_request()

    assert recovery_module._sha256_file(data_dir / "organizador.db") == current_database_sha
    assert (data_dir / "settings.json").read_bytes() == current_settings
    assert (data_dir / RESTORE_REQUEST_FAILED_NAME).is_file()
    assert not any(path.name.endswith(".tmp") for path in data_dir.iterdir())


def test_restore_failure_while_saving_a_sidecar_restores_the_settings(
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
    sidecar = data_dir / "organizador.db-wal"
    sidecar.write_bytes(b"sidecar")
    original_replace = Path.replace

    def failing_replace(self: Path, target: Path) -> Path:
        if self == sidecar:
            raise PermissionError("bloqueado")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_replace)
    coordinator.request_restore(bundle.path)

    with pytest.raises(PermissionError):
        coordinator.consume_restore_request()

    assert recovery_module._sha256_file(data_dir / "organizador.db") == current_database_sha
    assert (data_dir / "settings.json").read_bytes() == current_settings
    assert sidecar.read_bytes() == b"sidecar"
    assert not any(path.name.endswith(".tmp") for path in data_dir.iterdir())


def test_failed_rollback_keeps_the_saved_original_for_recovery(
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
    sidecar = data_dir / "organizador.db-wal"
    sidecar.write_bytes(b"sidecar")
    original_replace = Path.replace

    def failing_replace(self: Path, target: Path) -> Path:
        if self == sidecar:
            raise PermissionError("bloqueado")
        if (
            self.name.startswith(".settings.json.replaced-")
            and target == data_dir / "settings.json"
        ):
            raise PermissionError("bloqueado outra vez")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_replace)
    coordinator.request_restore(bundle.path)

    with pytest.raises(PermissionError):
        coordinator.consume_restore_request()

    assert recovery_module._sha256_file(data_dir / "organizador.db") == current_database_sha
    saved = [
        path
        for path in data_dir.iterdir()
        if path.name.startswith(".settings.json.replaced-") and path.name.endswith(".tmp")
    ]
    assert len(saved) == 1
    assert saved[0].read_bytes() == current_settings


def test_restore_is_refused_when_the_safety_snapshot_fails(
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
    coordinator.request_restore(bundle.path)

    def failing_snapshot(marker: str = "") -> object:
        raise PermissionError("sem espaço para a cópia de segurança")

    monkeypatch.setattr(coordinator, "create_snapshot", failing_snapshot)

    with pytest.raises(PermissionError):
        coordinator.consume_restore_request()

    assert recovery_module._sha256_file(data_dir / "organizador.db") == current_database_sha
    assert (data_dir / "settings.json").read_bytes() == current_settings
    assert not any(
        path.name.startswith("pre_restore-") for path in coordinator.backups_dir.iterdir()
    )
    assert (data_dir / RESTORE_REQUEST_FAILED_NAME).is_file()


def test_restore_skips_the_snapshot_when_the_current_database_is_unusable(
    tmp_path: Path,
) -> None:
    data_dir, database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()
    coordinator.request_restore(bundle.path)
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO subjects(name, code, color, keywords_json, folder_name, created_at)"
            " VALUES ('Extra', 'EXT', '#123456', '[]', 'EXT - Extra', '2026-01-01')"
        )
        connection.commit()
    (data_dir / "organizador.db").write_bytes(b"nao e uma base de dados")

    outcome = coordinator.consume_restore_request()

    assert outcome is not None
    assert _subject_count(data_dir / "organizador.db") == 1
    assert not any(
        path.name.startswith("pre_restore-") for path in coordinator.backups_dir.iterdir()
    )


def _rewrite_bundle_manifest(
    bundle_path: Path,
    *,
    database_sha256: str | None = None,
    user_version: int | None = None,
) -> None:
    manifest_path = bundle_path / MANIFEST_NAME
    payload = json.loads(manifest_path.read_bytes())
    if database_sha256 is not None:
        payload["files"]["database"]["sha256"] = database_sha256
    if user_version is not None:
        payload["schema"]["user_version"] = user_version
    manifest_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def test_backup_with_a_newer_schema_is_rejected_before_the_swap(tmp_path: Path) -> None:
    data_dir, database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()
    current_database_sha = recovery_module._sha256_file(data_dir / "organizador.db")
    with sqlite3.connect(bundle.path / DATABASE_BACKUP_NAME) as connection:
        connection.execute("PRAGMA user_version = 7")
        connection.commit()
    _rewrite_bundle_manifest(
        bundle.path,
        database_sha256=recovery_module._sha256_file(bundle.path / DATABASE_BACKUP_NAME),
        user_version=7,
    )

    with pytest.raises(NewerDatabaseError):
        coordinator.restore_bundle(bundle.path)

    assert recovery_module._sha256_file(data_dir / "organizador.db") == current_database_sha
    assert not any(path.name.endswith(".tmp") for path in data_dir.iterdir())


def test_backup_with_a_manifest_version_mismatch_is_rejected(tmp_path: Path) -> None:
    data_dir, database = _prepared_data(tmp_path)
    coordinator = RecoveryCoordinator(data_dir)
    bundle = coordinator.create_snapshot()
    with database.connect() as connection:
        connection.execute("DELETE FROM subjects")
        connection.commit()
    current_database_sha = recovery_module._sha256_file(data_dir / "organizador.db")
    _rewrite_bundle_manifest(bundle.path, user_version=5)

    with pytest.raises(RecoveryError):
        coordinator.restore_bundle(bundle.path)

    assert recovery_module._sha256_file(data_dir / "organizador.db") == current_database_sha


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
