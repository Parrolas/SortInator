# Changelog

All notable changes to Organizador are recorded here.

## 0.17.1 - 2026-09-20

### Fixed

- An update whose data validation hit a transient file lock (for example an
  antivirus scan) can no longer leave an installation that refuses to start:
  bundle validation retries briefly before quarantining, and a failed update
  handshake rolls the data back even when the bundle was already quarantined.
- Deleting a file and re-downloading the same name no longer bounces with a
  database conflict: a new ingest adopts the stale inbox row that still owns
  the destination path.
- One conflicted interrupted ingest no longer aborts the whole startup
  reconciliation; the item stays visible as a finding while everything else
  is still repaired.
- "Remover do catálogo" and "Remover registo em falta" refuse while a move is
  in flight, so a document can no longer end up untracked on disk.
- Saving settings (or any watcher restart) during stabilization no longer
  strands a download: undelivered candidates are handed to the new watcher.
- Files below the configured minimum size no longer occupy the stabilizer for
  two minutes per attempt; they are rejected once after they finish and are
  reconsidered only when their content changes.
- An update helper that never becomes ready is terminated before its lock is
  released; if it cannot be stopped, the lock is kept and the notice explains
  that a restart is needed instead of letting a second helper race it.
- Backup import enforces decompressed size caps (512 MiB database, 16 MiB
  settings, 1 GiB total) and refuses encrypted members, so a crafted archive
  can no longer fill the disk before validation.
- Rolled-back updates reclaim their staged application copy on a later launch
  instead of retaining it forever.
- The adopt-file dialog, the "Rever {name}" task titles created from the
  filing prompt, and settings validation errors now follow the selected
  language.

## 0.17.0 - 2026-09-19

### Added

- The keyboard command palette (`Ctrl+K`) finds and runs navigation and app
  actions — pages, notes search, import from Downloads, pause or resume
  watching, undo, check updates, open the University folder and create a
  backup — with accent-tolerant, debounced filtering on a worker thread.
  `Ctrl+F` focuses the notes search; `Ctrl+1`–`Ctrl+6` still navigate.
- Settings are organised into four titled groups (pastas, vigilância,
  aparência e idioma, cópias de segurança) separated by one-pixel rules in a
  single scrollable body, with boolean settings as painted switches and the
  save action fixed outside the scrolling body.
- The tasks calendar sits in a 300px panel beside the task list and folds
  behind a labeled toggle below a 1120px window width; weekend days render
  in the regular text colour.

### Fixed

- The settings body fills the available window height, so the save row
  stays pinned at the bottom instead of floating mid-page.
- Scrolling over the settings value controls no longer edits them: the
  wheel always scrolls the page; values change through typing, arrow keys
  or the control's own steppers.
- Switch state changes keep a short 140ms thumb travel (instant in the
  high-contrast theme) while remaining immediate in behaviour.

## 0.16.2 - 2026-09-16

### Fixed

- Moving a document that is still queued for indexing no longer strands it:
  the indexer requeues from the document's current path when the recorded path
  disappears, and a guarded write rejected because the file moved during
  extraction is retried by the refill pass.
- Duplicate detection compares the current on-disk size instead of stale
  stored metadata, so edits that change a document's size are still found.
- Duplicate hashing runs on a background thread, so large files no longer
  freeze the interface while the prompt opens.
- Exiting the app waits for a running backup (create, import or export) to
  finish, and an update install refuses to start while one is running.
- The release workflow validates the legacy updater against the candidate
  bytes before publishing, in addition to the public-byte re-check.

## 0.16.1 - 2026-09-16

### Fixed

- A failed restore can no longer delete the live catalogue or settings: the
  rollback now removes only what it installed and restores only what it
  saved, and a failed safety snapshot aborts the restore instead of
  continuing without protection.
- Backups from a newer schema, or whose schema disagrees with their manifest,
  are refused before anything is replaced.
- An interrupted "substituir a versão anterior" undo now recovers the
  previous version's catalogue path at startup.
- The restart that applies a restore keeps a custom data directory.
- Editing a general task no longer assigns it to a subject, the filing prompt
  no longer carries the replacement checkbox to the next document, the popup
  shows the real origin folder of Explorer imports, and the subject file list
  updates its counts after a move.

## 0.16.0 - 2026-09-15

### Added

- Mover: a catalogued document can be moved to another type folder of the
  same subject or to another subject entirely, from the subject's file list.
  The move keeps the filename, is collision-safe and journaled, updates the
  catalog and the search index in place, and interrupted moves are recovered
  at startup.

### Changed

- Undo follows the document: "Desfazer última organização" restores a filed
  document from its current folder, so moving it after filing no longer
  breaks undo.

## 0.15.1 - 2026-09-14

### Fixed

- A failed restore can no longer leave settings and the catalogue out of
  sync: the database and settings are now swapped as one transaction and
  rolled back together when any step fails.
- Duplicate detection revalidates cached content hashes against each file's
  size and modification time, so documents edited after filing are compared
  by their current content instead of an outdated fingerprint.
- "Substituir a versão anterior" now works regardless of the incoming
  filename and for adopted documents, and undo restores each file to its
  original name.
- A download whose move keeps failing now exhausts its bounded retry budget
  instead of retrying (and notifying) indefinitely.
- Reindexar now shows its progress in the file list, refreshes the row when
  the extraction finishes, and reports a busy queue instead of appearing to
  do nothing.

## 0.15.0 - 2026-09-13

### Added

- Backups: create catalog+settings snapshots from Settings, export a portable
  ".zip", import one back, and restore it with full hash validation and an
  automatic pre-restore safety snapshot. Restoring replaces the catalog and
  settings only — your documents are never touched — and the app reopens
  itself when the staged restore is applied at the next launch.
- Retention: user backups are never deleted automatically; automatic
  snapshots keep the newest two per kind for up to 30 days.
- Hidden CLI flags `--backup-now <folder>` and `--restore-from <path>` that
  the release E2E now uses to verify backup and restore on every release.

## 0.14.4 - 2026-09-13

### Changed

- The ✕ button in the filing popup now behaves like "Não é da universidade":
  it returns the file to the folder it came from instead of only dismissing
  the popup. Esc and the window close button still keep the file in the
  Inbox ("Mais tarde").

## 0.14.3 - 2026-09-12

### Changed

- The filing popup now waits for your decision by default instead of closing
  on a timer; dismiss it with "Mais tarde", the new ✕ corner button, Esc or
  the window close button.
- Settings gained "Fechar o popup automaticamente": enable it to restore the
  countdown that closes the popup after the configured seconds.

## 0.14.2 - 2026-09-12

### Fixed

- The filing prompt keeps the start of long subject names visible, ending
  them with "…" instead of clipping the middle. The full name stays available
  in the tooltip and to screen readers.

## 0.14.1 - 2026-09-12

### Added

- Explorer context menu: "Organizar com Organizador" appears for the file types
  configured in the app (current-user SystemFileAssociations) and hands the
  selected file to the running instance. Entries are re-synced on startup,
  settings changes and uninstall, and never touch other programs' verbs.
- Files organized from Explorer return to the folder they came from when you
  choose "Devolver", instead of always going to Downloads.

### Changed

- Move-failure messages now name the folder where the file stayed instead of
  always saying Downloads.

## 0.14.0 - 2026-09-12

### Added

- Duplicate detection: when a new download matches a document already in the
  catalog, the filing prompt shows where the existing copy lives, with a
  button to reveal it and an option to replace the previous version. The
  replaced file stays in its folder with a "versão anterior" suffix, is
  journaled like every other move, and is restored by undo together with the
  new filing.
- Content fingerprints are recorded at ingestion and cached per document on
  first comparison, so detection adds no cost to ordinary filings.

## 0.13.3 - 2026-09-12

### Fixed

- A failed undo that rolled the document back under an alternative name now
  redirects the catalog and the filing history to that name, so a later undo
  can no longer move an unrelated file.
- Startup recovery only completes interrupted filings, returns and undos when
  the destination size matches the recorded document; inconsistent
  destinations stay flagged for manual review instead of being accepted.
- Downloads arriving while an update is being prepared are retained and
  collected again if the update fails instead of being silently forgotten.

### Development

- Calendar tests use date-relative offsets so fixed days of the month can no
  longer collide with the test's reference date.

## 0.13.2 - 2026-09-10

### Fixed

- The updated application now validates the migrated data while the helper can
  still roll the binary back; only then does it acknowledge health and close
  the data rollback window. The two rollback decisions can no longer disagree
  when validation fails.
- Spreadsheet extraction stops after a bounded number of visited cells, so a
  tiny sheet declaring an enormous sparse range can no longer occupy the
  indexing worker.
- Inbox ingestion reads its record inside the database transaction, removing
  the read-after-commit window that could return a file to Downloads while a
  pending Inbox entry stayed behind.
- A download that was stabilizing when a watcher pause began is queued again
  after the pause instead of being silently discarded.

## 0.13.1 - 2026-09-10

### Fixed

- A failure writing the update receipt after the new version reported healthy
  can no longer trigger a rollback that leaves the installation without a
  working executable.
- The database rollback decision now follows the executable's: the app
  acknowledges helper health before closing its migration backup, and a
  failed acknowledgement restores the backup instead of leaving the two
  decisions out of step.
- Office documents whose contents would expand far beyond their compressed
  size are indexed by name only instead of being loaded into memory.
- A read failure after a filing committed no longer moves the document back
  to the Inbox while the catalog records it as filed.
- Downloads that arrive while a return temporarily pauses the watcher are
  collected after the pause instead of being silently forgotten.

## 0.13.0 - 2026-09-10

### Added

- Persistent Windows filing notifications reveal their documents in Explorer,
  including after the app exits. Batches spanning folders open a document list.
- A per-user Setup executable creates shortcuts and an Installed Apps entry.
  Its uninstall files survive in-app updates, and user data is preserved.
- Optional trusted-certificate signing for the executable, Setup and uninstaller.

### Fixed

- Start Menu registration uses native COM instead of launching PowerShell.
- Notification activation is forwarded to the running instance without creating
  a second watcher. Stale notifications cannot open reused catalog records.
- Packaged smoke tests skip real Windows integration registration.
- Accepted transfers run in one FIFO queue. Conflicting filing, return, undo
  and bulk requests are rejected until their prior operation is handled.
- Normal exit keeps the interface responsive while accepted transfers finish;
  settings and updates wait until queued work and its UI completion finish.
- Download ingestion records its recovery entry before copying. Interrupted
  copies stay in manual review instead of becoming ordinary inbox documents.

### Development

- Local builds default to `artifacts/`, leaving the live `dist/Organizador`
  installation and committed icon assets untouched. Release CI explicitly
  selects `dist` as its output directory.
- Added a one-week daily-use checklist in `docs/daily-use-checklist.md`.

## 0.12.0 - 2026-09-06

### Fixed

- File transfers no longer freeze the interface: ingestion, filing, returns,
  undo and bulk filing now run on background worker threads, with prompts,
  toasts and inbox updates marshalled back to the UI thread. Return, undo
  and bulk runs ignore duplicate requests while one is in flight, and
  shutdown waits briefly for running transfers.
- The manual import summary now waits for every file's ingestion to finish
  instead of reporting while transfers are still in flight.

## 0.11.0 - 2026-09-06

### Fixed

- Edited documents are reconsidered for search: the index now records each
  file's size and modification time, a startup pass requeues changed files,
  and the file list offers "Reindexar" for every document, not just failed
  ones.
- Text extraction stops at a bounded budget instead of expanding huge Office
  documents in memory; oversized PDF pages are rendered at a reduced scale
  or skipped within a pixel ceiling.
- A temporary ingestion failure now retries automatically with backoff
  instead of silently ignoring the file.
- New subjects can no longer claim a folder that another subject already
  owns under Windows naming rules; restoring a colliding subject is refused,
  and existing collisions surface as a dismissable startup warning.

## 0.10.1 - 2026-09-05

### Fixed

- A failed deletion of the previous version after a healthy update no longer
  rolls back the working installation; the old copy is retained and swept by
  the next launch.
- A second copy of the app installed in another folder can no longer operate
  on the same data; one instance per data folder is now enforced in addition
  to the per-installation guard.
- Settings restored by recovery are now reloaded, so the session never runs
  with folders that contradict its restored configuration.
- OCR text can no longer be attached to the wrong PDF page when one page
  fails to render.
- The filing prompt regenerates the suggested filename when the subject or
  document type changes (a manual edit always wins).
- Paths containing apostrophes no longer break Start Menu shortcut creation.
- The login startup entry now follows the current installation on every
  launch when startup is enabled.
- The license inventory documents the PDF rendering and OCR dependencies.

## 0.10.0 - 2026-09-05

### Added

- Quieter intake: notifications for new inbox material are batched within a
  10-second window, so a burst of downloads produces a single toast. Rapid
  filing confirmations aggregate into one summary after the first toast.
- New setting "Silenciar notificações de arquivo" suppresses intake and
  filing toasts entirely; errors, deadlines and update notices stay visible.

## 0.9.0 - 2026-09-05

### Added

- OCR for scanned PDFs using the built-in Windows engine: pages without
  extractable text are recognized (pt-PT preferred) and indexed like normal
  text, toggleable in Definições. Without a language pack or with OCR off,
  documents keep the filename-only fallback.

## 0.8.1 - 2026-09-04

### Added

- Real application logo: the packaged executable, taskbar, tray, window,
  and Start Menu shortcut now show the Organizador mark instead of the
  default icon.

## 0.8.0 - 2026-09-04

### Added

- Search filters by subject and document type, combinable with text search;
  with only filters set, the search page lists recent matching documents.

## 0.7.0 - 2026-09-04

### Added

- Every organized document is now searchable by its final filename, even
  when no text can be extracted; search results show the current file name.
- Indexing tracks per-document state: the search page reports pending and
  failed counts, failed documents can be retried from the search page or
  from the subject file overview, and changed files refresh automatically.

## 0.6.5 - 2026-09-04

### Fixed

- Cross-volume moves now preserve timestamps and basic attributes, and warn
  in the diagnostic log when alternate data streams cannot travel with the
  file; ACL, encryption, and sparse-file limits are documented.
- Fixed two unclosed SQLite connections in tests that produced
  ResourceWarnings under the full suite.

## 0.6.4 - 2026-09-04

### Fixed

- Filing destinations are resolved and required to stay inside their managed
  folder, so junctions or symlinks planted below the inbox, subject, or
  Downloads trees can no longer redirect documents outside the library.
- Indexing re-checks the on-disk size before extracting: changed files refresh
  their record and wait for the next pass instead of indexing stale content,
  and extracted text is capped so one document cannot bloat the search index.
- Subject codes only match on token boundaries; "MAT" no longer claims
  "material_de_estudo.pdf" with full confidence.
- Filing errors, the task checkbox, and the no-deadline label are translated;
  a scanner test now fails the suite if any interface literal lacks a
  translation.

### Changed

- Release and CI workflows pin GitHub Actions by commit hash with Dependabot
  watching for updates.

## 0.6.3 - 2026-09-04

### Fixed

- Migration recovery now stays open until the application finishes starting:
  an activation failure restores the pre-migration database automatically,
  in normal launches and in update handshakes.
- A new version that never becomes healthy is rolled back automatically,
  including after the binary swap: the previous version is restored and
  relaunched, and its startup recovers the pending migration backup.
- Overlapping update checks can no longer overwrite in-flight install state.

## 0.6.2 - 2026-09-04

### Added

- Transactional updates: each install attempt gets a unique staging/rollback
  workspace, an installation lock, and a PID-aware PowerShell helper that waits
  for the old process, verifies every move, and only commits after the new
  version signals readiness and health. Failures before commit restore the
  previous version automatically; the outcome is shown once after relaunch.
- Pre-migration safety: the database is inspected read-only before any write,
  snapshotted with SQLite's online backup API (WAL-safe) together with the
  exact settings bytes, and restored automatically only if the new version
  never reaches its health point. At most two healthy snapshots are retained.
- Clearer update feedback: manual checks report "up to date" or the failure
  reason, transient errors keep the pending update, and failed preparations
  restore the install action for retry.
- The packaged `update-manifest.json` pins the exact release version validated
  before every swap, and the updater no longer requires the app folder to be
  named `Organizador`.

### Notes

- v0.6.2 is published as a prerelease and is not offered as an automatic
  update: the exact v0.6.1 updater was proven to silently skip the swap on
  install paths with non-ASCII characters (its helper misreads UTF-8 paths),
  so v0.6.1 installations must update to v0.6.2 manually, once. From v0.6.2
  onward, updates use the transactional helper verified end to end.

## 0.6.1 - 2026-09-03

### Added

- The packaged app registers itself in the per-user Start Menu, so it appears
  in Windows search (Win+S) and the apps list and can be launched with a click.
  The shortcut self-heals after updates or folder moves.

## 0.6.0 - 2026-09-02

### Added

- Automatic updates: the packaged app checks GitHub for a newer release on
  launch (toggleable in Definições). When one exists, a tray notification and
  an "Instalar atualização" menu item appear; one click downloads, verifies
  the SHA-256, swaps the app folder and relaunches. The previous version is
  kept as a rollback folder until the new one starts successfully.

## 0.5.0 - 2026-09-02

### Added

- Five switchable themes in Definições: Escuro (the original), Claro (light),
  Oceano (deep blue), Sépia (warm paper) and Alto contraste (accessibility).
  The theme applies immediately on save.
- Interface languages: Português (Portugal), English, Español and Français,
  selectable in Definições and applied after a restart. Missing translations
  fall back to Portuguese.

## 0.4.0 - 2026-09-01

### Added

- A calendar on the Tarefas e prazos page: days with deadlines are marked
  (red overdue, amber today, teal upcoming, muted completed), clicking a day
  filters the task list, and double-clicking a day prefills the new-task
  deadline.
- Each Disciplinas row now shows how many files it organises and their total
  size, with a "Ver ficheiros" overview listing every file with per-kind
  counts and safe open actions.
- Bulk filing: select several inbox files and organise them with one decision,
  previewing every final name before confirming. Each file keeps its own journal;
  failed files stay pending and only the latest filing can be undone.
- Filename templates with tokens such as `{codigo}` and `{nome_original}`,
  configurable in Definições and previewed live in the filing prompt.
- Advance deadline reminders with a configurable lead time, shown at most once
  per day per task, surviving restarts.
- Tasks can now be edited: title, subject, deadline and per-task reminder.
- Archived subjects can be shown and restored from the Disciplinas page.

### Fixed

- Filename date detection no longer mistakes section numbering like "Aula 5-3"
  for a deadline; a date is only suggested with unambiguous order or deadline
  vocabulary, and the task checkbox only auto-ticks for real dates.
- Task notifications no longer repeat after every application restart.

## 0.3.0 - 2026-09-01

### Added

- A "Tranquilidade" panel on the home page summarising lifetime safety activity:
  files organized, collisions renamed without overwriting, interrupted operations
  recovered, documents adopted, returns, and undos.

### Fixed

- A database created by a newer application version now shows actionable guidance
  instead of asking the user to inspect the diagnostic log.

## 0.2.0 - 2026-09-01

### Added

- Persisted review decisions for reconciliation findings, keyed by path and reason.
- Safe in-place adoption and catalog removal for files already inside subject folders.
- Bounded retries for downloads that do not stabilize during the first check.
- Early rotating logs and frozen-application crash logging.

### Changed

- Settings paths are strictly validated before any directory is created or watched.
- Settings loading rejects malformed JSON shapes and invalid field types with a safe fallback.
- Watcher bookkeeping now uses canonical path keys across aliases.
- The minimum file size round-trips in exact bytes.
- Windows builds explicitly disable UPX for reproducible package behavior.

### Fixed

- Stopping a manual import can no longer leave the interface stuck in an active state.
- Multiple reconciliation reasons for the same path are no longer collapsed into one row.
- Missing catalog records use recoverable tombstones after a final absence check.
- Full-text search failures are recorded in the diagnostic log.

## 0.1.0 - 2026-08-31

- Initial Windows release with safe filing, local search, undo, crash reconciliation,
  tray operation, deterministic packaging, licenses, and checksums.
