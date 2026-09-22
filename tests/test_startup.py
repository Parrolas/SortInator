"""Start Menu shortcut registration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import pythoncom
from win32com.propsys import propsys
from win32com.shell import shell

from organizador import startup


def test_shortcut_path_resolution_uses_the_programs_override(tmp_path: Path) -> None:
    assert startup.start_menu_shortcut_path(tmp_path) == tmp_path / "SortInator.lnk"


def test_ensure_shortcut_skips_source_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(startup.sys, "frozen", raising=False)

    created = startup.ensure_start_menu_shortcut(tmp_path)

    assert created is False
    assert not (tmp_path / "SortInator.lnk").exists()


def test_ensure_shortcut_creates_a_real_lnk_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)

    created = startup.ensure_start_menu_shortcut(tmp_path)

    assert created is True
    shortcut = tmp_path / "SortInator.lnk"
    assert shortcut.is_file()
    assert shortcut.read_bytes().startswith(b"\x4c\x00\x00\x00")


def test_ensure_shortcut_refreshes_an_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    shortcut = tmp_path / "SortInator.lnk"
    shortcut.write_bytes(b"stale placeholder")

    created = startup.ensure_start_menu_shortcut(tmp_path)

    assert created is True
    assert shortcut.is_file()
    assert shortcut.read_bytes().startswith(b"\x4c\x00\x00\x00")


def test_shortcut_failure_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)

    def fail(*args: object) -> None:
        raise OSError("access denied")

    monkeypatch.setattr(startup, "create_shortcut", fail)
    assert startup.ensure_start_menu_shortcut(tmp_path) is False


def test_native_shortcut_preserves_unicode_and_notification_identity(tmp_path: Path) -> None:
    from organizador.windows_shell import AUMID, TOAST_CLSID, create_shortcut, shortcut_target

    target = tmp_path / "José's material & notas" / "SortInator.exe"
    shortcut = tmp_path / "Menu" / "SortInator.lnk"
    create_shortcut(target, shortcut)
    assert shortcut_target(shortcut) == target
    pythoncom.CoInitialize()
    try:
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
        )
        link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(shortcut))
        properties = link.QueryInterface(propsys.IID_IPropertyStore)
        assert (
            properties.GetValue(
                propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID")
            ).GetValue()
            == AUMID
        )
        assert (
            str(
                properties.GetValue(
                    propsys.PSGetPropertyKeyFromName("System.AppUserModel.ToastActivatorCLSID")
                ).GetValue()
            )
            == TOAST_CLSID
        )
    finally:
        pythoncom.CoUninitialize()


def test_refresh_launch_at_login_rewrites_a_stale_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    values = {"SortInator": '"C:\\instalacao-antiga\\SortInator.exe" --background'}
    written: dict[str, str] = {}

    class _FakeKey:
        def __enter__(self) -> _FakeKey:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def QueryValueEx(self, _key: object, name: str) -> tuple[object, int]:
            return values[name], 1

        def SetValueEx(
            self, _key: object, name: str, _reserved: int, _type: object, value: str
        ) -> None:
            written[name] = value

    class _FakeWinreg:
        HKEY_CURRENT_USER = 2147483649
        KEY_SET_VALUE = 2
        REG_SZ = 1

        def OpenKey(self, _hive: object, _path: str, *_rest: object) -> _FakeKey:
            return _FakeKey()

        def QueryValueEx(self, _key: object, name: str) -> tuple[object, int]:
            return values[name], 1

        def SetValueEx(
            self, _key: object, name: str, _reserved: int, _type: object, value: str
        ) -> None:
            written[name] = value

    fake = _FakeWinreg()
    monkeypatch.setattr(startup, "winreg", fake)

    assert startup.refresh_launch_at_login() is True
    assert written["SortInator"] == startup.startup_command()

    values["SortInator"] = written["SortInator"]
    assert startup.refresh_launch_at_login() is False


def test_refresh_launch_at_login_keeps_a_disabled_entry_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    written: dict[str, str] = {}

    class _FakeWinreg:
        HKEY_CURRENT_USER = 2147483649
        KEY_SET_VALUE = 2
        REG_SZ = 1

        def OpenKey(self, _hive: object, _path: str, *_rest: object) -> object:
            raise OSError("value missing")

    class _RecordingWinreg(_FakeWinreg):
        def SetValueEx(
            self, _key: object, name: str, _reserved: int, _type: object, value: str
        ) -> None:
            written[name] = value

    monkeypatch.setattr(startup, "winreg", _RecordingWinreg())

    assert startup.refresh_launch_at_login() is False
    assert written == {}


def test_refresh_windows_integration_refreshes_both_surfaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SORTINATOR_DISABLE_WINDOWS_INTEGRATION", raising=False)
    calls: list[str] = []
    monkeypatch.setattr(startup, "refresh_launch_at_login", lambda: calls.append("run") or True)
    monkeypatch.setattr(
        startup, "ensure_start_menu_shortcut", lambda *args, **kwargs: calls.append("shortcut")
    )

    startup.refresh_windows_integration()

    assert calls == ["run", "shortcut"]


def test_isolated_update_suppresses_all_machine_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SORTINATOR_DISABLE_WINDOWS_INTEGRATION", "1")
    monkeypatch.setattr(startup, "refresh_launch_at_login", lambda: pytest.fail("registry write"))
    assert startup.refresh_windows_integration() is False


class _FakeKeyContext:
    def __init__(self, registry: _FakeRegistry, path: str) -> None:
        self._registry = registry
        self.path = path

    def __enter__(self) -> _FakeKeyContext:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _FakeRegistry:
    HKEY_CURRENT_USER = 2147483649
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.keys: dict[str, dict[str, str]] = {startup.MENU_ROOT: {}}

    def CreateKey(self, _hive: object, path: str) -> _FakeKeyContext:
        self.keys.setdefault(path, {})
        return _FakeKeyContext(self, path)

    def OpenKey(self, _hive: object, path: str, *_rest: object) -> _FakeKeyContext:
        if path not in self.keys:
            raise FileNotFoundError(path)
        return _FakeKeyContext(self, path)

    def SetValueEx(
        self, key: _FakeKeyContext, name: str, _reserved: int, _type: object, value: str
    ) -> None:
        self.keys[key.path][name] = value

    def QueryValueEx(self, key: _FakeKeyContext, name: str) -> tuple[str, int]:
        values = self.keys[key.path]
        if name not in values:
            raise FileNotFoundError(name)
        return str(values[name]), 1

    def EnumKey(self, key: _FakeKeyContext, index: int) -> str:
        prefix = key.path + "\\"
        children = sorted(
            {name[len(prefix) :].split("\\", 1)[0] for name in self.keys if name.startswith(prefix)}
        )
        if index >= len(children):
            raise OSError("no more data")
        return children[index]

    def DeleteKey(self, _hive: object, path: str) -> None:
        if path not in self.keys:
            raise FileNotFoundError(path)
        del self.keys[path]


def test_context_menu_command_quotes_the_selected_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(startup.sys, "executable", r"C:\Programa Files\SortInator.exe")

    assert startup.context_menu_command() == '"C:\\Programa Files\\SortInator.exe" --organize "%1"'


def test_context_menu_registers_one_verb_per_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    fake = _FakeRegistry()
    monkeypatch.setattr(startup, "winreg", fake)

    assert startup.register_file_context_menu([".PDF", ".docx", "..\\Run", "invalida"]) is True

    command = startup.context_menu_command()
    verb = f"{startup.MENU_ROOT}\\.pdf\\shell\\SortInator"
    assert fake.keys[verb][""] == "Organizar com SortInator"
    assert fake.keys[verb]["Icon"].endswith(",0")
    assert fake.keys[verb + "\\command"][""] == command
    assert f"{startup.MENU_ROOT}\\.docx\\shell\\SortInator\\command" in fake.keys
    assert not any("Run" in path for path in fake.keys)
    assert not any("invalida" in path for path in fake.keys)


def test_context_menu_prunes_stale_verbs_only_when_ours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    fake = _FakeRegistry()
    monkeypatch.setattr(startup, "winreg", fake)
    command = startup.context_menu_command()
    fake.keys[f"{startup.MENU_ROOT}\\.txt\\shell\\SortInator"] = {}
    fake.keys[f"{startup.MENU_ROOT}\\.txt\\shell\\SortInator\\command"] = {"": command}
    fake.keys[f"{startup.MENU_ROOT}\\.rtf\\shell\\SortInator"] = {}
    fake.keys[f"{startup.MENU_ROOT}\\.rtf\\shell\\SortInator\\command"] = {
        "": '"outro.exe" --organize "%1"'
    }

    assert startup.register_file_context_menu([".pdf"]) is True

    assert f"{startup.MENU_ROOT}\\.txt\\shell\\SortInator" not in fake.keys
    assert f"{startup.MENU_ROOT}\\.pdf\\shell\\SortInator\\command" in fake.keys
    assert fake.keys[f"{startup.MENU_ROOT}\\.rtf\\shell\\SortInator\\command"][""] == (
        '"outro.exe" --organize "%1"'
    )


def test_unregister_removes_only_our_explorer_verbs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    fake = _FakeRegistry()
    monkeypatch.setattr(startup, "winreg", fake)
    command = startup.context_menu_command()
    fake.keys[f"{startup.MENU_ROOT}\\.pdf\\shell\\SortInator"] = {}
    fake.keys[f"{startup.MENU_ROOT}\\.pdf\\shell\\SortInator\\command"] = {"": command}
    fake.keys[f"{startup.MENU_ROOT}\\.rtf\\shell\\SortInator"] = {}
    fake.keys[f"{startup.MENU_ROOT}\\.rtf\\shell\\SortInator\\command"] = {
        "": '"outro.exe" --organize "%1"'
    }

    startup.unregister_windows_integration()

    assert f"{startup.MENU_ROOT}\\.pdf\\shell\\SortInator" not in fake.keys
    assert fake.keys[f"{startup.MENU_ROOT}\\.rtf\\shell\\SortInator\\command"][""] == (
        '"outro.exe" --organize "%1"'
    )


def test_refresh_windows_integration_registers_the_explorer_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SORTINATOR_DISABLE_WINDOWS_INTEGRATION", raising=False)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(startup, "refresh_launch_at_login", lambda: True)
    monkeypatch.setattr(startup, "ensure_start_menu_shortcut", lambda *args, **kwargs: True)
    monkeypatch.setattr(startup, "register_notification_protocol", lambda: True)
    monkeypatch.setattr(
        startup,
        "register_file_context_menu",
        lambda extensions: calls.append(tuple(extensions)) or True,
    )

    assert startup.refresh_windows_integration([".pdf", ".docx"]) is True
    assert calls == [(".pdf", ".docx")]
