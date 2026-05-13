from __future__ import annotations

import re
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





if __name__ == "__main__":
    import sys

   
    bookChapter = "GEN.1"
    # bookChapter = "GEN.3"
    # bookChapter = "PSA.119"
    # bookChapter = "PSA.77"
    # bookChapter = "ROM.1"
    # bookChapter = "ACT.20"
    # bookChapter = "MRK.1"

    bibleId = 107 # NET Bible
    # bibleId = 2287  #GKHB
    # # bibleId = 1270  #KOV
    # # bibleId = 1930 #  NVT
    # bibleId = 1608 # ARA


    response = get_chapter_data("3.3", bibleId, bookChapter)

    chapterCode = response['reference']['usfm'][0]
    title  = response['reference']['human']
    book, chapter = chapterCode.split(".")
    version_id = response['reference']['version_id']
    copyright = response['copyright']['html']
    soup = BeautifulSoup(copyright, "html.parser")
    # This removes all tags and returns just the text
    clean_text = soup.get_text()
    copyrightText = response['copyright']['text']
    

    textHtml = BeautifulSoup(response['content'], 'lxml')

   
    chapter_tag: Tag | None = textHtml.find(class_="chapter")


    if chapter_tag:
        fileName = f"debug_{book}_{chapter}_{bibleId}.txt"
        rows.append([id, bookChapter,version_id])
        id+=1
        with open(fileName, "w", encoding="utf-8") as _f:
            sys.stdout = _f
               
            tags_data = extract_tags_from_chapter(chapter_tag)
            write_rows_to_csv(fileName.replace(".txt", ".csv"))
        
    else:
        print("Chapter tag not found")

    # Restore stdout
    sys.stdout = sys.__stdout__  
                   

# usfm tags_
# \p	Normal paragraph	Indented
# \m	Paragraph (no indent)	❌ No indent
# \q	Poetry / quote	Styled (indent varies)
# .verse
# .content
# .note
# tn/sn/tc
# sc small caps?
               