"""The DocumentParser interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.documents.parsed import ParsedDocument


class ParserError(Exception):
    pass


class UnsupportedDocumentError(ParserError):
    def __init__(self, filename: str, content_type: str) -> None:
        super().__init__(f"parser cannot handle {filename!r} ({content_type})")
        self.filename = filename
        self.content_type = content_type


@runtime_checkable
class DocumentParser(Protocol):
    name: str

    @property
    def version(self) -> str: ...

    def supports(self, *, filename: str, content_type: str) -> bool: ...

    async def parse(self, data: bytes, *, filename: str, content_type: str) -> ParsedDocument: ...
