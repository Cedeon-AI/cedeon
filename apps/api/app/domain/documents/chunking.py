"""Heading-aware chunking of a parsed document.

Pure: given a ``ParsedDocument`` it produces ordered chunks that each carry their
section path, page range and character offsets into the document's full text. A
new chunk starts at every heading and whenever the running size passes a target.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.documents.parsed import BlockType, ParsedBlock, ParsedDocument

_PAGE_SEPARATOR = "\n\n"
_BLOCK_SEPARATOR = "\n"


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    ordinal: int
    page_from: int
    page_to: int
    section_path: str
    heading: str | None
    text: str
    char_start: int
    char_end: int


def document_text(parsed: ParsedDocument) -> str:
    """The canonical full text that chunk offsets index into."""
    return _PAGE_SEPARATOR.join(page.text for page in parsed.pages)


@dataclass(slots=True)
class _Placed:
    block: ParsedBlock
    page_number: int
    start: int
    end: int


@dataclass(slots=True)
class _Buffer:
    section_path: str
    heading: str | None
    placed: list[_Placed] = field(default_factory=list)

    @property
    def size(self) -> int:
        return sum(len(p.block.text) for p in self.placed)


def chunk_document(
    parsed: ParsedDocument,
    *,
    target_chars: int = 1200,
    max_chars: int = 2400,
) -> list[DocumentChunk]:
    full_text = document_text(parsed)
    placed = list(_place_blocks(parsed))
    chunks: list[DocumentChunk] = []
    section_stack: list[tuple[int, str]] = []  # (level, heading text)
    buffer = _Buffer(section_path="", heading=None)

    def flush() -> None:
        nonlocal buffer
        if not buffer.placed:
            return
        first, last = buffer.placed[0], buffer.placed[-1]
        chunks.append(
            DocumentChunk(
                ordinal=len(chunks),
                page_from=first.page_number,
                page_to=last.page_number,
                section_path=buffer.section_path,
                heading=buffer.heading,
                text=full_text[first.start : last.end],
                char_start=first.start,
                char_end=last.end,
            )
        )
        buffer = _Buffer(section_path=_join_stack(section_stack), heading=_top(section_stack))

    for item in placed:
        block = item.block
        if block.block_type is BlockType.HEADING:
            flush()
            level = block.level or 1
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()
            section_stack.append((level, block.text))
            buffer.section_path = _join_stack(section_stack)
            buffer.heading = block.text
            buffer.placed.append(item)
            continue

        if buffer.size and buffer.size + len(block.text) > max_chars:
            flush()
        buffer.placed.append(item)
        if buffer.size >= target_chars:
            flush()

    flush()
    return chunks


def _place_blocks(parsed: ParsedDocument) -> list[_Placed]:
    out: list[_Placed] = []
    cursor = 0
    for page_index, page in enumerate(parsed.pages):
        if page_index > 0:
            cursor += len(_PAGE_SEPARATOR)
        for block_index, block in enumerate(page.blocks):
            if block_index > 0:
                cursor += len(_BLOCK_SEPARATOR)
            start = cursor
            end = start + len(block.text)
            out.append(_Placed(block=block, page_number=page.page_number, start=start, end=end))
            cursor = end
    return out


def _join_stack(stack: list[tuple[int, str]]) -> str:
    return " > ".join(text for _, text in stack)


def _top(stack: list[tuple[int, str]]) -> str | None:
    return stack[-1][1] if stack else None
