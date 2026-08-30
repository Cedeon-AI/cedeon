"""PyMuPDFParser against synthetic PDFs. No DB."""

from __future__ import annotations

import pytest

from app.domain.documents.parsed import BlockType
from app.parsing import PyMuPDFParser
from app.parsing.base import UnsupportedDocumentError
from tests.support.pdfs import build_simple_pdf, build_treaty_pdf


@pytest.fixture
def parser() -> PyMuPDFParser:
    return PyMuPDFParser()


async def test_parses_pages_in_order_with_geometry(parser: PyMuPDFParser) -> None:
    pdf = build_simple_pdf(["Page one text.", "Page two text.", "Page three text."])
    parsed = await parser.parse(pdf, filename="doc.pdf", content_type="application/pdf")

    assert parsed.parser_name == "pymupdf"
    assert parsed.page_count == 3
    assert [p.page_number for p in parsed.pages] == [1, 2, 3]
    assert all(p.width > 0 and p.height > 0 for p in parsed.pages)
    assert "Page two text." in parsed.pages[1].text


async def test_detects_article_headings(parser: PyMuPDFParser) -> None:
    parsed = await parser.parse(
        build_treaty_pdf(), filename="treaty.pdf", content_type="application/pdf"
    )
    headings = [
        b.text for page in parsed.pages for b in page.blocks if b.block_type is BlockType.HEADING
    ]
    assert any("ARTICLE IV" in h for h in headings)
    assert any("ARTICLE VII" in h for h in headings)
    assert any("ARTICLE IX" in h for h in headings)


async def test_page_text_equals_joined_block_text(parser: PyMuPDFParser) -> None:
    parsed = await parser.parse(
        build_treaty_pdf(), filename="treaty.pdf", content_type="application/pdf"
    )
    for page in parsed.pages:
        assert page.text == "\n".join(b.text for b in page.blocks)


async def test_retention_and_limit_text_is_captured(parser: PyMuPDFParser) -> None:
    parsed = await parser.parse(
        build_treaty_pdf(), filename="treaty.pdf", content_type="application/pdf"
    )
    full = " ".join(p.text for p in parsed.pages)
    assert "USD 50,000,000" in full
    assert "USD 20,000,000" in full


async def test_rejects_non_pdf(parser: PyMuPDFParser) -> None:
    with pytest.raises(UnsupportedDocumentError):
        await parser.parse(b"not a pdf", filename="notes.txt", content_type="text/plain")


async def test_blocks_carry_reading_order_and_bbox(parser: PyMuPDFParser) -> None:
    parsed = await parser.parse(
        build_treaty_pdf(), filename="treaty.pdf", content_type="application/pdf"
    )
    page = parsed.pages[1]
    orders = [b.reading_order for b in page.blocks]
    assert orders == sorted(orders)
    assert all(b.bbox is not None and len(b.bbox) == 4 for b in page.blocks)
