"""A canned extraction result for the synthetic treaty — lets the whole
review → validate flow be tested without calling a model."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.ai.extraction import ExtractionResult
from app.ai.extraction.schema import (
    ParticipationCandidate,
    Provenance,
    TermCandidate,
    TermCandidateStatus,
    TreatyExtraction,
)
from app.services.extraction import TreatyExtractionService


def golden_extraction() -> TreatyExtraction:
    return TreatyExtraction(
        is_excess_of_loss=True,
        currency="USD",
        terms=[
            TermCandidate(
                key="attachment",
                status=TermCandidateStatus.EXTRACTED,
                value="50000000.00",
                currency="USD",
                confidence=0.95,
                provenance=Provenance(
                    page_number=2,
                    section="ARTICLE IV - LIMIT AND RETENTION",
                    quoted_text="a retention of USD 50,000,000 each and every loss occurrence",
                ),
                reasoning="Stated retention.",
            ),
            TermCandidate(
                key="limit",
                status=TermCandidateStatus.EXTRACTED,
                value="20000000.00",
                currency="USD",
                confidence=0.95,
                provenance=Provenance(
                    page_number=2,
                    section="ARTICLE IV - LIMIT AND RETENTION",
                    quoted_text="shall not exceed USD 20,000,000 each and every loss occurrence",
                ),
                reasoning="Stated limit.",
            ),
            TermCandidate(
                key="notice_provision",
                status=TermCandidateStatus.EXTRACTED,
                value="within 30 days of a reserve >= 50% of the retention",
                confidence=0.8,
                provenance=Provenance(
                    page_number=3,
                    section="ARTICLE VII - NOTICE OF LOSS",
                    quoted_text="within 30 days of the Company establishing a reserve",
                ),
                reasoning="Notice clause.",
            ),
        ],
        participations=[
            ParticipationCandidate(
                reinsurer_name="Reinsurer Alpha", placed_share_percent=50.0, confidence=0.9
            ),
            ParticipationCandidate(
                reinsurer_name="Reinsurer Beta", placed_share_percent=30.0, confidence=0.9
            ),
            ParticipationCandidate(
                reinsurer_name="Reinsurer Gamma", placed_share_percent=20.0, confidence=0.9
            ),
        ],
        suspected_prompt_injection=False,
        summary="Property catastrophe XOL, USD 20M xs USD 50M each occurrence.",
    )


def golden_result() -> ExtractionResult:
    extraction = golden_extraction()
    return ExtractionResult(
        extraction=extraction,
        provider="anthropic",
        model="anthropic:claude-opus-5",
        prompt_version="treaty-extraction/v1",
        input_tokens=1200,
        output_tokens=400,
        cost_usd=Decimal("0.012000"),
        latency_ms=1234,
        output=extraction.model_dump(mode="json"),
    )


async def run_extraction(
    session: object,
    settings: object,
    org_id: UUID,
    version_id: UUID,
    *,
    extraction: TreatyExtraction | None = None,
) -> object:
    result = golden_result()
    if extraction is not None:
        result = ExtractionResult(
            extraction=extraction,
            provider=result.provider,
            model=result.model,
            prompt_version=result.prompt_version,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
            output=extraction.model_dump(mode="json"),
        )

    async def _fake(**_kwargs: object) -> ExtractionResult:
        return result

    service = TreatyExtractionService(session, settings, extractor=_fake)  # type: ignore[arg-type]
    return await service.run(org_id, version_id)
