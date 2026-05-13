"""
bible_db/models.py
──────────────────
Pydantic v2 models mirroring the MongoDB schema.
Used for validation before insertion and for typed return values.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED / INLINE
# ═══════════════════════════════════════════════════════════════════════════════

class MarkType(str, Enum):
    BOLD            = "bold"
    ITALIC          = "italic"
    UNDERLINE       = "underline"
    STRIKETHROUGH   = "strikethrough"
    SUPERSCRIPT     = "superscript"
    SUBSCRIPT       = "subscript"
    SMALL_CAPS      = "smallCaps"
    RED_LETTER      = "redLetter"
    SELAH           = "selah"
    POETRY_INDENT   = "poetryIndent"
    COLOR           = "color"
    FONT            = "font"
    HIGHLIGHT       = "highlight"
    FOOTNOTE_MARKER = "footnoteMarker"
    CROSS_REF_MARKER= "crossRefMarker"
    STRONGS         = "strongs"


class Mark(BaseModel):
    type:   MarkType
    value:  Optional[str]   = None   # color hex
    family: Optional[str]   = None   # font family
    size:   Optional[float] = None   # pt
    ref:    Optional[str]   = None   # footnote / Strong's
    level:  Optional[int]   = None   # poetry indent depth
    color:  Optional[str]   = None   # highlight color

    model_config = {"extra": "forbid"}


class NodeType(str, Enum):
    DOCUMENT    = "document"
    HEADING     = "heading"
    PARAGRAPH   = "paragraph"
    BLOCKQUOTE  = "blockquote"
    LIST        = "list"
    LIST_ITEM   = "listItem"
    TABLE       = "table"
    TABLE_ROW   = "tableRow"
    TABLE_CELL  = "tableCell"
    VERSE       = "verse"
    VERSE_NUM   = "verseNumber"
    SECTION     = "section"
    TEXT        = "text"
    HARD_BREAK  = "hardBreak"


class ContentNode(BaseModel):
    type:     NodeType
    text:     Optional[str]              = None
    marks:    Optional[List[Mark]]       = None
    attrs:    Optional[Dict[str, Any]]   = None
    children: Optional[List["ContentNode"]] = None

    @model_validator(mode="after")
    def text_nodes_need_text(self) -> "ContentNode":
        if self.type == NodeType.TEXT and self.text is None:
            raise ValueError("text nodes must have a 'text' field")
        return self

    model_config = {"extra": "forbid"}

ContentNode.model_rebuild()


class Footnote(BaseModel):
    marker: str
    text:   str
    model_config = {"extra": "forbid"}


# ═══════════════════════════════════════════════════════════════════════════════
# EDITION
# ═══════════════════════════════════════════════════════════════════════════════

class SourceTextType(str, Enum):
    ORIGINAL    = "original"
    TRANSLATION = "translation"
    PARAPHRASE  = "paraphrase"
    INTERLINEAR = "interlinear"


class Edition(BaseModel):
    id:                 str  = Field(alias="_id")
    name:               str
    abbreviation:       str
    language:           str
    direction:          Literal["ltr", "rtl"] = "ltr"
    script:             Optional[str]   = None
    year:               Optional[int]   = None
    publisher:          Optional[str]   = None
    copyright:          Optional[str]   = None
    has_red_letters:    bool = Field(False, alias="hasRedLetters")
    has_strongs:        bool = Field(False, alias="hasStrongsNumbers")
    has_word_alignment: bool = Field(False, alias="hasWordAlignment")
    source_text_type:   SourceTextType = Field(SourceTextType.TRANSLATION, alias="sourceTextType")
    source_edition_ids: List[str]      = Field([], alias="sourceEditionIds")
    created_at:         datetime       = Field(default_factory=_now, alias="createdAt")
    updated_at:         datetime       = Field(default_factory=_now, alias="updatedAt")

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def to_doc(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)


# ═══════════════════════════════════════════════════════════════════════════════
# BOOK
# ═══════════════════════════════════════════════════════════════════════════════

class Testament(str, Enum):
    OT = "OT"
    NT = "NT"
    DC = "DC"


class BookCategory(str, Enum):
    LAW          = "Law"
    HISTORY      = "History"
    POETRY       = "Poetry"
    PROPHECY     = "Prophecy"
    GOSPEL       = "Gospel"
    ACTS         = "Acts"
    EPISTLE      = "Epistle"
    APOCALYPTIC  = "Apocalyptic"
    DEUTEROCANON = "Deuterocanon"


class Book(BaseModel):
    id:             str  = Field(alias="_id")
    edition_id:     str  = Field(alias="editionId")
    testament:      Testament
    order:          int
    name:           str
    abbreviation:   str
    usfm_code:      Optional[str] = Field(None, alias="usfmCode")
    osis:           Optional[str] = None
    category:       Optional[BookCategory] = None
    total_chapters: int  = Field(alias="totalChapters")
    total_verses:   int  = Field(alias="totalVerses")
    created_at:     datetime = Field(default_factory=_now, alias="createdAt")
    updated_at:     datetime = Field(default_factory=_now, alias="updatedAt")

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def to_doc(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)


# ═══════════════════════════════════════════════════════════════════════════════
# VERSE (embedded in Chapter)
# ═══════════════════════════════════════════════════════════════════════════════

class Verse(BaseModel):
    verse_id:          str      = Field(alias="verseId")
    order:             int
    reference:         str
    canonical_ref:     str      = Field(alias="canonicalRef")
    root:              ContentNode
    plain_text:        str      = Field(alias="plainText")
    word_count:        int      = Field(0, alias="wordCount")
    strongs_refs:      List[str] = Field([], alias="strongsRefs")
    footnotes:         List[Footnote] = []
    cross_references:  List[str] = Field([], alias="crossReferences")
    liturgical_markers: List[str] = Field([], alias="liturgicalMarkers")

    @field_validator("canonical_ref", mode="before")
    @classmethod
    def validate_canonical_ref(cls, v: str) -> str:
        import re
        if not re.match(r"^[A-Z0-9]+\.[0-9]+\.[0-9]+$", v):
            raise ValueError(f"Invalid canonicalRef format: {v!r}")
        return v

    @field_validator("strongs_refs", mode="before")
    @classmethod
    def validate_strongs(cls, v: List[str]) -> List[str]:
        import re
        for ref in v:
            if not re.match(r"^[HG][0-9]{4}$", ref):
                raise ValueError(f"Invalid Strong's number: {ref!r}")
        return v

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def to_doc(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CHAPTER
# ═══════════════════════════════════════════════════════════════════════════════

class SectionHeading(BaseModel):
    before_verse: int  = Field(alias="beforeVerse")
    text:         str
    model_config = {"populate_by_name": True, "extra": "forbid"}


class Chapter(BaseModel):
    id:               str  = Field(alias="_id")
    edition_id:       str  = Field(alias="editionId")
    book_id:          str  = Field(alias="bookId")
    order:            int
    reference:        str
    canonical_ref:    str  = Field(alias="canonicalRef")
    total_verses:     int  = Field(alias="totalVerses")
    verses:           List[Verse]
    plain_text:       str  = Field("", alias="plainText")
    section_headings: List[SectionHeading] = Field([], alias="sectionHeadings")
    schema_version:   int  = Field(1, alias="schemaVersion")
    created_at:       datetime = Field(default_factory=_now, alias="createdAt")
    updated_at:       datetime = Field(default_factory=_now, alias="updatedAt")

    @model_validator(mode="after")
    def auto_plain_text(self) -> "Chapter":
        """Concatenate verse plain texts if plainText not explicitly set."""
        if not self.plain_text and self.verses:
            self.plain_text = " ".join(v.plain_text for v in self.verses)
        for v in self.verses:
            if v.word_count == 0 and v.plain_text:
                v.word_count = len(v.plain_text.split())
        return self

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def to_doc(self) -> dict:
        doc = self.model_dump(by_alias=True, exclude_none=True)
        # Ensure verses are serialised as dicts
        doc["verses"] = [v.to_doc() for v in self.verses]
        return doc


# ═══════════════════════════════════════════════════════════════════════════════
# LEXICON
# ═══════════════════════════════════════════════════════════════════════════════

class LexiconLanguage(str, Enum):
    HEBREW  = "Hebrew"
    ARAMAIC = "Aramaic"
    GREEK   = "Greek"


class KjvUsage(BaseModel):
    word:  str
    count: int
    model_config = {"extra": "forbid"}


class LexiconEntry(BaseModel):
    id:                 str  = Field(alias="_id")        # 'H3068'
    language:           LexiconLanguage
    strongs_number:     str  = Field(alias="strongsNumber")
    lemma:              str
    transliteration:    Optional[str] = None
    pronunciation:      Optional[str] = None
    part_of_speech:     Optional[str] = Field(None, alias="partOfSpeech")
    definition:         str
    extended_definition: Optional[str] = Field(None, alias="extendedDefinition")
    usage_notes:        Optional[str]  = Field(None, alias="usageNotes")
    kjv_translations:   List[KjvUsage] = Field([], alias="kjvTranslations")
    related_strongs:    List[str]      = Field([], alias="relatedStrongs")
    created_at:         datetime = Field(default_factory=_now, alias="createdAt")
    updated_at:         datetime = Field(default_factory=_now, alias="updatedAt")

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def to_doc(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)


# ═══════════════════════════════════════════════════════════════════════════════
# VERSE ALIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

class VerseAlignment(BaseModel):
    id:               str  = Field(alias="_id")
    canonical_ref:    str  = Field(alias="canonicalRef")
    editions:         Dict[str, Optional[str]]   # editionId → verseId | None
    verse_split_note: Optional[str] = Field(None, alias="verseSplitNote")

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def to_doc(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)


# ═══════════════════════════════════════════════════════════════════════════════
# WORD ALIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

class WordSlot(BaseModel):
    slot:        int
    words:       Dict[str, List[str]]     # editionId → [word, …]
    strongs_ref: Optional[str] = Field(None, alias="strongsRef")
    model_config = {"populate_by_name": True, "extra": "forbid"}


class WordAlignment(BaseModel):
    id:            str  = Field(alias="_id")
    canonical_ref: str  = Field(alias="canonicalRef")
    alignments:    List[WordSlot]

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def to_doc(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ANNOTATION
# ═══════════════════════════════════════════════════════════════════════════════

class AnnotationType(str, Enum):
    HIGHLIGHT  = "highlight"
    NOTE       = "note"
    CROSS_REF  = "crossRef"
    BOOKMARK   = "bookmark"


class Selection(BaseModel):
    verse_id:     str  = Field(alias="verseId")
    start_offset: int  = Field(alias="startOffset")
    end_offset:   Optional[int] = Field(None, alias="endOffset")
    model_config = {"populate_by_name": True, "extra": "forbid"}


class HighlightStyle(BaseModel):
    color:   str
    opacity: float = 0.4
    model_config = {"extra": "forbid"}


class NoteBody(BaseModel):
    root:       Optional[ContentNode] = None
    plain_text: Optional[str]         = Field(None, alias="plainText")
    model_config = {"populate_by_name": True, "extra": "forbid"}


class Annotation(BaseModel):
    user_id:            str  = Field(alias="userId")
    type:               AnnotationType
    canonical_ref:      str  = Field(alias="canonicalRef")
    edition_id:         Optional[str]           = Field(None, alias="editionId")
    selection:          Optional[Selection]     = None
    style:              Optional[HighlightStyle]= None
    note:               Optional[NoteBody]      = None
    linked_canonical_ref: Optional[str]         = Field(None, alias="linkedCanonicalRef")
    tags:               List[str]               = []
    is_private:         bool                    = Field(True, alias="isPrivate")
    group_id:           Optional[str]           = Field(None, alias="groupId")
    created_at:         datetime = Field(default_factory=_now, alias="createdAt")
    updated_at:         datetime = Field(default_factory=_now, alias="updatedAt")

    @model_validator(mode="after")
    def validate_type_constraints(self) -> "Annotation":
        if self.type == AnnotationType.CROSS_REF and not self.linked_canonical_ref:
            raise ValueError("crossRef annotations require linkedCanonicalRef")
        if self.type in (AnnotationType.HIGHLIGHT, AnnotationType.NOTE) and not self.selection:
            raise ValueError(f"{self.type} annotations require a selection")
        if self.type == AnnotationType.HIGHLIGHT and not self.style:
            raise ValueError("highlight annotations require a style")
        return self

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def to_doc(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)
