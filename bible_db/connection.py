"""
bible_db/connection.py
──────────────────────
MongoDB connection management and index creation for the Bible database.
"""

from __future__ import annotations

import logging
from typing import Optional

from pymongo import ASCENDING, TEXT, MongoClient
from pymongo.database import Database

log = logging.getLogger(__name__)


# ── Singleton connection ──────────────────────────────────────────────────────

_client: Optional[MongoClient] = None
_db: Optional[Database] = None


def get_db(
    uri: str = "mongodb://localhost:27017",
    db_name: str = "bible",
) -> Database:
    """Return (and cache) the MongoDB database handle."""
    global _client, _db
    if _db is None:
        _client = MongoClient(uri, serverSelectionTimeoutMS=5_000)
        _db = _client[db_name]
        log.info("Connected to MongoDB: %s / %s", uri, db_name)
    return _db


def close():
    """Close the MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        log.info("MongoDB connection closed.")


# ── Index creation ────────────────────────────────────────────────────────────

def create_indexes(db: Database) -> None:
    """
    Create all indexes for every collection.
    Safe to call repeatedly — MongoDB is idempotent for existing indexes.
    """
    log.info("Creating indexes …")

    # editions
    db.editions.create_index("abbreviation", unique=True)
    db.editions.create_index("language")

    # books
    db.books.create_index([("editionId", ASCENDING), ("order", ASCENDING)])
    db.books.create_index([("editionId", ASCENDING), ("testament", ASCENDING), ("order", ASCENDING)])
    db.books.create_index([("usfmCode", ASCENDING), ("editionId", ASCENDING)])

    # chapters
    db.chapters.create_index(
        [("editionId", ASCENDING), ("bookId", ASCENDING), ("order", ASCENDING)],
        unique=True,
    )
    db.chapters.create_index("canonicalRef")
    db.chapters.create_index("verses.canonicalRef")
    db.chapters.create_index("verses.strongsRefs")
    db.chapters.create_index("verses.crossReferences")
    db.chapters.create_index([("plainText", TEXT), ("verses.plainText", TEXT)])

    # lexicon
    db.lexicon.create_index("strongsNumber", unique=True)
    db.lexicon.create_index("language")
    db.lexicon.create_index([("lemma", TEXT), ("definition", TEXT)])

    # verseAlignments
    db.verseAlignments.create_index("canonicalRef", unique=True)

    # wordAlignments
    db.wordAlignments.create_index("canonicalRef", unique=True)
    db.wordAlignments.create_index("alignments.strongsRef")

    # annotations
    db.annotations.create_index([("userId", ASCENDING), ("createdAt", ASCENDING)])
    db.annotations.create_index([("userId", ASCENDING), ("canonicalRef", ASCENDING)])
    db.annotations.create_index([("userId", ASCENDING), ("type", ASCENDING)])
    db.annotations.create_index([("userId", ASCENDING), ("tags", ASCENDING)])
    db.annotations.create_index([("groupId", ASCENDING), ("canonicalRef", ASCENDING)])
    db.annotations.create_index("linkedCanonicalRef")
    db.annotations.create_index([("note.plainText", TEXT)])

    # readingProgress
    db.readingProgress.create_index(
        [("userId", ASCENDING), ("editionId", ASCENDING)],
        unique=True,
    )

    log.info("All indexes created.")
