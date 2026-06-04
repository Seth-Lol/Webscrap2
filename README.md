# Webscrap2

Webscrap2 is a Python project for scraping Bible chapter content, turning it into structured data, storing it in MongoDB, and serving it through a small FastAPI API.

The project currently has two related data flows:

1. `scrapper/assist_real.py` scrapes one Bible chapter from bible.com and writes structured output files.
2. `script/csv_to_mongo.py` imports CSV chapter files into the newer `bible_db` MongoDB schema used by the API.

Some files in `scrapper/experiments/` are older learning versions of the scraper.

## Folder Layout

```text
Webscrap2/
  api/
    main.py                  FastAPI app for reading verses/chapters/search

  bible_db/
    connection.py            MongoDB connection and index setup
    models.py                Pydantic database models
    repository.py            MongoDB read/write helper classes
    importer.py              Higher-level import tools for JSON/XML formats

  scrapper/
    assist_real.py           Main current scraper script
    model.py                 Simple dataclasses used by assist_real.py
    scrape_net_bible.py      Simpler full NET Bible CSV scraper
    data/
      old.json               Old Testament book metadata
      new.json               New Testament book metadata
    experiments/             Older practice/test scraper files

  script/
    csv_to_mongo.py          Imports CSV files into MongoDB chapters collection
```

## How The Project Works

## Project Diagram

```text
                         bible.com API
                              |
                              v
                    scrapper/assist_real.py
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
      app/json/           app/csv/            app/txt/
          |                   |
          |                   v
          |          script/csv_to_mongo.py
          |                   |
          v                   v
  bible.translation     bible.chapters
          |                   |
          |                   v
          |            bible_db/repository.py
          |                   |
          |                   v
          |              api/main.py
          |                   |
          +-------------------+
                              |
                              v
                       FastAPI endpoints
                  /verse  /chapter  /search
```

Short version:

```text
Scrape -> Save files -> Import to MongoDB -> Read through API
```

### 1. Scraping

The scraper calls the bible.com chapter API:

```python
https://nodejs.bible.com/api/bible/chapter/3.3
```

The important inputs are:

```python
book_chapter = "PSA.77"
bibleId = 1930
```

In `scrapper/assist_real.py`, `book_chapter` chooses the chapter and `bibleId` chooses the translation.

Example Bible IDs already in the file:

```text
107   NET
1930  NVT
59    ESV
1608  ARA
2287  GKHB
1270  KOV
```

The scraper receives HTML content from the API, parses it with BeautifulSoup, then walks through the HTML tags. It turns pieces of the chapter into `Entry` objects:

```python
Entry(rowId=1, keyParts=["p1", "verse", "v1", "content"], value="...")
```

Those entries are saved into JSON, TXT, CSV, and MongoDB.

### 2. Book Metadata

The scraper uses:

```text
scrapper/data/old.json
scrapper/data/new.json
```

These files tell the script which books are Old Testament or New Testament, their order, book IDs, and chapter verse counts.

### 3. MongoDB Models

There are two model files:

```text
scrapper/model.py
bible_db/models.py
```

They are different on purpose.

`scrapper/model.py` is a small beginner-friendly dataclass model used by `assist_real.py`.

`bible_db/models.py` is the larger Pydantic model system for the database and API. It defines things like:

```text
Edition
Book
Chapter
Verse
ContentNode
Footnote
Annotation
```

### 4. CSV To Mongo

`script/csv_to_mongo.py` reads CSV rows and turns verse rows into `Verse` objects. Then it wraps those verses in a `Chapter` object and saves the chapter through `ChapterRepo`.

The saved MongoDB chapter document looks roughly like:

```text
chapter
  editionId
  bookId
  canonicalRef
  verses[]
    verseId
    reference
    canonicalRef
    plainText
```

### 5. API

`api/main.py` exposes a FastAPI app with these routes:

```text
GET /                         Health check
GET /verse/{canonical_ref}     Example: /verse/GEN.1.1
GET /chapter/{book}/{chapter}  Example: /chapter/GEN/1
GET /search?q=beginning        Full-text search
```

The API reads from MongoDB using `ChapterRepo`.

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the packages used by the project:

```bash
pip install requests beautifulsoup4 lxml pymongo pydantic fastapi uvicorn
```

Make sure MongoDB is running locally:

```text
mongodb://localhost:27017
```

The project uses the database name:

```text
bible
```

## Running The Main Scraper

From the repo root:

```bash
python3 scrapper/assist_real.py
```

Before running, edit these lines in `scrapper/assist_real.py`:

```python
book_chapter = "PSA.77"
bibleId = 1930
```

The script writes output under:

```text
app/json/
app/txt/
app/csv/
```

It also writes to MongoDB collection:

```text
bible.translation
```

## Running The CSV Importer

Open `script/csv_to_mongo.py` and update:

```python
DATA_DIR = Path("...")
EDITION_ID = "edition_net_107"
```

Then run:

```bash
python3 script/csv_to_mongo.py
```

This writes chapter documents into MongoDB collection:

```text
bible.chapters
```

## Running The API

From the repo root:

```bash
uvicorn api.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

Example API calls:

```text
http://127.0.0.1:8000/verse/GEN.1.1
http://127.0.0.1:8000/chapter/GEN/1
http://127.0.0.1:8000/search?q=beginning
```

## Beginner Debugging Notes

In `scrapper/assist_real.py`, search for:

```text
BREAKPOINT
```

Good places to pause:

```text
API fetch             See what comes back from bible.com
Parsed HTML           See how BeautifulSoup reads the chapter HTML
Enter the parser      Step into the main parsing function
Main parser loop      Watch each HTML tag get processed
New verse label       See when the parser starts a new verse
Footnote branch       See how footnotes are handled
```

## Important Notes

The project is still in progress. The scraper currently writes to `bible.translation`, while the API reads from `bible.chapters`. That means the API is mainly connected to the `csv_to_mongo.py` / `bible_db` flow.

The `scrapper/experiments/` files are useful for learning, but they are not the main path.

Generated JSON files are ignored by Git because `.gitignore` includes:

```gitignore
*.json
```
