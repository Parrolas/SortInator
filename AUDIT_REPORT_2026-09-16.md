# Organizador — code and project audit

**Date:** 16 September 2026  
**Version:** 0.16.0  
**Commit:** `9194e893560b2cb0129f5883fea9ead554abe89f`  
**Scope:** application code, persistence, file operations, recovery, background work, UI behavior, tests, dependencies, packaging, CI/release configuration, and documentation.

## Executive summary

**15 findings: 1 high severity, 11 medium, and 3 low.** The most serious defect can delete the live database and settings while handling an early restore failure. Fixing that should take priority over the other findings.

The standard quality gates all pass, including **458 tests**. The findings below concern cases outside the existing tests or behavior that the tests do not currently assert. Each finding distinguishes runtime evidence from source inspection.

No application, test, script, or configuration source was changed. This Markdown report is the only project file added. Additional checks executed in-memory probes against disposable temporary databases and files; they did not use the daily installation or real study documents.

### Severity definitions

- **High / P1:** a credible data-loss failure requiring prompt attention.
- **Medium / P2:** incorrect behavior, incomplete recovery, interrupted work, responsiveness problems, or a release-process gap under identifiable conditions.
- **Low / P3:** misleading display or test-environment inconsistencies with limited direct impact.

## Validation results

- Ruff lint: passed.
- Ruff formatting: passed; 61 files already formatted.
- Strict mypy: passed; 35 source files checked.
- Standard pytest run: **458 passed in 75.30 seconds** on Windows, Python 3.13.5.
- `pip check`: passed; no broken installed requirements.
- Initial run with `ORGANIZADOR_DISABLE_WINDOWS_INTEGRATION=1`: 456 passed, 2 failed. Both failures are explained in F13.
- A separate targeted rerun encountered a sandbox denial accessing pytest's existing temporary directory. The complete standard run was subsequently rerun outside the sandbox and passed. That permission error is not a product defect.
- Additional service/UI probes and injected failures confirmed the behaviors described below without adding test files.

## High-severity finding

### F01 — Restore rollback can delete originals that were never saved

**Priority:** P1 — high. **Evidence:** reproduced with an injected filesystem failure.

**Location:** [recovery.py:709](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/recovery.py:709>), [recovery.py:729](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/recovery.py:729>).

The restore first renames current settings, database sidecars, and the database into temporary saved originals. If any of those renames fails, the exception handler unconditionally deletes all live database/settings paths. It then restores only entries already recorded in `saved_originals`.

**Reproduction:** create valid current data and a backup, stage a restore, then inject a `PermissionError` when the existing settings file is first renamed. No original has been saved at that point. After the handler runs, both `organizador.db` and `settings.json` are absent, and the restore request is quarantined.

**Impact:** a failed restore can remove the current catalogue/settings instead of preserving them. In this reproduction, the automatic pre-restore snapshot remained available for manual recovery; the live files were still deleted. The subsequent startup path can continue after the failed user restore, making the missing live catalogue particularly dangerous.

**Suggested correction:** track exactly which originals have been saved and which replacement files have actually been installed. Rollback must never delete an untouched original. Cover failures at every original-save step, as well as failures during rollback itself. Existing tests cover later swap/verification failures but miss this early failure.

## Medium-severity findings

### F02 — Restore continues after the safety backup fails

**Priority:** P2. **Evidence:** reproduced with an injected backup failure.

**Location:** [recovery.py:541](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/recovery.py:541>).

`_snapshot_before_restore()` catches every exception and only logs it. This treats permission errors or backup-storage failures like an already-unusable database, allowing a healthy current catalogue to be replaced without its promised safety snapshot.

**Reproduction:** back up a one-subject catalogue, add a second subject, then restore the older backup while making safety-snapshot creation raise `PermissionError`. Restoration reports success, the catalogue returns to one subject, and there are zero pre-restore snapshots.

**Impact:** recent data can become unrecoverable if the user needs to reverse the restore. This also removes a recovery route for F01.

**Suggested correction:** distinguish unusable current data from an inability to save a healthy current state; stop the latter restore or require an explicit, informed decision to continue without protection.

### F03 — A backup with an unsupported database schema replaces live data before being rejected

**Priority:** P2. **Evidence:** reproduced using a valid, checksummed synthetic newer-schema backup.

**Location:** [recovery.py:637](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/recovery.py:637>), [db.py:376](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/db.py:376>).

Backup validation verifies hashes and SQLite structural health, but does not reject a database version newer than the running application supports. It also does not compare the manifest's schema version against the actual database version.

**Reproduction:** prepare an otherwise valid backup with `user_version=7`, update its manifest/hash accordingly, and restore with the current schema-6 application. The restore succeeds and installs schema 7; `Database.initialize()` then raises `NewerDatabaseError`.

**Impact:** the application replaces a usable catalogue with one it refuses to open. Recovery requires a compatible application or restoring another backup.

**Suggested correction:** inspect the backup database's actual schema and compatibility before accepting or applying the restore, and verify its agreement with the manifest.

### F04 — Interrupted undo of a replacement leaves the previous version pointing at a missing path

**Priority:** P2. **Evidence:** reproduced with a simulated interruption between filesystem work and database commit.

**Location:** [filer.py:550](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/filer.py:550>), [reconcile.py:404](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/reconcile.py:404>), [db.py:2209](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/db.py:2209>).

Undoing a replacement moves the incoming document back to the inbox and renames the previous version back to its original name. Only the first move has an undo-pending marker. Recovery of that marker does not complete the previous-version metadata update.

**Reproduction:** file an old document, file a replacement, interrupt immediately before `mark_filing_undone()`, then run reconciliation. The undo marker is removed, but the old document's catalogue path does not exist. Its physical file exists at its restored original name, and reconciliation still reports one missing document.

**Impact:** a crash during undo breaks catalogue/search access to a document that remains on disk.

**Suggested correction:** journal and recover both filesystem operations in the replacement undo, including restoration of the linked version's catalogue path.

### F05 — Moving a queued document can leave indexing stuck for the session

**Priority:** P2. **Evidence:** reproduced with a controlled index-worker queue.

**Location:** [indexer.py:80](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/indexer.py:80>), [indexer.py:128](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/indexer.py:128>), [controller.py:1571](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/controller.py:1571>).

Index jobs retain the document's old path. Moving a document does not change its record token or clear the indexer's attempted-key exclusion. A queued job then finds its old path missing and exits while leaving that exclusion in place. Refill cannot enqueue the current path.

**Reproduction:** hold the index worker, submit a document, move it to another subject, then release the worker and run refill. The moved file exists, `indexed_at` remains null, pending count is 1, active jobs are 0, and ordinary resubmission returns false.

**Impact:** the document can remain unavailable to text search until restart or an explicit reindex. A path change during extraction can similarly cause the guarded database write to be discarded without a new job.

**Suggested correction:** coordinate path changes with index jobs and allow the current document snapshot to be retried when an old-path job is superseded.

### F06 — Duplicate detection misses size-changing edits

**Priority:** P2. **Evidence:** reproduced with real temporary files.

**Location:** [duplicates.py:61](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/duplicates.py:61>), [db.py:1654](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/db.py:1654>).

Hash freshness is checked only after candidates are selected by the stored catalogue size, using the stored inbox size. An edited document whose size changed can be excluded before its fingerprint is ever examined.

**Reproduction:** file an 8-byte document, edit it to 23 bytes, and ingest a byte-identical 23-byte copy. The catalogue still records 8 bytes, and `find_duplicate()` returns no match.

**Impact:** users lose duplicate warnings and the replacement option for matching edited documents until metadata is refreshed. Editing an inbox document's size presents the corresponding stale-input problem.

**Suggested correction:** refresh relevant size metadata before using it as a definitive candidate filter; hash revalidation alone is insufficient.

### F07 — Editing a general task silently assigns it to a subject

**Priority:** P2. **Evidence:** reproduced with the actual Qt dialog.

**Location:** [dialogs.py:169](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/ui/dialogs.py:169>).

The task editor populates its subject dropdown with subjects only. Unlike task creation, it has no `Geral` entry with a null subject ID. For an existing general task, selection falls back to the first subject.

**Reproduction:** create a task with `subject_id=None`, open `TaskDialog`, and inspect its values without changing anything. The returned subject ID is 1, and the dropdown has no null-subject option.

**Impact:** saving a title/deadline edit unexpectedly changes task classification; existing subject tasks also cannot be changed to general through this editor.

**Suggested correction:** preserve the general-task option and explicitly select it for null subject IDs.

### F08 — The replacement checkbox carries over to the next document

**Priority:** P2. **Evidence:** reproduced with the actual filing prompt.

**Location:** [prompt.py:211](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/ui/prompt.py:211>), [prompt.py:338](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/ui/prompt.py:338>).

`show_item()` resets several per-document fields but does not reset `replace_check`. The duplicate-banner update clears the checkbox only when there is no duplicate or its destination differs.

**Reproduction:** show a duplicate, select replacement, finish that prompt, and show another duplicate targeting the same subject/type. Replacement is already checked for the second document.

**Impact:** confirming the next document can rename an existing version without a fresh replacement choice. The file contents are preserved, but the action is unintended.

**Suggested correction:** reset replacement consent whenever a new inbox item is shown.

### F09 — Normal application exit can interrupt backup/import/export work

**Priority:** P2. **Evidence:** reproduced at the controller lifecycle boundary.

**Location:** [controller.py:1879](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/controller.py:1879>), [controller.py:454](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/controller.py:454>).

Backup creation, import, and export run on untracked daemon threads. Shutdown waits for file transfers but not backup jobs. Disabling the backup buttons does not protect those jobs from Exit or an update restart.

**Reproduction:** hold snapshot creation in progress, request controller shutdown, and inspect the state. Shutdown is marked complete while the backup worker remains alive and has `daemon=True`.

**Impact:** process exit can abandon a requested backup/export or leave temporary/unfinished backup data. The UI has no guaranteed completion or orderly cancellation path.

**Suggested correction:** track accepted backup jobs and complete or safely cancel them before allowing the process to exit or restart.

### F10 — Restore relaunch drops a custom data directory

**Priority:** P2. **Evidence:** inspected the generated command with process creation mocked; no executable was launched.

**Location:** [controller.py:2031](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/controller.py:2031>).

The packaged restore relaunch invokes only the executable, without `--data-dir`. A session using a custom catalogue stages its restore in that custom directory, but the new process opens the default profile.

**Impact:** the requested restore remains pending in the custom profile, and the user sees another catalogue or onboarding after the promised restart.

**Suggested correction:** preserve the selected data directory in the relaunch arguments, using safe Windows argument quoting.

### F11 — Duplicate hashing runs synchronously on the GUI thread

**Priority:** P2. **Evidence:** runtime thread probe plus source inspection; no large-file performance benchmark was run.

**Location:** [controller.py:1247](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/controller.py:1247>), [duplicates.py:55](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/duplicates.py:55>).

Opening the next prompt calls duplicate detection synchronously. Missing/stale hashes cause whole files to be read, potentially across every candidate of the same stored size. Filing accepts files above the indexer's 50 MB content-extraction limit; that limit does not constrain hashing.

**Reproduction:** instrument `file_sha256()` during `_show_next_prompt()`. Both hash operations in the fixture execute on the main thread.

**Impact:** large files, slow disks, or many uncached candidates can make the interface unresponsive while the prompt is prepared. The delay depends on the data and storage speed.

**Suggested correction:** perform duplicate lookup/hashing in background work and deliver the result to the GUI, with protection against the user switching to another item in the meantime.

### F12 — Legacy-update validation occurs after immutable public publication

**Priority:** P2. **Evidence:** release-workflow and documentation inspection; no release was published during the audit.

**Location:** [release.yml:74](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/.github/workflows/release.yml:74>), [release.yml:110](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/.github/workflows/release.yml:110>), [README.md:340](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/README.md:340>).

The workflow publishes the prerelease, downloads the public artifacts, and only then invokes the legacy-update E2E script. There is no earlier invocation against the candidate bytes, despite the README describing validation both before and after publication. The earlier installer lifecycle gate exercises the current updater, which does not replace the legacy-updater check.

**Impact:** if that compatibility check fails, the failing artifact is already publicly downloadable. A rerun also hits the published-assets-are-immutable guard. The prerelease policy correctly keeps it out of stable `/releases/latest`; this finding does not imply unsafe automatic promotion.

**Suggested correction:** validate the candidate with the legacy updater before publishing, then retain the public-byte verification after publication. Keep the documented manual local gate as well.

## Low-severity findings

### F13 — Two tests conflict with the documented integration-disable environment

**Priority:** P3. **Evidence:** reproduced by running the full suite in both configurations.

**Location:** [test_startup.py:171](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/tests/test_startup.py:171>), [test_startup.py:320](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/tests/test_startup.py:320>), [startup.py:102](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/startup.py:102>).

The two `refresh_windows_integration` tests expect mocked integration calls but do not clear `ORGANIZADOR_DISABLE_WINDOWS_INTEGRATION`. With that variable set to `1`, the function correctly exits immediately and both tests fail. With the standard environment, all 458 tests pass.

**Impact:** the documented safe integration-disabled test setup produces misleading failures. The checked-in CI workflow does not currently set this variable globally.

**Suggested correction:** make these tests explicitly control the variable and align the test-running guidance with the intended configuration.

### F14 — Subject-file summary stays stale after moving documents

**Priority:** P3. **Evidence:** reproduced with the actual subject-files dialog.

**Location:** [dialogs.py:688](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/ui/dialogs.py:688>), [dialogs.py:732](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/ui/dialogs.py:732>).

File count, total size, and counts by type are computed only in the constructor. `set_documents()` rebuilds the rows after a move but leaves those summary labels unchanged.

**Reproduction:** open a subject containing one file, move that file to another subject, and refresh its documents. The dialog has zero documents but still reports one file in its header.

**Suggested correction:** update the summary labels whenever the document collection changes.

### F15 — Explorer imports are incorrectly labelled as originating from Downloads

**Priority:** P3. **Evidence:** direct source inspection.

**Location:** [prompt.py:220](<C:/Users/José Parrolas/Desktop/Personal_Projects/life_changing_app/src/organizador/ui/prompt.py:220>).

The prompt always displays “recebido da pasta Downloads”, including files explicitly imported through Explorer from other folders. The inbox model already retains the true original path.

**Impact:** the prompt gives incorrect provenance and can mislead the user about where the return action will send the file. The actual return-directory logic is separate and does use the recorded origin.

**Suggested correction:** derive the displayed source folder from the inbox item's original path.

## Project assessment and coverage limits

### Controls that passed or are present

- Clean starting working tree, matching package/changelog version, lint, formatting, strict typing, and the complete existing test suite.
- Journal-first primary file operations, collision refusal, path-containment checks, database record tokens, and guarded index writes.
- Transactional SQLite migration logic and standalone SQLite backups with checksums.
- Updater checksum verification, bounded ZIP extraction, rollback-handshake tests, and a stable/prerelease separation.
- Release dependency constraints, pinned GitHub Action revisions, installer lifecycle automation, and preservation of user documents during uninstall by design.

These controls are useful, but their presence does not negate the specific failure paths above.

### What this audit did not establish

- It did not rebuild or install the application, run a new packaged release E2E, publish a release, or interact with the daily installation. Packaging/release conclusions are based on source/workflow review and existing tests.
- Qt checks were headless. Real Notification Center interaction, Explorer presentation, accessibility, display scaling, and visual behavior still require desktop acceptance testing.
- `pip check` validates installed dependency compatibility, not security advisories. No external CVE database, antivirus scan, signing validation of release binaries, or hosted CI/repository-permission audit was performed.
- Fault injections exercised specific exceptions/interleavings. They do not constitute an exhaustive power-loss, filesystem, concurrency, or performance test campaign.
- A broad audit cannot prove the absence of additional defects. The report includes supported findings and does not count speculative concerns as confirmed bugs.

## Recommended order of attention

1. **F01:** repair restore rollback before relying on restore for real data recovery.
2. **F02–F04:** close the remaining backup-validation and recovery gaps.
3. **F05–F10:** correct indexing, duplicate detection, task/prompt state, and backup/relaunch behavior.
4. **F11–F12:** address GUI responsiveness and pre-publication validation.
5. **F13–F15:** align tests and polish misleading UI details.

All suggested corrections are recommendations only. No fixes were implemented.
