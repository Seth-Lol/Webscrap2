from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Entry:
    rowId: int
    keyParts: list
    value: str


@dataclass
class ChapterDoc:
    chapter: int
    entries: list[Entry] = field(default_factory=list)


@dataclass
class BookDoc:
    bookId: str
    testament: str
    order: int
    title: str | None = None
    abbreviation: str | None = None
    chapters: list[ChapterDoc] = field(default_factory=list)


@dataclass
class TranslationDoc:
    translationId: str
    name: str
    abbreviation: str
    language: str
    copyright: str
    books: list[BookDoc] = field(default_factory=list)
