"""
bible_structure.py
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import Literal

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


FootnoteType = Literal["tn", "sn", "tc", "unknown"]
KNOWN_PREFIXES: set[str] = {"tn", "sn", "tc"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_NOTE_BOUNDARY = re.compile(r'(?:^|(?<=[.!?"\])])) *(tn|sn|tc)(?= )')


@dataclass
class Footnote:
    type: FootnoteType
    text: str
    def __repr__(self):
        return f"Footnote(type={self.type!r}, text={self.text[:60]!r})"

@dataclass
class Chunk:
    text: str
    footnotes: list[Footnote] = field(default_factory=list)
    def __repr__(self):
        return f"Chunk({self.text[:45]!r}, fns={len(self.footnotes)})"

@dataclass
class Verse:
    number: int | None
    chunks: list[Chunk] = field(default_factory=list)

    @property
    def plain_text(self):
        return " ".join(c.text for c in self.chunks if c.text).strip()

    @property
    def all_footnotes(self):
        return [fn for chunk in self.chunks for fn in chunk.footnotes]

    def footnotes_by_type(self, ftype):
        return [fn for fn in self.all_footnotes if fn.type == ftype]

    def __repr__(self):
        return f"Verse(number={self.number}, chunks={len(self.chunks)}, footnotes={len(self.all_footnotes)})"

@dataclass
class Paragraph:
    verses: list[Verse] = field(default_factory=list)

    @property
    def plain_text(self):
        return " ".join(v.plain_text for v in self.verses).strip()

    def __repr__(self):
        return f"Paragraph(verses={len(self.verses)})"

@dataclass
class Section:
    heading: str | None
    heading_footnotes: list[Footnote] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)

    def __repr__(self):
        fn = f", {len(self.heading_footnotes)} fn" if self.heading_footnotes else ""
        return f"Section(heading={self.heading!r}{fn}, paragraphs={len(self.paragraphs)})"

@dataclass
class ChapterPage:
    book: str
    chapter: int
    version: str
    title: str
    source_url: str
    sections: list[Section] = field(default_factory=list)

    @property
    def all_paragraphs(self):
        return [p for s in self.sections for p in s.paragraphs]

    @property
    def all_verses(self):
        return [v for p in self.all_paragraphs for v in p.verses]

    @property
    def all_footnotes(self):
        return [fn for v in self.all_verses for fn in v.all_footnotes]

    def footnotes_by_type(self, ftype):
        return [fn for fn in self.all_footnotes if fn.type == ftype]

    def __repr__(self):
        return (
            f"ChapterPage(book={self.book!r}, chapter={self.chapter}, "
            f"version={self.version!r}, "
            f"sections={len(self.sections)}, "
            f"verses={len(self.all_verses)}, "
            f"footnotes={len(self.all_footnotes)} "
            f"[tn={len(self.footnotes_by_type('tn'))} "
            f"sn={len(self.footnotes_by_type('sn'))} "
            f"tc={len(self.footnotes_by_type('tc'))}])"
        )


def get_chapter_data(version: str, book_id: int, reference: str) -> dict:
    url = f"https://nodejs.bible.com/api/bible/chapter/{version}"
    params = {"id": book_id, "reference": reference}
    response = requests.get(url, params=params, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def _parse_footnote_block(raw: str) -> list[Footnote]:
    notes: list[Footnote] = []
    boundaries = [(m.start(), m.group(1)) for m in _NOTE_BOUNDARY.finditer(raw)]
    for i, (start, ftype) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(raw)
        body = raw[start + 3 : end].strip()
        notes.append(Footnote(type=ftype, text=body))
    if not notes and raw.strip():
        notes.append(Footnote(type="unknown", text=raw.strip()))
    return notes


def _parse_raw_text(raw: str) -> list[Chunk]:
    parts = raw.split("#")
    chunks: list[Chunk] = []
    pending_text = parts[0].strip()

    for i in range(1, len(parts)):
        raw_block = parts[i]
        last_punc = max(raw_block.rfind("."), raw_block.rfind("?"), raw_block.rfind("!"))

        if last_punc == -1 or last_punc == len(raw_block) - 1:
            footnote_text  = raw_block
            trailing_bible = ""
        else:
            footnote_text  = raw_block[: last_punc + 1]
            trailing_bible = raw_block[last_punc + 1 :].strip()

        footnotes = _parse_footnote_block(footnote_text)
        chunks.append(Chunk(text=pending_text, footnotes=footnotes))
        pending_text = trailing_bible

    if pending_text:
        chunks.append(Chunk(text=pending_text, footnotes=[]))

    return chunks


def _extract_verse_number(text: str) -> tuple[int | None, str]:
    m = re.match(r"^(\d+)\s*(.*)", text, re.DOTALL)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, text


def _collect_raw(tag: Tag) -> str:
    parts: list[str] = []
    for node in tag.descendants:
        if isinstance(node, NavigableString):
            if isinstance(node.parent, Tag) and "ft" in (node.parent.get("class") or []):
                continue
            text = str(node)
            if text:
                parts.append(text)
        elif isinstance(node, Tag) and "ft" in (node.get("class") or []):
            parts.append("#" + node.get_text())
    return "".join(parts)


def _parse_paragraph_tag(p_tag: Tag) -> Paragraph:
    paragraph = Paragraph()
    verse_spans = p_tag.find_all(
        lambda t: isinstance(t, Tag)
        and t.name == "span"
        and any("verse" in c for c in (t.get("class") or []))
    )
    if verse_spans:
        for span in verse_spans:
            raw = _collect_raw(span)
            verse_num, rest = _extract_verse_number(raw)
            chunks = _parse_raw_text(rest)
            paragraph.verses.append(Verse(number=verse_num, chunks=chunks))
    else:
        raw = _collect_raw(p_tag)
        if raw.strip():
            verse_num, rest = _extract_verse_number(raw)
            chunks = _parse_raw_text(rest)
            paragraph.verses.append(Verse(number=verse_num, chunks=chunks))
    return paragraph


def parse_chapter(soup, book, chapter, version, source_url, title) -> ChapterPage:
    chapter_page = ChapterPage(
        book=book, chapter=chapter, version=version,
        title=title, source_url=source_url,
    )

    chapter_root = soup.find(
        lambda t: isinstance(t, Tag)
        and any("chapter" in c for c in (t.get("class") or []))
    )
    if chapter_root is None:
        chapter_root = soup

    current_section: Section | None = None

    def _ensure_section() -> Section:
        nonlocal current_section
        if current_section is None:
            current_section = Section(heading=None)
            chapter_page.sections.append(current_section)
        return current_section

    for child in chapter_root.children:
        if not isinstance(child, Tag):
            continue
        classes: list[str] = child.get("class") or []

        if any("s1" in c or "__s" in c for c in classes):
            raw_heading = _collect_raw(child)
            heading_text, heading_fn_raw = (raw_heading.split("#", 1) + [""])[:2]
            heading_footnotes = _parse_footnote_block(heading_fn_raw) if heading_fn_raw else []
            current_section = Section(
                heading=heading_text.strip() or None,
                heading_footnotes=heading_footnotes,
            )
            chapter_page.sections.append(current_section)

        elif any("__p" in c or c == "p" for c in classes):
            para = _parse_paragraph_tag(child)
            if para.verses:
                _ensure_section().paragraphs.append(para)

        else:
            verse_spans = child.find_all(
                lambda t: isinstance(t, Tag)
                and t.name == "span"
                and any("verse" in c for c in (t.get("class") or []))
            )
            if verse_spans:
                para = _parse_paragraph_tag(child)
                if para.verses:
                    _ensure_section().paragraphs.append(para)

    return chapter_page


if __name__ == "__main__":
    BOOK_CHAPTER = "GEN.1"
    BIBLE_ID     = 107
    API_VERSION  = "3.3"

    print(f"Fetching {BOOK_CHAPTER} (bible id={BIBLE_ID})...")
    response      = get_chapter_data(API_VERSION, BIBLE_ID, BOOK_CHAPTER)
    chapter_ref   = response["reference"]["usfm"][0]
    chapter_human = response["reference"]["human"]
    content_html  = response["content"]

    soup = BeautifulSoup(content_html, "lxml")

    book_name, chapter_num_str = chapter_ref.split(".")
    chapter_num = int(chapter_num_str)

    chapter_page = parse_chapter(
        soup       = soup,
        book       = book_name,
        chapter    = chapter_num,
        version    = f"NET (id={BIBLE_ID})",
        source_url = f"https://www.bible.com/bible/{BIBLE_ID}/{chapter_ref}",
        title      = chapter_human,
    )

    print(chapter_page)
    print()
    for si, section in enumerate(chapter_page.sections, 1):
        print(f"  Section {si}: {section}")
        for pi, para in enumerate(section.paragraphs, 1):
            print(f"    Paragraph {pi}: {para}")
            for verse in para.verses:
                print(f"      {verse}")
                for chunk in verse.chunks:
                    print(f"        {chunk}")
    print()

    a = f"output_{chapter_human}_{BIBLE_ID}.html"
    with open(a, "w", encoding="utf-8") as fh:
        fh.write(soup.prettify())
    print(f"Raw HTML written to {a}")