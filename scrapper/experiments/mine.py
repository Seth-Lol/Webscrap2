from __future__ import annotations

import re
import os
from dataclasses import dataclass, field
from typing import Literal
import sys
from unittest import case
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import csv

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

paragraphNumber = 0  # Define globally before use
q1Number = 0
q2Number = 0
q3Number = 0
mNumber = 0
rows = [["id","tag","text"]]
ids = [str]
tags = [str]
texts = [str]
id = 0

@dataclass
class TagInfo:
    """Data structure to store tag information"""
    tag_type: str  # Tag name (e.g., 's1', 'p', 'verse')
    text: str  # Text content of the tag
    classes: list[str]  # CSS classes
    tag_obj: Tag  # Original BeautifulSoup Tag object for further processing

# import csv

# rows = [
#     ["id", "note"],
#     [1, "Line one\nLine two"],  # contains newline
# ]

# with open("out.csv", "w", newline="", encoding="utf-8") as f:
#     writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
#     writer.writerows(rows)
# val = "new value"
# row = [1, "Line one\nLine two"]
# row.append(val)
# Multiple variables:
# a, b, c = 2, "Another\nLine", "tag1"
# rows.append([a, b, c])

# Building rows in a loop from variables (e.g., from lists):

# ids = [1,2,3]
# notes = ["A\nB","C\nD","E\nF"]
# tags = ["x","y","z"]

# rows = [["id","note","tag"]]
# for i, n, t in zip(ids, notes, tags):
#     rows.append([i, n, t])


# with open("out.csv", "w", newline="", encoding="utf-8") as f:
#     writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
#     writer.writerows(rows)


def write_rows_to_csv(fileName: str) -> None:
#    for id, tag, text in zip(ids, tags, texts):
#     rows.append([id, tag, text])
    """Write rows of data to a CSV file with proper handling of newlines and special characters."""
    # with open(filename, "w", newline="", encoding="utf-8") as f:

    # remove all rows that text is empty or just whitespace
    rows_to_write = [row for row in rows if isinstance(row[2], str) and row[2].strip()]
    
    with open(fileName, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f,  dialect=csv.excel, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(rows_to_write)




def extract_tags_from_chapter(chapter_tag: Tag) -> list[TagInfo]:
    """
    Extract all meaningful tags from the chapter tag and store in TagInfo objects.
    
    Args:
        chapter_tag: The BeautifulSoup Tag object representing the chapter
    
    Returns:
        List of TagInfo objects containing tag information
    """
    tags_list: list[TagInfo] = []
    tag_classes = []  # Initialize  tag_classes 
    child_classes = []  # Initialize child_classes 
    nephew_classes = []  # Initialize nephew_classes 
    classes = [] # Initialize classes
    global id
    for tag in chapter_tag:

        if isinstance(tag, Tag):
            tag_classes = []
            tag_classes = tag.attrs.get('class', [])
            # if tag.attrs.get('class', []) = 'p' then add an integer to the tag_classes list to indicate the paragraph number, and increment the paragraph number for the next paragraph tag
            match tag.attrs.get(['class'][0])[0]:  
                case 'p': 
            # if tag.attrs.get('class', []) == ['p']:
                    global paragraphNumber
                    paragraphNumber += 1
                    if 'p' in tag_classes:
                        tag_classes[tag_classes.index('p')] = f"p{paragraphNumber}"
                case 'm':
                    global mNumber
                    mNumber += 1
                    if 'm' in tag_classes:  
                        tag_classes[tag_classes.index('m')] = f"m{mNumber}" 
                case 'q1':
                    global q1Number
                    q1Number += 1
                    if 'q1' in tag_classes:
                        tag_classes[tag_classes.index('q1')] = f"q1_{q1Number}"  
                case 'q2':
                    global q2Number
                    q2Number += 1
                    if 'q2' in tag_classes:
                        tag_classes[tag_classes.index('q2')] = f"q2_{q2Number}"  
                case 'q3':
                    global q3Number
                    q3Number += 1
                    if 'q3' in tag_classes:
                        tag_classes[tag_classes.index('q3')] = f"q3_{q3Number}"  
                case _:
                    pass

            # check if tag has children, if it does, iterate through the children and print their text content, otherwise print the tag's text content
            for child in tag.children:
                child_classes = []
                
                if isinstance(child, Tag):
                    child_classes = child.attrs.get('class', []) # need to check if it is a note  child_classes = ['note', 'f']
                    nephew_classes = [] 
                    # check if child has children, if it does, iterate through the children and print their text content, otherwise print the child's text content
                    for nephew in child.children:
                        if isinstance(nephew, Tag):
                            nephew_classes = nephew.attrs.get('class', [])  # need to check if it is a note  nephew_classes = ['note', 'f'] and ['body']
                            classes = tag_classes + child_classes + nephew_classes
                            #check if classes contains 'note' and 'f', if it does, need split if footenote
                            if {'note', 'f'}.issubset(classes):

                                _BOUNDARY = re.compile(
                                    r'(?:'
                                    r' # '                             # Type A: explicit " # " separator
                                    r'|'
                                    r'(?<=[.!?"\u201d\u2019\])])\s*'  # Type B: after punctuation (incl. curly quotes)
                                    r')'
                                    r'(tn|sn|tc|map)'                  # capture the prefix
                                    r'(?= )'                           # followed by a space
                                )

                                result = _BOUNDARY.sub(r'\n\1', nephew.get_text(strip=True))
                                footnotes = result.splitlines()
                                strTemp = ''''''
                                for i, footenote in enumerate(footnotes):
                                    if footenote.startswith(('#')):
                                            footenote = footenote[1:].strip()  # Remove the leading '#' and any extra whitespace

                                    if i < len(footnotes) - 1:
                                        strTemp += footenote + '\n' 
                                    else:
                                        strTemp += footenote
                                print( str(classes)  + "\t" + strTemp)
                                # global id
                                rows.append([id, str(classes), strTemp])
                                id+=1

                            else: 
                                # if isinstance(nephew, NavigableString) and nephew.strip():
                                    print( str(classes)  + "\t" + nephew.get_text(strip=True))      # if classes = ['p1', 'verse', 'v1', 'note', 'f'] nephew.get_text(strip=True) is a footnote content
                                                                                                    # if classes = ['s1', 'note', 'f', 'body'] nephew.get_text(strip=True) is footnote content
                                    # global id
                                    rows.append([id, str(classes), nephew.get_text(strip=True)])
                                    id+=1
                        else:
                            # print only if nephew is not empyt and not just whitespace
                            # if isinstance(nephew, NavigableString) and nephew.strip():
                                classes = tag_classes + child_classes 
                                print(str(classes)  + "\t" + str(nephew)) # print 's', 'headings'
                                # global id
                                rows.append([id, str(classes), nephew.get_text(strip=True)])
                                id+=1
                else:
                    # print only if child is not empyt and not just whitespace
                    # if isinstance(child, NavigableString) and child.strip():
                        classes = tag_classes 
                        print(str(classes)  + "\t" + str(child))
                        # global id
                        rows.append([id, str(classes), str(child)])
                        id+=1

        else:
            # Handle non-Tag content if necessary (e.g., NavigableString)
            # print(tag)
            pass
        tag_classes = []  # Reset tag_classes for the next tag
        child_classes = []  # Reset child_classes for the next tag
        nephew_classes = []  # Reset nephew_classes for the next tag
        classes = []  # Reset classes for the next tag
    
    return tags_list


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


def get_all_books(bible_id: int) -> list:
    """
    Fetch all books available in a specific Bible translation.
    
    Args:
        bible_id: The Bible ID (e.g., 107 for NET Bible)
    
    Returns:
        List of books with their metadata
    """
    url = f"https://nodejs.bible.com/api/bible/{bible_id}/books"
    
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def get_book_chapters(bible_id: int, book_id: str) -> list:
    """
    Fetch all chapters available for a specific book.
    
    Args:
        bible_id: The Bible ID (e.g., 107 for NET Bible)
        book_id: The book ID (e.g., "GEN", "ROM")
    
    Returns:
        List of chapters for the book
    """
    url = f"https://nodejs.bible.com/api/bible/{bible_id}/books/{book_id}/chapters"
    
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def reset_global_counters() -> None:
    """Reset all global counters for a new chapter."""
    global paragraphNumber, q1Number, q2Number, q3Number, mNumber, rows, id
    paragraphNumber = 0
    q1Number = 0
    q2Number = 0
    q3Number = 0
    mNumber = 0
    rows = [["id", "tag", "text"]]  # Reset rows with header
    id = 0


# Add this near the top of your file
BIBLE_BOOKS = {
    # Old Testament
    "GEN": 50, "EXO": 40, "LEV": 27, "NUM": 36, "DEU": 34,
    "JOS": 24, "JDG": 21, "RUT": 4,  "1SA": 31, "2SA": 24,
    "1KI": 22, "2KI": 25, "1CH": 29, "2CH": 36, "EZR": 10,
    "NEH": 13, "EST": 10, "JOB": 42, "PSA": 150,"PRO": 31,
    "ECC": 12, "SNG": 8,  "ISA": 66, "JER": 52, "LAM": 5,
    "EZK": 48, "DAN": 12, "HOS": 14, "JOL": 3,  "AMO": 9,
    "OBA": 1,  "JON": 4,  "MIC": 7,  "NAM": 3,  "HAB": 3,
    "ZEP": 3,  "HAG": 2,  "ZEC": 14, "MAL": 4,
    # New Testament
    "MAT": 28, "MRK": 16, "LUK": 24, "JHN": 21, "ACT": 28,
    "ROM": 16, "1CO": 16, "2CO": 13, "GAL": 6,  "EPH": 6,
    "PHP": 4,  "COL": 4,  "1TH": 5,  "2TH": 3,  "1TI": 6,
    "2TI": 4,  "TIT": 3,  "PHM": 1,  "HEB": 13, "JAS": 5,
    "1PE": 5,  "2PE": 3,  "1JN": 5,  "2JN": 1,  "3JN": 1,
    "JUD": 1,  "REV": 22,
}


if __name__ == "__main__":
    import os
    from datetime import datetime

    bibleId = 107   # NET Bible
    version = "3.3"

    print("Starting Bible scraping process...")
    print(f"Bible ID: {bibleId}")

    # Create output folder
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("data", f"net_bible_scrape_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output folder: {output_dir}")

    total = 0

    for book_code, total_chapters in BIBLE_BOOKS.items():
        print(f"\nProcessing {book_code} ({total_chapters} chapters)...")

        for chapter_num in range(1, total_chapters + 1):
            try:
                reset_global_counters()

                reference = f"{book_code}.{chapter_num}"
                response  = get_chapter_data(version, bibleId, reference)

                textHtml    = BeautifulSoup(response['content'], 'lxml')
                chapter_tag = textHtml.find(class_="chapter")

                if chapter_tag:
                    csv_filename = os.path.join(
                        output_dir,
                        f"{book_code}_{chapter_num:03d}.csv"
                    )
                    extract_tags_from_chapter(chapter_tag)
                    write_rows_to_csv(csv_filename)
                    total += 1
                    print(f"  ✓ {reference}")
                else:
                    print(f"  ✗ {reference} — chapter tag not found")

            except Exception as e:
                print(f"  ✗ {reference} — error: {e}")
                continue

        print(f"\n{'='*50}")
        print(f"Done! {total} chapters saved to {output_dir}")
        print(f"{'='*50}")
        

# usfm tags_
# \p	Normal paragraph	Indented
# \m	Paragraph (no indent)	❌ No indent
# \q	Poetry / quote	Styled (indent varies)
# .verse
# .content
# .note
# tn/sn/tc
# sc small caps?
               