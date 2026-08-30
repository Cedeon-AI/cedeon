"""PyMuPDF parser — fast, digital-text PDFs. Preserves page numbers, text blocks,
reading order and bounding boxes; heading detection is a font-size heuristic
(Docling does this properly)."""

from __future__ import annotations

from collections import Counter

import anyio
import pymupdf

from app.domain.documents.parsed import BlockType, ParsedBlock, ParsedDocument, ParsedPage
from app.parsing.base import UnsupportedDocumentError

_PDF_TYPES = {"application/pdf", "application/x-pdf"}
_BOLD_FLAG = 1 << 4
_HEADING_SIZE_RATIO = 1.15
_HEADING_MAX_CHARS = 140


class PyMuPDFParser:
    name = "pymupdf"

    @property
    def version(self) -> str:
        return pymupdf.__version__

    def supports(self, *, filename: str, content_type: str) -> bool:
        return content_type in _PDF_TYPES or filename.lower().endswith(".pdf")

    async def parse(self, data: bytes, *, filename: str, content_type: str) -> ParsedDocument:
        if not self.supports(filename=filename, content_type=content_type):
            raise UnsupportedDocumentError(filename, content_type)
        return await anyio.to_thread.run_sync(self._parse_sync, data)

    def _parse_sync(self, data: bytes) -> ParsedDocument:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            raw_pages = [page.get_text("dict") for page in doc]
            body_size = _body_font_size(raw_pages)
            pages = [
                self._build_page(index + 1, raw, body_size) for index, raw in enumerate(raw_pages)
            ]
        return ParsedDocument(
            parser_name=self.name,
            parser_version=self.version,
            page_count=len(pages),
            pages=pages,
        )

    def _build_page(self, page_number: int, raw: dict, body_size: float) -> ParsedPage:
        blocks: list[ParsedBlock] = []
        order = 0
        for raw_block in raw.get("blocks", []):
            if raw_block.get("type") != 0:  # 0 = text
                continue
            spans = [span for line in raw_block.get("lines", []) for span in line.get("spans", [])]
            text = " ".join(span["text"] for span in spans).strip()
            if not text:
                continue
            max_size = max((span["size"] for span in spans), default=body_size)
            is_bold = any(span["flags"] & _BOLD_FLAG for span in spans)
            block_type = _classify(text, max_size, is_bold, body_size)
            blocks.append(
                ParsedBlock(
                    text=text,
                    block_type=block_type,
                    reading_order=order,
                    bbox=_bbox(raw_block.get("bbox")),
                    level=1 if block_type is BlockType.HEADING else None,
                )
            )
            order += 1

        return ParsedPage(
            page_number=page_number,
            width=round(raw.get("width", 0.0), 2),
            height=round(raw.get("height", 0.0), 2),
            text="\n".join(block.text for block in blocks),
            blocks=blocks,
        )


def _bbox(raw: object) -> tuple[float, float, float, float] | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        x0, y0, x1, y1 = (round(float(v), 2) for v in raw)
        return (x0, y0, x1, y1)
    return None


def _classify(text: str, max_size: float, is_bold: bool, body_size: float) -> BlockType:
    looks_big = max_size >= body_size * _HEADING_SIZE_RATIO
    short_and_titlish = len(text) <= _HEADING_MAX_CHARS and not text.endswith((".", ";", ","))
    if short_and_titlish and (looks_big or (is_bold and max_size >= body_size)):
        return BlockType.HEADING
    return BlockType.PARAGRAPH


def _body_font_size(raw_pages: list[dict]) -> float:
    sizes: Counter[float] = Counter()
    for raw in raw_pages:
        for raw_block in raw.get("blocks", []):
            for line in raw_block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        sizes[round(span["size"], 1)] += len(span["text"])
    if not sizes:
        return 10.0
    # The size carrying the most characters is the body text.
    return sizes.most_common(1)[0][0]
