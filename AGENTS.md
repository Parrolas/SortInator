# AGENTS.md

Windows-only PySide6 app (Python 3.13) that watches Downloads and files study documents into a local SQLite-catalogued university folder. UI language is Portuguese; **source string literals are the i18n keys**. Respond to the user in English.

## Commands

```powershell
# Gates (run in this order; CI mirrors it)
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe -m ruff format --check src tests scripts
.venv\Scripts\python.exe -m mypy src\organizador      # strict mode
.venv\Scripts\python.exe -m pytest                    # full suite, ~60s; single test: -k "name"

# Build (PyInstaller; runs gates itself; requires dev+build extras and constraints-release.txt pins).
# Default output is artifacts/ and does NOT touch the live dist\Organizador install.
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1                # candidate build
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -OutputRoot dist  # release-style build (clobbers the live install)

# Per-user installer (needs Inno Setup; setup_installer.ps1 downloads it into artifacts/tools)
powershell -ExecutionPolicy Bypass -File .\scripts\setup_installer.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1      # -> artifacts\releases\...-Setup.exe + .sha256

# Update E2E (mandatory before any release; sandbox dir must already exist)
powershell -ExecutionPolicy Bypass -File .\scripts\run_update_release_e2e.ps1 `
  -CandidateZip "artifacts\releases\Organizador-<ver>-windows-x64.zip" -CandidateVersion "<ver>" `
  -SandboxRoot "C:\<ascii-path>"
```

## Release ladder (strict order)

1. Bump `__version__` in `src/organizador/__init__.py` + CHANGELOG entry.
2. Gates → `build.ps1` → installer build → update E2E (use an ASCII `-SandboxRoot` locally).
3. Commit, `git tag -a vX.Y.Z` (tag MUST equal `__version__`; CI enforces), push both.
4. `release.yml` builds with `-OutputRoot dist`, compiles and gates the Setup.exe on a disposable CI account, publishes the **prerelease** (zip + sha256 + Setup + sha256), re-downloads the public assets, and re-runs the legacy zip E2E (v0.6.1 baseline) against them.
5. Move the daily install deliberately: run the published `Setup.exe` (per-user, `%LOCALAPPDATA%\Programs\Organizador`) or update the portable `dist\Organizador` from the published zip; verify the `.sha256` first.

- Tag force-move (`git tag -f` + `--force` push) is only safe **before** the release is published — published assets are immutable (CI throws if the release exists).
- **Never auto-promote a prerelease to stable.** Manual-bridge policy: the v0.6.1 updater silently no-ops on non-ASCII install paths, so stable (currently v0.8.1) must stay ahead only when proven safe. `updater.check_latest_release` targets `/releases/latest` (stable only) — prerelease-to-prerelease OTA does not happen by design.
- `gh` CLI is authenticated and can read CI logs: `gh run view <id> --log-failed` works when the API returns 403 for ad-hoc requests. Prefer it before asking the user to paste logs.
- Reproduce a failing CI gate with a fresh venv + `pip install -e ".[dev]"` before touching product code.

## Hard-won gotchas

- **Never round-trip source files through PowerShell** (`Get-Content`/`Set-Content` mojibakes UTF-8 as cp1252). Use file editing tools. Reversal: `raw.encode('cp1252').decode('utf-8')`, write UTF-8 no BOM.
- **`-OutputRoot dist` requires stopping any running `Organizador.exe` first** (file lock; `dist\Organizador` is the legacy live install). Default candidate builds go to `artifacts/` and are safe while the app runs.
- **i18n AST scanner**: every new `_(...)` literal needs a key in EN/ES/FR dicts in `src/organizador/i18n_data.py`, placeholders must match across languages, and long translations must differ from the PT key (`tests/test_i18n.py` fails otherwise).
- **SQLite schema policy**: additive changes (new column, new `CREATE TABLE IF NOT EXISTS` in `SCHEMA` + `_EXPECTED_TABLES`) need **no** `SCHEMA_VERSION` bump; bump only for reshaping changes. Older binaries tolerate newer additive DBs; recovery.py restores a backup if migration fails mid-way.
- **Adding a config field** touches five places: `config.py` dataclass + `_bool_setting` in `load`, `SettingsPayload` in `ui/pages.py`, the settings checkbox, `_save_settings`, and `_restore_config` (easiest to miss).
- **File moves are journal-first**: every move writes a DB event before touching the filesystem; `reconcile.py` recovers interrupted moves at startup (including `ingest_pending`). Never move user files outside `filer.py`.
- **Backups share the migration bundle format** (`recovery.py`): `user`/`pre_restore` marker dirs live under `data_dir\backups\<kind>-<stamp>-<uuid>`; user snapshots are never auto-pruned and only they can be deleted. A restore is staged as `data_dir\restore-request.json` and consumed at the next startup *before* the database opens; a failed consume quarantines the request to `restore-request-failed.json` and keeps the current data. Restores swap the database and settings as one transaction and roll both back on any failure. `--backup-now`/`--restore-from` are the headless CLI; the windowed exe has no stdout, so the release E2E globs the exported zip instead of parsing output.
- **Cached content hashes are only trusted with a matching fingerprint**: `files`/`inbox` `content_sha256` must be paired with `hash_fingerprint` (size:mtime_ns); always refresh both together or duplicate detection will match stale content.
- **Replace-previous-version matches by subject+kind, never by filename**; adopted documents can be versioned too, and undo must restore the previous version to the version event's `source_path`, not the filing destination.
- **Moves are journaled like filings** (`move_pending` → `move`): `filer.move_document` keeps the filename (collision-safe), updates `files.subject_id/kind/current_path` and `document_pages.subject/title` in one transaction, and reconciliation recovers interrupted moves. Filing undo follows `files.current_path` (never the historical event destination), so a moved document can still be undone.
- **Reindexar reports acceptance**: `DocumentIndexer.reindex`/`submit` return whether the job was queued (a rejected job keeps its cleared index state for the refill pass), and the open subject-files dialog refreshes its rows on `index_completed` so the click is never inert.
- **File transfers run on one FIFO worker thread** (controller `_submit_transfer` + claims); conflicting filing/return/undo/bulk requests are rejected while a claim overlaps. Only the `_finish_*` handlers may touch Qt widgets, the tray, or the prompt. UI callbacks marshal via the `transfer_finished` signal.
- **Windows integration is native COM (pywin32), not PowerShell**: `windows_shell.py` writes shortcuts with AUMID + toast activator; `startup.py` registers the `organizador://` protocol and unregisters only entries that still point at the current exe. Smoke tests and CI set `ORGANIZADOR_DISABLE_WINDOWS_INTEGRATION=1`. The installer E2E (`run_installer_e2e.py`) refuses accounts with existing Organizador data — run it only in CI/disposable accounts.
- **Explorer context menu** is registered per configured extension under `HKCU\Software\Classes\SystemFileAssociations\<ext>\shell\Organizador` (command `"...\Organizador.exe" --organize "%1"`), pruned/removed only when the command still points at this exe, and re-synced on startup and settings save. `--organize` selections use the normal journaled ingest; "Devolver" returns them to the recorded origin folder (falling back to Downloads).
- **Packaged smoke startups must never show blocking UI** (CI runners have no tray): persisted update results are skipped when `smoke_test=True`. A modal `QMessageBox` fallback would hang the process for the full timeout.
- **Inno uninstallers are two-phase**: the first process can exit before the second-phase cleanup runs, so tests must wait for the payload file to disappear (not the exe, which is deleted earlier) after invoking an uninstaller.
- **`updater.extract_to_staging` consumes (deletes) its input archive** by design. Tests driving it with release artifacts must extract a copy; the installer E2E preserves the published zip this way.
- The update helper's PowerShell script is embedded in `updater.py`; validate changes with the real-PowerShell integration tests in `tests/test_updater.py` (session fixture compiles a C# sleeper exe).

## Layout

- `src/organizador/main.py` — entry point, single-instance guards (data-dir + install-dir), notification activation forwarding
- `src/organizador/controller.py` — `AppController`: orchestrates everything, owns tray/prompt/indexer/transfer queue
- `src/organizador/filer.py` — sole file-moving service (ingest/file/return/undo)
- `src/organizador/watcher.py` — Downloads watcher with stabilization + bounded retries
- `src/organizador/db.py` — SQLite + FTS5 catalog (schema + migrations at top of file)
- `src/organizador/updater.py` — transactional updates + embedded PowerShell swap helper
- `src/organizador/notifications.py` / `windows_shell.py` / `startup.py` — toast actions, COM shell helper, registry integration
- `src/organizador/duplicates.py` — content fingerprints and catalog duplicate lookup
- `src/organizador/ocr.py` / `extractors.py` / `indexer.py` — search text pipeline
- `scripts/installer.iss` + `build_installer.ps1` — Inno Setup package; payload in `{app}\app` is updater-replaceable
- Tests mirror modules; shared fixtures (`qt_app`, `app_config`, `database`, `subject`) in `tests/conftest.py`. OCR engine tests skip without a pt-PT language pack.
