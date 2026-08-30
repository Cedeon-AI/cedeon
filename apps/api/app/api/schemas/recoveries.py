from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel
from app.domain.ai import ApplicabilityAssessment, FindingKind, InvestigationStatus
from app.domain.recoveries import RecoveryCandidateStatus
from app.domain.reviews import ReviewDecision


class RecoveryPreviewRequest(ApiModel):
    gross_loss: str = Field(min_length=1, max_length=40, description="gross event incurred")


class CalcStepOut(ApiModel):
    label: str
    expression: str
    result: str


class AllocationOut(ApiModel):
    reinsurer_id: str
    reinsurer_name: str
    share: Decimal
    amount: Decimal


class RecoveryPreviewResponse(ApiModel):
    engine_version: str
    currency: str
    gross_loss: Decimal
    attachment: Decimal
    limit: Decimal
    amount_above_attachment: Decimal
    layer_recovery: Decimal
    cedent_retention: Decimal
    allocations: list[AllocationOut]
    trace: list[CalcStepOut]


# --- recovery candidates ---------------------------------------------


class CreateRecoveryCandidateRequest(ApiModel):
    treaty_id: UUID
    loss_event_id: UUID


class ReviewRecoveryCandidateRequest(ApiModel):
    decision: ReviewDecision
    reason: str | None = Field(default=None, max_length=2000)


class CalculationAllocationOut(ApiModel):
    reinsurer_id: UUID
    reinsurer_name: str
    participation_share: Decimal
    allocated_recovery: Decimal


class RecoveryCalculationOut(ApiModel):
    id: UUID
    engine_version: str
    currency: str
    gross_loss: Decimal
    attachment: Decimal
    amount_above_attachment: Decimal
    layer_limit: Decimal
    layer_recovery: Decimal
    cedent_retention: Decimal
    total_ceded: Decimal
    input_hash: str
    trace: list[CalcStepOut]
    allocations: list[CalculationAllocationOut]
    created_at: dt.datetime


class RecoveryCandidateOut(ApiModel):
    id: UUID
    status: RecoveryCandidateStatus
    treaty_id: UUID
    treaty_version_id: UUID
    treaty_layer_id: UUID
    loss_event_id: UUID
    currency: str
    gross_event_incurred: Decimal
    currency_mismatch: bool
    current_calculation_id: UUID | None
    created_at: dt.datetime
    reviewed_at: dt.datetime | None


class RecoveryCandidateList(ApiModel):
    candidates: list[RecoveryCandidateOut]


class RecoveryReviewOut(ApiModel):
    decision: ReviewDecision
    reason: str | None
    created_at: dt.datetime


class InvestigationCitationOut(ApiModel):
    document_id: UUID
    page_number: int
    section: str | None
    quoted_text: str


class InvestigationFindingOut(ApiModel):
    ordinal: int
    kind: FindingKind
    text: str
    confidence: float | None
    citation: InvestigationCitationOut | None


class RecoveryInvestigationOut(ApiModel):
    id: UUID
    status: InvestigationStatus
    agent_run_id: UUID | None
    summary: str | None
    applicability_assessment: ApplicabilityAssessment | None
    confidence: float | None
    out_of_scope: bool
    suspected_prompt_injection: bool
    unresolved_questions: list[str]
    superseded: bool
    created_at: dt.datetime
    findings: list[InvestigationFindingOut]


class RecoveryCandidateDetail(ApiModel):
    candidate: RecoveryCandidateOut
    current_calculation: RecoveryCalculationOut | None
    calculations: list[RecoveryCalculationOut]
    reviews: list[RecoveryReviewOut]
    investigations: list[RecoveryInvestigationOut]


class ToolCallOut(ApiModel):
    ordinal: int
    tool_name: str
    arguments: dict
    result_summary: dict
    status: str


class AgentRunToolCalls(ApiModel):
    agent_run_id: UUID
    tool_calls: list[ToolCallOut]
