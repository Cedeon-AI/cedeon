from __future__ import annotations

import datetime as dt
from uuid import UUID

from app.api.schemas import ApiModel
from app.domain.documents import DocumentKind, DocumentStatus, ParseStatus


class DocumentOut(ApiModel):
    id: UUID
    kind: DocumentKind
    original_filename: str
    content_type: str
    byte_size: int
    status: DocumentStatus
    created_at: dt.datetime


class DocumentList(ApiModel):
    documents: list[DocumentOut]


class ParseInfo(ApiModel):
    id: UUID
    parser_name: str
    parser_version: str
    status: ParseStatus
    page_count: int | None
    ocr_used: bool
    error: str | None
    started_at: dt.datetime | None
    finished_at: dt.datetime | None


class DocumentDetail(ApiModel):
    document: DocumentOut
    current_parse: ParseInfo | None


class PageOut(ApiModel):
    page_number: int
    width: float
    height: float
    text: str


class PageList(ApiModel):
    pages: list[PageOut]


class ChunkOut(ApiModel):
    ordinal: int
    page_from: int
    page_to: int
    section_path: str
    heading: str | None
    text: str
    char_start: int
    char_end: int


class ChunkList(ApiModel):
    chunks: list[ChunkOut]
