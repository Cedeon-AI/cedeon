"""The investigator output schema + its grounding downgrade."""

from __future__ import annotations

from app.ai.investigator.schema import Finding, FindingCitation, RecoveryInvestigation
from app.domain.ai import ApplicabilityAssessment, FindingKind

_CITE = FindingCitation(
    page_number=2, section="ARTICLE IV", quoted_text="a retention of USD 50,000,000"
)


def _inv(findings: list[Finding]) -> RecoveryInvestigation:
    return RecoveryInvestigation(
        summary="s",
        applicability_assessment=ApplicabilityAssessment.SUPPORTED,
        findings=findings,
        overall_confidence=0.7,
    )


def test_cited_findings_survive_grounding() -> None:
    inv = _inv(
        [Finding(kind=FindingKind.RELEVANT_CLAUSE, text="x", citation=_CITE, confidence=0.9)]
    )
    inv.grounded()
    assert inv.findings[0].kind is FindingKind.RELEVANT_CLAUSE


def test_uncited_must_cite_finding_is_downgraded() -> None:
    inv = _inv(
        [Finding(kind=FindingKind.SUPPORTING_EVIDENCE, text="claim", citation=None, confidence=0.9)]
    )
    inv.grounded()
    assert inv.findings[0].kind is FindingKind.AMBIGUITY
    assert inv.findings[0].text.startswith("[uncited]")


def test_uncited_missing_information_is_left_alone() -> None:
    inv = _inv(
        [
            Finding(
                kind=FindingKind.MISSING_INFORMATION,
                text="no report",
                citation=None,
                confidence=0.8,
            )
        ]
    )
    inv.grounded()
    assert inv.findings[0].kind is FindingKind.MISSING_INFORMATION


def test_next_step_needs_no_citation() -> None:
    inv = _inv(
        [Finding(kind=FindingKind.NEXT_STEP, text="call the broker", citation=None, confidence=0.6)]
    )
    inv.grounded()
    assert inv.findings[0].kind is FindingKind.NEXT_STEP


def test_guardrail_defaults_are_safe() -> None:
    inv = _inv([])
    assert inv.recomputed_a_different_number is False
    assert inv.out_of_scope is False
    assert inv.suspected_prompt_injection is False
