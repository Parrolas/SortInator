# SortInator

<!-- impeccable:product-schema 1 -->

## Platform

Windows desktop

## Stack

Delegated: Python 3.13, PySide6, watchdog and SQLite FTS5. This stack was chosen
because the app must run quietly in the Windows tray and monitor local folders
without requiring a server or administrator access.

## Users

The primary user is a university student who downloads notes, slides,
assignments and notebooks throughout the day and wants those files organised
without repeatedly navigating Windows Explorer.

## Product Purpose

SortInator moves eligible completed downloads into a safe university inbox,
asks for the relevant subject and document type, and files the document in the
right folder. It also keeps subject-linked tasks and makes PDF, modern Office,
text and notebook contents searchable. Success means the Downloads folder no
longer becomes an accidental archive and every move remains understandable and
reversible.

## Positioning

The app joins file-system automation with a fast human confirmation step. It
does not silently guess where important coursework belongs: it proposes a
destination, learns only after repeated confirmed choices, and preserves an
undo trail.

## Operating Context

- The app runs in the Windows system tray.
- Chrome, Edge and Firefox may create temporary download files before renaming
  them to their final name.
- Files are organised under a user-selected university root, initially proposed
  as `Documents\Universidade`.
- Subject folders are divided into Slides, Exercícios, Testes, Trabalhos and
  Outros.
- The interface is Portuguese (Portugal).

## Capabilities and Constraints

- Only configured study-oriented file extensions are monitored.
- Files must be complete and unlocked before the app moves them.
- The app never overwrites or deletes a user file.
- All filing operations are logged and the latest filing can be undone.
- PDF, DOCX, PPTX, XLSX, text and notebook search is local and does not upload
  documents.
- Scanned image-only PDFs are recognized by the built-in Windows OCR engine
  when a language pack is installed and the setting is on; pages without a
  usable engine fall back to filename-only search.
- Existing files in Downloads are never moved automatically. The user may scan
  the top level explicitly, confirm the exact candidate count, and import no
  more than 25 into the inbox per confirmation; each still needs a filing
  decision.
- Learned suggestions require at least two matching confirmed filings, abstain
  when choices conflict, and never bypass human confirmation.

## Evidence on Hand

The brand mark is a supplied logo asset (`assets/icon.png`, processed into
`icon-square.png` and `icon.ico` by `scripts/generate_icon.py`). There are no
production datasets. UI examples and
empty states must not be presented as real university data.

## Product Principles

- Never lose or overwrite coursework.
- Ask once, then make the common action very fast.
- Keep all document contents on the user's computer.
- Prefer a visible inbox over an uncertain automatic classification.
- Treat learned patterns as suggestions, never as permission to file silently.
- Remain useful even when the main window is closed.

## Accessibility & Inclusion

Primary actions must be keyboard-accessible, state must not rely on colour
alone, and Portuguese copy must name both the problem and the recovery action.
