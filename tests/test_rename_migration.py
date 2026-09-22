"""Rename migration bridges: legacy data directory and shell registrations."""

from __future__ import annotations

import os
import stat as stat_module
from pathlib import Path
from types import SimpleNamespace

import pytest

from organizador import startup
from organizador.config import APP_NAME, LEGACY_APP_NAME, migrate_legacy_data_dir


def _legacy_dir(tmp_path: Path) -> Path:
    legacy = tmp_path / LEGACY_APP_NAME
    legacy.mkdir()
    (legacy / "organizador.db").write_bytes(b"db")
    (legacy / "organizador.db-wal").write_bytes(b"wal")
    (legacy / "organizador.log").write_text("log")
    (legacy / "settings.json").write_text("{}")
    return legacy


def _is_reparse_point(path: Path) -> bool:
    attributes = os.lstat(path).st_file_attributes
    return bool(attributes & stat_module.FILE_ATTRIBUTE_REPARSE_POINT)


def test_migration_moves_the_legacy_directory_and_leaves_a_junction(tmp_path: Path) -> None:
    legacy = _legacy_dir(tmp_path)
    target = tmp_path / APP_NAME

    assert migrate_legacy_data_dir(target) is None

    assert target.is_dir()
    assert (target / "sortinator.db").read_bytes() == b"db"
    assert (target / "sortinator.db-wal").read_bytes() == b"wal"
    assert (target / "sortinator.log").read_text() == "log"
    assert (target / "settings.json").is_file()
    assert not (target / "organizador.db").exists()

    # The legacy path keeps working for an older binary restored by a rollback.
    assert legacy.is_dir()
    assert _is_reparse_point(legacy)
    assert (legacy / "sortinator.db").read_bytes() == b"db"

    assert migrate_legacy_data_dir(target) is None
    assert (target / "sortinator.db").read_bytes() == b"db"


def test_migration_failure_keeps_everything_and_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = _legacy_dir(tmp_path)
    target = tmp_path / APP_NAME

    def failing_rename(self: Path, destination: object) -> Path:
        raise PermissionError("locked by another process")

    monkeypatch.setattr(Path, "rename", failing_rename)

    error = migrate_legacy_data_dir(target)

    assert error is not None
    assert legacy.is_dir()
    assert not _is_reparse_point(legacy)
    assert (legacy / "organizador.db").read_bytes() == b"db"
    assert not target.exists()


def test_migration_skips_when_the_new_directory_already_exists(tmp_path: Path) -> None:
    legacy = _legacy_dir(tmp_path)
    target = tmp_path / APP_NAME
    target.mkdir()
    (target / "keep.txt").write_text("keep")

    assert migrate_legacy_data_dir(target) is None

    assert (target / "keep.txt").read_text() == "keep"
    assert legacy.is_dir()
    assert not _is_reparse_point(legacy)
    assert (legacy / "organizador.db").read_bytes() == b"db"


def test_command_executable_parses_quoted_registry_commands(tmp_path: Path) -> None:
    app = tmp_path / "app"
    assert startup._command_executable(f'"{app}\\SortInator.exe" --background') == (
        app / "SortInator.exe"
    )
    assert startup._command_executable("not-quoted") is None
    assert startup._command_executable('"" broken') is None
    assert startup._command_executable('"unterminated') is None


def test_targets_this_install_matches_only_our_folder(tmp_path: Path) -> None:
    app_dir = tmp_path / "Programs" / "SortInator" / "app"
    app_dir.mkdir(parents=True)
    other = tmp_path / "Elsewhere"
    other.mkdir()

    assert startup._targets_this_install(f'"{app_dir}\\SortInator.exe" --organize "%1"', app_dir)
    assert not startup._targets_this_install(f'"{other}\\Organizador.exe" --organize "%1"', app_dir)
    assert not startup._targets_this_install("garbage", app_dir)


class _FakeKey:
    def __init__(self, registry: _FakeRegistry, path: str) -> None:
        self._registry = registry
        self._path = path

    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def QueryValueEx(self, _key: object, name: str) -> tuple[str, int]:
        try:
            return self._registry.keys[self._path][name], 1
        except KeyError as exc:
            raise OSError("missing value") from exc

    def SetValueEx(
        self, _key: object, name: str, _reserved: int, _type: object, value: str
    ) -> None:
        self._registry.keys[self._path][name] = value

    def DeleteValue(self, _key: object, name: str) -> None:
        self._registry.keys[self._path].pop(name, None)


class _FakeRegistry:
    """Dict-backed HKCU supporting the subset the shell bridge uses."""

    HKEY_CURRENT_USER = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self, values: dict[str, dict[str, str]] | None = None) -> None:
        self.keys: dict[str, dict[str, str]] = dict(values or {})
        self.deleted_keys: list[str] = []

    def OpenKey(self, _hive: object, path: str, *_rest: object) -> _FakeKey:
        if path not in self.keys and not any(key.startswith(path + "\\") for key in self.keys):
            raise OSError("missing key")
        return _FakeKey(self, path)

    def CreateKey(self, _hive: object, path: str) -> _FakeKey:
        self.keys.setdefault(path, {})
        return _FakeKey(self, path)

    def QueryValueEx(self, key: _FakeKey, name: str) -> tuple[str, int]:
        return key.QueryValueEx(None, name)

    def DeleteValue(self, key: _FakeKey, name: str) -> None:
        key.DeleteValue(None, name)

    def EnumKey(self, key: _FakeKey, index: int) -> str:
        path = key._path
        children = sorted(
            {
                name[len(path) + 1 :].split("\\")[0]
                for name in self.keys
                if name.startswith(path + "\\")
            }
        )
        try:
            return children[index]
        except IndexError as exc:
            raise OSError("no more keys") from exc

    def DeleteKey(self, _hive: object, path: str) -> None:
        if path not in self.keys:
            raise OSError("missing key")
        self.deleted_keys.append(path)
        for key in [name for name in self.keys if name == path or name.startswith(path + "\\")]:
            self.keys.pop(key, None)


def test_legacy_shell_cleanup_retires_only_entries_of_this_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_dir = tmp_path / "Programs" / "SortInator" / "app"
    app_dir.mkdir(parents=True)
    other_dir = tmp_path / "Elsewhere" / "app"
    other_dir.mkdir(parents=True)
    registry = _FakeRegistry(
        {
            startup.RUN_KEY: {
                "Organizador": f'"{app_dir}\\Organizador.exe" --background',
            },
            startup.LEGACY_PROTOCOL_KEY + r"\shell\open\command": {
                "": f'"{app_dir}\\Organizador.exe" --notification-uri "%1"',
            },
            r"Software\Classes\SystemFileAssociations\.pdf\shell\Organizador\command": {
                "": f'"{app_dir}\\Organizador.exe" --organize "%1"',
            },
            r"Software\Classes\SystemFileAssociations\.docx\shell\Organizador\command": {
                "": f'"{other_dir}\\Organizador.exe" --organize "%1"',
            },
        }
    )
    legacy_shortcut = tmp_path / LEGACY_APP_NAME / "shortcut-dir"
    legacy_shortcut.mkdir(parents=True)
    shortcut_file = legacy_shortcut / startup.LEGACY_SHORTCUT_NAME
    shortcut_file.write_bytes(b"lnk")
    monkeypatch.setattr(
        startup, "sys", SimpleNamespace(frozen=True, executable=str(app_dir / "Organizador.exe"))
    )
    monkeypatch.setattr(startup, "winreg", registry)
    monkeypatch.setattr(startup, "start_menu_shortcut_path", lambda *args, **kwargs: shortcut_file)
    monkeypatch.setattr(startup, "shortcut_target", lambda _path: app_dir / "Organizador.exe")

    startup.cleanup_legacy_shell_integration()

    assert "Organizador" not in registry.keys.get(startup.RUN_KEY, {})
    assert startup.LEGACY_PROTOCOL_KEY + r"\shell\open\command" not in registry.keys
    assert (
        r"Software\Classes\SystemFileAssociations\.pdf\shell\Organizador\command"
        not in registry.keys
    )
    assert (
        r"Software\Classes\SystemFileAssociations\.docx\shell\Organizador\command" in registry.keys
    )
    assert not shortcut_file.exists()


def test_legacy_shell_cleanup_keeps_foreign_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_dir = tmp_path / "Programs" / "SortInator" / "app"
    app_dir.mkdir(parents=True)
    other_dir = tmp_path / "Elsewhere" / "app"
    other_dir.mkdir(parents=True)
    registry = _FakeRegistry(
        {
            startup.RUN_KEY: {
                "Organizador": f'"{other_dir}\\Organizador.exe" --background',
            },
            startup.LEGACY_PROTOCOL_KEY + r"\shell\open\command": {
                "": f'"{other_dir}\\Organizador.exe" --notification-uri "%1"',
            },
        }
    )
    monkeypatch.setattr(
        startup, "sys", SimpleNamespace(frozen=True, executable=str(app_dir / "SortInator.exe"))
    )
    monkeypatch.setattr(startup, "winreg", registry)
    monkeypatch.setattr(
        startup, "start_menu_shortcut_path", lambda *args, **kwargs: tmp_path / "missing.lnk"
    )

    startup.cleanup_legacy_shell_integration()

    assert registry.keys[startup.RUN_KEY]["Organizador"].startswith(f'"{other_dir}')
    assert startup.LEGACY_PROTOCOL_KEY + r"\shell\open\command" in registry.keys
