"""
NET Bible Full Scraper - Scrapes all 66 books with all chapters
Saves each chapter to individual CSV files in ./net_bible_data/
"""

import re
import os
import sys
import time
import requests
import csv
from bs4 import BeautifulSoup, Tag
from pathlib import Path

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# All 66 Bible books with chapter counts
BIBLE_BOOKS = {
    "GEN": 50, "EXO": 40, "LEV": 27, "NUM": 36, "DEU": 34,
    "JOS": 24, "JDG": 21, "RUT": 4, "1SA": 31, "2SA": 24,
    "1KI": 22, "2KI": 25, "1CH": 29, "2CH": 36, "EZR": 10,
    "NEH": 13, "EST": 10, "JOB": 42, "PSA": 150, "PRO": 31,
    "ECC": 12, "SNG": 8, "ISA": 66, "JER": 52, "LAM": 5,
    "EZK": 48, "DAN": 12, "HOS": 14, "JOL": 3, "AMO": 9,
    "OBA": 1, "JON": 4, "MIC": 7, "NAH": 3, "HAB": 3,
    "ZEP": 3, "HAG": 2, "ZEC": 14, "MAL": 4, "MAT": 28,
    "MRK": 16, "LUK": 24, "JHN": 21, "ACT": 28, "ROM": 16,
    "1CO": 16, "2CO": 13, "GAL": 6, "EPH": 6, "PHP": 4,
    "COL": 4, "1TH": 5, "2TH": 3, "1TI": 6, "2TI": 4,
    "TIT": 3, "PHM": 1, "HEB": 13, "JAS": 5, "1PE": 5,
    "2PE": 3, "1JN": 5, "2JN": 1, "3JN": 1, "JUD": 1,
    "REV": 22,
}


def get_chapter_data(version: str, bible_id: int, reference: str) -> dict:
    """Fetch chapter data from bible.com API"""
    url = "https://nodejs.bible.com/api/bible/chapter/3.3"
    params = {"id": bible_id, "reference": reference}
    response = requests.get(url, params=params, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.json()


def extract_verse_content(chapter_tag: Tag) -> list[list]:
    """Extract all content from chapter tag into rows"""
    rows = [["id", "tag", "text"]]
    row_id = 0
    
    if not chapter_tag:
        return rows

    # Flatten all text content from the chapter
    for tag in chapter_tag.find_all(True):  # Find all descendants
        tag_classes = tag.attrs.get('class', [])
        text = tag.get_text(strip=True)
        
        if text:  # Only add non-empty content
            class_str = ' '.join(tag_classes) if tag_classes else tag.name
            rows.append([row_id, class_str, text])
            row_id += 1
    
    return rows


def save_chapter_csv(output_path: str, rows: list[list]) -> None:
    """Write rows to CSV file"""
    # Filter out empty rows
    rows_to_write = [row for row in rows if len(row) >= 3 and row[2].strip()]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(rows_to_write)


def scrape_all_chapters(bible_id: int = 107, output_dir: str = "./net_bible_data"):
    """
    Scrape all chapters from all books.
    
    Args:
        bible_id: 107 for NET Bible
        output_dir: Directory to save CSV files
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    total_books = len(BIBLE_BOOKS)
    total_chapters = sum(BIBLE_BOOKS.values())
    
    print(f"\n{'='*70}")
    print(f"Scraping NET Bible - {total_books} books, {total_chapters} chapters")
    print(f"Output directory: {output_path.absolute()}")
    print(f"{'='*70}\n")
    
    chapters_scraped = 0
    chapters_failed = 0
    start_time = time.time()
    
    for book_idx, (book_code, chapter_count) in enumerate(BIBLE_BOOKS.items(), 1):
        print(f"[{book_idx:2d}/{total_books}] {book_code:<5} ", end="", flush=True)
        
        for chapter_num in range(1, chapter_count + 1):
            reference = f"{book_code}.{chapter_num}"
            
            try:
                response = get_chapter_data("3.3", bible_id, reference)
                
                # Parse HTML content
                html_content = response.get("content", "")
                soup = BeautifulSoup(html_content, "lxml")
                chapter_tag = soup.find(class_="chapter")
                
                # Extract and save data
                rows = extract_verse_content(chapter_tag)
                output_file = output_path / f"data_{book_code}_{chapter_num}_{bible_id}.csv"
                save_chapter_csv(str(output_file), rows)
                
                chapters_scraped += 1
                print(".", end="", flush=True)
                
                # Be respectful to API
                time.sleep(0.3)
                
            except requests.exceptions.RequestException as e:
                chapters_failed += 1
                print("E", end="", flush=True)
                time.sleep(1)
            except Exception as e:
                chapters_failed += 1
                print("F", end="", flush=True)
        
        print()  # New line after each book
    
    elapsed = time.time() - start_time
    print(f"\n{'='*70}")
    print(f"✓ Scraped: {chapters_scraped} chapters")
    print(f"✗ Failed:  {chapters_failed} chapters")
    print(f"⏱ Time:    {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print(f"📁 Saved to: {output_path.absolute()}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    # NET Bible ID is 107
    scrape_all_chapters(bible_id=107, output_dir="./net_bible_data")
