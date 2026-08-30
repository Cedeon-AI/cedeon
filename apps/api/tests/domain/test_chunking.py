"""Heading-aware chunking. Pure — no DB."""

from __future__ import annotations

from app.domain.documents import chunk_document, document_text
from app.domain.documents.parsed import BlockType, ParsedBlock, ParsedDocument, ParsedPage


def _page(page_number: int, blocks: list[ParsedBlock]) -> ParsedPage:
    return ParsedPage(
        page_number=page_number,
        width=595.0,
        height=842.0,
        text="\n".join(b.text for b in blocks),
        blocks=blocks,
    )


def _h(text: str, order: int, level: int = 1) -> ParsedBlock:
    return ParsedBlock(text=text, block_type=BlockType.HEADING, reading_order=order, level=level)


def _p(text: str, order: int) -> ParsedBlock:
    return ParsedBlock(text=text, block_type=BlockType.PARAGRAPH, reading_order=order)


def test_new_chunk_at_every_heading() -> None:
    doc = ParsedDocument(
        parser_name="test",
        parser_version="0",
        page_count=1,
        pages=[
            _page(
                1,
                [
                    _h("ARTICLE I - BUSINESS COVERED", 0),
                    _p("This contract covers property catastrophe business.", 1),
                    _h("ARTICLE IV - LIMIT AND RETENTION", 2),
                    _p("USD 20,000,000 excess of USD 50,000,000 each loss occurrence.", 3),
                ],
            )
        ],
    )
    chunks = chunk_document(doc)
    assert [c.section_path for c in chunks] == [
        "ARTICLE I - BUSINESS COVERED",
        "ARTICLE IV - LIMIT AND RETENTION",
    ]
    assert [c.ordinal for c in chunks] == [0, 1]
    assert chunks[1].heading == "ARTICLE IV - LIMIT AND RETENTION"


def test_offsets_slice_the_full_text_exactly() -> None:
    doc = ParsedDocument(
        parser_name="test",
        parser_version="0",
        page_count=2,
        pages=[
            _page(1, [_h("ARTICLE I", 0), _p("First article body text here.", 1)]),
            _page(2, [_h("ARTICLE II", 0), _p("Second article body text here.", 1)]),
        ],
    )
    full = document_text(doc)
    for chunk in chunk_document(doc):
        assert full[chunk.char_start : chunk.char_end] == chunk.text


def test_page_range_spans_source_pages() -> None:
    doc = ParsedDocument(
        parser_name="test",
        parser_version="0",
        page_count=2,
        pages=[
            _page(1, [_h("ARTICLE I", 0), _p("body one " * 10, 1)]),
            _page(2, [_p("continues onto page two " * 10, 0)]),
        ],
    )
    chunks = chunk_document(doc, target_chars=100_000, max_chars=200_000)
    assert len(chunks) == 1
    assert chunks[0].page_from == 1
    assert chunks[0].page_to == 2


def test_long_section_is_split_at_target() -> None:
    body = [
        _p(f"Paragraph number {i} with some filler content to add length." * 3, i + 1)
        for i in range(20)
    ]
    doc = ParsedDocument(
        parser_name="test",
        parser_version="0",
        page_count=1,
        pages=[_page(1, [_h("ARTICLE X", 0), *body])],
    )
    chunks = chunk_document(doc, target_chars=400, max_chars=800)
    assert len(chunks) > 1
    assert all(c.section_path == "ARTICLE X" for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_nested_headings_build_a_path() -> None:
    doc = ParsedDocument(
        parser_name="test",
        parser_version="0",
        page_count=1,
        pages=[
            _page(
                1,
                [
                    _h("ARTICLE IV", 0, level=1),
                    _h("Section 4.2 - Reinstatements", 1, level=2),
                    _p("Two reinstatements at 100% additional premium.", 2),
                ],
            )
        ],
    )
    chunks = chunk_document(doc)
    assert chunks[-1].section_path == "ARTICLE IV > Section 4.2 - Reinstatements"


def test_empty_document() -> None:
    doc = ParsedDocument(parser_name="test", parser_version="0", page_count=0, pages=[])
    assert chunk_document(doc) == []
