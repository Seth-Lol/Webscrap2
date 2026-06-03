# csv_to_mongo.py
import sys
from pathlib import Path

# Add parent directory to path to import bible_db
sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
from bible_db.connection import get_db
from bible_db.repository import ChapterRepo
from bible_db.models import Chapter, Verse, ContentNode, NodeType

import re

def extract_verse_number(tag: str) -> int:
    match = re.search(r"'v(\d+)'", tag)
    if match:
        return int(match.group(1))
    return 0

def import_csv(filepath: str, edition_id: str, book: str, chapter_num: int):
    db = get_db()
    repo = ChapterRepo(db)
    verses = []

    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # only rows that are actual verse content
            if "verse" not in row["tag"]:
                continue
            verse_num = extract_verse_number(row["tag"])
            verses.append(Verse(
                verseId=f"{book.lower()}_{chapter_num}_{verse_num}",
                order=verse_num,
                reference=f"{book} {chapter_num}:{verse_num}",
                canonicalRef=f"{book}.{chapter_num}.{verse_num}",
                root=ContentNode(type=NodeType.TEXT, text=row["text"]),
                plainText=row["text"],
            ))

    chapter = Chapter(
        _id=f"ch_{edition_id}_{book.lower()}_{chapter_num}",
        editionId=edition_id,
        bookId=f"book_{edition_id}_{book.lower()}",
        order=chapter_num,
        reference=f"{book} {chapter_num}",
        canonicalRef=f"{book}.{chapter_num}",
        totalVerses=len(verses),
        verses=verses,
    )
    repo.upsert(chapter)
    print(f"Inserted {len(verses)} verses for {book} {chapter_num}")

if __name__ == "__main__":
    from pathlib import Path

    DATA_DIR    = Path("/Users/seth/VS/Webscrap2/data/net_bible_scrape_20260513_172359")          # folder containing the CSVs
    EDITION_ID  = "edition_net_107"

    BIBLE_BOOKS = {
        "GEN": 50, "EXO": 40, "LEV": 27, "NUM": 36, "DEU": 34,
        "JOS": 24, "JDG": 21, "RUT": 4,  "1SA": 31, "2SA": 24,
        "1KI": 22, "2KI": 25, "1CH": 29, "2CH": 36, "EZR": 10,
        "NEH": 13, "EST": 10, "JOB": 42, "PSA": 150, "PRO": 31,
        "ECC": 12, "SNG": 8,  "ISA": 66, "JER": 52, "LAM": 5,
        "EZK": 48, "DAN": 12, "HOS": 14, "JOL": 3,  "AMO": 9,
        "OBA": 1,  "JON": 4,  "MIC": 7,  "NAM": 3,  "HAB": 3,
        "ZEP": 3,  "HAG": 2,  "ZEC": 14, "MAL": 4,
        "MAT": 28, "MRK": 16, "LUK": 24, "JHN": 21, "ACT": 28,
        "ROM": 16, "1CO": 16, "2CO": 13, "GAL": 6,  "EPH": 6,
        "PHP": 4,  "COL": 4,  "1TH": 5,  "2TH": 3,  "1TI": 6,
        "2TI": 4,  "TIT": 3,  "PHM": 1,  "HEB": 13, "JAS": 5,
        "1PE": 5,  "2PE": 3,  "1JN": 5,  "2JN": 1,  "3JN": 1,
        "JUD": 1,  "REV": 22,
    }

    for book, total_chapters in BIBLE_BOOKS.items():
        for chapter_num in range(1, total_chapters + 1):
            filepath = DATA_DIR / f"{book}_{chapter_num:03d}.csv"  # e.g. 1CH_001.csv
            if not filepath.exists():
                print(f"  SKIP {filepath.name} — not found")
                continue
            try:
                import_csv(
                    filepath    = str(filepath),
                    edition_id  = EDITION_ID,
                    book        = book,
                    chapter_num = chapter_num,
                )
            except Exception as e:
                print(f"  ERROR {filepath.name}: {e}")