# Third-party notices

SortInator is distributed under the MIT License. The Windows package also
contains the following independent open-source components. Each component
remains governed by its own license.

## Qt and Qt for Python

The package uses unmodified, dynamically linked Qt 6 libraries through
PySide6-Essentials and shiboken6. They are used under the GNU Lesser General
Public License version 3. The distribution does not prohibit reverse
engineering for debugging modifications to those libraries. Compatible Qt
DLLs can be replaced in the package's `_internal` directory.

- PySide6-Essentials 6.11.2 and shiboken6 6.11.2
- License: LGPL-3.0-only (the packages also offer GPL/commercial alternatives)
- Source: https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.11.2
- Qt source: https://download.qt.io/archive/qt/6.11/6.11.2/single/
- License texts: `LGPL-3.0.txt` and `GPL-3.0.txt`

No Qt or PySide source files were modified for this distribution.

## Python and packaging

- Python 3.13: Python Software Foundation License Version 2. The exact license
  from the interpreter used to build the package is in `PYTHON-LICENSE.txt`.
- PyInstaller bootloader 6.22.2: GPL-2.0-or-later with the PyInstaller
  bootloader exception. Its exact `COPYING.txt` is collected under `packages`.

## Python libraries

Native Windows shell integration uses pywin32 312. Its exact license is
included under `packages/pywin32-312`; project: https://github.com/mhammond/pywin32.

| Component | Version | License | Project |
| --- | --- | --- | --- |
| defusedxml | 0.7.1 | PSF-2.0 | https://github.com/tiran/defusedxml |
| openpyxl | 3.1.5 | MIT | https://openpyxl.readthedocs.io |
| et_xmlfile | 2.0.0 | MIT | https://foss.heptapod.net/openpyxl/et_xmlfile |
| pypdf | 6.16.2 | BSD-3-Clause | https://pypdf.readthedocs.io |
| python-docx | 1.2.0 | MIT | https://github.com/python-openxml/python-docx |
| python-pptx | 1.0.2 | MIT | https://github.com/scanny/python-pptx |
| lxml | 6.1.2 | BSD-3-Clause | https://lxml.de |
| Pillow | 12.3.0 | MIT-CMU | https://python-pillow.github.io |
| XlsxWriter | 3.2.9 | BSD-2-Clause | https://xlsxwriter.readthedocs.io |
| RapidFuzz | 3.14.5 | MIT | https://github.com/rapidfuzz/RapidFuzz |
| watchdog | 6.0.0 | Apache-2.0 | https://github.com/gorakhargosh/watchdog |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |

`defusedxml` is an intentional runtime dependency. `openpyxl` detects it at
runtime and uses its hardened XML parser when reading untrusted workbooks.

## PDF rendering and OCR

The packaged app bundles the following components for PDF text extraction and
Windows OCR; these distributions ship no license file of their own, so their
terms are documented here.

- pypdfium2 5.13.0: BSD-3-Clause. Project:
  https://github.com/pypdfium2-team/pypdfium2. It bundles Google's PDFium
  binary (`pdfium.dll`), licensed under Apache-2.0:
  https://pdfium.googlesource.com/pdfium/
- Python/WinRT projections 3.2.1 (`winrt-runtime`, `winrt-Windows.Foundation`,
  `winrt-Windows.Foundation.Collections`, `winrt-Windows.Globalization`,
  `winrt-Windows.Graphics.Imaging`, `winrt-Windows.Media.Ocr`,
  `winrt-Windows.Storage.Streams`, `winrt-Windows.UI.Notifications`,
  `winrt-Windows.Data.Xml.Dom`): MIT License. Project:
  https://github.com/pywinrt/pywinrt

  Permission is hereby granted, free of charge, to any person obtaining a
  copy of this software and associated documentation files (the "Software"),
  to deal in the Software without restriction, including without limitation
  the rights to use, copy, modify, merge, publish, distribute, sublicense,
  and/or sell copies of the Software, and to permit persons to whom the
  Software is furnished to do so, subject to the following conditions: the
  above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED
  "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
  NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
  PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
  ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
  CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
- The OCR engine itself is a Windows component (Windows.Media.Ocr); it is
  not redistributed with the package.

The build copies the exact license, copying, notice, and author files supplied
by these installed distributions into the `packages` subdirectory. Copyright
notices in those files are retained verbatim.

Qt itself includes additional third-party software. Its authoritative notices
and corresponding source references are published with the Qt 6.11.2 source
distribution linked above.
