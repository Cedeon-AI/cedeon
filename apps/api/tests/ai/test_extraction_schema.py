"""Pure tests for the extraction output contract. No model call."""

from __future__ import annotations

import pytest

from app.ai.extraction.schema import (
    Provenance,
    TermCandidate,
    TermCandidateStatus,
    TreatyExtraction,
)


def _term(key: str, *, status: TermCandidateStatus, cited: bool) -> TermCandidate:
    return TermCandidate(
        key=key,
        status=status,
        value="50000000.00",
        currency="USD",
        confidence=0.9,
        provenance=(
            Provenance(page_number=2, section="Article IV", quoted_text="USD 50,000,000")
            if cited
            else None
        ),
        reasoning="x",
    )


def test_uncited_material_term_is_downgraded_to_ambiguous() -> None:
    extraction = TreatyExtraction(
        is_excess_of_loss=True,
        summary="s",
        terms=[
            _term("attachment", status=TermCandidateStatus.EXTRACTED, cited=False),
            _term("limit", status=TermCandidateStatus.EXTRACTED, cited=True),
        ],
    )
    extraction.downgrade_uncited_material_terms()
    by_key = {t.key: t for t in extraction.terms}
    assert by_key["attachment"].status is TermCandidateStatus.AMBIGUOUS
    assert by_key["limit"].status is TermCandidateStatus.EXTRACTED


def test_non_material_uncited_term_is_left_alone() -> None:
    extraction = TreatyExtraction(
        is_excess_of_loss=True,
        summary="s",
        terms=[_term("notice_provision", status=TermCandidateStatus.EXTRACTED, cited=False)],
    )
    extraction.downgrade_uncited_material_terms()
    assert extraction.terms[0].status is TermCandidateStatus.EXTRACTED


def test_confidence_is_bounded() -> None:
    with pytest.raises(ValueError):
        TermCandidate(
            key="limit", status=TermCandidateStatus.EXTRACTED, confidence=1.5, reasoning="x"
        )


def test_provenance_requires_a_page() -> None:
    with pytest.raises(ValueError):
        Provenance(page_number=0, quoted_text="x")


def test_prompt_and_model_defaults_are_configured() -> None:
    from app.ai.prompts import TREATY_EXTRACTION_PROMPT_VERSION
    from app.core.config import Settings

    assert TREATY_EXTRACTION_PROMPT_VERSION.startswith("treaty-extraction/")
    assert Settings().treaty_extraction_model.startswith("anthropic:")
