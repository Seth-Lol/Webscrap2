"""
bible_db/repository.py
──────────────────────
All database read/write operations.
Each method accepts validated Pydantic models and talks to MongoDB.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterator, List, Optional

from pymongo import UpdateOne, ReplaceOne
from pymongo.database import Database
from pymongo.errors import BulkWriteError

from .models import (
    Annotation, Book, Chapter, Edition,
    LexiconEntry, VerseAlignment, WordAlignment,
)

log = logging.getLogger(__name__)

# ── Batch size for bulk writes ────────────────────────────────────────────────
_BATCH = 200


def _batched(items: list, size: int = _BATCH) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ═══════════════════════════════════════════════════════════════════════════════
# EDITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class EditionRepo:
    def __init__(self, db: Database):
        self.col = db.editions

    def upsert(self, edition: Edition) -> str:
        doc = edition.to_doc()
        self.col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        log.info("Upserted edition: %s", doc["_id"])
        return doc["_id"]

    def get(self, edition_id: str) -> Optional[dict]:
        return self.col.find_one({"_id": edition_id})

    def all(self) -> List[dict]:
        return list(self.col.find())


# ═══════════════════════════════════════════════════════════════════════════════
# BOOKS
# ═══════════════════════════════════════════════════════════════════════════════

class BookRepo:
    def __init__(self, db: Database):
        self.col = db.books

    def upsert(self, book: Book) -> str:
        doc = book.to_doc()
        self.col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        log.info("Upserted book: %s", doc["_id"])
        return doc["_id"]

    def bulk_upsert(self, books: List[Book]) -> int:
        if not books:
            return 0
        ops = [
            ReplaceOne({"_id": b.to_doc()["_id"]}, b.to_doc(), upsert=True)
            for b in books
        ]
        result = self.col.bulk_write(ops, ordered=False)
        log.info("Bulk upserted %d books", len(books))
        return result.upserted_count + result.modified_count

    def get_by_edition(self, edition_id: str) -> List[dict]:
        return list(self.col.find({"editionId": edition_id}).sort("order", 1))

    def get(self, book_id: str) -> Optional[dict]:
        return self.col.find_one({"_id": book_id})


# ═══════════════════════════════════════════════════════════════════════════════
# CHAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

class ChapterRepo:
    def __init__(self, db: Database):
        self.col = db.chapters

    def upsert(self, chapter: Chapter) -> str:
        doc = chapter.to_doc()
        self.col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        return doc["_id"]

    def bulk_upsert(self, chapters: List[Chapter]) -> int:
        """
        Insert chapters in batches.
        Returns total number of documents written.
        """
        if not chapters:
            return 0
        written = 0
        for batch in _batched(chapters):
            ops = [
                ReplaceOne({"_id": c.to_doc()["_id"]}, c.to_doc(), upsert=True)
                for c in batch
            ]
            try:
                result = self.col.bulk_write(ops, ordered=False)
                written += result.upserted_count + result.modified_count
            except BulkWriteError as e:
                log.error("Bulk write error (partial): %s", e.details)
                raise
        log.info("Bulk upserted %d chapters", written)
        return written

    # ── Queries ──────────────────────────────────────────────────────────────

    def get(self, edition_id: str, book_id: str, order: int) -> Optional[dict]:
        return self.col.find_one(
            {"editionId": edition_id, "bookId": book_id, "order": order}
        )

    def get_by_canonical(self, canonical_ref: str) -> Optional[dict]:
        """Fetch a chapter by canonical ref (edition-agnostic)."""
        return self.col.find_one({"canonicalRef": canonical_ref})

    def get_toc(self, edition_id: str, book_id: str) -> List[dict]:
        """All chapters of a book, ordered, without verse content (fast TOC)."""
        return list(
            self.col.find(
                {"editionId": edition_id, "bookId": book_id},
                {"verses": 0},
            ).sort("order", 1)
        )

    def get_verse(self, canonical_verse_ref: str) -> Optional[dict]:
        """
        Fetch a single verse by its canonical ref.
        Returns the verse sub-document only.
        e.g. canonical_verse_ref = 'JN.3.16'
        """
        doc = self.col.find_one(
            {"verses.canonicalRef": canonical_verse_ref},
            {"verses.$": 1, "editionId": 1, "bookId": 1},
        )
        if doc and doc.get("verses"):
            return doc["verses"][0]
        return None

    def search_fulltext(
        self,
        query: str,
        edition_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[dict]:
        """Full-text search across plainText fields."""
        filt: dict = {"$text": {"$search": query}}
        if edition_id:
            filt["editionId"] = edition_id
        return list(
            self.col.find(filt, {"score": {"$meta": "textScore"}})
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )

    def search_strongs(
        self,
        strongs_refs: List[str],
        edition_id: Optional[str] = None,
        match_all: bool = True,
    ) -> List[dict]:
        """Find chapters containing one or more Strong's numbers."""
        filt: dict = {}
        if match_all:
            filt["verses.strongsRefs"] = {"$all": strongs_refs}
        else:
            filt["verses.strongsRefs"] = {"$in": strongs_refs}
        if edition_id:
            filt["editionId"] = edition_id
        return list(self.col.find(filt, {"verses.root": 0}))

    def find_cross_references(self, canonical_verse_ref: str) -> List[dict]:
        """All verses that contain this canonical ref as a cross-reference."""
        return list(
            self.col.find(
                {"verses.crossReferences": canonical_verse_ref},
                {"verses.root": 0},
            )
        )


# ═══════════════════════════════════════════════════════════════════════════════
# LEXICON
# ═══════════════════════════════════════════════════════════════════════════════

class LexiconRepo:
    def __init__(self, db: Database):
        self.col = db.lexicon

    def upsert(self, entry: LexiconEntry) -> str:
        doc = entry.to_doc()
        self.col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        return doc["_id"]

    def bulk_upsert(self, entries: List[LexiconEntry]) -> int:
        if not entries:
            return 0
        written = 0
        for batch in _batched(entries):
            ops = [
                ReplaceOne({"_id": e.to_doc()["_id"]}, e.to_doc(), upsert=True)
                for e in batch
            ]
            result = self.col.bulk_write(ops, ordered=False)
            written += result.upserted_count + result.modified_count
        log.info("Bulk upserted %d lexicon entries", written)
        return written

    def get(self, strongs_number: str) -> Optional[dict]:
        return self.col.find_one({"_id": strongs_number})

    def search(self, query: str) -> List[dict]:
        return list(self.col.find({"$text": {"$search": query}}).limit(20))


# ═══════════════════════════════════════════════════════════════════════════════
# VERSE ALIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

class VerseAlignmentRepo:
    def __init__(self, db: Database):
        self.col = db.verseAlignments

    def upsert(self, alignment: VerseAlignment) -> str:
        doc = alignment.to_doc()
        self.col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        return doc["_id"]

    def bulk_upsert(self, alignments: List[VerseAlignment]) -> int:
        if not alignments:
            return 0
        written = 0
        for batch in _batched(alignments):
            ops = [
                ReplaceOne({"_id": a.to_doc()["_id"]}, a.to_doc(), upsert=True)
                for a in batch
            ]
            result = self.col.bulk_write(ops, ordered=False)
            written += result.upserted_count + result.modified_count
        return written

    def get(self, canonical_ref: str) -> Optional[dict]:
        return self.col.find_one({"canonicalRef": canonical_ref})

    def get_parallel(self, canonical_ref: str, edition_ids: List[str]) -> Dict[str, Optional[str]]:
        """
        For a canonical verse ref, return {editionId: verseId} for
        the requested editions. None values mean the verse is absent.
        """
        doc = self.col.find_one({"canonicalRef": canonical_ref})
        if not doc:
            return {}
        editions = doc.get("editions", {})
        return {eid: editions.get(eid) for eid in edition_ids}


# ═══════════════════════════════════════════════════════════════════════════════
# ANNOTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class AnnotationRepo:
    def __init__(self, db: Database):
        self.col = db.annotations

    def insert(self, annotation: Annotation) -> str:
        doc = annotation.to_doc()
        result = self.col.insert_one(doc)
        return str(result.inserted_id)

    def get_for_verse(self, user_id: str, canonical_ref: str) -> List[dict]:
        return list(
            self.col.find({"userId": user_id, "canonicalRef": canonical_ref})
        )

    def get_highlights(self, user_id: str, canonical_ref: str) -> List[dict]:
        return list(
            self.col.find(
                {"userId": user_id, "canonicalRef": canonical_ref, "type": "highlight"}
            )
        )

    def get_by_tag(self, user_id: str, tag: str) -> List[dict]:
        return list(
            self.col.find({"userId": user_id, "tags": tag}).sort("createdAt", -1)
        )

    def search_notes(self, user_id: str, query: str) -> List[dict]:
        return list(
            self.col.find(
                {"userId": user_id, "type": "note", "$text": {"$search": query}}
            ).limit(20)
        )

    def delete(self, annotation_id: str, user_id: str) -> bool:
        from bson import ObjectId
        result = self.col.delete_one(
            {"_id": ObjectId(annotation_id), "userId": user_id}
        )
        return result.deleted_count > 0
