"""Generate PyInstaller Windows version metadata from the package version."""

from __future__ import annotations

import argparse
from pathlib import Path

from organizador import __version__


def main() -> None:
    """Write the metadata file consumed by PyInstaller."""

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    numbers = tuple(int(part) for part in __version__.split("."))
    if len(numbers) != 3:
        raise ValueError("A versão deve usar o formato MAJOR.MINOR.PATCH.")
    version = (*numbers, 0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version!r},
    prodvers={version!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'José Parrolas'),
         StringStruct('FileDescription', 'SortInator - organização de ficheiros de estudo'),
         StringStruct('FileVersion', '{__version__}'),
         StringStruct('InternalName', 'SortInator'),
         StringStruct('LegalCopyright', 'Copyright (c) 2026 José Parrolas'),
         StringStruct('OriginalFilename', 'SortInator.exe'),
         StringStruct('ProductName', 'SortInator'),
         StringStruct('ProductVersion', '{__version__}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
