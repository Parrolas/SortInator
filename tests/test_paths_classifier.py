"""Filename safety, classifier and deadline tests."""

from __future__ import annotations

import dataclasses
import logging
import os
import subprocess
from datetime import date
from pathlib import Path

import pytest

import organizador.paths as path_operations
from organizador.classifier import extract_due_date, guess_filing, normalise
from organizador.models import ExistingDownload, FilingHint, Subject
from organizador.paths import (
    move_without_overwrite,
    resolve_contained,
    sanitise_component,
    sanitise_filename,
    unique_path,
    windows_folder_key,
)


def test_windows_folder_key_folds_accents_with_case() -> None:
    assert windows_folder_key("MAT101 - Cálculo I") == windows_folder_key("MAT101 - CÁLCULO I")
    assert windows_folder_key("Cálculo") == windows_folder_key("calculo")
    assert windows_folder_key("Física") == windows_folder_key("FISICA")
    assert windows_folder_key("Cálculo") != windows_folder_key("Álgebra")
    assert windows_folder_key("Cálculo I") != windows_folder_key("Cálculo II")


def test_windows_components_remove_invalid_and_reserved_names() -> None:
    assert sanitise_component("  aula: 3 / revisão?  ") == "aula- 3 - revisão-"
    assert sanitise_component("CON") == "CON_"
    assert sanitise_filename(r"..\segredo?.pdf") == "segredo-.pdf"


def test_unique_path_adds_a_human_readable_counter(tmp_path: Path) -> None:
    (tmp_path / "Aula.pdf").write_bytes(b"one")
    (tmp_path / "Aula (2).pdf").write_bytes(b"two")

    assert unique_path(tmp_path, "Aula.pdf").name == "Aula (3).pdf"


def test_move_without_overwrite_refuses_an_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    target = tmp_path / "target.pdf"
    source.write_bytes(b"new material")
    target.write_bytes(b"existing material")

    with pytest.raises(FileExistsError):
        move_without_overwrite(source, target)

    assert source.read_bytes() == b"new material"
    assert target.read_bytes() == b"existing material"


def test_move_without_overwrite_revalidates_confirmed_identity(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    target = tmp_path / "target.pdf"
    source.write_bytes(b"confirmed material")
    confirmed = ExistingDownload.capture(source)
    assert confirmed is not None
    source.write_bytes(b"replacement material with another size")

    with pytest.raises(OSError, match="changed"):
        move_without_overwrite(
            source,
            target,
            expected_identity=(
                confirmed.device,
                confirmed.inode,
                confirmed.size,
                confirmed.modified_ns,
            ),
        )

    assert source.read_bytes() == b"replacement material with another size"
    assert not target.exists()


def test_windows_copy_fallback_is_exclusive_and_removes_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.pdf"
    target = tmp_path / "target.pdf"
    source.write_bytes(b"cross-volume style copy")
    monkeypatch.setattr(path_operations, "_rename_windows_handle", lambda *_args: False)

    move_without_overwrite(source, target)

    assert not source.exists()
    assert target.read_bytes() == b"cross-volume style copy"


def test_destination_created_during_move_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.pdf"
    target = tmp_path / "target.pdf"
    source.write_bytes(b"new material")

    def create_competing_target(*_args: object) -> bool:
        target.write_bytes(b"competing material")
        return False

    monkeypatch.setattr(path_operations, "_rename_windows_handle", create_competing_target)

    with pytest.raises(FileExistsError):
        move_without_overwrite(source, target)

    assert source.read_bytes() == b"new material"
    assert target.read_bytes() == b"competing material"


def test_failed_copy_cleanup_reports_the_leftover_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.pdf"
    target = tmp_path / "target.pdf"
    source.write_bytes(b"material")
    monkeypatch.setattr(path_operations, "_rename_windows_handle", lambda *_args: False)
    monkeypatch.setattr(path_operations, "_delete_windows_handle", lambda *_args: False)

    with pytest.raises(path_operations.IncompleteMoveError) as error:
        move_without_overwrite(source, target)

    assert error.value.leftover_path == target
    assert source.exists()
    assert target.exists()


def test_normalise_folds_portuguese_accents() -> None:
    assert normalise("CÁLCULO — Integração") == "calculo integracao"


def test_classifier_uses_code_keyword_and_document_type() -> None:
    subjects = [
        Subject(1, "Cálculo I", "MAT101", "#000000", ("derivadas",), "MAT101"),
        Subject(2, "Bases de Dados", "BD201", "#000000", ("sql",), "BD201"),
    ]

    guess = guess_filing("MAT101_ficha_derivadas_04.pdf", subjects)

    assert guess.subject_id == 1
    assert guess.kind == "Exercícios"
    assert guess.confidence >= 90


def test_classifier_does_not_force_an_unrelated_subject() -> None:
    subjects = [Subject(1, "Álgebra", "ALG", "#000000", (), "ALG")]

    guess = guess_filing("receita_de_bolo.pdf", subjects)

    assert guess.subject_id == 1  # A single configured subject remains a low-confidence shortcut.
    assert guess.confidence == 30


def test_classifier_code_requires_a_token_boundary() -> None:
    subjects = [Subject(1, "Matemática", "MAT", "#000000", (), "MAT")]

    guess = guess_filing("material_de_estudo.pdf", subjects)

    assert guess.confidence < 90

    prefixed = guess_filing(
        "aula-mat101_extra.pdf", [dataclasses.replace(subjects[0], code="MAT101")]
    )

    assert prefixed.subject_id == 1
    assert prefixed.confidence >= 90


def test_classifier_learns_only_after_two_matching_confirmations() -> None:
    subjects = [
        Subject(1, "Física", "FIS", "#000000", (), "FIS"),
        Subject(2, "História", "HIS", "#000000", (), "HIS"),
    ]
    hints = [
        FilingHint("folha_semanal_01.pdf", 2, "Testes"),
        FilingHint("Folha Semanal 02.docx", 2, "Testes"),
    ]
    baseline = guess_filing("folha-semanal-03.pdf", subjects)

    assert guess_filing("folha-semanal-03.pdf", subjects, hints[:1]) == baseline

    learned = guess_filing("folha-semanal-03.pdf", subjects, hints)
    assert learned.subject_id == 2
    assert learned.kind == "Testes"
    assert learned.confidence == 70


def test_classifier_abstains_on_conflicting_learned_values() -> None:
    subjects = [
        Subject(1, "Física", "FIS", "#000000", (), "FIS"),
        Subject(2, "História", "HIS", "#000000", (), "HIS"),
    ]
    hints = [
        FilingHint("ficha_semanal_01.pdf", 1, "Slides"),
        FilingHint("ficha semanal 02.pdf", 1, "Trabalhos"),
    ]

    guess = guess_filing("ficha-semanal-03.pdf", subjects, hints)

    assert guess.subject_id == 1
    assert guess.kind == "Exercícios"
    assert guess.confidence == 70


def test_classifier_ignores_generic_or_invalid_learning() -> None:
    subjects = [Subject(1, "Física", "FIS", "#000000", (), "FIS")]
    invalid = [
        FilingHint("aula_01.pdf", 99, "Desconhecido"),
        FilingHint("aula_02.pdf", 99, "Desconhecido"),
    ]

    assert guess_filing("aula_03.pdf", subjects, invalid) == guess_filing("aula_03.pdf", subjects)


def test_due_date_supports_iso_and_portuguese_numeric_forms() -> None:
    assert extract_due_date("trabalho_2026-09-15.pdf") == date(2026, 9, 15)
    assert extract_due_date("entrega_30-09.pdf", today=date(2026, 8, 1)) == date(2026, 9, 30)
    assert extract_due_date("entrega_02-01.pdf", today=date(2026, 8, 1)) == date(2027, 1, 2)


def test_due_date_rejects_invalid_calendar_values() -> None:
    assert extract_due_date("entrega_2026-13-45.pdf") is None
    assert extract_due_date("sem_data.pdf") is None


def test_due_date_ignores_section_numbering_without_deadline_context() -> None:
    assert extract_due_date("Aula 5-3.pdf") is None
    assert extract_due_date("Capitulo 12-4.pdf") is None
    assert extract_due_date("aula_7-8.pdf") is None
    assert extract_due_date("Seccao 2-10.pdf") is None
    assert extract_due_date("Ficha3-4.pdf") is None


def test_resolve_contained_accepts_inside_paths(tmp_path: Path) -> None:
    root = tmp_path / "Universidade"
    (root / "MAT101" / "Slides").mkdir(parents=True)

    resolved = resolve_contained(root / "MAT101" / "Slides" / "aula.pdf", root)

    assert resolved == (root / "MAT101" / "Slides" / "aula.pdf").resolve()


def test_resolve_contained_rejects_dotdot_escape(tmp_path: Path) -> None:
    root = tmp_path / "Universidade"
    root.mkdir()

    with pytest.raises(OSError, match="managed folder"):
        resolve_contained(root / ".." / "outside.pdf", root)


def _force_copy_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(path_operations, "_rename_windows_handle", lambda *args, **kwargs: False)


def test_cross_volume_fallback_preserves_times_and_attributes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "orig.pdf"
    source.write_bytes(b"bytes" * 100)
    created_ns = source.stat().st_ctime_ns
    old_ns = 1_600_000_000_000_000_000
    os.utime(source, ns=(old_ns, old_ns))
    subprocess.run(["attrib", "+h", str(source)], check=True)
    _force_copy_fallback(monkeypatch)
    target = tmp_path / "dest.pdf"

    result = move_without_overwrite(source, target)

    assert result == target
    assert not source.exists()
    assert target.stat().st_mtime_ns == old_ns
    assert target.stat().st_ctime_ns == created_ns
    assert target.stat().st_file_attributes & 0x2


def test_cross_volume_fallback_warns_about_dropped_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    source = tmp_path / "com-mark.pdf"
    source.write_bytes(b"main content")
    Path(f"{source}:Zone.Identifier").write_text("[ZoneTransfer]\nZoneId=3\n")
    _force_copy_fallback(monkeypatch)
    target = tmp_path / "sem-mark.pdf"

    with caplog.at_level(logging.WARNING, logger="organizador.paths"):
        result = move_without_overwrite(source, target)

    assert result == target
    assert target.read_bytes() == b"main content"
    assert not Path(f"{target}:Zone.Identifier").exists()
    assert "alternate data streams" in caplog.text
    assert "Zone.Identifier" in caplog.text


def test_due_date_accepts_unambiguous_or_contextual_pairs() -> None:
    assert extract_due_date("resumo_30-09.pdf") == date(date.today().year, 9, 30)
    assert extract_due_date("Teste 5-3.pdf", today=date(2026, 8, 1)) == date(2027, 3, 5)
    assert extract_due_date("entrega aula 5-3.pdf", today=date(2026, 8, 1)) is None
    assert extract_due_date("ficha_2026-05-10.pdf") == date(2026, 5, 10)


def test_classifier_ignores_common_word_subject_codes() -> None:
    subjects = [
        Subject(1, "Alemão", "DE", "#000000", (), "DE"),
        Subject(2, "Biologia", "BIO", "#000000", (), "BIO"),
    ]

    guess = guess_filing("Trabalho de Biologia.pdf", subjects)

    assert guess.subject_id == 2


def test_classifier_accepts_a_weak_code_next_to_a_number() -> None:
    subjects = [
        Subject(1, "Alemão", "DE", "#000000", (), "DE"),
        Subject(2, "Biologia", "BIO", "#000000", (), "BIO"),
    ]

    guess = guess_filing("DE 101 aula.pdf", subjects)

    assert guess.subject_id == 1
    assert guess.confidence >= 90
