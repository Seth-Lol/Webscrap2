from __future__ import annotations

from dataclasses import asdict
import re
# from dataclasses import dataclass, field
from typing import List, Literal
import sys
from unittest import case
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import csv
import model as model
import json
import re
from pymongo import MongoClient
import os

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")

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



def extract_tags_from_chapter(version_id: int, chapter_tag: Tag, rows: list, lineNumber: int,) -> list[model.Entry]: 
    entries: list[model.Entry] = []
    entry = model.Entry(rowId=0, keyParts=[], value="")

    paragraphNumber = 0  # Define globally before use
    q1Number = 0
    q2Number = 0
    q3Number = 0
    mNumber = 0
    verse_qtt = 0
    
    tag_classes = []  # Initialize  tag_classes 
    child_classes = []  # Initialize child_classes 
    nephew_classes = []  # Initialize nephew_classes 
    classes = [] 

    # handle NET PSALM 119:113 that has a label with the verse number different from the verse number in the verse tag, so I need to update the verse number in the classes to match the verse number in the label, and also update the entry value to match the verse number in the label
    chapter_exception, verse_exception = 0, 0
   
    # BREAKPOINT: Main parser loop. Pause here to inspect each top-level HTML tag in the chapter.
    for tag in chapter_tag:

        if isinstance(tag, Tag):
            tag_classes = []
            tag_classes = tag.attrs.get('class', [])
            # if tag.attrs.get('class', []) = 'p' then add an integer to the tag_classes list to indicate the paragraph number, and increment the paragraph number for the next paragraph tag
            match tag.attrs.get(['class'][0])[0]:  
                case 'p': 
                    paragraphNumber += 1
                    if 'p' in tag_classes:
                        tag_classes[tag_classes.index('p')] = f"p{paragraphNumber}"
                case 'm':
                    mNumber += 1
                    if 'm' in tag_classes:  
                        tag_classes[tag_classes.index('m')] = f"m{mNumber}" 
                case 'q1':
                    q1Number += 1
                    if 'q1' in tag_classes:
                        tag_classes[tag_classes.index('q1')] = f"q1_{q1Number}"  
                case 'q2':
                    q2Number += 1
                    if 'q2' in tag_classes:
                        tag_classes[tag_classes.index('q2')] = f"q2_{q2Number}"  
                case 'q3':
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
                        if isinstance(nephew, Tag) and nephew.get_text(strip=True): # check if nephew is a Tag and not empty or just whitespace
                            nephew_classes = nephew.attrs.get('class', [])  # need to check if it is a note  nephew_classes = ['note', 'f'] and ['body']
                            classes = [lineNumber] + tag_classes + child_classes + nephew_classes
                            entry.rowId = lineNumber
                            entry.keyParts = classes
                            strTemp = nephew.get_text(strip=True)
                            # BREAKPOINT: Footnote branch. Pause here to learn how note text is detected and cleaned.
                            if {'note', 'f'}.issubset(classes):

                                # match version_id:  
                                #     case 107: 
                                        # XXXX if NET bible and the nephew is a footnote, then the nephew text content needs to be split into two lines, the first line is the footnote type (tn/sn/tc/map) and the second line is the footnote text content, and the entry value needs to be updated to the footnote text content only, without the footnote type
                            #check if classes contains 'note' and 'f', if it does, need split if footenote
                        
                                if len(nephew.get_text(strip=True)) > 1:
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
                                        #a linha abaixo da erro em GKHB gen 3.6, pois o footnote n~ao tem as marcacoes do NET bible (tn|sn|tc|map)
                                        
                                        #XXXX Version GKHB PSALMs 119 ver 30 there is a footnote that does not have the prefix tn/sn/tc/map, so it is not split into two lines, but it should be. Need to find a way to split it into two lines without the prefix
                                        # footnote_type, footnote_text = footenote.split(" ", 1)

                                        if i < len(footnotes) - 1:
                                            strTemp += footenote + '\n' 
                                        else:
                                            strTemp += footenote
                                    # case _:
                                    entry.rowId = lineNumber
                                    entry.value = strTemp
                                    entries.append(entry)
                                    entry = model.Entry(rowId=0, keyParts=[], value="")
                                    print( str(classes)  + "\t" + strTemp)
                                    rows.append([lineNumber, str(classes), strTemp])
                                    lineNumber+=1

                            else: #verse
                                # BREAKPOINT: New verse label. Pause here to see when the parser moves to a new verse.
                                if {'verse', 'label'}.issubset(classes):
                                    lineNumber = append_verse_plain_text(entries, rows, lineNumber, verse_qtt)
                                    verse_qtt += 1
                                    verse_exception, chapter_exception = 0, 0
                                # ====================================================================
                                # handle NET PSALM 119:113 that has a label with the verse number different from the verse number in the verse tag, so I need to update the verse number in the classes to match the verse number in the label, and also update the entry value to match the verse number in the label 
                                if re.search(r'\d+:\d+', nephew.get_text(strip=True)):
                                    chapter_exception, verse_exception = map(int, re.search(r'(\d+):(\d+)', nephew.get_text(strip=True).strip()).groups())
                                    classes[4] = 'label'  # Ensure the last element is 'label'
                                    entry.value = str(verse_exception) #nephew.get_text(strip=True)
                                    verse_qtt+=1
                                else:
                                    entry.value = nephew.get_text(strip=True)

                                if verse_exception != 0:
                                    # [702, 'p234', 'verse', 'v110', 'label']	 110
                                    # [719, 'p241', 'verse', 'v112', 'bd']	 119:113
                                    classes[3] = f'v{verse_exception}'     # Update the verse number in classes to match the verse number in the label
                                # ==================================================================== 

                                entry.keyParts = classes  
                                entry.rowId = lineNumber
                                
                                entries.append(entry)
                                
                                classes[0] = lineNumber   
                                print( str(classes)  + "\t" + entry.value)      # if classes = ['p1', 'verse', 'v1', 'note', 'f'] nephew.get_text(strip=True) is a footnote content
                                                                                                # if classes = ['s1', 'note', 'f', 'body'] nephew.get_text(strip=True) is footnote content
                                rows.append([lineNumber, str(classes), entry.value])
                                lineNumber+=1
                                entry = model.Entry(rowId=0, keyParts=[], value="") 
                        else:
                            # s1 and heading
                            # YYYY need to verify if there is any verse before that need to be added as plain_text  
                            lineNumber = append_verse_plain_text(entries, rows, lineNumber, verse_qtt)
                                 
                            if nephew.get_text(strip=True): 
                                classes = [lineNumber] + tag_classes + child_classes
                                entry.rowId = lineNumber
                                entry.keyParts = tag_classes + child_classes 
                                entry.value = nephew.get_text(strip=True)
                                entries.append(entry)  
                                entry = model.Entry(rowId=0, keyParts=[], value="")                            
                                print(str(classes)  + "\t" + str(nephew)) # print 's', 'headings'
                                rows.append([lineNumber, str(classes), nephew.get_text(strip=True)])
                                lineNumber+=1
                else: # simple label without children

                    classes = [lineNumber] + tag_classes 
                    entry.keyParts = tag_classes
                    entry.rowId = lineNumber
                    entry.value = child.get_text(strip=True)
                    entries.append(entry)
                    entry = model.Entry(rowId=0, keyParts=[], value="")
                    print(str(classes)  + "\t" + str(child))
                    
                    rows.append([lineNumber, str(classes), str(child)])
                    lineNumber+=1

        else:
            pass

        tag_classes = []  # Reset tag_classes for the next tag
        child_classes = []  # Reset child_classes for the next tag
        nephew_classes = []  # Reset nephew_classes for the next tag
        classes = []  # Reset classes for the next tag
        entry = model.Entry(rowId=0, keyParts=[], value="")
    #add the last verse plain_text 
  
    verse_text = f'{verse_qtt} ' + get_verse_content(entries, f'v{verse_qtt}')
    plain_text_classes = [lineNumber] + get_verse_key_parts(entries, f'v{verse_qtt}') + ["plain_text"]
    entry.rowId = lineNumber
    entry.keyParts = plain_text_classes
    entry.value = verse_text
    entries.append(entry)
    entry = model.Entry(rowId=0, keyParts=[], value="")
    
    print( str(plain_text_classes)  + "\t" + verse_text)
    rows.append([lineNumber, str(plain_text_classes), verse_text])
    lineNumber+=1

    return entries 
    
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

def load_ot_books_from_json(path: str) -> List:
    ot = {}
    nt = {}  
    """Load books from a JSON file"""
    with open(path + "/old.json") as f:
        ot = json.load(f)
    return ot

def load_nt_books_from_json(path: str) -> List:
    nt = {}  
    """Load books from a JSON file"""
    with open(path + "/new.json") as f:
        nt = json.load(f)
    return nt


def get_translation_by_id(
    translation_id: str,
    db_name: str = "bible",
    collection_name: str = "translation",
) -> dict | None:
    """Fetch a translation document from MongoDB by translationId."""
    client = MongoClient("mongodb://localhost:27017")
    collection = client[db_name][collection_name]
    return collection.find_one({"translationId": translation_id})


def get_book_from_translation(translation: dict | None, book_id: str) -> dict | None:
    """Return a book object from a translation document by bookId or abbreviation."""
    if not translation:
        return None
    return next(
        (
            book
            for book in translation.get("books", [])
            if book.get("bookId") == book_id or book.get("abbreviation") == book_id
        ),
        None,
    )

def get_chapter_from_book(book: dict | None, chapter_number: int) -> dict | None:
    """Return a chapter object from a book object by chapter number."""
    if not book:
        return None
    return next(
        (chapter for chapter in book.get("chapters", []) if chapter.get("chapter") == chapter_number),
        None,
    )

def dict_to_entry(entry: dict) -> model.Entry:
    return model.Entry(
        rowId=entry.get("rowId", 0),
        keyParts=entry.get("keyParts", []),
        value=entry.get("value", ""),
    )

def dict_to_chapter(chapter: dict) -> model.ChapterDoc:
    return model.ChapterDoc(
        chapter=chapter.get("chapter", 0),
        entries=[dict_to_entry(entry) for entry in chapter.get("entries", [])],
    )

def dict_to_book(book: dict) -> model.BookDoc:
    return model.BookDoc(
        bookId=book.get("bookId", ""),
        testament=book.get("testament", ""),
        order=book.get("order", 0),
        title=book.get("title"),
        abbreviation=book.get("abbreviation"),
        chapters=[dict_to_chapter(chapter) for chapter in book.get("chapters", [])],
    )

def dict_to_translation(translation: dict) -> model.TranslationDoc:
    return model.TranslationDoc(
        translationId=translation.get("translationId", ""),
        name=translation.get("name", ""),
        abbreviation=translation.get("abbreviation", ""),
        language=translation.get("language", ""),
        copyright=translation.get("copyright", ""),
        books=[dict_to_book(book) for book in translation.get("books", [])],
    )

def find_book_in_translation_doc(
    translation: model.TranslationDoc,
    book_id: str,
) -> model.BookDoc | None:
    return next(
        (
            book
            for book in translation.books
            if book.bookId == book_id or book.abbreviation == book_id
        ),
        None,
    )

def find_chapter_in_book_doc(
    book: model.BookDoc,
    chapter_number: int,
) -> model.ChapterDoc | None:
    return next(
        (chapter for chapter in book.chapters if chapter.chapter == chapter_number),
        None,
    )

def get_chapter_document(
    translation_id: str,
    book_id: str,
    chapter_number: int,
    db_name: str = "bible",
    collection_name: str = "translation",
) -> dict | None:
    """Fetch a chapter nested doc by translationId, bookId, and chapter number."""
    translation = get_translation_by_id(translation_id, db_name, collection_name)
    book = get_book_from_translation(translation, book_id)
    return get_chapter_from_book(book, chapter_number)


def get_verse_content(entries: list[model.Entry], verse_label: str) -> str:
    """Concatenates all content entries for a specific verse label (e.g., 'v1', 'v2'), including small caps ('sc')."""
    return " ".join([
        entry.value 
        for entry in entries 
        if 'verse' in entry.keyParts 
        and ('content' in entry.keyParts or 'sc' in entry.keyParts)
        and verse_label in entry.keyParts
    ])

def get_verse_key_parts(entries: list[model.Entry], verse_label: str) -> list:
    """Returns the list of keyParts for a specific verse label (e.g., 'v1', 'v2') excluding the first element and 'content'."""
    for entry in entries:
        if 'verse' in entry.keyParts and 'content' in entry.keyParts and verse_label in entry.keyParts:
            return [part for part in entry.keyParts[1:] if part != 'content']
    return []

def append_verse_plain_text(
    entries: list[model.Entry],
    rows: list,
    lineNumber: int,
    verse_qtt: int,
) -> int:
    """Append the verse plain_text entry when a new verse label is encountered."""
    if verse_qtt == 0:
        return lineNumber

    verse_label = f'v{verse_qtt}'
    #append to entries and rows only if there is not already a plain_text entry for the current verse label, to avoid duplicate plain_text entries for the same verse label, because in some cases there are multiple tags with the same verse label, but I only want to add one plain_text entry for each verse label
    if any(
        'plain_text' in entry.keyParts and verse_label in entry.keyParts
        for entry in entries
    ):
        return lineNumber

    verse_text = f'{verse_qtt} ' + get_verse_content(entries, verse_label)
    plain_text_classes = [lineNumber] + get_verse_key_parts(entries, verse_label) + ["plain_text"]

    entry = model.Entry(rowId=lineNumber, keyParts=plain_text_classes, value=verse_text)
    entries.append(entry)
    rows.append([lineNumber, str(plain_text_classes), verse_text])
    print(str(plain_text_classes) + "\t" + verse_text)
    return lineNumber + 1


def get_last_plain_text_verse(entries):
    for entry in reversed(entries):
        if entry.keyParts and "plain_text" in entry.keyParts:
            return next(
                (part for part in entry.keyParts if re.match(r"^v\d+$", str(part))),
                None,
            )
    return None

def get_book_from_json(json_file_path: str, book_id: str) -> tuple[str, dict] | None:
    """
    Retrieve a book element from a JSON file by book_id.
    
    Args:
        json_file_path: Path to the JSON file (e.g., "./app/json/old.json")
        book_id: The book ID to search for (e.g., "JDG", "GEN")
    
    Returns:
        A tuple of (book_name, book_data) if found, else None
        Example: ("Judges", {"book_id": "JDG", "chapters": [36, 23, ...]})
    """
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for index, (book_name, book_data) in enumerate(data.items()):
            if book_data.get("book_id") == book_id:
                return (index, book_name, book_data)
        
        return None
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {json_file_path}")
        return None

if __name__ == "__main__":
    import sys
    rows = [["id","tag","text"]]
    lineNumber = 0
    ot = load_ot_books_from_json(DATA_DIR)
    nt = load_nt_books_from_json(DATA_DIR)
    testament = "NT"  # "OT" or "NT"
    book_number = 0

    # book_chapter = "GEN.1"
    # book_chapter = "GEN.2"
    # book_chapter = "GEN.3"
    # book_chapter = "GEN.4"
    # book_chapter = "JDG.1"
    book_chapter = "PSA.77"
    # book_chapter = "PSA.119"  
    # bookChapter = "MRK.1"
    # book_chapter = "ROM.1"
    # bookChapter = "ACT.20"
    # bookChapter = "REV.21"

    # bibleId = 107 # NET Bible
    # bibleId = 2287  #GKHB
    # bibleId = 1270  #KOV
    bibleId = 1930 #  NVT
    # bibleId = 59 #  ESV
    # bibleId = 1608 # ARA



    # for book_name, book_data in ot.items():
    #     book_id = book_data["book_id"]
    #     # Loop through each chapter (1-indexed based on the index in the chapters list)
    #     for chapter_num in range(1, len(book_data["chapters"]) + 1):
    #         lineNumber = 0
    #         book_chapter = f"{book_id}.{chapter_num}"
    #         print(book_chapter)  # Outputs: GEN.1, GEN.2, ..., EXO.1, etc.

    # BREAKPOINT: API fetch. Pause here to inspect bibleId, book_chapter, and the response from bible.com.
    response = get_chapter_data("3.3", bibleId, book_chapter)

    chapterCode = response['reference']['usfm'][0]
    # response['next']['usfm'][0] has the next chapter to scrap
    
    bookName  = response['reference']['human']
    bookName, chapter_num = bookName.split(" ")
    bookAbbreviation, chapter_num = chapterCode.split(".")


    versionId = response['reference']['version_id']
    match versionId:  
        case 59: 
            translationAbbreviation = "ESV"
            translationName = "English Standard Version"
            language = "English"
        case 107: 
            translationAbbreviation = "NET"
            translationName = "New English Translation"
            language = "English"
        case 2287: 
            translationAbbreviation = "GKHB"
            translationName = "Global Khmer Bible"
            language = "Khmer"
        case 1270: 
            translationAbbreviation = "KOV"
            translationName = "Khmer Old Version"
            language = "Khmer"
        case 1930: 
            translationAbbreviation = "NVT"
            translationName = "Nova Versão Transformadora"
            language = "Portuguese"
        case 1608: 
            translationAbbreviation = "ARA"
            translationName = "Almeida Revista e Atualizada"
            language = "Portuguese"

    copyright = response['copyright']['html']

    
    soup = BeautifulSoup(copyright, "html.parser")
    # This removes all tags and returns just the text
    clean_text = soup.get_text()
    copyrightText = response['copyright']['text']

    translation: model.TranslationDoc | None = None
    book: model.BookDoc | None = None
    chapter: model.ChapterDoc | None = None

    translation = get_translation_by_id(translationAbbreviation, db_name="bible", collection_name="translation")
    if isinstance(translation, dict):
        translation = dict_to_translation(translation)

    if isinstance(translation, model.TranslationDoc):
        book = find_book_in_translation_doc(translation, bookAbbreviation)
    else:
        book_dict = get_book_from_translation(translation, bookAbbreviation)
        if isinstance(book_dict, dict):
            book = dict_to_book(book_dict)

    if isinstance(book, model.BookDoc):
        chapter = find_chapter_in_book_doc(book, int(chapter_num))
    elif isinstance(book, dict):
        chapter = get_chapter_from_book(book, int(chapter_num))
        if isinstance(chapter, dict):
            chapter = dict_to_chapter(chapter)

    if translation is None:
        translation = model.TranslationDoc( translationId = translationAbbreviation,   name= translationName, abbreviation= translationAbbreviation,  language=language,copyright=copyrightText, books = [])

    result = next(
        (
            (index, name)
            for index, (name, data) in enumerate(nt.items())
            if data["book_id"] == bookAbbreviation
        ),
        (None, None),
    )

    book_index, book_title = result
    if book_title is None:
        testament = "OT"
        result = next(
            (
                (index, name)
                for index, (name, data) in enumerate(ot.items())
                if data["book_id"] == bookAbbreviation
            ),
            (None, None),
        )

        book_index, book_title = result

        book = model.BookDoc(
            bookId=bookAbbreviation,
            testament=testament,
            order=book_index + 1,
            title=book_title,
            abbreviation=bookAbbreviation,
            chapters=[],
        )

    if chapter is None:   
        chapter = model.ChapterDoc(chapter = int(chapter_num), entries = [])
    

    textHtml = BeautifulSoup(response['content'], 'lxml')
    # BREAKPOINT: Parsed HTML. Pause here to inspect textHtml and chapter_tag before parsing entries.
    chapter_tag: Tag | None = textHtml.find(class_="chapter")

    if chapter_tag:
        # Define output directories (organized by translation then book)
        json_dir = os.path.join("app", "json", translationAbbreviation, testament, f"{book_index+1:02d}_"+ bookAbbreviation)
        txt_dir = os.path.join("app", "txt", translationAbbreviation,testament, f"{book_index+1:02d}_"+ bookAbbreviation)
        csv_dir = os.path.join("app", "csv", translationAbbreviation, testament, f"{book_index+1:02d}_"+ bookAbbreviation)

        # Ensure directories exist
        os.makedirs(json_dir, exist_ok=True)
        os.makedirs(txt_dir, exist_ok=True)
        os.makedirs(csv_dir, exist_ok=True)

        chapter_num = int(chapter_num)
        filename = translationAbbreviation + "_" + bookAbbreviation + "_" + f"{chapter_num:03d}"

        fileName_txt = os.path.join(txt_dir, f"{filename}.txt")
        rows.append([lineNumber, book_chapter,versionId])
        lineNumber+=1
        with open(fileName_txt, "w", encoding="utf-8") as _f:
            sys.stdout = _f
            
            # BREAKPOINT: Enter the parser. Step into this function to watch HTML become Entry objects.
            entries = extract_tags_from_chapter(versionId, chapter_tag, rows, lineNumber)
            chapter.entries = entries

            # ==== verify if the last verse number in the entries matches the expected chapter length from the JSON files, and print a warning if it does not match, to identify potential issues with the scraped data, such as missing verses or incorrect verse numbers, which can be caused by changes in the HTML structure of the source website or inconsistencies in the data. This is especially important for books with a large number of verses, like Psalms 119, to ensure that all verses are correctly captured and accounted for. ====
            last_verse = get_last_plain_text_verse(entries)
            match = re.match(r"^([A-Za-z]+)(\d+)$", last_verse)
            if match:
                prefix, number = match.groups()
                last_verse_number = int(number)

            testament = "OT"
            result = get_book_from_json(os.path.join(DATA_DIR, "old.json"), bookAbbreviation)
            if result is None:
                result = get_book_from_json(os.path.join(DATA_DIR, "new.json"), bookAbbreviation)
                testament = "NT"

            index, book_name, book_data = result
            # print(book_name)  # "Judges"
            # print(book_data["book_id"])  # "JDG"
            # print(book_data["chapters"])  # [36, 23, 31, 24, ...]
            if book_data["chapters"][chapter.chapter-1] !=  last_verse_number:
                print(f"XXXX ===================== Warning: Last verse number {last_verse} does not match expected chapter length {book_data['chapters'][chapter.chapter-1]} for {bookAbbreviation} chapter {chapter.chapter}")
        



            existing_book = None
            if isinstance(translation, model.TranslationDoc):
                existing_book = find_book_in_translation_doc(translation, bookAbbreviation)
            if existing_book is None:
                testament = "NT"
                result = next(
                    (
                        (index, name)
                        for index, (name, data) in enumerate(nt.items())
                        if data["book_id"] == bookAbbreviation
                    ),
                    (None, None),
                )

                book_index, book_title = result
                if book_title is None:
                    testament = "OT"
                    result = next(
                        (
                            (index, name)
                            for index, (name, data) in enumerate(ot.items())
                            if data["book_id"] == bookAbbreviation
                        ),
                        (None, None),
                    )

                    book_index, book_title = result

                book = model.BookDoc(
                    bookId=bookAbbreviation,
                    testament=testament,
                    order=book_index + 1,
                    title=book_title,
                    abbreviation=bookAbbreviation,
                    chapters=[],
                )

                translation.books.append(book)
            else:
                book = existing_book

            existing_chapter = None
            if isinstance(book, model.BookDoc):
                existing_chapter = find_chapter_in_book_doc(book, int(chapter_num))

            if existing_chapter is None:
                book.chapters.append(chapter)
            else:
                existing_chapter.entries = entries
                chapter = existing_chapter

            client = MongoClient("mongodb://localhost:27017")
            db = client["bible"]
            collection = db["translation"]

            # Create a separate, clean document just for the current chapter's JSON file
            current_chapter_only_book = model.BookDoc(
                bookId=book.bookId,
                testament=book.testament,
                order=book.order,
                title=book.title,
                abbreviation=book.abbreviation,
                chapters=[chapter]
            )
            current_book_only_translation = model.TranslationDoc(
                translationId=translation.translationId,
                name=translation.name,
                abbreviation=translation.abbreviation,
                language=translation.language,
                copyright=translation.copyright,
                books=[current_chapter_only_book]
            )
            doc_json = asdict(current_book_only_translation)

            # create a json file =================================================
            fileNameJson = os.path.join(json_dir, f"{filename}.json")
            with open(fileNameJson, "w", encoding="utf-8") as f:
                json.dump(doc_json, f, ensure_ascii=False, indent=2)
                
            # For MongoDB, write the entire accumulated translation (all books & chapters)
            doc_db = asdict(translation)
            existing = collection.find_one({"translationId": translation.translationId})
            if existing:
                doc_db["_id"] = existing["_id"]
                collection.replace_one({"_id": existing["_id"]}, doc_db)
            else:
                collection.insert_one(doc_db)

            fileNameCsv = os.path.join(csv_dir, f"{filename}.csv")
            write_rows_to_csv(fileNameCsv)
        
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
               
