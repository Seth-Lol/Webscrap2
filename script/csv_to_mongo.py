# csv_to_mongo.py
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
    import_csv(
        filepath    = "debug_GEN_1_107.csv",   # your CSV file
        edition_id  = "edition_net_107",
        book        = "GEN",
        chapter_num = 1
    )
