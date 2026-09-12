"""End-to-end file movement tests in temporary folders."""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import NoReturn

import pytest

from organizador.config import AppConfig
from organizador.db import Database
from organizador.filer import FilingError, FilingService, render_final_name
from organizador.models import FilingHint, HistoryEvent, Subject
from organizador.paths import IncompleteMoveError


def _download(config: AppConfig, name: str = "MAT101_ficha.pdf", size: int = 200) -> Path:
    path = config.downloads_dir / name
    path.write_bytes(b"x" * size)
    return path


def test_ingest_and_file_document_are_collision_safe(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    source = _download(app_config)
    item = filer.ingest(source)
    assert item is not None
    assert not source.exists()
    assert item.path.parent == app_config.inbox_dir

    target_folder = app_config.university_root / subject.folder_name / "Exercícios"
    (target_folder / "Ficha.pdf").write_bytes(b"existing")
    document = filer.file_document(item.id, subject.id, "Exercícios", "Ficha.pdf")

    assert document.current_path.name == "Ficha (2).pdf"
    assert document.current_path.read_bytes() == b"x" * 200
    assert database.count_inbox_items() == 0
    assert database.filing_hints() == [FilingHint("MAT101_ficha.pdf", subject.id, "Exercícios")]
    assert database.activity_summary().collisions_renamed == 1


def test_filing_survives_a_catalog_read_failure(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _download(app_config)
    item = filer.ingest(source)
    assert item is not None

    def fail_get_file(*args: object, **kwargs: object) -> NoReturn:
        raise RuntimeError("leitura falhou depois do commit")

    monkeypatch.setattr(database, "get_file", fail_get_file)

    document = filer.file_document(item.id, subject.id, "Exercícios", "Ficha.pdf")

    assert document.current_path.is_file()
    assert not item.path.exists()
    monkeypatch.undo()
    stored = database.get_file(document.id)
    assert stored is not None
    assert stored.catalog_state == "active"
    refreshed = database.get_inbox_item(item.id)
    assert refreshed is not None
    assert refreshed.status == "filed"


def test_ingestion_survives_a_catalog_read_failure(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _download(app_config)

    def fail_get_inbox_item(*args: object, **kwargs: object) -> NoReturn:
        raise RuntimeError("leitura falhou depois do commit")

    monkeypatch.setattr(database, "get_inbox_item", fail_get_inbox_item)

    item = filer.ingest(source)

    assert item is not None
    assert item.status == "pending"
    assert item.path.is_file()
    assert item.path.parent == app_config.inbox_dir
    assert not source.exists()
    monkeypatch.undo()
    stored = database.get_inbox_item(item.id)
    assert stored is not None
    assert stored.status == "pending"
    assert database.list_pending_ingests() == []


def test_requested_extension_cannot_change_the_original(
    app_config: AppConfig, filer: FilingService, subject: Subject
) -> None:
    item = filer.ingest(_download(app_config, "notas.pdf"))
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", "Notas.exe")

    assert document.current_path.name == "Notas.pdf"


def test_small_or_unsupported_files_remain_in_downloads(
    app_config: AppConfig, filer: FilingService
) -> None:
    small = _download(app_config, "curto.txt", size=2)
    unsupported = _download(app_config, "programa.exe", size=200)

    assert filer.ingest(small) is None
    assert filer.ingest(unsupported) is None
    assert small.exists()
    assert unsupported.exists()


def test_existing_download_plan_is_top_level_deterministic_and_capped(
    app_config: AppConfig, filer: FilingService
) -> None:
    for index in range(30):
        _download(app_config, f"documento_{index:02}.pdf")
    _download(app_config, "demasiado_pequeno.pdf", size=2)
    _download(app_config, "ignorado.exe")
    nested = app_config.downloads_dir / "Pasta"
    nested.mkdir()
    (nested / "aninhado.pdf").write_bytes(b"x" * 200)
    (app_config.downloads_dir / "pasta.pdf").mkdir()

    plan = filer.plan_existing_downloads()

    assert plan.total == 30
    assert len(plan.selected) == 25
    assert plan.selected[0].path.name == "documento_00.pdf"
    assert plan.selected[-1].path.name == "documento_24.pdf"


def test_manual_import_rejects_a_file_changed_after_confirmation(
    app_config: AppConfig, filer: FilingService
) -> None:
    source = _download(app_config, "confirmado.pdf")
    plan = filer.plan_existing_downloads()
    candidate = plan.selected[0]
    source.write_bytes(b"changed after confirmation" * 20)

    assert filer.ingest(source, expected=candidate) is None
    assert source.exists()


def test_new_download_can_reuse_a_path_while_an_older_item_is_pending(
    app_config: AppConfig, database: Database, filer: FilingService
) -> None:
    source = _download(app_config, "repetido.pdf")
    first = filer.ingest(source)
    assert first is not None
    source.write_bytes(b"a genuinely newer download" * 10)

    second = filer.ingest(source)

    assert second is not None
    assert second.id != first.id
    assert second.path.name == "repetido (2).pdf"
    assert database.activity_summary().collisions_renamed == 1


def test_undo_collision_is_renamed_without_overwrite_and_counted(
    app_config: AppConfig, database: Database, filer: FilingService, subject: Subject
) -> None:
    item = filer.ingest(_download(app_config))
    assert item is not None
    filer.file_document(item.id, subject.id, "Slides", "MAT101_ficha.pdf")
    (app_config.inbox_dir / "MAT101_ficha.pdf").write_bytes(b"newer inbox file")

    restored = filer.undo_latest_filing()

    assert restored is not None
    assert restored.path.name == "MAT101_ficha (2).pdf"
    assert (app_config.inbox_dir / "MAT101_ficha.pdf").read_bytes() == b"newer inbox file"
    assert database.activity_summary().collisions_renamed == 1


def test_non_university_file_returns_without_overwrite(
    app_config: AppConfig, filer: FilingService
) -> None:
    item = filer.ingest(_download(app_config, "fatura.pdf"))
    assert item is not None
    (app_config.downloads_dir / "fatura.pdf").write_bytes(b"newer file")

    destination = filer.return_to_downloads(item.id)

    assert destination.name == "fatura (2).pdf"
    assert destination.exists()


def test_undo_restores_latest_document_to_inbox(
    app_config: AppConfig, filer: FilingService, subject: Subject
) -> None:
    item = filer.ingest(_download(app_config, "aula.pdf"))
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", "Aula.pdf")

    restored = filer.undo_latest_filing()

    assert restored is not None
    assert restored.path.exists()
    assert restored.path.parent == app_config.inbox_dir
    assert not document.current_path.exists()
    assert filer.database.list_pending_undos() == []


def test_failed_undo_redirects_the_catalog_to_the_rollback_destination(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = filer.ingest(_download(app_config, "aula.pdf"))
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", "Aula.pdf")
    original_bytes = document.current_path.read_bytes()

    def sabotaged_mark(event: HistoryEvent, restored_path: Path, **_kwargs: object) -> None:
        del restored_path
        Path(event.destination_path).write_bytes(b"unrelated replacement")
        raise RuntimeError("histórico indisponível")

    monkeypatch.setattr(database, "mark_filing_undone", sabotaged_mark)

    with pytest.raises(FilingError):
        filer.undo_latest_filing()

    folder = app_config.university_root / subject.folder_name / "Slides"
    replacement = folder / "Aula.pdf"
    rolled_back = folder / "Aula (2).pdf"
    assert replacement.read_bytes() == b"unrelated replacement"
    assert rolled_back.read_bytes() == original_bytes

    stored = database.get_file(document.id)
    assert stored is not None
    assert stored.current_path == rolled_back
    assert [event.destination_path for event in database.list_undoable_filings()] == [rolled_back]
    assert database.list_pending_undos() == []

    monkeypatch.undo()

    restored = filer.undo_latest_filing()

    assert restored is not None
    assert restored.path.read_bytes() == original_bytes
    assert database.get_file(document.id) is None
    assert replacement.read_bytes() == b"unrelated replacement"


def test_undo_never_skips_a_missing_newest_document(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
) -> None:
    older_item = filer.ingest(_download(app_config, "anterior.pdf"))
    assert older_item is not None
    older = filer.file_document(older_item.id, subject.id, "Slides", "Anterior.pdf")
    newest_item = filer.ingest(_download(app_config, "recente.pdf"))
    assert newest_item is not None
    newest = filer.file_document(newest_item.id, subject.id, "Slides", "Recente.pdf")
    newest.current_path.unlink()

    with pytest.raises(FilingError, match="último ficheiro organizado"):
        filer.undo_latest_filing()

    latest = database.latest_undoable_filing()
    assert latest is not None
    assert latest.destination_path == newest.current_path
    assert older.current_path.exists()


def test_incomplete_undo_keeps_its_recovery_marker(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = filer.ingest(_download(app_config, "parcial.pdf"))
    assert item is not None
    document = filer.file_document(item.id, subject.id, "Slides", "Parcial.pdf")

    def leave_partial(_source: Path, target: Path, **_kwargs: object) -> Path:
        target.write_bytes(b"partial copy")
        raise IncompleteMoveError(target)

    monkeypatch.setattr("organizador.filer.move_without_overwrite", leave_partial)

    with pytest.raises(FilingError, match="ficou incompleta"):
        filer.undo_latest_filing()

    assert document.current_path.exists()
    assert len(database.list_pending_undos()) == 1
    pending = database.list_pending_undos()[0]
    assert pending.destination_path.read_bytes() == b"partial copy"


def test_incomplete_filing_keeps_its_recovery_marker(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = filer.ingest(_download(app_config, "arquivo-parcial.pdf"))
    assert item is not None

    def leave_partial(_source: Path, target: Path, **_kwargs: object) -> Path:
        target.write_bytes(b"partial filing copy")
        raise IncompleteMoveError(target)

    monkeypatch.setattr("organizador.filer.move_without_overwrite", leave_partial)

    with pytest.raises(FilingError, match="ficou incompleta"):
        filer.file_document(item.id, subject.id, "Slides", "Parcial.pdf")

    assert item.path.exists()
    assert len(database.list_pending_filings()) == 1
    pending = database.list_pending_filings()[0]
    assert pending.destination_path.read_bytes() == b"partial filing copy"


def test_database_failure_rolls_subject_move_back(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = filer.ingest(_download(app_config, "aula.pdf"))
    assert item is not None

    def fail_record(*_args: object, **_kwargs: object) -> NoReturn:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(database, "record_filing", fail_record)

    with pytest.raises(FilingError, match="revertido"):
        filer.file_document(item.id, subject.id, "Slides", "Aula.pdf")

    assert item.path.exists()
    refreshed = database.get_inbox_item(item.id)
    assert refreshed is not None
    assert refreshed.status == "pending"


def test_render_final_name_keeps_the_original_extension() -> None:
    name = render_final_name(
        "{codigo}_{tipo}_{nome_original}",
        subject_name="Cálculo I",
        subject_code="MAT101",
        kind="Slides",
        original_name="Aula 5.pdf",
        when=datetime(2026, 9, 1, 10, 0, 0),
    )

    assert name == "MAT101_Slides_Aula 5.pdf"


def test_template_without_extension_still_gets_one_through_filing(
    app_config: AppConfig, database: Database, filer: FilingService, subject: Subject
) -> None:
    item = filer.ingest(_download(app_config, "notas.pdf"))
    assert item is not None
    final_name = render_final_name(
        "{codigo}_resumo",
        subject_name=subject.name,
        subject_code=subject.code,
        kind="Slides",
        original_name=item.original_name,
        when=item.detected_at,
    )

    document = filer.file_document(item.id, subject.id, "Slides", final_name)

    assert final_name == "MAT101_resumo.pdf"
    assert document.current_path.name == "MAT101_resumo.pdf"
    assert database.activity_summary().collisions_renamed == 0


def _make_junction(link: Path, target: Path) -> bool:
    """Create a directory junction without administrator rights, if possible."""

    target.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
    )
    return completed.returncode == 0 and link.is_dir()


def test_filing_rejects_subject_folder_that_escapes_through_a_junction(
    app_config: AppConfig,
    database: Database,
    filer: FilingService,
    subject: Subject,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    link = app_config.university_root / subject.folder_name
    shutil.rmtree(link, ignore_errors=True)
    if not _make_junction(link, outside):
        pytest.skip("directory junctions are not available on this filesystem")
    item = filer.ingest(_download(app_config))
    assert item is not None

    with pytest.raises(FilingError, match="não é segura"):
        filer.file_document(item.id, subject.id, "Slides", "Ficha.pdf")

    assert list(outside.iterdir()) == []
    assert database.count_inbox_items() == 1


def test_replace_previous_version_round_trip(
    app_config: AppConfig, database: Database, filer: FilingService, subject: Subject
) -> None:
    item = filer.ingest(_download(app_config, "aula.pdf"))
    assert item is not None
    old = filer.file_document(item.id, subject.id, "Slides", "Aula.pdf")
    old_bytes = old.current_path.read_bytes()

    source = app_config.downloads_dir / "aula.pdf"
    source.write_bytes(b"versao nova " * 20)
    new_item = filer.ingest(source)
    assert new_item is not None
    new_document = filer.file_document(
        new_item.id, subject.id, "Slides", "Aula.pdf", replace_document_id=old.id
    )

    folder = app_config.university_root / subject.folder_name / "Slides"
    destination = folder / "Aula.pdf"
    versioned = folder / "Aula (versão anterior).pdf"
    assert destination.read_bytes() == b"versao nova " * 20
    assert versioned.read_bytes() == old_bytes
    stored_old = database.get_file(old.id)
    assert stored_old is not None
    assert stored_old.current_path == versioned
    assert new_document.current_path == destination
    assert database.list_pending_versions() == []

    restored = filer.undo_latest_filing()

    assert restored is not None
    assert restored.path.read_bytes() == b"versao nova " * 20
    assert database.get_file(new_document.id) is None
    stored_old = database.get_file(old.id)
    assert stored_old is not None
    assert stored_old.current_path == destination
    assert destination.read_bytes() == old_bytes
    assert not versioned.exists()


def test_replacement_uses_a_free_versioned_name(
    app_config: AppConfig, database: Database, filer: FilingService, subject: Subject
) -> None:
    item = filer.ingest(_download(app_config, "aula.pdf"))
    assert item is not None
    old = filer.file_document(item.id, subject.id, "Slides", "Aula.pdf")

    folder = app_config.university_root / subject.folder_name / "Slides"
    (folder / "Aula (versão anterior).pdf").write_bytes(b"versao ainda mais antiga")

    source = app_config.downloads_dir / "aula.pdf"
    source.write_bytes(b"nova versao " * 10)
    new_item = filer.ingest(source)
    assert new_item is not None
    filer.file_document(new_item.id, subject.id, "Slides", "Aula.pdf", replace_document_id=old.id)

    assert (folder / "Aula (versão anterior) (2).pdf").read_bytes() == b"x" * 200
    assert (folder / "Aula (versão anterior).pdf").read_bytes() == b"versao ainda mais antiga"
    stored_old = database.get_file(old.id)
    assert stored_old is not None
    assert stored_old.current_path == folder / "Aula (versão anterior) (2).pdf"


def test_replace_requires_the_matching_destination(
    app_config: AppConfig, database: Database, filer: FilingService, subject: Subject
) -> None:
    item = filer.ingest(_download(app_config, "aula.pdf"))
    assert item is not None
    old = filer.file_document(item.id, subject.id, "Slides", "Aula.pdf")

    source = app_config.downloads_dir / "aula.pdf"
    source.write_bytes(b"outra versao")
    new_item = filer.ingest(source)
    assert new_item is not None
    new_document = filer.file_document(
        new_item.id, subject.id, "Trabalhos", "aula.pdf", replace_document_id=old.id
    )

    assert old.current_path.is_file()
    assert old.current_path.name == "Aula.pdf"
    assert new_document.current_path.parent.name == "Trabalhos"
    assert new_document.current_path.name == "aula.pdf"
    stored_old = database.get_file(old.id)
    assert stored_old is not None
    assert stored_old.current_path == old.current_path
