# api/main.py
import sys
from pathlib import Path

# Add parent directory to path to import bible_db
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from bible_db.connection import get_db
from bible_db.repository import ChapterRepo

app = FastAPI(title="Bible API")

@app.get("/")
def home():
    return {"message": "Bible API is running ✅"}

@app.get("/verse/{canonical_ref}")
def get_verse(canonical_ref: str):
    """Get one verse.  e.g. /verse/GEN.1.1"""
    db = get_db()
    verse = ChapterRepo(db).get_verse(canonical_ref)
    if not verse:
        raise HTTPException(404, "Verse not found")
    return verse

@app.get("/chapter/{book}/{chapter}")
def get_chapter(book: str, chapter: int, edition: str = "edition_net_107"):
    """Get full chapter.  e.g. /chapter/GEN/1"""
    db = get_db()
    result = ChapterRepo(db).get(
        edition,
        f"book_{edition}_{book.lower()}",
        chapter
    )
    if not result:
        raise HTTPException(404, "Chapter not found")
    return result

@app.get("/search")
def search(q: str, edition: str = "edition_net_107"):
    """Search verses.  e.g. /search?q=beginning"""
    db = get_db()
    results = ChapterRepo(db).search_fulltext(q, edition)
    return {"query": q, "results": results}