"""OCR rendering, recognition, and indexer integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from organizador import ocr
from organizador.db import Database
from organizador.indexer import DocumentIndexer
from organizador.models import Subject

NEEDS_OCR_ENGINE = pytest.mark.skipif(
    not ocr.ocr_available(("pt-PT",)),
    reason="no Portuguese OCR engine installed",
)


def _blank_pdf(path: Path, pages: int = 1) -> Path:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(612, 792)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _file_record(database: Database, subject: Subject, path: Path) -> int:
    item = database.add_inbox_item(
        path, path.parent / "original.pdf", path.name, path.stat().st_size
    )
    return database.record_filing(item.id, subject.id, "Outros", path).id


def test_preferred_language_tags() -> None:
    assert ocr.preferred_language_tags("pt") == ("pt-PT", "pt-BR", "en-US")
    assert ocr.preferred_language_tags("xx") == ("en-US",)


def test_render_pdf_pages_missing_file(tmp_path: Path) -> None:
    assert ocr.render_pdf_pages(tmp_path / "ausente.pdf") == {}


def test_render_pdf_pages_produces_png_images(tmp_path: Path) -> None:
    path = _blank_pdf(tmp_path / "branco.pdf", pages=2)

    rendered = ocr.render_pdf_pages(path)

    assert sorted(rendered) == [0, 1]
    assert all(image.startswith(b"\x89PNG\r\n\x1a\n") for image in rendered.values())


def test_recognize_page_empty_bytes() -> None:
    assert ocr.recognize_page(b"", ("pt-PT",)) == ""


def test_recognize_page_without_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "_cached_engine", lambda _tags: None)

    assert ocr.recognize_page(b"not really an image", ("pt-PT",)) == ""


@NEEDS_OCR_ENGINE
def test_recognize_page_reads_rendered_text(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1200, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 80), "SortInator teste oitenta", fill="black")
    path = tmp_path / "amostra.png"
    image.save(path)
    image_bytes = path.read_bytes()

    text = ocr.recognize_page(image_bytes, ("pt-PT",))

    assert "oitenta" in text.casefold()


def test_ocr_blank_pages_fills_only_blanks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _blank_pdf(tmp_path / "misto.pdf", pages=3)
    calls: list[bytes] = []

    def fake_recognize(image: bytes, tags: object) -> str:
        calls.append(image)
        return "TEXTO"

    monkeypatch.setattr(ocr, "ocr_available", lambda _tags: True)
    monkeypatch.setattr(ocr, "recognize_page", fake_recognize)

    filled = ocr.ocr_blank_pages(path, ["mantido", "", "  "], ("pt-PT",))

    assert filled == ["mantido", "TEXTO", "TEXTO"]
    assert len(calls) == 2


def test_ocr_blank_pages_respects_max_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _blank_pdf(tmp_path / "longo.pdf", pages=5)
    calls: list[bytes] = []

    def fake_recognize(image: bytes, tags: object) -> str:
        calls.append(image)
        return "TEXTO"

    monkeypatch.setattr(ocr, "ocr_available", lambda _tags: True)
    monkeypatch.setattr(ocr, "recognize_page", fake_recognize)

    filled = ocr.ocr_blank_pages(path, [""] * 5, ("pt-PT",), max_pages=2)

    assert filled == ["TEXTO", "TEXTO", "", "", ""]
    assert len(calls) == 2


def test_ocr_blank_pages_skips_when_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _blank_pdf(tmp_path / "qualquer.pdf")
    monkeypatch.setattr(ocr, "ocr_available", lambda _tags: False)

    def fail_recognize(image: bytes, tags: object) -> str:
        raise AssertionError("recognition must not run")

    monkeypatch.setattr(ocr, "recognize_page", fail_recognize)
    pages = ["", ""]

    assert ocr.ocr_blank_pages(path, pages, ("pt-PT",)) is pages


def test_ocr_blank_pages_skips_render_when_nothing_is_blank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _blank_pdf(tmp_path / "texto.pdf")

    def fail_render(path: Path, **kwargs: object) -> dict[int, bytes]:
        raise AssertionError("rendering must not run")

    monkeypatch.setattr(ocr, "render_pdf_pages", fail_render)

    assert ocr.ocr_blank_pages(path, ["já existe"], ("pt-PT",)) == ["já existe"]


def test_ocr_blank_pages_keeps_true_page_mapping_on_render_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _blank_pdf(tmp_path / "falha.pdf", pages=3)
    first_image = b"page-1-png"
    third_image = b"page-3-png"

    def failing_render(path: Path, **kwargs: object) -> dict[int, bytes]:
        return {0: first_image, 2: third_image}

    def fake_recognize(image: bytes, tags: object) -> str:
        return "UM" if image == first_image else "TRES"

    monkeypatch.setattr(ocr, "ocr_available", lambda _tags: True)
    monkeypatch.setattr(ocr, "render_pdf_pages", failing_render)
    monkeypatch.setattr(ocr, "recognize_page", fake_recognize)

    filled = ocr.ocr_blank_pages(path, ["", "", ""], ("pt-PT",))

    assert filled == ["UM", "", "TRES"]


def test_render_pdf_pages_clamps_oversized_pages(tmp_path: Path) -> None:
    import io

    from PIL import Image
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=3000, height=4000)
    path = tmp_path / "largo.pdf"
    with path.open("wb") as handle:
        writer.write(handle)

    rendered = ocr.render_pdf_pages(path)

    image = Image.open(io.BytesIO(rendered[0]))
    width, height = image.size
    assert width * height <= ocr.MAX_RENDER_PIXELS
    assert (width, height) == (3000, 4000)


def test_render_pdf_pages_skips_unusable_pages(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100000, height=100000)
    path = tmp_path / "gigante.pdf"
    with path.open("wb") as handle:
        writer.write(handle)

    assert ocr.render_pdf_pages(path) == {}


def test_indexer_never_calls_ocr_without_provider(
    database: Database, subject: Subject, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _blank_pdf(tmp_path / "digitalizado.pdf")
    file_id = _file_record(database, subject, path)
    document = database.get_file(file_id)
    assert document is not None

    def fail_ocr(path: Path, pages: list[str], tags: object, **kwargs: object) -> list[str]:
        raise AssertionError("OCR must stay disabled without a provider")

    monkeypatch.setattr(ocr, "ocr_blank_pages", fail_ocr)
    indexer = DocumentIndexer(database)

    indexer.index_document(document)
    indexer.shutdown()

    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.indexed_at is not None
    assert database.search("digitalizado")


def test_indexer_uses_ocr_for_blank_pdf_pages(
    database: Database, subject: Subject, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _blank_pdf(tmp_path / "digitalizado.pdf")
    file_id = _file_record(database, subject, path)
    document = database.get_file(file_id)
    assert document is not None
    calls: list[tuple[str, ...]] = []

    def fake_blank_pages(path: Path, pages: list[str], tags: object, **kwargs: object) -> list[str]:
        calls.append(tuple(tags))
        assert pages == [""]
        return ["CONTEUDO ESCANEADO"]

    monkeypatch.setattr(ocr, "ocr_blank_pages", fake_blank_pages)
    indexer = DocumentIndexer(database, ocr_languages=lambda: ("pt-PT",))

    indexer.index_document(document)
    indexer.shutdown()

    assert calls == [(("pt-PT",))]
    assert database.search("escaneado")
    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.index_state == ""


def test_indexer_ocr_failure_keeps_filename_row(
    database: Database, subject: Subject, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _blank_pdf(tmp_path / "digitalizado.pdf")
    file_id = _file_record(database, subject, path)
    document = database.get_file(file_id)
    assert document is not None

    def fail_ocr(path: Path, pages: list[str], tags: object, **kwargs: object) -> list[str]:
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(ocr, "ocr_blank_pages", fail_ocr)
    indexer = DocumentIndexer(database, ocr_languages=lambda: ("pt-PT",))

    indexer.index_document(document)
    indexer.shutdown()

    refreshed = database.get_file(file_id)
    assert refreshed is not None
    assert refreshed.indexed_at is not None
    assert database.search("digitalizado")
