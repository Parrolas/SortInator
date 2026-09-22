"""Current-user Windows login startup, Start Menu and Explorer registration."""

from __future__ import annotations

import logging
import os
import re
import sys
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

from organizador import __version__
from organizador.config import DEFAULT_EXTENSIONS
from organizador.i18n import _
from organizador.windows_shell import UNINSTALL_KEY, create_shortcut, shortcut_target

try:
    import winreg
except ImportError:  # pragma: no cover - Windows is the shipping platform
    winreg = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SortInator"
SHORTCUT_NAME = "SortInator.lnk"
MENU_VERB = "SortInator"
PROTOCOL_KEY = r"Software\Classes\sortinator"
MENU_ROOT = r"Software\Classes\SystemFileAssociations"
# Pre-rename registrations retired by cleanup_legacy_shell_integration().
LEGACY_VALUE_NAME = "Organizador"
LEGACY_SHORTCUT_NAME = "Organizador.lnk"
LEGACY_MENU_VERB = "Organizador"
LEGACY_PROTOCOL_KEY = r"Software\Classes\organizador"
_MENU_EXTENSION = re.compile(r"^\.[A-Za-z0-9][A-Za-z0-9._-]{0,40}$")


def startup_command() -> str:
    """Return the command Windows should run after user login."""

    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --background'
    return f'"{Path(sys.executable)}" -m organizador.main --background'


def set_launch_at_login(enabled: bool) -> None:
    """Create or remove the HKCU Run entry without administrator access."""

    if os.name != "nt" or winreg is None:
        raise OSError("O arranque automático só está disponível no Windows.")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            with suppress(FileNotFoundError):
                winreg.DeleteValue(key, VALUE_NAME)


def is_launch_at_login() -> bool:
    """Return whether the SortInator startup value currently exists."""

    if os.name != "nt" or winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except OSError:
        return False
    return bool(value)


def refresh_launch_at_login() -> bool:
    """Point the login entry at the current executable when startup is enabled.

    The registration stores an absolute path; rewriting it on every launch
    keeps a freshly updated installation authoritative without resurrecting
    an entry the user turned off.
    """

    if not getattr(sys, "frozen", False) or os.name != "nt" or winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except OSError:
        return False
    desired = startup_command()
    if str(value) == desired:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, desired)
    except OSError:
        LOGGER.warning("Could not refresh the login startup entry", exc_info=True)
        return False
    return True


def refresh_windows_integration(allowed_extensions: Iterable[str] | None = None) -> bool:
    """Refresh the login entry, Start Menu shortcut and Explorer menu."""

    if os.environ.get("SORTINATOR_DISABLE_WINDOWS_INTEGRATION") == "1":
        return False
    cleanup_legacy_shell_integration()
    refresh_launch_at_login()
    shortcut_ready = ensure_start_menu_shortcut()
    protocol_ready = register_notification_protocol()
    menu_ready = register_file_context_menu(allowed_extensions or DEFAULT_EXTENSIONS)
    refresh_installed_version()
    return shortcut_ready and protocol_ready and menu_ready


def start_menu_shortcut_path(programs_dir: Path | None = None) -> Path:
    """Return the per-user Start Menu shortcut for the packaged application."""

    if programs_dir is not None:
        return programs_dir / SHORTCUT_NAME
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / SHORTCUT_NAME


def ensure_start_menu_shortcut(programs_dir: Path | None = None) -> bool:
    """Create the notification-aware shortcut using COM, without a shell process."""
    if not getattr(sys, "frozen", False) or os.name != "nt":
        return False
    shortcut = start_menu_shortcut_path(programs_dir)
    try:
        create_shortcut(Path(sys.executable), shortcut)
    except Exception:
        LOGGER.warning("Could not create the Start Menu shortcut", exc_info=True)
        return False
    return shortcut.is_file()


def register_notification_protocol() -> bool:
    """Register only a fixed executable command, never a shell or arbitrary target."""
    if not getattr(sys, "frozen", False) or winreg is None:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, PROTOCOL_KEY) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:SortInator")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, PROTOCOL_KEY + r"\shell\open\command"
        ) as key:
            winreg.SetValueEx(
                key,
                "",
                0,
                winreg.REG_SZ,
                f'"{Path(sys.executable)}" --notification-uri "%1"',
            )
    except OSError:
        LOGGER.warning("Could not register notification activation", exc_info=True)
        return False
    return True


def context_menu_command() -> str:
    """Return the Explorer command that hands one file to this installation."""

    return f'"{Path(sys.executable)}" --organize "%1"'


def _menu_extension_verb_path(extension: str) -> str:
    return rf"{MENU_ROOT}\{extension}\shell\{MENU_VERB}"


def _safe_menu_extension(extension: str) -> bool:
    """Reject extension names that could escape their registry key."""

    return bool(_MENU_EXTENSION.match(extension))


def register_file_context_menu(allowed_extensions: Iterable[str]) -> bool:
    """Publish one Explorer verb for each accepted extension and prune old ones."""

    if not getattr(sys, "frozen", False) or winreg is None:
        return False
    command = context_menu_command()
    icon = f'"{Path(sys.executable)}",0'
    desired: set[str] = set()
    for raw in allowed_extensions:
        extension = str(raw).strip().casefold()
        if _safe_menu_extension(extension):
            desired.add(extension)
    ready = True
    for extension in sorted(desired):
        try:
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER, _menu_extension_verb_path(extension)
            ) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, _("Organizar com SortInator"))
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon)
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER, _menu_extension_verb_path(extension) + r"\command"
            ) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
        except OSError:
            LOGGER.warning("Could not register the Explorer entry for %s", extension, exc_info=True)
            ready = False
    for extension in _registered_menu_extensions(command) - desired:
        _remove_menu_extension(extension, command)
    return ready


def _registered_menu_extensions(command: str) -> set[str]:
    """Return extensions whose SortInator verb still points at this executable."""

    found: set[str] = set()
    if winreg is None:
        return found
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MENU_ROOT) as root:
            index = 0
            while True:
                try:
                    extension = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                if extension.startswith(".") and _menu_command(extension) == command:
                    found.add(extension)
    except OSError:
        return found
    return found


def _menu_command(extension: str) -> str | None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _menu_extension_verb_path(extension) + r"\command"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "")
    except OSError:
        return None
    return str(value)


def _remove_menu_extension(extension: str, command: str) -> None:
    if _menu_command(extension) != command:
        return
    with suppress(OSError):
        winreg.DeleteKey(
            winreg.HKEY_CURRENT_USER, _menu_extension_verb_path(extension) + r"\command"
        )
    with suppress(OSError):
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, _menu_extension_verb_path(extension))


def _command_executable(command: str) -> Path | None:
    """Return the executable path a quoted registry command starts with."""

    stripped = command.strip()
    if not stripped.startswith('"'):
        return None
    end = stripped.find('"', 1)
    if end <= 1:
        return None
    try:
        return Path(stripped[1:end])
    except (OSError, ValueError):  # pragma: no cover - malformed registry data
        return None


def _targets_this_install(command: str, app_dir: Path) -> bool:
    """Return whether a registry command points inside our own app folder."""

    executable = _command_executable(command)
    if executable is None:
        return False
    try:
        parent = executable.resolve(strict=False).parent
    except (OSError, RuntimeError):
        return False
    return os.path.normcase(str(parent)) == os.path.normcase(str(app_dir))


def cleanup_legacy_shell_integration() -> None:
    """Retire pre-rename registrations that point at this installation.

    An over-the-air update renames the executable without running the
    installer, so the old login value, Start Menu shortcut, protocol key and
    Explorer verbs must be removed here; the normal refresh on the same
    startup recreates their replacements. Entries that point at a different
    installation are left alone.
    """

    if not getattr(sys, "frozen", False) or winreg is None or os.name != "nt":
        return
    app_dir = Path(sys.executable).resolve().parent

    with suppress(OSError):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, _ = winreg.QueryValueEx(key, LEGACY_VALUE_NAME)
        if _targets_this_install(str(command), app_dir):
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, LEGACY_VALUE_NAME)

    legacy_shortcut = start_menu_shortcut_path().with_name(LEGACY_SHORTCUT_NAME)
    with suppress(Exception):
        if legacy_shortcut.is_file():
            target = shortcut_target(legacy_shortcut)
            if not target.exists() or _targets_this_install(f'"{target}"', app_dir):
                legacy_shortcut.unlink()

    with suppress(OSError):
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, LEGACY_PROTOCOL_KEY + r"\shell\open\command"
        ) as key:
            command, _ = winreg.QueryValueEx(key, "")
        if _targets_this_install(str(command), app_dir):
            for suffix in (r"\shell\open\command", r"\shell\open", r"\shell", ""):
                with suppress(OSError):
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, LEGACY_PROTOCOL_KEY + suffix)

    for extension in _legacy_menu_extensions(app_dir):
        _remove_legacy_menu_extension(extension)


def _legacy_menu_verb_path(extension: str) -> str:
    return rf"{MENU_ROOT}\{extension}\shell\{LEGACY_MENU_VERB}"


def _legacy_menu_extensions(app_dir: Path) -> set[str]:
    """Return extensions whose pre-rename verb still points at this install."""

    found: set[str] = set()
    if winreg is None:
        return found
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MENU_ROOT) as root:
            index = 0
            while True:
                try:
                    extension = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                if not extension.startswith("."):
                    continue
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, _legacy_menu_verb_path(extension) + r"\command"
                    ) as key:
                        command, _ = winreg.QueryValueEx(key, "")
                except OSError:
                    continue
                if _targets_this_install(str(command), app_dir):
                    found.add(extension)
    except OSError:
        return found
    return found


def _remove_legacy_menu_extension(extension: str) -> None:
    with suppress(OSError):
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, _legacy_menu_verb_path(extension) + r"\command")
    with suppress(OSError):
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, _legacy_menu_verb_path(extension))


def refresh_installed_version() -> None:
    """Update metadata only when the uninstaller owns this exact runtime folder."""
    if not getattr(sys, "frozen", False) or winreg is None:
        return
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
        ) as key:
            root, _ = winreg.QueryValueEx(key, "InstallLocation")
            if (Path(root) / "app").resolve() != Path(sys.executable).resolve().parent:
                return
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, __version__)
    except OSError:
        return


def unregister_windows_integration() -> None:
    """Remove registrations only if they still point to this executable."""
    if not getattr(sys, "frozen", False) or winreg is None:
        return
    cleanup_legacy_shell_integration()
    expected = f'"{Path(sys.executable)}"'
    with suppress(OSError):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, _ = winreg.QueryValueEx(key, VALUE_NAME)
        if command == expected + " --background":
            set_launch_at_login(False)
    with suppress(OSError):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PROTOCOL_KEY + r"\shell\open\command") as key:
            command, _ = winreg.QueryValueEx(key, "")
        if command == expected + ' --notification-uri "%1"':
            for suffix in (r"\shell\open\command", r"\shell\open", r"\shell", ""):
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, PROTOCOL_KEY + suffix)
            with suppress(Exception):
                from winrt.windows.ui.notifications import ToastNotificationManager

                from organizador.windows_shell import AUMID

                ToastNotificationManager.history.clear_with_id(AUMID)
    menu_command = context_menu_command()
    for extension in _registered_menu_extensions(menu_command):
        _remove_menu_extension(extension, menu_command)
    shortcut = start_menu_shortcut_path()
    with suppress(Exception):
        if shortcut_target(shortcut).resolve() == Path(sys.executable).resolve():
            shortcut.unlink()
