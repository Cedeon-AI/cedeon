"""Typed output of the Recovery Investigator.

The agent investigates a recovery candidate: does the treaty respond, what
supports it, what is missing, what is ambiguous, what notice is owed. It is handed
the deterministic recovery figure as a **fact to explain or challenge** — it never
recomputes it (docs/AI_ARCHITECTURE.md §2b, ADR-0010)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.ai import ApplicabilityAssessment, FindingKind


class FindingCitation(BaseModel):
    page_number: int = Field(ge=1, description="1-based page the supporting text is on")
    section: str | None = Field(default=None, description="article / heading, if identifiable")
    quoted_text: str = Field(
        max_length=600, description="verbatim span from the treaty that supports this finding"
    )


class Finding(BaseModel):
    kind: FindingKind
    text: str = Field(description="one clear sentence; plain, for a reinsurance reviewer")
    citation: FindingCitation | None = Field(
        default=None,
        description="required for relevant_clause / supporting_evidence / notice_obligation; "
        "omit only for missing_information and next_step",
    )
    confidence: float = Field(ge=0, le=1)


class RecoveryInvestigation(BaseModel):
    summary: str = Field(description="2-4 sentences: does the treaty respond to this loss, and why")
    applicability_assessment: ApplicabilityAssessment
    findings: list[Finding] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0, le=1)

    # Guardrail signals — checked by post-processing and the eval suite.
    recovery_amount_reviewed: str | None = Field(
        default=None,
        description="echo back the deterministic layer-recovery amount you were given, "
        "as a plain decimal string. Do not change it.",
    )
    recomputed_a_different_number: bool = Field(
        default=False,
        description="true ONLY if you think the deterministic figure is wrong; explain in summary",
    )
    out_of_scope: bool = Field(
        default=False,
        description="true if the question requires a treaty structure Cedeon does not model "
        "(anything other than per-occurrence excess of loss)",
    )
    suspected_prompt_injection: bool = Field(default=False)
    injection_note: str | None = None

    def grounded(self) -> RecoveryInvestigation:
        """A finding that should cite but doesn't is downgraded to an ambiguity — a
        conclusion without evidence is not a conclusion (docs/AI_ARCHITECTURE.md §7)."""
        must_cite = {
            FindingKind.RELEVANT_CLAUSE,
            FindingKind.SUPPORTING_EVIDENCE,
            FindingKind.NOTICE_OBLIGATION,
            FindingKind.INCONSISTENCY,
        }
        for finding in self.findings:
            if finding.kind in must_cite and finding.citation is None:
                finding.kind = FindingKind.AMBIGUITY
                finding.text = f"[uncited] {finding.text}"
        return self
