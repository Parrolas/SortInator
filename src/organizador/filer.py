"""The only application service permitted to move user files."""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from organizador.config import (
    DEFAULT_FILENAME_TEMPLATE,
    MANUAL_IMPORT_BATCH_LIMIT,
    AppConfig,
)
from organizador.db import METRIC_COLLISIONS_RENAMED, Database
from organizador.duplicates import file_sha256
from organizador.i18n import _
from organizador.models import (
    FILE_KINDS,
    ExistingDownload,
    ExistingDownloadsPlan,
    FiledDocument,
    HistoryEvent,
    InboxItem,
    Subject,
)
from organizador.paths import (
    IncompleteMoveError,
    is_direct_child,
    move_without_overwrite,
    resolve_contained,
    sanitise_component,
    sanitise_filename,
    unique_path,
)

LOGGER = logging.getLogger(__name__)


def _restore_original_extension(requested: str, original: str) -> str:
    """Keep the requested stem but force the original file extension."""

    original_suffix = Path(original).suffix
    safe = sanitise_filename(requested or original)
    if original_suffix and Path(safe).suffix.casefold() != original_suffix.casefold():
        safe = f"{Path(safe).stem}{original_suffix}"
    return safe


def render_name_template(
    template: str,
    *,
    subject_name: str,
    subject_code: str,
    kind: str,
    original_name: str,
    when: datetime,
) -> str:
    """Expand a user filename template; unknown text is kept, never blanked."""

    replacements = {
        "{disciplina}": subject_name.strip(),
        "{codigo}": subject_code.strip(),
        "{tipo}": kind,
        "{nome_original}": original_name,
        "{data}": f"{when.year:04d}-{when.month:02d}-{when.day:02d}",
        "{ano}": f"{when.year:04d}",
        "{mes}": f"{when.month:02d}",
        "{dia}": f"{when.day:02d}",
    }
    result = template
    for token, value in replacements.items():
        result = result.replace(token, value)
    return result


def render_final_name(
    template: str = DEFAULT_FILENAME_TEMPLATE,
    *,
    subject_name: str,
    subject_code: str,
    kind: str,
    original_name: str,
    when: datetime,
) -> str:
    """Render a template and restore the original extension, exactly as filing will."""

    rendered = render_name_template(
        template,
        subject_name=subject_name,
        subject_code=subject_code,
        kind=kind,
        original_name=original_name,
        when=when,
    )
    return _restore_original_extension(rendered, original_name)


class FilingError(RuntimeError):
    """A recoverable file-operation failure suitable for display to the user."""


class FilingService:
    """Perform collision-safe moves and keep persistence in sync."""

    def __init__(self, config: AppConfig, database: Database) -> None:
        self.config = config
        self.database = database

    def plan_existing_downloads(self) -> ExistingDownloadsPlan:
        """Build a deterministic, read-only plan for a confirmed manual import."""

        try:
            paths = sorted(
                self.config.downloads_dir.iterdir(),
                key=lambda path: (path.name.casefold(), path.name),
            )
        except OSError as exc:
            raise FilingError(_("Não foi possível ler a pasta Downloads configurada.")) from exc

        candidates: list[ExistingDownload] = []
        for path in paths:
            if not self.config.accepts(path):
                continue
            candidate = ExistingDownload.capture(path)
            if candidate is None or candidate.size < self.config.minimum_file_size:
                continue
            candidates.append(candidate)
        return ExistingDownloadsPlan(len(candidates), tuple(candidates[:MANUAL_IMPORT_BATCH_LIMIT]))

    def ingest(
        self,
        source: Path,
        *,
        expected: ExistingDownload | None = None,
    ) -> InboxItem | None:
        """Move one completed eligible download into the university inbox."""

        source = source.absolute()
        if not is_direct_child(source, self.config.downloads_dir):
            return None
        return self._ingest(source, expected)

    def ingest_external(self, source: Path) -> InboxItem | None:
        """Move one file explicitly chosen outside Downloads into the inbox."""

        return self._ingest(source.absolute(), None)

    def _ingest(
        self,
        source: Path,
        expected: ExistingDownload | None,
    ) -> InboxItem | None:
        """Move one accepted completed file into the university inbox."""

        if not self.config.accepts(source):
            return None
        origin = source.parent.name
        current = ExistingDownload.capture(source)
        if current is None:
            if source.exists():
                return None
            exc = FileNotFoundError(source)
            raise FilingError(
                _("Já não foi possível encontrar {name}.").format(name=source.name)
            ) from exc
        if expected is not None and current != expected:
            return None
        size = current.size
        if size < self.config.minimum_file_size:
            return None

        try:
            self.config.inbox_dir.mkdir(parents=True, exist_ok=True)
            destination, collided = self._plan_contained_destination(
                self.config.inbox_dir, source.name, self.config.inbox_dir
            )
            if expected is not None and not expected.still_matches():
                return None
            expected_identity = (
                (expected.device, expected.inode, expected.size, expected.modified_ns)
                if expected is not None
                else None
            )
        except OSError as exc:
            raise FilingError(str(exc)) from exc
        try:
            pending = self.database.begin_ingest(source, destination, size)
        except Exception as exc:
            raise FilingError(_("Não foi possível preparar a recolha do ficheiro.")) from exc
        try:
            move_without_overwrite(source, destination, expected_identity=expected_identity)
        except IncompleteMoveError as exc:
            raise FilingError(
                _(
                    "{name} ficou em {origin}, mas uma cópia incompleta pode ter ficado "
                    "em {leftover}. Compara os ficheiros antes de a remover."
                ).format(name=source.name, origin=origin, leftover=exc.leftover_path)
            ) from exc
        except OSError as exc:
            if source.is_file() and not destination.exists():
                with suppress(Exception):
                    self.database.cancel_ingest(pending.id)
            raise FilingError(
                _("{name} mudou ou ainda está a ser usado e ficou em {origin}.").format(
                    name=source.name, origin=origin
                )
            ) from exc
        try:
            item = self.database.complete_ingest(pending.id, file_sha256(destination))
        except Exception as exc:
            rollback = unique_path(source.parent, source.name)
            try:
                move_without_overwrite(destination, rollback)
            except OSError as rollback_error:
                LOGGER.exception("Failed to roll back an inbox move")
                leftover = _("Não foi possível registar {name}. O ficheiro ficou em {destination}.")
                raise FilingError(
                    leftover.format(name=source.name, destination=destination)
                ) from rollback_error
            with suppress(Exception):
                self.database.cancel_ingest(pending.id)
            returned = _(
                "Não foi possível registar {name}; foi devolvido a {origin} como {returned}."
            )
            raise FilingError(
                returned.format(name=source.name, origin=origin, returned=rollback.name)
            ) from exc
        self._register_collision(collided)
        return item

    def file_document(
        self,
        inbox_id: int,
        subject_id: int,
        kind: str,
        requested_name: str,
        *,
        replace_document_id: int | None = None,
    ) -> FiledDocument:
        """Move an inbox document to a subject/type folder."""

        item = self.database.get_inbox_item(inbox_id)
        subject = self.database.get_subject(subject_id)
        if item is None:
            raise FilingError(_("Este ficheiro já não está na Caixa de Entrada."))
        if subject is None or not subject.active:
            raise FilingError(_("Escolhe uma disciplina ativa."))
        if kind not in FILE_KINDS:
            raise FilingError(_("Escolhe um tipo de documento válido."))
        if not item.path.is_file():
            self.database.set_inbox_status(inbox_id, "error", "Ficheiro não encontrado")
            raise FilingError(
                _("Não foi possível encontrar {name}.").format(name=item.original_name)
            )

        filename = self._name_with_original_extension(requested_name, item.original_name)
        folder = self.config.university_root / subject.folder_name / kind
        version_event = self._replace_previous_version(
            folder, replace_document_id, subject_id, kind
        )
        destination, collided = self._plan_contained_destination(
            folder, filename, self.config.university_root
        )
        try:
            pending = self.database.begin_document_filing(
                inbox_id,
                subject_id,
                kind,
                destination,
                related_event_id=version_event.id if version_event is not None else None,
            )
        except Exception as exc:
            raise FilingError(_("Não foi possível preparar o histórico da organização.")) from exc
        try:
            move_without_overwrite(item.path, destination)
        except IncompleteMoveError as exc:
            raise FilingError(
                _(
                    "A organização ficou incompleta. O original e a cópia foram mantidos; "
                    "revê ambos na Caixa de Entrada antes de continuar."
                )
            ) from exc
        except OSError as exc:
            try:
                self.database.cancel_pending_inbox_operation(
                    pending.id, status="error", error=str(exc)
                )
            except Exception:
                LOGGER.exception("Failed to cancel a prepared filing")
            raise FilingError(
                _(
                    "O ficheiro ainda está a ser usado por outra aplicação. "
                    "Fecha-o e tenta novamente."
                )
            ) from exc

        try:
            document = self.database.record_filing(
                inbox_id,
                subject_id,
                kind,
                destination,
                pending_event_id=pending.id,
            )
        except Exception as exc:
            rollback = unique_path(item.path.parent, item.path.name)
            rolled_back = False
            try:
                move_without_overwrite(destination, rollback)
            except OSError:
                LOGGER.exception("Failed to roll back a subject filing")
            else:
                try:
                    self.database.cancel_pending_inbox_operation(pending.id, current_path=rollback)
                    rolled_back = True
                except Exception:
                    LOGGER.exception("Failed to cancel the rolled-back filing")
            message = (
                _("O movimento foi revertido porque não foi possível atualizar o histórico.")
                if rolled_back
                else _(
                    "Não foi possível atualizar o histórico. "
                    "Revê a Caixa de Entrada antes de repetir."
                )
            )
            raise FilingError(message) from exc
        self._register_collision(collided)
        return document

    @staticmethod
    def _previous_version_name(filename: str) -> str:
        path = Path(filename)
        return f"{path.stem} ({_('versão anterior')}){path.suffix}"

    def _replace_previous_version(
        self,
        folder: Path,
        replace_document_id: int | None,
        subject_id: int,
        kind: str,
    ) -> HistoryEvent | None:
        """Rename the document being replaced when the request matches it.

        Replacement is decided by the document identity (subject and kind),
        not by the incoming filename, so a duplicate filed under a different
        name still supersedes the old version. A failed rename is not fatal:
        the filing then proceeds as an ordinary collision-safe copy, and any
        retained rename stays journaled.
        """

        if replace_document_id is None:
            return None
        existing = self.database.get_file(replace_document_id)
        if existing is None or existing.catalog_state != "active":
            return None
        if existing.subject_id != subject_id or existing.kind != kind:
            return None
        try:
            versioned, _ = self._plan_contained_destination(
                folder,
                self._previous_version_name(existing.current_path.name),
                self.config.university_root,
            )
        except FilingError:
            return None
        try:
            event = self.database.begin_version_rename(existing.id, versioned)
        except Exception:
            LOGGER.exception("Could not prepare the previous-version rename")
            return None
        try:
            move_without_overwrite(existing.current_path, versioned)
        except OSError:
            LOGGER.exception("Could not rename the previous version")
            with suppress(Exception):
                self.database.cancel_version_rename(event.id)
            return None
        try:
            self.database.complete_version_rename(event.id, versioned)
        except Exception:
            LOGGER.exception("Could not finalize the previous-version rename")
            with suppress(OSError):
                move_without_overwrite(versioned, existing.current_path)
            return None
        return event

    def move_document(self, file_id: int, subject_id: int, kind: str) -> FiledDocument:
        """Move a catalogued document to another subject folder or kind."""

        document = self.database.get_file(file_id)
        if document is None:
            raise FilingError(_("Este documento já não está no catálogo."))
        subject = self.database.get_subject(subject_id)
        if subject is None or not subject.active:
            raise FilingError(_("Escolhe uma disciplina ativa."))
        if kind not in FILE_KINDS:
            raise FilingError(_("Escolhe um tipo de documento válido."))
        if document.subject_id == subject_id and document.kind == kind:
            return document
        folder = self.config.university_root / subject.folder_name / kind
        destination, collided = self._plan_contained_destination(
            folder, document.current_path.name, self.config.university_root
        )
        if not document.current_path.is_file():
            raise FilingError(
                _("Não foi possível encontrar {name}.").format(name=document.current_path.name)
            )
        try:
            pending = self.database.begin_document_move(file_id, subject_id, kind, destination)
        except Exception as exc:
            raise FilingError(_("Não foi possível preparar o histórico do movimento.")) from exc
        try:
            move_without_overwrite(document.current_path, destination)
        except IncompleteMoveError as exc:
            raise FilingError(
                _(
                    "O movimento ficou incompleto. O original e a cópia foram mantidos; "
                    "revê ambos antes de continuar."
                )
            ) from exc
        except OSError as exc:
            with suppress(Exception):
                self.database.cancel_document_move(pending.id)
            raise FilingError(
                _(
                    "O ficheiro ainda está a ser usado por outra aplicação. "
                    "Fecha-o e tenta novamente."
                )
            ) from exc
        try:
            moved = self.database.complete_document_move(
                pending.id, destination, subject_id=subject_id, kind=kind
            )
        except Exception as exc:
            rollback = unique_path(document.current_path.parent, document.current_path.name)
            rolled_back = False
            try:
                move_without_overwrite(destination, rollback)
            except OSError:
                LOGGER.exception("Failed to roll back a document move")
            else:
                with suppress(Exception):
                    self.database.cancel_document_move(pending.id, new_path=rollback)
                rolled_back = True
            message = (
                _("O movimento foi revertido porque não foi possível atualizar o histórico.")
                if rolled_back
                else _(
                    "Não foi possível atualizar o histórico. Revê os ficheiros antes de repetir."
                )
            )
            raise FilingError(message) from exc
        self._register_collision(collided)
        return moved

    def return_to_origin(self, inbox_id: int) -> Path:
        """Return non-university material to the folder it came from, safely."""

        item = self.database.get_inbox_item(inbox_id)
        if item is None or not item.path.is_file():
            raise FilingError(_("O ficheiro já não está disponível para devolver."))
        destination_dir = self._return_directory(item)
        destination, collided = self._plan_contained_destination(
            destination_dir, item.original_name, destination_dir
        )
        try:
            pending = self.database.begin_return(inbox_id, destination)
        except Exception as exc:
            raise FilingError(_("Não foi possível preparar o histórico da devolução.")) from exc
        try:
            move_without_overwrite(item.path, destination)
        except IncompleteMoveError as exc:
            raise FilingError(
                _(
                    "A devolução ficou incompleta. O original e a cópia foram mantidos; "
                    "revê a Caixa de Entrada e Downloads antes de continuar."
                )
            ) from exc
        except OSError as exc:
            try:
                self.database.cancel_pending_inbox_operation(
                    pending.id, status="error", error=str(exc)
                )
            except Exception:
                LOGGER.exception("Failed to cancel a prepared return")
            raise FilingError(
                _(
                    "Não foi possível devolver o ficheiro. "
                    "Fecha-o noutras aplicações e tenta de novo."
                )
            ) from exc
        try:
            self.database.record_return(inbox_id, destination, pending_event_id=pending.id)
        except Exception as exc:
            rollback = unique_path(item.path.parent, item.path.name)
            try:
                move_without_overwrite(destination, rollback)
            except OSError:
                LOGGER.exception("Failed to roll back a return to Downloads")
            else:
                try:
                    self.database.cancel_pending_inbox_operation(pending.id, current_path=rollback)
                except Exception:
                    LOGGER.exception("Failed to cancel the rolled-back return")
            raise FilingError(_("Não foi possível registar a devolução do ficheiro.")) from exc
        self._register_collision(collided)
        return destination

    def undo_latest_filing(self) -> InboxItem | None:
        """Restore the latest filed document to the university inbox."""

        event = self.database.latest_undoable_filing()
        if event is None:
            return None
        document = self.database.get_file(event.file_id) if event.file_id is not None else None
        source_path = document.current_path if document is not None else event.destination_path
        if not source_path.is_file():
            raise FilingError(
                _(
                    "O último ficheiro organizado já não está no destino. "
                    "O histórico não foi alterado."
                )
            )
        version_event = self.database.linked_version_event(event)
        restored_path, collided = self._plan_contained_destination(
            self.config.inbox_dir, event.source_path.name, self.config.inbox_dir
        )
        try:
            pending = self.database.begin_filing_undo(event, restored_path, source_path=source_path)
        except Exception as exc:
            raise FilingError(_("Não foi possível preparar o histórico para desfazer.")) from exc
        try:
            move_without_overwrite(source_path, restored_path)
        except IncompleteMoveError as exc:
            raise FilingError(
                _(
                    "A operação de desfazer ficou incompleta. O original e a cópia foram mantidos; "
                    "revê ambos na Caixa de Entrada antes de continuar."
                )
            ) from exc
        except OSError as exc:
            try:
                self.database.cancel_pending_undo(pending.id)
            except Exception:
                LOGGER.exception("Failed to cancel a prepared undo")
            raise FilingError(
                _("Não foi possível desfazer porque o ficheiro está a ser usado.")
            ) from exc
        version_reverted = False
        if version_event is not None:
            try:
                move_without_overwrite(version_event.destination_path, version_event.source_path)
                version_reverted = True
            except OSError:
                LOGGER.exception("Failed to restore the previous version name")
        try:
            self.database.mark_filing_undone(
                event,
                restored_path,
                version_event=version_event if version_reverted else None,
                source_path=source_path,
            )
        except Exception as exc:
            if version_reverted and version_event is not None:
                with suppress(OSError):
                    move_without_overwrite(
                        version_event.source_path, version_event.destination_path
                    )
            rollback = unique_path(source_path.parent, source_path.name)
            try:
                move_without_overwrite(restored_path, rollback)
            except OSError:
                LOGGER.exception("Failed to roll back an undo operation")
            else:
                redirected = False
                if event.file_id is not None:
                    try:
                        redirected = self.database.redirect_filing_destination(
                            event.id,
                            event.file_id,
                            source_path,
                            rollback,
                            pending.id,
                        )
                    except Exception:
                        LOGGER.exception("Failed to redirect the filing after a rolled-back undo")
                if not redirected:
                    LOGGER.error(
                        "The rolled-back undo left the catalog pointing at %s while the "
                        "document is at %s",
                        source_path,
                        rollback,
                    )
                    try:
                        self.database.cancel_pending_undo(pending.id)
                    except Exception:
                        LOGGER.exception("Failed to cancel the rolled-back undo")
            raise FilingError(_("Não foi possível atualizar o histórico ao desfazer.")) from exc
        self._register_collision(collided)
        if event.inbox_id is None:  # pragma: no cover - schema invariant
            return None
        return self.database.get_inbox_item(event.inbox_id)

    def ensure_subject_structure(self, subject: Subject) -> None:
        """Create each configured type folder for a subject."""

        subject_root = self.config.university_root / subject.folder_name
        for kind in FILE_KINDS:
            (subject_root / kind).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def subject_folder_name(name: str, code: str = "") -> str:
        """Build a stable readable folder name for a new subject."""

        prefix = f"{code.strip()} - " if code.strip() else ""
        return sanitise_component(f"{prefix}{name.strip()}", fallback="Disciplina")

    @staticmethod
    def _name_with_original_extension(requested: str, original: str) -> str:
        return _restore_original_extension(requested, original)

    def _return_directory(self, item: InboxItem) -> Path:
        """Prefer the recorded origin folder; never return into managed roots."""

        origin = item.original_path.parent
        try:
            resolved = origin.resolve()
        except OSError:
            return self.config.downloads_dir
        if not resolved.is_dir():
            return self.config.downloads_dir
        for root in (self.config.university_root, self.config.data_dir):
            try:
                root_resolved = root.resolve()
            except OSError:
                continue
            if resolved == root_resolved or root_resolved in resolved.parents:
                return self.config.downloads_dir
        return origin

    def _plan_destination(self, directory: Path, filename: str) -> tuple[Path, bool]:
        """Plan a collision-safe destination and report whether a rename was needed."""

        destination = unique_path(directory, filename)
        return destination, destination.name != sanitise_filename(filename)

    def _plan_contained_destination(
        self, directory: Path, filename: str, root: Path
    ) -> tuple[Path, bool]:
        """Plan a destination that cannot escape its managed root via reparse points."""

        destination, collided = self._plan_destination(directory, filename)
        try:
            resolve_contained(destination, root)
        except OSError as exc:
            raise FilingError(
                _("A pasta de destino não é segura: {path}.").format(path=directory)
            ) from exc
        return destination, collided

    def _register_collision(self, collided: bool) -> None:
        """Count one safely renamed collision for the activity summary."""

        if collided:
            self.database.increment_metric(METRIC_COLLISIONS_RENAMED)
