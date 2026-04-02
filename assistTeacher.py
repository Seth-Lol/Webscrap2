"""
bible_structure.py
──────────────────
Hierarchical data structure for bible.com NET Bible chapters.

PYTHON OBJECT HIERARCHY
═══════════════════════
ChapterPage
 ├── book, chapter, version, title, source_url
 └── sections[]
      ├── heading         (str | None)
      │     └── footnotes[]
      │               ├── type    ("tn" | "sn" | "tc" | "unknown")
      │               └── text    (str — full note body) 
      └── paragraphs[]
           └── verses[]
                ├── number     (int | None)
                └── chunks[]
                     ├── text          (str — Bible text fragment)
                     └── footnotes[]
                          ├── type    ("tn" | "sn" | "tc" | "unknown")
                          └── text    (str — full note body)

HOW THE RAW TEXT IS STRUCTURED
═══════════════════════════════
The raw paragraph text uses '#' as the delimiter between Bible text and footnotes:

    "1 In the beginning#tn Note body.sn Another note. God#sn Note. created#tn Note."
     ─── bible ─────── ─── notes block ─────────────────── ─── notes ─── ────────

  - '#' always introduces a footnote block.
  - Inside a block, multiple notes are concatenated after punctuation:
        "tn First note body.sn Second note body."
  - The note type is the first 2 characters: tn / sn / tc.
  - Trailing bible text (e.g. "God", "created") lives at the END of a
    non-last block, after the final note's closing punctuation.

FOOTNOTE TYPES
══════════════
  tn  Translator's Note   -- translation choices, Hebrew/Greek word meanings
  sn  Study Note          -- biblical, historical, theological context
  tc  Textual Criticism   -- manuscript variants and textual traditions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


# ── Constants ─────────────────────────────────────────────────────────────────

FootnoteType = Literal["tn", "sn", "tc", "unknown"]
KNOWN_PREFIXES: set[str] = {"tn", "sn", "tc"}

CLS_HEADING = "s1"
CLS_CHAPTER = "chapter"
CLS_P       = "p"
CLS_FT      = "ft"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Note boundary: start-of-string OR after punctuation, then known prefix + space
_NOTE_BOUNDARY = re.compile(r'(?:^|(?<=[.!?"\])])) *(tn|sn|tc)(?= )')




# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Footnote:
    """One tn / sn / tc annotation attached to a Bible text chunk."""
    type: FootnoteType
    text: str

    def __repr__(self) -> str:
        return f"Footnote(type={self.type!r}, text={self.text[:60]!r})"


@dataclass
class Chunk:
    """
    Atomic unit: a Bible text fragment + its immediately following footnotes.
    Preserves the inline order the text will be displayed:
        text -> [fn, fn, ...] -> next text -> [fn] -> ...
    """
    text: str
    footnotes: list[Footnote] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Chunk({self.text[:45]!r}, fns={len(self.footnotes)})"


@dataclass
class Verse:
    """One verse (or unnumbered poetic line) composed of ordered Chunks."""
    number: int | None
    chunks: list[Chunk] = field(default_factory=list)

    @property
    def plain_text(self) -> str:
        return " ".join(c.text for c in self.chunks if c.text).strip()

    @property
    def all_footnotes(self) -> list[Footnote]:
        return [fn for chunk in self.chunks for fn in chunk.footnotes]

    def footnotes_by_type(self, ftype: FootnoteType) -> list[Footnote]:
        return [fn for fn in self.all_footnotes if fn.type == ftype]

    def __repr__(self) -> str:
        return (
            f"Verse(number={self.number}, "
            f"chunks={len(self.chunks)}, "
            f"footnotes={len(self.all_footnotes)})"
        )


@dataclass
class Paragraph:
    """One <div class='__p'> block -- a group of consecutive verses."""
    verses: list[Verse] = field(default_factory=list)

    @property
    def plain_text(self) -> str:
        return " ".join(v.plain_text for v in self.verses).strip()

    def __repr__(self) -> str:
        return f"Paragraph(verses={len(self.verses)})"


@dataclass
class Section:
    """One heading + its paragraphs.
    heading_footnotes holds any footnotes attached directly to the heading
    (e.g. the psalm-intro note on Psalm 119).
    """
    heading:            str | None
    heading_footnotes:  list[Footnote] = field(default_factory=list)
    paragraphs:         list[Paragraph] = field(default_factory=list)

    def __repr__(self) -> str:
        fn = f", {len(self.heading_footnotes)} fn" if self.heading_footnotes else ""
        return f"Section(heading={self.heading!r}{fn}, paragraphs={len(self.paragraphs)})"


@dataclass
class ChapterPage:
    """Root object for one scraped Bible chapter page."""
    book:       str
    chapter:    int
    version:    str
    title:      str
    source_url: str
    sections:   list[Section] = field(default_factory=list)

    @property
    def all_paragraphs(self) -> list[Paragraph]:
        return [p for s in self.sections for p in s.paragraphs]

    @property
    def all_verses(self) -> list[Verse]:
        return [v for p in self.all_paragraphs for v in p.verses]

    @property
    def all_footnotes(self) -> list[Footnote]:
        return [fn for v in self.all_verses for fn in v.all_footnotes]

    def footnotes_by_type(self, ftype: FootnoteType) -> list[Footnote]:
        return [fn for fn in self.all_footnotes if fn.type == ftype]

    def __repr__(self) -> str:
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
# ── API Functions ─────────────────────────────────────────────────────────────

def get_chapter_data(version: str, book_id: int, reference: str) -> dict:
    """
    Fetch chapter data from bible.com API.
    
    Args:
        API version:  "3.1" or "3.2"or "3.3"
        book_id: Book ID number
        reference: Chapter reference (e.g., "GEN.1")
    
    Returns:
           JSON response from the API
    """
    url = f"https://nodejs.bible.com/api/bible/chapter/{version}"
    params = {
        "id": book_id,
        "reference": reference
    }
    
    response = requests.get(url, params=params, headers=HEADERS)
    response.raise_for_status()
    return response.json()




# ── HTML Parsing Functions ────────────────────────────────────────────────────

def parse_html_to_chapter_page(html_content: str | Tag, source_url: str = "") -> ChapterPage:
    """
    Convert HTML from Bible API response into a ChapterPage object.
    
    Step-by-step process:
    1. Parse HTML into BeautifulSoup object
    2. Extract metadata (book, chapter, version)
    3. Find all chapter/book containers
    4. Parse sections (heading + paragraphs)
    5. Return populated ChapterPage
    
    Args:
        html_content: HTML string or BeautifulSoup Tag from API response
        source_url: Optional source URL for reference
        
    Returns:
        ChapterPage object with complete hierarchy
    """
    # ─ STEP 1: Ensure html_content is a BeautifulSoup object ────────────────
    # If it's a string, parse it; if it's already a Tag, find the version div
    if isinstance(html_content, str):
        soup = BeautifulSoup(html_content, 'html.parser')
    else:
        soup = html_content
    
    # ─ STEP 2: Extract the version container ────────────────────────────────
    # <div class="version vid1270 iso6393khm" data-iso6393="khm" data-vid="1270">
    version_div = soup.find('div', class_='version')
    if not version_div:
        raise ValueError("No version div found in HTML")
    
    # Extract version ID from data-vid attribute
    version_id = version_div.get('data-vid', 'unknown')
    iso_code = version_div.get('data-iso6393', 'unknown')
    
    # ─ STEP 3: Extract book container ─────────────────────────────────────────
    # <div class="book bkGEN">
    book_div = version_div.find('div', class_='book')
    if not book_div:
        raise ValueError("No book div found in version")
    
    # Extract book name from class (e.g., "bkGEN" → "Genesis")
    book_classes = book_div.get('class', [])
    book_code = next((c[2:] for c in book_classes if c.startswith('bk')), 'Unknown')
    book_name = _usfm_to_book_name(book_code)
    
    # ─ STEP 4: Extract chapter container ──────────────────────────────────────
    # <div class="chapter ch1" data-usfm="GEN.1">
    chapter_div = book_div.find('div', class_='chapter')
    if not chapter_div:
        raise ValueError("No chapter div found in book")
    
    # Extract chapter number from data-usfm (e.g., "GEN.1" → 1)
    usfm_ref = chapter_div.get('data-usfm', 'UNKNOWN.0')
    chapter_num = int(usfm_ref.split('.')[-1])
    
    # ─ STEP 5: Parse all paragraphs and sections ──────────────────────────────
    # Group paragraphs into sections by headings
    sections = _parse_sections(chapter_div)
    
    # ─ STEP 6: Create and return ChapterPage ────────────────────────────────
    chapter_page = ChapterPage(
        book=book_name,
        chapter=chapter_num,
        version=version_id,
        title=f"{book_name} Chapter {chapter_num}",
        source_url=source_url,
        sections=sections
    )
    
    return chapter_page


def _usfm_to_book_name(code: str) -> str:
    """
    Convert USFM book code (e.g., 'GEN') to full book name.
    """
    book_map = {
        'GEN': 'Genesis', 'EXO': 'Exodus', 'LEV': 'Leviticus', 'NUM': 'Numbers',
        'DEU': 'Deuteronomy', 'JOS': 'Joshua', 'JDG': 'Judges', 'RUT': 'Ruth',
        'SA1': '1 Samuel', 'SA2': '2 Samuel', 'KI1': '1 Kings', 'KI2': '2 Kings',
        'CH1': '1 Chronicles', 'CH2': '2 Chronicles', 'EZR': 'Ezra', 'NEH': 'Nehemiah',
        'EST': 'Esther', 'JOB': 'Job', 'PSA': 'Psalms', 'PRO': 'Proverbs',
        'ECC': 'Ecclesiastes', 'SNG': 'Song of Songs', 'ISA': 'Isaiah', 'JER': 'Jeremiah',
        'LAM': 'Lamentations', 'EZK': 'Ezekiel', 'DAN': 'Daniel', 'HOS': 'Hosea',
        'JOL': 'Joel', 'AMO': 'Amos', 'OBA': 'Obadiah', 'JON': 'Jonah',
        'MIC': 'Micah', 'NAM': 'Nahum', 'HAB': 'Habakkuk', 'ZEP': 'Zephaniah',
        'HAG': 'Haggai', 'ZEC': 'Zechariah', 'MAL': 'Malachi',
        'MAT': 'Matthew', 'MRK': 'Mark', 'LUK': 'Luke', 'JHN': 'John',
        'ACT': 'Acts', 'ROM': 'Romans', 'CO1': '1 Corinthians', 'CO2': '2 Corinthians',
        'GAL': 'Galatians', 'EPH': 'Ephesians', 'PHP': 'Philippians', 'COL': 'Colossians',
        'TH1': '1 Thessalonians', 'TH2': '2 Thessalonians', 'TI1': '1 Timothy',
        'TI2': '2 Timothy', 'TIT': 'Titus', 'PHM': 'Philemon', 'HEB': 'Hebrews',
        'JAS': 'James', 'PE1': '1 Peter', 'PE2': '2 Peter', 'JO1': '1 John',
        'JO2': '2 John', 'JO3': '3 John', 'JUD': 'Jude', 'REV': 'Revelation',
    }
    return book_map.get(code, code)


def _parse_sections(chapter_div: Tag) -> list[Section]:
    """
    Parse all sections from a chapter div.
    
    A section is: optional heading + one or more paragraphs
    
    HTML structure:
        <div class="chapter">
            <div class="label">1</div>
            <div class="p">...</div>  ← first paragraph
            <div class="p">...</div>  ← second paragraph
        </div>
    
    Returns:
        List of Section objects containing all paragraphs
    """
    sections = []
    
    # Find all paragraph divs
    p_divs = chapter_div.find_all('div', class_='p', recursive=False)
    
    for p_div in p_divs:
        # Parse this paragraph
        paragraph = _parse_paragraph(p_div)
        
        # Create a section for this paragraph (no heading in this HTML structure)
        section = Section(
            heading=None,
            heading_footnotes=[],
            paragraphs=[paragraph]
        )
        sections.append(section)
    
    return sections


def _parse_paragraph(p_div: Tag) -> Paragraph:
    """
    Parse one <div class="p"> into a Paragraph with verses.
    
    HTML structure:
        <div class="p">
            <span class="verse v1" data-usfm="GEN.1.1">
                <span class="label">1</span>
                <span class="content">កាល​ដើម...</span>
            </span>
            <span class="verse v2" data-usfm="GEN.1.2">
                ...
            </span>
        </div>
    
    Returns:
        Paragraph object containing ordered Verse objects
    """
    verses = []
    
    # Find all verse spans (direct children only)
    verse_spans = p_div.find_all('span', class_='verse', recursive=False)
    
    for verse_span in verse_spans:
        verse = _parse_verse(verse_span)
        verses.append(verse)
    
    return Paragraph(verses=verses)


def _parse_verse(verse_span: Tag) -> Verse:
    """
    Parse one <span class="verse"> into a Verse with chunks.
    
    HTML structure:
        <span class="verse v1" data-usfm="GEN.1.1">
            <span class="label">1</span>                    ← verse number
            <span class="content">កាល​ដើម...</span>      ← verse text
        </span>
    
    Steps:
    1. Extract verse number from label span
    2. Extract text content from content span
    3. Create Chunk(s) from text (handling footnotes if present)
    4. Return Verse
    
    Returns:
        Verse object with one or more Chunks
    """
    # ─ Extract verse number ─────────────────────────────────────────────────
    label_span = verse_span.find('span', class_='label')
    verse_number = None
    if label_span:
        try:
            verse_number = int(label_span.get_text(strip=True))
        except (ValueError, TypeError):
            verse_number = None
    
    # ─ Extract verse text content ───────────────────────────────────────────
    content_span = verse_span.find('span', class_='content')
    verse_text = ""
    if content_span:
        verse_text = content_span.get_text(strip=True)
    
    # ─ Create Chunk from text ───────────────────────────────────────────────
    # For now, create a single chunk per verse (no inline footnote markers)
    chunks = []
    if verse_text:
        chunk = Chunk(text=verse_text, footnotes=[])
        chunks.append(chunk)
    
    # ─ Create and return Verse ──────────────────────────────────────────────
    return Verse(number=verse_number, chunks=chunks)


def load_html_file_to_chapter_page(file_path: str) -> ChapterPage:
    """
    Load an HTML file and convert it to ChapterPage.
    
    Args:
        file_path: Path to HTML file (e.g., "output_GEN.1_1270.html")
        
    Returns:
        ChapterPage object
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    chapter_page = parse_html_to_chapter_page(html_content, source_url=file_path)
    return chapter_page


# ── Main Execution ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    # ═══════════════════════════════════════════════════════════════════════════
    # EXAMPLE 1: Load HTML file and parse it
    # ═══════════════════════════════════════════════════════════════════════════
    
    html_file = "output_លោកុ‌ប្បត្តិ 1_1270.html"
    
    try:
        print(f"📖 Loading HTML file: {html_file}")
        chapter_page = load_html_file_to_chapter_page(html_file)
        
        print(f"\n✅ Successfully parsed HTML into ChapterPage:")
        print(f"   {chapter_page}")
        
        # ─ Print structure summary ──────────────────────────────────────────
        print(f"\n📊 STRUCTURE SUMMARY")
        print(f"   ├─ Book: {chapter_page.book}")
        print(f"   ├─ Chapter: {chapter_page.chapter}")
        print(f"   ├─ Version: {chapter_page.version}")
        print(f"   ├─ Sections: {len(chapter_page.sections)}")
        print(f"   ├─ Paragraphs: {len(chapter_page.all_paragraphs)}")
        print(f"   ├─ Verses: {len(chapter_page.all_verses)}")
        print(f"   └─ Footnotes: {len(chapter_page.all_footnotes)}")
        
        # ─ Print first 3 verses ────────────────────────────────────────────
        print(f"\n📝 FIRST 3 VERSES:")
        for verse in chapter_page.all_verses[:3]:
            text = verse.plain_text[:80]
            print(f"   Verse {verse.number}: {text}...")
    
    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e}")
    except ValueError as e:
        print(f"❌ Error: Parsing failed - {e}")






  
   
   
    


