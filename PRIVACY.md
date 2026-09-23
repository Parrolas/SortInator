# SortInator Privacy Policy

SortInator is a local-first desktop application. It does not send your files,
file names, file contents, or usage statistics to any external service.

The only network request the application itself makes is the update check: it
contacts GitHub (`api.github.com`) to read the latest release version number,
and only when automatic update checks are enabled (they are on by default and
can be turned off in Settings). When you install an update, the release archive
is downloaded from GitHub Releases and its SHA-256 checksum is verified before
use.

All application data — settings, the SQLite catalogue, search index, backups,
update state and the local diagnostic log — stays on your computer under
`%LOCALAPPDATA%\SortInator`. Your study documents stay in the university folder
you chose. Nothing is uploaded anywhere.

Third-party components bundled with the Windows package (Qt, Python and the
libraries listed in `LICENSES/THIRD-PARTY-NOTICES.md`) run locally as part of
the application and make no network requests of their own.

If you have privacy questions, open an issue at
https://github.com/Parrolas/SortInator/issues.
