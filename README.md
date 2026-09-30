# SortInator

English · [Português](README.pt.md)

A local Windows 11 app that watches Downloads, asks how to classify academic
files, and keeps a searchable library by subject, topic and content type —
with backups of the catalog.

**Contents:** [Video](#video) · [Features](#features) ·
[File protection](#file-protection) · [Install on
Windows](#install-on-windows) · [Tray area](#tray-area) ·
[Backups](#backups) · [Data & privacy](#data--privacy) ·
[Update & rollback](#update--rollback) · [Uninstall](#uninstall) ·
[Current limitations](#current-limitations) · [Contributing](#contributing) ·
[Code-signing policy](#code-signing-policy) · [Licenses](#licenses)

## Video

[![SortInator intro video](https://github.com/user-attachments/assets/93e18966-5711-49b7-adc9-3c25867b47b5)](https://github.com/user-attachments/assets/e362318e-088a-42be-adcc-72284971a93a)

*Intro video — 22 seconds (Portuguese narration). Click to watch with music.*

## Features

**Watching and intake**

- Watches only new eligible files in the configured Downloads folder; the
  accepted extensions are configurable in Settings.
- Moves every file into a safe inbox before asking for a decision.
- Lets you import existing files manually in capped batches.
- Recovers interrupted operations without guessing when state is ambiguous.

**Filing decisions**

- The popup shows the suggested subject and type and waits for your decision;
  it can also close by itself after N seconds, if you enable that in Settings.
- Lets you choose subject, content type, final name and an optional task with
  a due date.
- Detects when the same file is already in the catalog and shows where it is:
  you can open the existing one or replace the previous version, which stays
  in the folder with the "previous version" suffix and is restored when you
  undo the filing.
- "Later" keeps the file in the inbox; "✕" and "Not university material"
  return it to its source folder.
- Files without silently overwriting existing files.
- Moves an already-filed document to another type of the same subject or to
  another subject, keeping the catalog and search up to date.

**Search and indexing**

- Keeps local full-text search over file names and content of the supported
  formats (PDF, DOCX, PPTX, XLSX, IPYNB, Markdown, TXT and CSV), backed by a
  SQLite FTS index.
- Reads scanned (image-only) PDFs with Windows OCR when the option is on.
- Lets you adopt into the catalog a file that already exists in a subject
  folder without moving it, and mark reconciliation findings as reviewed.
- Keeps history and lets you undo the most recent filing.

**Study organisation**

- Manage subjects with code, colour, keywords and folder, plus their
  per-content-type folders.
- Keeps tasks with due dates, a calendar and a configurable lead-time
  reminder.

**Windows integration**

- Explorer context menu: "Organize with SortInator" for files with the
  configured extensions; "Return" puts them back in their source folder.
- Native clickable notifications ("Show in folder") that keep working after
  the app closes.
- Lives in the notification area and can start with the Windows session.
- Five themes and an interface in Portuguese, English, Spanish or French.

**Keyboard navigation**

- `Ctrl+K` opens the command palette: type to filter and run actions such as
  navigating between pages, importing from Downloads, pausing or resuming
  watching, undoing the latest filing, checking for updates, opening the
  University folder or creating a backup.
- `Ctrl+F` focuses the notes search; `Ctrl+1` to `Ctrl+6` open the pages
  directly.
- In the filing popup, keys `1` to `9` pick the subject.

**Backups**

- Creates copies of the catalog and settings, exports them as a portable
  `.zip`, imports them back and restores them with full validation.
- Manual backups are never deleted automatically.

## File protection

SortInator never replaces or deletes documents silently. It waits for a
download to stop being temporary and stay stable, uses alternative names such
as `name (2).pdf` on collisions, and journals every move so it can recover
after an interruption. Ambiguous states stay visible for manual review
instead of being guessed away.

Replacing a previous version never erases the existing file: the old one is
renamed with the "previous version" suffix and the pair of moves is reverted
when you undo the filing.

Files that were already in Downloads before startup are not imported
automatically. Manual import requires confirmation and processes at most 25
files per batch.

Backups and restores cover only the catalog and settings. Neither updates
nor restores ever touch the University folder or Downloads.

When quitting, file operations already accepted finish before the app
closes. While they run, saving settings or installing an update is blocked
with an explanation. Copies interrupted mid-transfer stay for manual review
in the inbox.

## Install on Windows

The per-user installer is the recommended way. It installs into
`%LOCALAPPDATA%\Programs\SortInator` without asking for administrator
rights, creates the Start Menu entry (and a desktop shortcut if you want)
and shows up under **Installed apps** for uninstalling.

1. Open the version you want on the
   [Releases](https://github.com/Parrolas/SortInator/releases) page.
2. Download `SortInator-<version>-Setup.exe` and the matching `.sha256`
   file.
3. Verify the SHA-256 in PowerShell:

   ```powershell
   Get-FileHash .\SortInator-<version>-Setup.exe -Algorithm SHA256
   Get-Content .\SortInator-<version>-Setup.exe.sha256
   ```

4. Confirm both values match and run the `Setup.exe`. Quit SortInator from
   the tray icon menu before installing or uninstalling.

### Portable version (ZIP)

You can also use `SortInator-<version>-windows-x64.zip`. Verify the
`.sha256` the same way, extract the whole ZIP into a permanent folder and
run `SortInator.exe`. Don't move just the executable: the `_internal` folder
that ships with it is required too.

The executable is not code-signed yet. Microsoft Defender SmartScreen may
show "Windows protected your PC" on first run. If the file came from the
official page and the SHA-256 matches, choose **More info** and then **Run
anyway**. Never ignore the warning if the source or the hash is not what you
expect.

On first run you choose the University folder. By default the app uses
`Documents\Universidade`, creates `_Caixa de Entrada` (the inbox) inside it
and watches the Windows-known Downloads folder. Everything can be changed in
**Settings**, including the accepted extensions, the name template and
notifications.

## Tray area

Closing the main window does not end the app: it hides to the tray to keep
watching Downloads. The icon menu lets you open the inbox, pause watching,
undo the latest filing, check and install updates, open Settings and quit.

Filing notifications are native Windows toasts: clicking one opens the
folder with the file selected, even after the app has closed. In a batch
with several destinations, the notification lists the files in a window
with a "Show in folder" action.

## Backups

In **Settings → Backups** you can create a manual copy of the catalog and
settings, export it as a portable `.zip` (to a USB stick or another folder,
for example) and restore it later.

- **Create backup now** creates an internal copy under
  `%LOCALAPPDATA%\SortInator\backups`.
- **Create and export .zip…** creates the copy and also writes a
  `SortInator-backup-<date>.zip` into the folder you choose.
- **Restore…** lists the available backups (manual, pre-update and
  pre-restore) and lets you import a `.zip`. Restoring validates the
  manifest and every hash, first creates an automatic backup of the current
  data, and only then replaces the catalog and settings; the app reopens by
  itself to finish. Your documents are not touched.
- Manual backups are never deleted automatically. Automatic backups (taken
  before updating or restoring) keep the two newest of each kind, for at
  most 30 days.

A backup covers the catalog, history, search index and settings — it does
not include the University folder documents, which remain the original
files.

## Data & privacy

SortInator works locally. It never sends files, names, content or usage
statistics to external services; the update check only contacts GitHub to
read the latest version number.

Internal data lives in `%LOCALAPPDATA%\SortInator`:

- `settings.json`: application settings.
- `sortinator.db`: SQLite catalog, history and search index.
- `backups\`: catalog and settings backups.
- `updates\`: transient update state.
- `sortinator.log`: local rotating diagnostics.

Your documents stay in the University folder you choose. The app never uses
the database as a copy of your documents.

## Update & rollback

The app automatically checks for a new version at startup (you can turn
this off in Settings). When one exists, "Install update" appears in the
tray icon menu; one click downloads it, verifies the published SHA-256 and
package version, stages the update in an isolated area and only then
restarts to apply it. A dedicated helper waits for the old app to exit,
swaps the folders with per-step verification and only confirms once the new
version starts successfully. Your data always stays in
`%LOCALAPPDATA%\SortInator` and is never touched by the update.

The app follows published stable releases. A prerelease is installed
manually with its own Setup or ZIP.

Before any database migration the app creates an automatic backup (database
and settings) and only seals it after a full successful startup. If the new
version fails before it becomes healthy — including after the folder swap —
the previous version and data are restored automatically and the outcome is
shown once at the next startup. After the app is healthy there is never an
automatic data rollback: the previous version is kept for manual recovery.

The previous version is kept in a rollback folder until the new startup
runs successfully, serving as an immediate rollback if anything goes wrong.

Before updating manually:

1. Use **Quit** on the notification-area icon.
2. Create a backup in **Settings → Backups** (or copy the
   `%LOCALAPPDATA%\SortInator` folder).
3. Keep the Setup/ZIP of the current version until you have confirmed the
   new one.
4. Install the new Setup or extract the new version into a fresh folder and
   run it.

Database migrations are automatic. To roll back, quit the app, go back to
the previous Setup/ZIP and also restore the data backup made by that
version. Do not mix an already-migrated database with an older executable.
The documents in the University folder never need restoring.

## Uninstall

**Installer (recommended):**

1. In **Settings**, turn off **Start SortInator when I sign in to Windows**
   and save (uninstalling also clears that registration).
2. Use **Quit** on the notification-area icon.
3. In Windows **Installed apps**, uninstall **SortInator**.

Uninstalling removes the program, shortcuts and Windows registrations, but
keeps `%LOCALAPPDATA%\SortInator` so you can reinstall without losing the
catalog.

**Portable version:**

1. Use **Quit** on the notification-area icon.
2. Delete the folder where you extracted the app.
3. If you also want to erase the catalog, history, settings, backups and
   logs, delete `%LOCALAPPDATA%\SortInator`.

In either case, uninstalling never deletes the University folder or the
documents inside it.

## Current limitations

- Scanned (image-only) PDFs are read by Windows OCR when the option is
  enabled in Settings. Preferred languages follow the app language
  (Portuguese, English, Spanish or French), falling back to English;
  without the language pack installed, those files are searchable by name
  only.
- `.doc`, `.ppt`, `.xls` and OneNote files can be filed, but their content
  is not indexed.
- Documents over 50 MB are filed without indexing to limit background
  memory.
- The text indexed per document is capped to protect the database; very
  long documents stay searchable by their beginning.
- Learned suggestions depend on repeated naming patterns and still require
  confirmation.
- The Explorer context menu only appears for the extensions configured in
  Settings.
- The filing popup handles one file at a time; the rest queue up until they
  are reviewed.
- Backups cover the catalog and settings, not the documents.
- Moves between different drives preserve content, dates and basic
  attributes, but not alternate data streams (ADS), ACLs, encryption or
  fragmentation; those cases are recorded in the diagnostics.

## Contributing

Development, build and release instructions live in
[CONTRIBUTING.md](CONTRIBUTING.md). The
[one-week daily-use checklist](docs/daily-use-checklist.md) helps you log
concrete issues before choosing the next improvement.

## Code-signing policy

**Code signing policy.** Free code signing provided by SignPath.io,
certificate by SignPath Foundation.

Published SortInator releases are digitally signed through the SignPath
Foundation open-source program, which verifies that every binary was built
from this repository. The certificate private key is generated and stored
in SignPath's hardware security module (HSM); it never leaves it.

Team roles (all held by José Parrolas,
[@Parrolas](https://github.com/Parrolas)):

- Committers and reviewers: the repository maintainer.
- Approvers: the repository maintainer.

Privacy policy: [PRIVACY.md](PRIVACY.md) — the app runs locally and does
not transfer information to other networked systems, except the GitHub
update check when enabled. Code of conduct:
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Licenses

SortInator's code is distributed under the MIT license in `LICENSE`. The
Windows package includes third-party components under their own licenses,
documented in `LICENSES/THIRD-PARTY-NOTICES.md` and the respective license
texts.
