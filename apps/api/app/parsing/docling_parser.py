"""Docling parser — structure-rich (headings, tables, reading order, provenance),
the right basis for citation-first treaty extraction.

Not yet implemented. Docling pulls a VLM + PyTorch and cannot run in CI, so it
belongs in a dedicated worker image with models pre-baked (see ADR-0005). When
implemented it must normalize to the same ``ParsedDocument`` contract as
``PyMuPDFParser``:

* one ``ParsedPage`` per page with real ``width`` / ``height``
* ``ParsedBlock`` per Docling item, mapping ``section_header``/``title`` →
  ``BlockType.HEADING`` (with ``level``), ``table`` → ``BlockType.TABLE``,
  ``caption`` → ``BlockType.CAPTION``, else ``PARAGRAPH``
* ``reading_order`` from Docling's item order; ``bbox`` and ``page_number`` from
  each item's provenance
* set ``ocr_used`` when Docling ran OCR
"""

from __future__ import annotations

from app.domain.documents.parsed import ParsedDocument
from app.parsing.base import ParserError


class DoclingParser:
    name = "docling"

    @property
    def version(self) -> str:
        try:
            import docling

            return getattr(docling, "__version__", "unknown")
        except ImportError:
            return "not-installed"

    def supports(self, *, filename: str, content_type: str) -> bool:
        lowered = filename.lower()
        return (
            lowered.endswith((".pdf", ".docx")) or "pdf" in content_type or "word" in content_type
        )

    async def parse(self, data: bytes, *, filename: str, content_type: str) -> ParsedDocument:
        raise ParserError(
            "DoclingParser is not implemented yet — use CEDEON_DOCUMENT_PARSER=pymupdf. "
            "See this module's docstring for the implementation contract."
        )
