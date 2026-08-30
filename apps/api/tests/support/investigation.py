"""A canned Recovery Investigator result — lets the persist / grounding / audit
flow be tested without calling a model."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ai.investigator.runner import InvestigationResult, ToolCallLog
from app.ai.investigator.schema import (
    Finding,
    FindingCitation,
    RecoveryInvestigation,
)
from app.domain.ai import ApplicabilityAssessment, FindingKind, ToolCallStatus


def golden_investigation(*, layer_recovery: str = "8700000.00") -> RecoveryInvestigation:
    return RecoveryInvestigation(
        summary=(
            "The 2027 property catastrophe layer responds: Hurricane Demo's gross "
            "incurred exceeds the USD 50,000,000 retention and the recovery is capped "
            "by the USD 20,000,000 limit."
        ),
        applicability_assessment=ApplicabilityAssessment.SUPPORTED,
        findings=[
            Finding(
                kind=FindingKind.RELEVANT_CLAUSE,
                text="Article IV sets a USD 50,000,000 retention and a USD 20,000,000 limit.",
                citation=FindingCitation(
                    page_number=2,
                    section="ARTICLE IV - LIMIT AND RETENTION",
                    quoted_text="a retention of USD 50,000,000",
                ),
                confidence=0.95,
            ),
            Finding(
                kind=FindingKind.NOTICE_OBLIGATION,
                text="Notice is due within 30 days of a reserve reaching 50% of the retention.",
                citation=FindingCitation(
                    page_number=3,
                    section="ARTICLE VII - NOTICE OF LOSS",
                    quoted_text="within 30 days of the Company establishing a reserve",
                ),
                confidence=0.9,
            ),
            Finding(
                kind=FindingKind.SUPPORTING_EVIDENCE,
                text="A subrogation waiver removes the reinsurer's recovery rights.",
                citation=FindingCitation(
                    page_number=1,
                    section=None,
                    quoted_text="the Reinsurer waives all rights of subrogation",  # not in the doc
                ),
                confidence=0.4,
            ),
            Finding(
                kind=FindingKind.MISSING_INFORMATION,
                text="The loss adjuster's report for the largest claims is not attached.",
                citation=None,
                confidence=0.8,
            ),
        ],
        unresolved_questions=["Is any claim still developing above the layer?"],
        overall_confidence=0.82,
        recovery_amount_reviewed=layer_recovery,
        recomputed_a_different_number=False,
        out_of_scope=False,
        suspected_prompt_injection=False,
    )


def golden_result(*, layer_recovery: str = "8700000.00") -> InvestigationResult:
    investigation = golden_investigation(layer_recovery=layer_recovery).grounded()
    return InvestigationResult(
        investigation=investigation,
        provider="anthropic",
        model="anthropic:claude-opus-5",
        prompt_version="recovery-investigator/v1",
        input_tokens=4200,
        output_tokens=900,
        cost_usd=Decimal("0.031000"),
        latency_ms=6100,
        tool_calls=[
            ToolCallLog(
                ordinal=1,
                tool_name="get_recovery_calculation",
                arguments={},
                result_summary={"keys": ["layer_recovery"], "error": None},
                status=ToolCallStatus.OK,
            ),
            ToolCallLog(
                ordinal=2,
                tool_name="search_treaty",
                arguments={"query": "retention limit each occurrence", "k": 3},
                result_summary={"count": 3},
                status=ToolCallStatus.OK,
            ),
        ],
        output=investigation.model_dump(mode="json"),
    )


async def run_investigation(
    session: object, settings: object, org_id: object, candidate_id: object
):
    from app.services.investigation import InvestigationService

    async def _fake(**_kwargs: Any) -> InvestigationResult:
        return golden_result()

    service = InvestigationService(session, settings, runner=_fake)  # type: ignore[arg-type]
    return await service.investigate(org_id, candidate_id)  # type: ignore[arg-type]
