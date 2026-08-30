"""The parser output contract (a domain type). Every parser — PyMuPDF, Docling,
a future cloud parser — normalizes to this shape, so treaty logic never depends on
which parser ran."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class BlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CAPTION = "caption"
    OTHER = "other"


class ParsedBlock(BaseModel):
    text: str
    block_type: BlockType = BlockType.PARAGRAPH
    reading_order: int
    # x0, y0, x1, y1 in PDF points, when the parser provides it.
    bbox: tuple[float, float, float, float] | None = None
    # Heading depth (1 = top level) when known.
    level: int | None = None


class ParsedPage(BaseModel):
    page_number: int = Field(ge=1)
    width: float
    height: float
    # Invariant: text == "\n".join(b.text for b in blocks). Chunk offsets rely on it.
    text: str
    blocks: list[ParsedBlock] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    parser_name: str
    parser_version: str
    page_count: int = Field(ge=0)
    pages: list[ParsedPage] = Field(default_factory=list)
    ocr_used: bool = False
