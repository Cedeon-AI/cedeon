"""Document pipeline domain: kinds, state machines, and pure chunking."""

from __future__ import annotations

from enum import StrEnum

from app.domain.documents.chunking import DocumentChunk, chunk_document, document_text

__all__ = [
    "DocumentChunk",
    "DocumentKind",
    "DocumentStatus",
    "ParseStatus",
    "chunk_document",
    "document_text",
]


class DocumentKind(StrEnum):
    TREATY = "treaty"
    ENDORSEMENT = "endorsement"
    SLIP = "slip"
    LOSS_ADVICE = "loss_advice"
    CORRESPONDENCE = "correspondence"
    OTHER = "other"


class DocumentStatus(StrEnum):
    """Document-level state machine."""

    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSE_FAILED = "parse_failed"


class ParseStatus(StrEnum):
    """Status of one parse run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
