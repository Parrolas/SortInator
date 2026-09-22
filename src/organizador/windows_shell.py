"""Native Windows shell integration, without command interpreters."""

from __future__ import annotations

import ctypes
from pathlib import Path

AUMID = "Parrolas.SortInator"
TOAST_CLSID = "{B6886E9C-F2BF-46C0-8C4B-2B157B393D4F}"
APP_MUTEX = "Local\\Parrolas.SortInator.Running"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SortInator_is1"


class AppMutex:
    """Let Setup detect the app until its normal transfer-safe exit completes."""

    def __init__(self) -> None:
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        self._kernel.CreateMutexW.restype = ctypes.c_void_p
        self._kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel.CloseHandle.restype = ctypes.c_bool
        self._handle = self._kernel.CreateMutexW(None, False, APP_MUTEX)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self._handle:
            self._kernel.CloseHandle(self._handle)
            self._handle = None


def create_shortcut(target: Path, shortcut: Path) -> None:
    """Write the app identity and protocol-only toast activator into a shortcut."""
    import pythoncom
    import pywintypes
    from win32com.propsys import propsys
    from win32com.shell import shell

    shortcut.parent.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    try:
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
        )
        link.SetPath(str(target))
        link.SetWorkingDirectory(str(target.parent))
        link.SetIconLocation(str(target), 0)
        link.SetDescription("SortInator - estudo local")
        properties = link.QueryInterface(propsys.IID_IPropertyStore)
        properties.SetValue(
            propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID"),
            propsys.PROPVARIANTType(AUMID),
        )
        properties.SetValue(
            propsys.PSGetPropertyKeyFromName("System.AppUserModel.ToastActivatorCLSID"),
            propsys.PROPVARIANTType(pywintypes.IID(TOAST_CLSID), pythoncom.VT_CLSID),
        )
        properties.Commit()
        link.QueryInterface(pythoncom.IID_IPersistFile).Save(str(shortcut), 1)
    finally:
        pythoncom.CoUninitialize()


def reveal_files(paths: list[Path]) -> None:
    """Select files together in Explorer; callers supply one common directory."""
    import pythoncom
    from win32com.shell import shell

    if not paths:
        return
    parent = paths[0].parent
    if any(path.parent != parent for path in paths):
        raise ValueError("Explorer selection requires one folder")
    pythoncom.CoInitialize()
    try:
        folder = shell.SHILCreateFromPath(str(parent), 0)[0]
        children = [shell.SHILCreateFromPath(str(path), 0)[0][-1:] for path in paths]
        shell.SHOpenFolderAndSelectItems(folder, children, 0)
    finally:
        pythoncom.CoUninitialize()


def shortcut_target(shortcut: Path) -> Path:
    import pythoncom
    from win32com.shell import shell

    pythoncom.CoInitialize()
    try:
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
        )
        link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(shortcut))
        return Path(link.GetPath(0)[0])
    finally:
        pythoncom.CoUninitialize()
