"""Named commands behind the keyboard palette.

The controller registers every action the palette may run; the palette only
knows ids, titles and keywords. Lookup is a pure function over a snapshot, so
it can run on any thread without touching widgets.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Command:
    """One action the palette can run, with the words that should surface it."""

    id: str
    title: str
    keywords: str = ""
    shortcut: str = ""
    callback: Callable[[], None] | None = None


def fold(text: str) -> str:
    """Return a case- and accent-folded key for text matching."""

    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def lookup(query: str, commands: Sequence[Command]) -> tuple[Command, ...]:
    """Rank commands against ``query``; an empty query returns them unchanged."""

    needle = fold(query.strip())
    if not needle:
        return tuple(commands)

    starts: list[Command] = []
    contains: list[Command] = []
    keyword_only: list[Command] = []
    for command in commands:
        title = fold(command.title)
        keywords = fold(command.keywords)
        if title.startswith(needle):
            starts.append(command)
        elif needle in title:
            contains.append(command)
        elif needle in keywords:
            keyword_only.append(command)
    return tuple(starts + contains + keyword_only)


class CommandRegistry:
    """Collects the controller's commands in a stable registration order."""

    def __init__(self) -> None:
        self._commands: list[Command] = []
        self._ids: set[str] = set()

    def register(self, command: Command) -> None:
        """Add one command; duplicate ids are ignored by design."""

        if command.id in self._ids:
            return
        self._ids.add(command.id)
        self._commands.append(command)

    def commands(self) -> tuple[Command, ...]:
        """Return every registered command, in registration order."""

        return tuple(self._commands)
