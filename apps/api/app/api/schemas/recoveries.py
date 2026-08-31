from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel
from app.domain.ai import ApplicabilityAssessment, FindingKind, InvestigationStatus
from app.domain.recoveries import (
    NoticeKind,
    NoticeStatus,
    PacketStatementClass,
    PacketVersionStatus,
    RecoverableStatus,
    RecoveryCandidateStatus,
)
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
    knowledge_date: dt.date | None
    created_at: dt.datetime
    reviewed_at: dt.datetime | None


class RecoveryCandidateList(ApiModel):
    candidates: list[RecoveryCandidateOut]


class SetKnowledgeDateRequest(ApiModel):
    knowledge_date: dt.date | None = Field(
        default=None, description="date the cedent knew a loss was likely to involve this treaty"
    )


class NoticeObligationOut(ApiModel):
    provision_text: str | None
    has_structured_term: bool
    period_days: int | None
    trigger: str | None
    basis: str | None
    reference_date: dt.date | None
    reference_label: str | None
    deadline: dt.date | None
    days_until: int | None
    satisfied: bool
    satisfied_on: dt.date | None
    note: str | None


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
    notice_obligation: NoticeObligationOut | None


class ToolCallOut(ApiModel):
    ordinal: int
    tool_name: str
    arguments: dict
    result_summary: dict
    status: str


class AgentRunToolCalls(ApiModel):
    agent_run_id: UUID
    tool_calls: list[ToolCallOut]


# --- recovery packet ------------------------------------------------


class PacketCitationOut(ApiModel):
    document_id: str | None
    page_number: int | None
    section: str | None
    quoted_text: str | None


class PacketStatementOut(ApiModel):
    key: str
    statement_class: PacketStatementClass
    text: str
    citation: PacketCitationOut | None
    detail: dict[str, str]
    edited_by_human: bool


class PacketSectionOut(ApiModel):
    key: str
    title: str
    statements: list[PacketStatementOut]


class PacketContentOut(ApiModel):
    title: str
    subtitle: str
    generated_at: str
    engine_version: str
    sections: list[PacketSectionOut]


class RecoveryPacketVersionOut(ApiModel):
    id: UUID
    version_no: int
    status: PacketVersionStatus
    calculation_id: UUID
    investigation_id: UUID | None
    review_note: str | None
    approved_at: dt.datetime | None
    superseded: bool
    created_at: dt.datetime
    content: PacketContentOut


class RecoveryPacketVersionSummary(ApiModel):
    id: UUID
    version_no: int
    status: PacketVersionStatus
    superseded: bool
    created_at: dt.datetime


class RecoveryPacketDetail(ApiModel):
    packet_id: UUID
    recovery_candidate_id: UUID
    human_overrides: dict[str, dict[str, str]]
    current_version: RecoveryPacketVersionOut | None
    versions: list[RecoveryPacketVersionSummary]


class GeneratePacketResponse(ApiModel):
    packet_id: UUID
    version: RecoveryPacketVersionOut


class PacketReviewRequest(ApiModel):
    decision: ReviewDecision
    reason: str | None = Field(default=None, max_length=2000)
    statement_key: str | None = Field(default=None, max_length=120)
    value: str | None = Field(default=None, max_length=2000)


# --- recovery notice -----------------------------------------------


class NoticeRecipientModel(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    organisation: str = Field(min_length=1, max_length=200)
    role: str = Field(default="", max_length=150)
    email: str = Field(default="", max_length=200)


class DraftNoticeRequest(ApiModel):
    kind: NoticeKind
    recipient: NoticeRecipientModel


class NoticeReviewRequest(ApiModel):
    decision: ReviewDecision
    subject: str | None = Field(default=None, max_length=300)
    body_markdown: str | None = Field(default=None, max_length=20000)
    recipient: NoticeRecipientModel | None = None
    reason: str | None = Field(default=None, max_length=2000)


class RecoveryNoticeOut(ApiModel):
    id: UUID
    recovery_candidate_id: UUID
    kind: NoticeKind
    status: NoticeStatus
    recipient: dict[str, str]
    subject: str
    body_markdown: str
    key_figures: dict[str, str]
    caveats: list[str]
    used_only_provided_facts: bool
    notes_for_reviewer: str | None
    context: dict
    agent_run_id: UUID | None
    recovery_packet_version_id: UUID | None
    review_note: str | None
    approved_at: dt.datetime | None
    superseded: bool
    created_at: dt.datetime


class RecoveryNoticeList(ApiModel):
    notices: list[RecoveryNoticeOut]


# --- collection tracking (ADR-0024) -------------------------------------------


class RecoverableOut(ApiModel):
    id: UUID
    recovery_candidate_id: UUID
    reinsurer_id: UUID
    reinsurer_name: str
    currency: str
    status: RecoverableStatus
    expected_amount: Decimal
    agreed_amount: Decimal | None
    billed_amount: Decimal | None
    collected_amount: Decimal
    outstanding: Decimal
    due_date: dt.date | None
    days_overdue: int
    aging_bucket: str
    notified_at: dt.datetime | None
    agreed_at: dt.datetime | None
    billed_at: dt.datetime | None
    settled_at: dt.datetime | None
    note: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class RecoverableList(ApiModel):
    recoverables: list[RecoverableOut]


class RecoverableUpdateRequest(ApiModel):
    status: RecoverableStatus | None = None
    agreed_amount: str | None = None
    billed_amount: str | None = None
    collect: str | None = Field(default=None, description="A positive amount just collected")
    due_date: dt.date | None = None
    clear_due_date: bool = False
    note: str | None = None


class RecoverableStatusTotalOut(ApiModel):
    status: RecoverableStatus
    count: int
    outstanding: Decimal


class RecoverableSummaryOut(ApiModel):
    currency: str
    count: int
    total_expected: Decimal
    total_collected: Decimal
    total_outstanding: Decimal
    overdue_count: int
    overdue_outstanding: Decimal
    by_status: list[RecoverableStatusTotalOut]
    by_aging: dict[str, Decimal]
