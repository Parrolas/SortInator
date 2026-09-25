"""Transparent filename-based subject, type and deadline suggestions."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from datetime import date
from typing import TypeVar

from rapidfuzz import fuzz

from organizador.models import FILE_KINDS, FilingGuess, FilingHint, Subject

LEARNED_CONFIDENCE = 70
MIN_LEARNED_OBSERVATIONS = 2
DEADLINE_CONTEXT_TERMS = frozenset(
    {
        "entrega",
        "entregar",
        "prazo",
        "deadline",
        "due",
        "ate",
        "limite",
        "teste",
        "exame",
        "frequencia",
        "avaliacao",
        "trabalho",
        "projeto",
        "relatorio",
        "homework",
        "ficha",
        "lista",
        "exercicio",
    }
)
SECTION_NUMBERING_TERMS = frozenset(
    {
        "aula",
        "aulas",
        "capitulo",
        "cap",
        "ch",
        "slide",
        "slides",
        "semana",
        "parte",
        "vol",
        "volume",
        "modulo",
        "seccao",
        "secao",
    }
)
WEAK_CODE_STOPWORDS = frozenset(
    {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "a",
        "o",
        "as",
        "os",
        "e",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "por",
        "para",
        "com",
        "sem",
        "uma",
        "um",
        "que",
        "se",
        "ao",
        "the",
        "an",
        "of",
        "to",
        "in",
        "on",
        "and",
        "or",
        "for",
        "with",
    }
)


def _is_weak_code_without_number(code: str, normalised_name: str) -> bool:
    """Tell whether a short/common-word code match is noise.

    Codes like ``DE`` or ``A`` appear as ordinary words in most filenames;
    they only earn the code bonus next to a number (``DE 101``), where the
    pairing reads as a course reference instead of prose.
    """

    if len(code) >= 3 and code not in WEAK_CODE_STOPWORDS:
        return False
    return (
        re.search(
            rf"(?:^| )\d+ {re.escape(code)}(?: |$)|(?:^| ){re.escape(code)} \d+(?: |$)",
            normalised_name,
        )
        is None
    )


Choice = TypeVar("Choice", int, str)

KIND_TERMS: dict[str, tuple[str, ...]] = {
    "Slides": ("slide", "slides", "aula", "lecture", "capitulo", "chapter", "teoria"),
    "Exercícios": (
        "exercicio",
        "exercicios",
        "ficha",
        "problema",
        "problemset",
        "exercise",
        "lista",
    ),
    "Testes": ("teste", "test", "exame", "exam", "quiz", "frequencia", "avaliacao"),
    "Trabalhos": (
        "trabalho",
        "assignment",
        "projeto",
        "project",
        "relatorio",
        "report",
        "entrega",
        "homework",
    ),
}


def normalise(value: str) -> str:
    """Fold accents, case and punctuation for predictable matching."""

    decomposed = unicodedata.normalize("NFKD", value)
    ascii_like = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_like.casefold()))


def guess_filing(
    filename: str,
    subjects: Sequence[Subject],
    hints: Sequence[FilingHint] = (),
) -> FilingGuess:
    """Suggest a subject and document kind from a filename."""

    normalised_name = normalise(filename.rsplit(".", 1)[0])
    tokens = set(normalised_name.split())
    kind = _guess_kind(tokens, normalised_name)
    best_subject_id: int | None = None
    best_score = 0

    for subject in subjects:
        subject_name = normalise(subject.name)
        code = normalise(subject.code)
        score = int(fuzz.WRatio(normalised_name, subject_name) * 0.42)
        if subject_name and subject_name in normalised_name:
            score += 55
        if (
            code
            and (
                code in tokens
                or re.search(r"\b" + re.escape(code) + r"\b", normalised_name) is not None
            )
            and not _is_weak_code_without_number(code, normalised_name)
        ):
            score += 90
        for keyword in subject.keywords:
            normalised_keyword = normalise(keyword)
            if not normalised_keyword:
                continue
            if normalised_keyword in tokens:
                score += 72
            elif len(normalised_keyword) >= 3 and normalised_keyword in normalised_name:
                score += 44
        if score > best_score:
            best_score = score
            best_subject_id = subject.id

    if len(subjects) == 1 and best_score < 30:
        best_subject_id = subjects[0].id
        best_score = 30
    if best_score < 28:
        best_subject_id = None
    confidence = min(100, best_score)

    signature = _filing_signature(filename)
    if signature:
        matching_hints = [
            hint for hint in hints if _filing_signature(hint.original_name) == signature
        ]
        active_subject_ids = {subject.id for subject in subjects}
        learned_subject_id = _repeated_unanimous(
            [hint.subject_id for hint in matching_hints if hint.subject_id in active_subject_ids]
        )
        learned_kind = _repeated_unanimous(
            [hint.kind for hint in matching_hints if hint.kind in FILE_KINDS]
        )
        if learned_subject_id is not None:
            if learned_subject_id == best_subject_id:
                confidence = max(confidence, LEARNED_CONFIDENCE)
            else:
                best_subject_id = learned_subject_id
                confidence = LEARNED_CONFIDENCE
        if learned_kind is not None:
            kind = learned_kind

    return FilingGuess(best_subject_id, kind, confidence)


def _filing_signature(filename: str) -> tuple[str, ...]:
    tokens = tuple(
        token for token in normalise(filename.rsplit(".", 1)[0]).split() if not token.isdigit()
    )
    return tokens if len(tokens) >= 2 else ()


def _repeated_unanimous(values: list[Choice]) -> Choice | None:
    if len(values) < MIN_LEARNED_OBSERVATIONS or len(set(values)) != 1:
        return None
    return values[0]


def _guess_kind(tokens: set[str], normalised_name: str) -> str:
    scores: dict[str, int] = {}
    for kind, terms in KIND_TERMS.items():
        score = 0
        for term in terms:
            if term in tokens:
                score += 3
            elif term in normalised_name:
                score += 1
        scores[kind] = score
    best_kind = max(scores, key=scores.__getitem__)
    return best_kind if scores[best_kind] else "Outros"


def extract_due_date(filename: str, *, today: date | None = None) -> date | None:
    """Extract common numeric deadline formats from a filename.

    Ambiguous day-month pairs are only accepted when the year is present, the
    order is unambiguous, or the filename contains deadline vocabulary - a
    bare "Aula 5-3" is section numbering, not a date.
    """

    reference = today or date.today()
    stem = filename.rsplit(".", 1)[0]
    iso_match = re.search(r"(?<!\d)(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)", stem)
    if iso_match:
        try:
            return date(*(int(value) for value in iso_match.groups()))
        except ValueError:
            return None

    local_match = re.search(r"(?<!\d)(\d{1,2})[-_.](\d{1,2})(?:[-_.](20\d{2}))?(?!\d)", stem)
    if not local_match:
        return None
    day_text, month_text, year_text = local_match.groups()
    day, month = int(day_text), int(month_text)
    if year_text is None:
        context_tokens = set(normalise(stem).split())
        before = stem[: local_match.start()]
        preceding = re.findall(r"[^\W\d_]+|\d+", before, re.UNICODE)
        section_precedes = bool(preceding) and normalise(preceding[-1]) in SECTION_NUMBERING_TERMS
        unambiguous = day > 12 or month > 12
        contextual = bool(context_tokens & DEADLINE_CONTEXT_TERMS)
        if section_precedes or not (unambiguous or contextual):
            return None
    try:
        candidate = date(int(year_text) if year_text else reference.year, month, day)
    except ValueError:
        return None
    if year_text is None and candidate < reference:
        try:
            candidate = candidate.replace(year=reference.year + 1)
        except ValueError:
            return None
    return candidate
