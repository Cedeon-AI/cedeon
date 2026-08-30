"""Document parsing behind a narrow interface (ADR-0005).

``PyMuPDFParser`` ships first and proves the pipeline. ``DoclingParser`` (heavier,
structure-rich) is selectable via ``CEDEON_DOCUMENT_PARSER=docling`` and lives in
the ``docling`` optional extra — it is not installed in CI.
"""

from __future__ import annotations

from app.core.config import Settings
from app.parsing.base import DocumentParser, ParserError, UnsupportedDocumentError
from app.parsing.pymupdf_parser import PyMuPDFParser

__all__ = [
    "DocumentParser",
    "ParserError",
    "PyMuPDFParser",
    "UnsupportedDocumentError",
    "build_parser",
]


def build_parser(settings: Settings) -> DocumentParser:
    if settings.document_parser == "docling":
        from app.parsing.docling_parser import DoclingParser

        return DoclingParser()
    return PyMuPDFParser()
