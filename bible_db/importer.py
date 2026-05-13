"""
bible_db/importer.py
────────────────────
High-level importer that converts source Bible data into Pydantic models
and drives bulk insertion via the repository layer.

Supported source formats
────────────────────────
  • OSIS XML        (most scholarly editions: LXX, NA28, WLC)
  • USFM            (most modern translations via open-source repos)
  • Zefania XML     (many free translations)
  • JSON (custom)   (our own format or pre-processed data)

Typical usage
─────────────
  from bible_db.connection import get_db, create_indexes
  from bible_db.importer  import BibleImporter

  db  = get_db("mongodb://localhost:27017", "bible")
  create_indexes(db)

  imp = BibleImporter(db, edition_id="edition_kjv")
  imp.from_json("data/kjv.json")          # custom JSON
  imp.from_osis("data/kjv.osis.xml")      # OSIS XML
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from pymongo.database import Database

from .models import (
    Book, BookCategory, Chapter, ContentNode, Edition,
    Footnote, Mark, MarkType, NodeType, SourceTextType,
    Testament, Verse, VerseAlignment,
)
from .repository import (
    BookRepo, ChapterRepo, EditionRepo, VerseAlignmentRepo,
)

log = logging.getLogger(__name__)

# ── OSIS XML namespaces ───────────────────────────────────────────────────────
_OSIS_NS = {"osis": "http://www.bibletechnologies.net/2003/OSIS/namespace"}

# ── USFM book-code → canonical USFM mapping ──────────────────────────────────
USFM_CODES: Dict[str, str] = {
    "GEN": "GN", "EXO": "EX", "LEV": "LV", "NUM": "NU", "DEU": "DT",
    "JOS": "JS", "JDG": "JG", "RUT": "RT", "1SA": "1S", "2SA": "2S",
    "1KI": "1K", "2KI": "2K", "1CH": "1C", "2CH": "2C", "EZR": "EZ",
    "NEH": "NH", "EST": "ES", "JOB": "JB", "PSA": "PS", "PRO": "PR",
    "ECC": "EC", "SNG": "SS", "ISA": "IS", "JER": "JR", "LAM": "LM",
    "EZK": "EK", "DAN": "DN", "HOS": "HS", "JOL": "JL", "AMO": "AM",
    "OBA": "OB", "JON": "JN", "MIC": "MC", "NAM": "NM", "HAB": "HB",
    "ZEP": "ZP", "HAG": "HG", "ZEC": "ZC", "MAL": "ML",
    "MAT": "MT", "MRK": "MK", "LUK": "LK", "JHN": "JN", "ACT": "AC",
    "ROM": "RO", "1CO": "1C", "2CO": "2C", "GAL": "GL", "EPH": "EP",
    "PHP": "PP", "COL": "CL", "1TH": "1T", "2TH": "2T", "1TI": "1I",
    "2TI": "2I", "TIT": "TT", "PHM": "PM", "HEB": "HB", "JAS": "JS",
    "1PE": "1P", "2PE": "2P", "1JN": "1J", "2JN": "2J", "3JN": "3J",
    "JUD": "JD", "REV": "RV",
}

BOOK_TESTAMENT: Dict[str, str] = {
    **{k: "OT" for k in list(USFM_CODES.keys())[:39]},
    **{k: "NT" for k in list(USFM_CODES.keys())[39:]},
}

BOOK_CATEGORY: Dict[str, BookCategory] = {
    "GEN": BookCategory.LAW, "EXO": BookCategory.LAW,
    "LEV": BookCategory.LAW, "NUM": BookCategory.LAW, "DEU": BookCategory.LAW,
    "PSA": BookCategory.POETRY, "PRO": BookCategory.POETRY,
    "JOB": BookCategory.POETRY, "ECC": BookCategory.POETRY, "SNG": BookCategory.POETRY,
    "MAT": BookCategory.GOSPEL, "MRK": BookCategory.GOSPEL,
    "LUK": BookCategory.GOSPEL, "JHN": BookCategory.GOSPEL,
    "ACT": BookCategory.ACTS,
    "REV": BookCategory.APOCALYPTIC,
}


def _make_book_id(edition_id: str, usfm: str) -> str:
    return f"book_{edition_id}_{usfm.lower()}"


def _make_chapter_id(edition_id: str, usfm: str, chapter: int) -> str:
    return f"ch_{edition_id}_{usfm.lower()}_{chapter}"


def _make_verse_id(usfm: str, chapter: int, verse: int) -> str:
    return f"{usfm.lower()}_{chapter}_{verse}"


def _canonical_chapter(usfm: str, chapter: int) -> str:
    code = USFM_CODES.get(usfm, usfm[:2].upper())
    return f"{code}.{chapter}"


def _canonical_verse(usfm: str, chapter: int, verse: int) -> str:
    return f"{_canonical_chapter(usfm, chapter)}.{verse}"


def _text_to_node(text: str) -> ContentNode:
    """Wrap a plain string in a minimal text ContentNode."""
    return ContentNode(type=NodeType.TEXT, text=text)


def _verse_to_node(verse_text: str, verse_num: int) -> ContentNode:
    """Build a verse ContentNode from plain text + verse number."""
    return ContentNode(
        type=NodeType.VERSE,
        children=[
            ContentNode(
                type=NodeType.VERSE_NUM,
                text=str(verse_num),
                marks=[Mark(type=MarkType.SUPERSCRIPT)],
            ),
            ContentNode(type=NodeType.TEXT, text=verse_text),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN IMPORTER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class BibleImporter:
    """
    Orchestrates parsing and bulk-inserting one Bible translation.

    Parameters
    ----------
    db          : pymongo Database handle
    edition_id  : string key used as FK across all documents, e.g. 'edition_kjv'
    batch_size  : chapter documents per bulk_write call
    """

    def __init__(
        self,
        db: Database,
        edition_id: str,
        batch_size: int = 100,
    ):
        self.db         = db
        self.edition_id = edition_id
        self.batch_size = batch_size

        self._editions   = EditionRepo(db)
        self._books      = BookRepo(db)
        self._chapters   = ChapterRepo(db)
        self._alignments = VerseAlignmentRepo(db)

    # ── Public entry points ──────────────────────────────────────────────────

    def from_json(self, path: str | Path) -> None:
        """
        Import from our custom JSON format.

        Expected top-level structure:
        {
          "edition": { ... Edition fields ... },
          "books": [
            {
              "usfmCode": "PSA",
              "name": "Psalms",
              ...
              "chapters": [
                {
                  "order": 1,
                  "verses": [
                    { "order": 1, "text": "Blessed is the man..." },
                    ...
                  ]
                }
              ]
            }
          ]
        }
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self._insert_edition(data["edition"])
        self._process_json_books(data["books"])

    def from_osis(self, path: str | Path) -> None:
        """Import from OSIS XML format."""
        tree = ET.parse(path)
        root = tree.getroot()
        self._process_osis(root)

    def from_zefania(self, path: str | Path) -> None:
        """Import from Zefania XML format."""
        tree = ET.parse(path)
        root = tree.getroot()
        self._process_zefania(root)

    def upsert_edition(self, edition: Edition) -> None:
        self._editions.upsert(edition)

    # ── JSON format ──────────────────────────────────────────────────────────

    def _insert_edition(self, data: dict) -> None:
        data.setdefault("_id", self.edition_id)
        edition = Edition(**data)
        self._editions.upsert(edition)
        log.info("Edition inserted: %s", edition.id)

    def _process_json_books(self, books_data: List[dict]) -> None:
        book_models: List[Book] = []
        all_chapters: List[Chapter] = []

        for b_order, book_data in enumerate(books_data, start=1):
            usfm = book_data["usfmCode"]
            book_id = _make_book_id(self.edition_id, usfm)
            chapters_data = book_data.pop("chapters", [])

            chapters, total_verses = self._build_json_chapters(
                book_id, usfm, chapters_data
            )
            all_chapters.extend(chapters)

            book_models.append(
                Book(
                    _id=book_id,
                    editionId=self.edition_id,
                    testament=Testament(
                        BOOK_TESTAMENT.get(usfm, "OT")
                    ),
                    order=book_data.get("order", b_order),
                    name=book_data["name"],
                    abbreviation=book_data.get("abbreviation", usfm[:3]),
                    usfmCode=usfm,
                    category=BOOK_CATEGORY.get(usfm),
                    totalChapters=len(chapters),
                    totalVerses=total_verses,
                )
            )

        self._books.bulk_upsert(book_models)
        log.info("Inserted %d books", len(book_models))

        self._bulk_insert_chapters(all_chapters)
        self._build_verse_alignments(all_chapters)

    def _build_json_chapters(
        self, book_id: str, usfm: str, chapters_data: List[dict]
    ) -> tuple[List[Chapter], int]:
        chapters: List[Chapter] = []
        total_verses = 0

        for ch_data in chapters_data:
            ch_order = ch_data["order"]
            verses: List[Verse] = []

            for v_data in ch_data.get("verses", []):
                v_order = v_data["order"]
                text    = v_data.get("text", "")
                strongs = v_data.get("strongsRefs", [])
                xrefs   = v_data.get("crossReferences", [])
                footnotes = [
                    Footnote(**f) for f in v_data.get("footnotes", [])
                ]

                verses.append(
                    Verse(
                        verseId=_make_verse_id(usfm, ch_order, v_order),
                        order=v_order,
                        reference=f"{usfm} {ch_order}:{v_order}",
                        canonicalRef=_canonical_verse(usfm, ch_order, v_order),
                        root=_verse_to_node(text, v_order),
                        plainText=text,
                        strongsRefs=strongs,
                        crossReferences=xrefs,
                        footnotes=footnotes,
                    )
                )

            total_verses += len(verses)
            chapters.append(
                Chapter(
                    _id=_make_chapter_id(self.edition_id, usfm, ch_order),
                    editionId=self.edition_id,
                    bookId=book_id,
                    order=ch_order,
                    reference=f"{usfm} {ch_order}",
                    canonicalRef=_canonical_chapter(usfm, ch_order),
                    totalVerses=len(verses),
                    verses=verses,
                )
            )

        return chapters, total_verses

    # ── OSIS XML format ──────────────────────────────────────────────────────

    def _process_osis(self, root: ET.Element) -> None:
        """Parse OSIS XML and insert into MongoDB."""
        ns = _OSIS_NS
        all_chapters: List[Chapter] = []
        book_models:  List[Book]    = []

        for b_order, book_el in enumerate(
            root.findall(".//osis:div[@type='book']", ns), start=1
        ):
            usfm    = book_el.get("osisID", f"UNK{b_order}").upper()
            book_id = _make_book_id(self.edition_id, usfm)
            chapters: List[Chapter] = []
            total_verses = 0

            for ch_el in book_el.findall(".//osis:chapter", ns):
                ch_id_attr = ch_el.get("osisID", "")
                try:
                    ch_order = int(ch_id_attr.split(".")[-1])
                except ValueError:
                    continue

                verses: List[Verse] = []
                for v_el in ch_el.findall(".//osis:verse", ns):
                    v_id = v_el.get("osisID", "")
                    try:
                        v_order = int(v_id.split(".")[-1])
                    except ValueError:
                        continue

                    text = "".join(v_el.itertext()).strip()
                    if not text:
                        continue

                    verses.append(
                        Verse(
                            verseId=_make_verse_id(usfm, ch_order, v_order),
                            order=v_order,
                            reference=f"{usfm} {ch_order}:{v_order}",
                            canonicalRef=_canonical_verse(usfm, ch_order, v_order),
                            root=_verse_to_node(text, v_order),
                            plainText=text,
                        )
                    )

                if verses:
                    total_verses += len(verses)
                    chapters.append(
                        Chapter(
                            _id=_make_chapter_id(self.edition_id, usfm, ch_order),
                            editionId=self.edition_id,
                            bookId=book_id,
                            order=ch_order,
                            reference=f"{usfm} {ch_order}",
                            canonicalRef=_canonical_chapter(usfm, ch_order),
                            totalVerses=len(verses),
                            verses=verses,
                        )
                    )

            all_chapters.extend(chapters)
            book_models.append(
                Book(
                    _id=book_id,
                    editionId=self.edition_id,
                    testament=Testament(BOOK_TESTAMENT.get(usfm, "OT")),
                    order=b_order,
                    name=usfm,
                    abbreviation=usfm[:3],
                    usfmCode=usfm,
                    category=BOOK_CATEGORY.get(usfm),
                    totalChapters=len(chapters),
                    totalVerses=total_verses,
                )
            )

        self._books.bulk_upsert(book_models)
        self._bulk_insert_chapters(all_chapters)
        self._build_verse_alignments(all_chapters)

    # ── Zefania XML format ───────────────────────────────────────────────────

    def _process_zefania(self, root: ET.Element) -> None:
        """
        Parse Zefania XML.

        Structure:
          <XMLBIBLE>
            <BIBLEBOOK bnumber="1" bname="Genesis" bsname="Gen">
              <CHAPTER cnumber="1">
                <VERS vnumber="1">In the beginning…</VERS>
              </CHAPTER>
            </BIBLEBOOK>
          </XMLBIBLE>
        """
        ZEFANIA_USFM = [
            "GEN","EXO","LEV","NUM","DEU","JOS","JDG","RUT","1SA","2SA",
            "1KI","2KI","1CH","2CH","EZR","NEH","EST","JOB","PSA","PRO",
            "ECC","SNG","ISA","JER","LAM","EZK","DAN","HOS","JOL","AMO",
            "OBA","JON","MIC","NAM","HAB","ZEP","HAG","ZEC","MAL",
            "MAT","MRK","LUK","JHN","ACT","ROM","1CO","2CO","GAL","EPH",
            "PHP","COL","1TH","2TH","1TI","2TI","TIT","PHM","HEB","JAS",
            "1PE","2PE","1JN","2JN","3JN","JUD","REV",
        ]

        all_chapters: List[Chapter] = []
        book_models:  List[Book]    = []

        for book_el in root.findall(".//BIBLEBOOK"):
            b_num = int(book_el.get("bnumber", 0))
            usfm  = ZEFANIA_USFM[b_num - 1] if 1 <= b_num <= len(ZEFANIA_USFM) else f"B{b_num:03d}"
            bname = book_el.get("bname", usfm)
            bsname = book_el.get("bsname", usfm[:3])
            book_id = _make_book_id(self.edition_id, usfm)

            chapters: List[Chapter] = []
            total_verses = 0

            for ch_el in book_el.findall("CHAPTER"):
                ch_order = int(ch_el.get("cnumber", 0))
                verses: List[Verse] = []

                for v_el in ch_el.findall("VERS"):
                    v_order = int(v_el.get("vnumber", 0))
                    text    = (v_el.text or "").strip()
                    if not text:
                        continue
                    verses.append(
                        Verse(
                            verseId=_make_verse_id(usfm, ch_order, v_order),
                            order=v_order,
                            reference=f"{bsname} {ch_order}:{v_order}",
                            canonicalRef=_canonical_verse(usfm, ch_order, v_order),
                            root=_verse_to_node(text, v_order),
                            plainText=text,
                        )
                    )

                if verses:
                    total_verses += len(verses)
                    chapters.append(
                        Chapter(
                            _id=_make_chapter_id(self.edition_id, usfm, ch_order),
                            editionId=self.edition_id,
                            bookId=book_id,
                            order=ch_order,
                            reference=f"{bsname} {ch_order}",
                            canonicalRef=_canonical_chapter(usfm, ch_order),
                            totalVerses=len(verses),
                            verses=verses,
                        )
                    )

            all_chapters.extend(chapters)
            book_models.append(
                Book(
                    _id=book_id,
                    editionId=self.edition_id,
                    testament=Testament(BOOK_TESTAMENT.get(usfm, "OT")),
                    order=b_num,
                    name=bname,
                    abbreviation=bsname,
                    usfmCode=usfm,
                    category=BOOK_CATEGORY.get(usfm),
                    totalChapters=len(chapters),
                    totalVerses=total_verses,
                )
            )

        self._books.bulk_upsert(book_models)
        self._bulk_insert_chapters(all_chapters)
        self._build_verse_alignments(all_chapters)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _bulk_insert_chapters(self, chapters: List[Chapter]) -> None:
        total = len(chapters)
        written = 0
        for i in range(0, total, self.batch_size):
            batch = chapters[i : i + self.batch_size]
            self._chapters.bulk_upsert(batch)
            written += len(batch)
            log.info("  Chapters inserted: %d / %d", written, total)

    def _build_verse_alignments(self, chapters: List[Chapter]) -> None:
        """
        After inserting chapters for one edition, upsert verseAlignment
        documents so the canonical→edition mapping stays current.
        Uses update with $set so other editions are not overwritten.
        """
        log.info("Building verse alignments for %s …", self.edition_id)
        ops = []
        col = self.db.verseAlignments

        for chapter in chapters:
            for verse in chapter.verses:
                key = f"editions.{self.edition_id}"
                ops.append(
                    UpdateOne(
                        {"canonicalRef": verse.canonical_ref},
                        {
                            "$set": {key: verse.verse_id},
                            "$setOnInsert": {
                                "_id": f"align_{verse.canonical_ref}",
                                "canonicalRef": verse.canonical_ref,
                            },
                        },
                        upsert=True,
                    )
                )

        # Flush in batches using pymongo UpdateOne
        from pymongo import UpdateOne as _UO
        batch_size = 500
        for i in range(0, len(ops), batch_size):
            col.bulk_write(ops[i : i + batch_size], ordered=False)

        log.info("Verse alignments updated: %d verses", len(ops))
