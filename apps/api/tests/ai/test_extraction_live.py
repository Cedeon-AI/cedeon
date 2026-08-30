"""Live extraction against the configured LLM provider. Skipped by default
(marked ``live``); run with:  uv run pytest -m live

Requires ANTHROPIC_API_KEY (+ ANTHROPIC_WORKSPACE_ID if the key is workspace-scoped)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.ai.extraction import extract_treaty_terms
from app.ai.extraction.schema import TermCandidateStatus
from app.core.config import get_settings
from app.domain.documents import chunk_document
from app.parsing import PyMuPDFParser
from tests.support.pdfs import build_treaty_pdf

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not get_settings().anthropic_api_key, reason="ANTHROPIC_API_KEY is not configured"
)
async def test_extracts_the_synthetic_treaty() -> None:
    settings = get_settings()
    parsed = await PyMuPDFParser().parse(
        build_treaty_pdf(), filename="treaty.pdf", content_type="application/pdf"
    )
    blocks = [f"[page {c.page_from}] {c.section_path}\n{c.text}" for c in chunk_document(parsed)]

    result = await extract_treaty_terms(document_blocks=blocks, settings=settings)
    extraction = result.extraction

    assert extraction.is_excess_of_loss
    assert (extraction.currency or "").upper() == "USD"
    assert not extraction.suspected_prompt_injection

    by_key = {t.key: t for t in extraction.terms}
    assert by_key["attachment"].status is TermCandidateStatus.EXTRACTED
    assert Decimal(by_key["attachment"].value or "0") == Decimal("50000000.00")
    assert by_key["attachment"].provenance is not None
    assert "50,000,000" in by_key["attachment"].provenance.quoted_text

    assert Decimal(by_key["limit"].value or "0") == Decimal("20000000.00")

    shares = {p.reinsurer_name.lower(): p.placed_share_percent for p in extraction.participations}
    assert any("alpha" in name for name in shares)
    assert abs(sum(shares.values()) - 100.0) < 1.0

    assert result.input_tokens and result.output_tokens
