"""Recovery candidates: turn a validated treaty + a loss event into a reviewable,
deterministically-calculated recovery. No AI in this module (ADR-0010)."""

from __future__ import annotations

import datetime as dt
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import HTMLResponse

from app.api.dependencies.context import (
    AppSettings,
    AuthedContext,
    DbSession,
    InvestigateEnqueuer,
    NoticeEnqueuer,
    get_investigate_enqueuer,
    get_notice_enqueuer,
)
from app.api.schemas.recoveries import (
    AgentRunToolCalls,
    CalcStepOut,
    CalculationAllocationOut,
    CreateRecoveryCandidateRequest,
    DraftNoticeRequest,
    GeneratePacketResponse,
    InvestigationCitationOut,
    InvestigationFindingOut,
    NoticeObligationOut,
    NoticeReviewRequest,
    PacketCitationOut,
    PacketContentOut,
    PacketReviewRequest,
    PacketSectionOut,
    PacketStatementOut,
    RecoverableList,
    RecoverableOut,
    RecoverableStatusTotalOut,
    RecoverableSummaryOut,
    RecoverableUpdateRequest,
    RecoveryCalculationOut,
    RecoveryCandidateDetail,
    RecoveryCandidateList,
    RecoveryCandidateOut,
    RecoveryInvestigationOut,
    RecoveryNoticeList,
    RecoveryNoticeOut,
    RecoveryPacketDetail,
    RecoveryPacketVersionOut,
    RecoveryPacketVersionSummary,
    RecoveryReviewOut,
    ReviewRecoveryCandidateRequest,
    SetKnowledgeDateRequest,
    SuggestedRecoveryList,
    SuggestedRecoveryOut,
    ToolCallOut,
)
from app.db.models.extraction import Review, ToolCall
from app.db.models.recoveries import (
    Recoverable,
    RecoveryCalculation,
    RecoveryCandidate,
    RecoveryInvestigation,
    RecoveryNotice,
    RecoveryPacket,
    RecoveryPacketVersion,
)
from app.domain.recoveries import (
    RecoverableStatus,
    RecoveryCandidateStatus,
    aging_bucket,
    days_overdue,
    outstanding,
)
from app.domain.recoveries.chasing import entered_status_on, recommend_chase
from app.services.collection import CollectionService
from app.services.errors import ConflictError
from app.services.investigation import InvestigationService
from app.services.notice import NoticeReview, NoticeService
from app.services.obligations import NoticeObligation, ObligationService
from app.services.packet import PacketReview, RecoveryPacketService
from app.services.recoveries import RecoveryCandidateService
from app.services.suggestions import SuggestionService

router = APIRouter(prefix="/recovery-candidates", tags=["recovery-candidates"])
packets_router = APIRouter(prefix="/recovery-packets", tags=["recovery-packets"])
notices_router = APIRouter(prefix="/recovery-notices", tags=["recovery-notices"])
recoverables_router = APIRouter(prefix="/recoverables", tags=["recoverables"])


def _candidate_out(candidate: RecoveryCandidate) -> RecoveryCandidateOut:
    return RecoveryCandidateOut(
        id=candidate.id,
        status=candidate.status,
        treaty_id=candidate.treaty_id,
        treaty_version_id=candidate.treaty_version_id,
        treaty_layer_id=candidate.treaty_layer_id,
        loss_event_id=candidate.loss_event_id,
        currency=candidate.currency,
        gross_event_incurred=candidate.gross_event_incurred,
        currency_mismatch=candidate.currency_mismatch,
        current_calculation_id=candidate.current_calculation_id,
        knowledge_date=candidate.knowledge_date,
        drifted_at=candidate.drifted_at,
        pre_drift_recovery=candidate.pre_drift_recovery,
        created_at=candidate.created_at,
        reviewed_at=candidate.reviewed_at,
    )


def _obligation_out(ob: NoticeObligation | None) -> NoticeObligationOut | None:
    if ob is None:
        return None
    return NoticeObligationOut(
        provision_text=ob.provision_text,
        has_structured_term=ob.spec is not None,
        period_days=ob.spec.days if ob.spec is not None else None,
        trigger=ob.spec.trigger.value if ob.spec is not None else None,
        basis=ob.spec.basis.value if ob.spec is not None else None,
        reference_date=ob.reference_date,
        reference_label=ob.reference_label,
        deadline=ob.deadline,
        days_until=ob.days_until,
        satisfied=ob.satisfied,
        satisfied_on=ob.satisfied_on,
        note=ob.note,
    )


def _calculation_out(calc: RecoveryCalculation) -> RecoveryCalculationOut:
    return RecoveryCalculationOut(
        id=calc.id,
        engine_version=calc.engine_version,
        currency=calc.currency,
        gross_loss=calc.gross_loss,
        attachment=calc.attachment,
        amount_above_attachment=calc.amount_above_attachment,
        layer_limit=calc.layer_limit,
        layer_recovery=calc.layer_recovery,
        cedent_retention=calc.cedent_retention,
        total_ceded=calc.total_ceded,
        input_hash=calc.input_hash,
        trace=[
            CalcStepOut(label=s["label"], expression=s["expression"], result=s["result"])
            for s in calc.trace
        ],
        allocations=[
            CalculationAllocationOut(
                reinsurer_id=a.reinsurer_id,
                reinsurer_name=a.reinsurer.name,
                participation_share=a.participation_share,
                allocated_recovery=a.allocated_recovery,
            )
            for a in calc.allocations
        ],
        created_at=calc.created_at,
    )


def _review_out(review: Review) -> RecoveryReviewOut:
    return RecoveryReviewOut(
        decision=review.decision, reason=review.reason, created_at=review.created_at
    )


def _investigation_out(inv: RecoveryInvestigation) -> RecoveryInvestigationOut:
    return RecoveryInvestigationOut(
        id=inv.id,
        status=inv.status,
        agent_run_id=inv.agent_run_id,
        summary=inv.summary,
        applicability_assessment=inv.applicability_assessment,
        confidence=float(inv.confidence) if inv.confidence is not None else None,
        out_of_scope=inv.out_of_scope,
        suspected_prompt_injection=inv.suspected_prompt_injection,
        unresolved_questions=list(inv.unresolved_questions),
        superseded=inv.superseded_at is not None,
        created_at=inv.created_at,
        findings=[
            InvestigationFindingOut(
                ordinal=f.ordinal,
                kind=f.kind,
                text=f.text,
                confidence=float(f.confidence) if f.confidence is not None else None,
                citation=(
                    InvestigationCitationOut(
                        document_id=f.citation.document_id,
                        page_number=f.citation.page_number,
                        section=f.citation.section,
                        quoted_text=f.citation.quoted_text,
                    )
                    if f.citation is not None
                    else None
                ),
            )
            for f in inv.findings
        ],
    )


def _tool_call_out(call: ToolCall) -> ToolCallOut:
    return ToolCallOut(
        ordinal=call.ordinal,
        tool_name=call.tool_name,
        arguments=dict(call.arguments),
        result_summary=dict(call.result_summary),
        status=call.status.value,
    )


@router.post(
    "",
    response_model=RecoveryCandidateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Open a recovery for every treaty layer that responds (returns the bottom layer)",
    operation_id="createRecoveryCandidate",
)
async def create_recovery_candidate(
    payload: CreateRecoveryCandidateRequest, context: AuthedContext, session: DbSession
) -> RecoveryCandidateOut:
    # A multi-layer treaty opens one candidate per responding layer; the bottom
    # one is returned here, the rest surface on the recoveries list and the
    # loss-event page (grouped by event).
    candidates = await RecoveryCandidateService(session).create(
        context, treaty_id=payload.treaty_id, loss_event_id=payload.loss_event_id
    )
    return _candidate_out(candidates[0])


@router.get("", response_model=RecoveryCandidateList, operation_id="listRecoveryCandidates")
async def list_recovery_candidates(
    context: AuthedContext,
    session: DbSession,
    status_filter: Annotated[RecoveryCandidateStatus | None, Query(alias="status")] = None,
) -> RecoveryCandidateList:
    candidates = await RecoveryCandidateService(session).list_candidates(
        context, status=status_filter
    )
    return RecoveryCandidateList(candidates=[_candidate_out(c) for c in candidates])


@router.get(
    "/suggestions",
    response_model=SuggestedRecoveryList,
    summary="Validated treaties that look like they respond to a loss event, with no recovery yet",
    operation_id="listRecoverySuggestions",
)
async def list_recovery_suggestions(
    context: AuthedContext,
    session: DbSession,
    loss_event_id: Annotated[UUID | None, Query()] = None,
) -> SuggestedRecoveryList:
    found = await SuggestionService(session).for_organization(context)
    return SuggestedRecoveryList(
        suggestions=[
            SuggestedRecoveryOut(
                treaty_id=s.treaty_id,
                treaty_name=s.treaty_name,
                loss_event_id=s.loss_event_id,
                loss_event_name=s.loss_event_name,
                currency=s.suggestion.currency,
                gross=s.suggestion.gross,
                attachment=s.suggestion.attachment,
                limit=s.suggestion.limit,
                indicative_recovery=s.suggestion.indicative_recovery,
                reason=s.suggestion.reason,
            )
            for s in found
            if loss_event_id is None or s.loss_event_id == loss_event_id
        ]
    )


@router.get(
    "/{candidate_id}", response_model=RecoveryCandidateDetail, operation_id="getRecoveryCandidate"
)
async def get_recovery_candidate(
    candidate_id: UUID, context: AuthedContext, session: DbSession, settings: AppSettings
) -> RecoveryCandidateDetail:
    service = RecoveryCandidateService(session)
    candidate = await service.get_candidate(context, candidate_id)
    reviews = await service.candidate_reviews(context, candidate_id)
    current = service.current_calculation(candidate)
    investigations = await InvestigationService(session, settings).list_for_candidate(
        context, candidate_id
    )
    obligation = await ObligationService(session).for_candidate(context, candidate)
    return RecoveryCandidateDetail(
        candidate=_candidate_out(candidate),
        current_calculation=_calculation_out(current) if current else None,
        calculations=[
            _calculation_out(c)
            for c in sorted(candidate.calculations, key=lambda x: x.created_at, reverse=True)
        ],
        reviews=[_review_out(r) for r in reviews],
        investigations=[_investigation_out(i) for i in investigations],
        notice_obligation=_obligation_out(obligation),
    )


@router.post(
    "/{candidate_id}/knowledge-date",
    response_model=RecoveryCandidateOut,
    summary="Set the date the cedent knew a loss was likely to involve this treaty",
    operation_id="setRecoveryKnowledgeDate",
)
async def set_recovery_knowledge_date(
    candidate_id: UUID,
    payload: SetKnowledgeDateRequest,
    context: AuthedContext,
    session: DbSession,
) -> RecoveryCandidateOut:
    candidate = await ObligationService(session).set_knowledge_date(
        context, candidate_id, payload.knowledge_date
    )
    return _candidate_out(candidate)


@router.post(
    "/{candidate_id}/recalculate",
    response_model=RecoveryCandidateOut,
    summary="Re-run the engine; a new immutable calculation is stored only if inputs changed",
    operation_id="recalculateRecoveryCandidate",
)
async def recalculate_recovery_candidate(
    candidate_id: UUID, context: AuthedContext, session: DbSession
) -> RecoveryCandidateOut:
    candidate = await RecoveryCandidateService(session).recalculate(context, candidate_id)
    return _candidate_out(candidate)


@router.post(
    "/{candidate_id}/review",
    response_model=RecoveryCandidateOut,
    summary="Human decision: confirm | reject | request_info",
    operation_id="reviewRecoveryCandidate",
)
async def review_recovery_candidate(
    candidate_id: UUID,
    payload: ReviewRecoveryCandidateRequest,
    context: AuthedContext,
    session: DbSession,
) -> RecoveryCandidateOut:
    candidate = await RecoveryCandidateService(session).review(
        context, candidate_id, decision=payload.decision, reason=payload.reason
    )
    return _candidate_out(candidate)


@router.post(
    "/{candidate_id}/investigate",
    response_model=RecoveryCandidateOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue the Recovery Investigator (bounded, read-only AI — never computes the recovery)",
    operation_id="investigateRecoveryCandidate",
)
async def investigate_recovery_candidate(
    candidate_id: UUID,
    context: AuthedContext,
    session: DbSession,
    settings: AppSettings,
    enqueue: Annotated[InvestigateEnqueuer, Depends(get_investigate_enqueuer)],
) -> RecoveryCandidateOut:
    if not settings.ai_enabled:
        raise ConflictError("AI is disabled in this environment")
    # Surfaces 404 / 409 before the job is queued.
    candidate = await RecoveryCandidateService(session).get_candidate(context, candidate_id)
    if candidate.current_calculation_id is None:
        raise ConflictError("the candidate has no calculation to investigate")
    await enqueue(context.organization.id, candidate.id, context.user.id)
    return _candidate_out(candidate)


@router.get(
    "/{candidate_id}/agent-runs/{agent_run_id}/tool-calls",
    response_model=AgentRunToolCalls,
    operation_id="getRecoveryAgentToolCalls",
)
async def get_recovery_agent_tool_calls(
    candidate_id: UUID,
    agent_run_id: UUID,
    context: AuthedContext,
    session: DbSession,
    settings: AppSettings,
) -> AgentRunToolCalls:
    calls = await InvestigationService(session, settings).tool_calls(context, agent_run_id)
    return AgentRunToolCalls(
        agent_run_id=agent_run_id, tool_calls=[_tool_call_out(c) for c in calls]
    )


# --- recovery packet ----------------------------------------------


def _packet_content_out(content: dict) -> PacketContentOut:
    return PacketContentOut(
        title=content["title"],
        subtitle=content["subtitle"],
        generated_at=content["generated_at"],
        engine_version=content["engine_version"],
        sections=[
            PacketSectionOut(
                key=section["key"],
                title=section["title"],
                statements=[
                    PacketStatementOut(
                        key=s["key"],
                        statement_class=s["statement_class"],
                        text=s["text"],
                        citation=(PacketCitationOut(**s["citation"]) if s["citation"] else None),
                        detail=s.get("detail", {}),
                        edited_by_human=s.get("edited_by_human", False),
                    )
                    for s in section["statements"]
                ],
            )
            for section in content["sections"]
        ],
    )


def _packet_version_out(version: RecoveryPacketVersion) -> RecoveryPacketVersionOut:
    return RecoveryPacketVersionOut(
        id=version.id,
        version_no=version.version_no,
        status=version.status,
        calculation_id=version.calculation_id,
        investigation_id=version.investigation_id,
        review_note=version.review_note,
        approved_at=version.approved_at,
        superseded=version.superseded_at is not None,
        created_at=version.created_at,
        content=_packet_content_out(version.content),
    )


def _packet_detail(
    packet: RecoveryPacket, current: RecoveryPacketVersion | None
) -> RecoveryPacketDetail:
    return RecoveryPacketDetail(
        packet_id=packet.id,
        recovery_candidate_id=packet.recovery_candidate_id,
        human_overrides=dict(packet.human_overrides),
        current_version=_packet_version_out(current) if current else None,
        versions=[
            RecoveryPacketVersionSummary(
                id=v.id,
                version_no=v.version_no,
                status=v.status,
                superseded=v.superseded_at is not None,
                created_at=v.created_at,
            )
            for v in sorted(packet.versions, key=lambda x: x.version_no, reverse=True)
        ],
    )


@router.post(
    "/{candidate_id}/packet",
    response_model=GeneratePacketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assemble a recovery packet (a new immutable version each time)",
    operation_id="generateRecoveryPacket",
)
async def generate_recovery_packet(
    candidate_id: UUID, context: AuthedContext, session: DbSession
) -> GeneratePacketResponse:
    version = await RecoveryPacketService(session).generate(context, candidate_id)
    return GeneratePacketResponse(
        packet_id=version.recovery_packet_id, version=_packet_version_out(version)
    )


@router.get(
    "/{candidate_id}/packet",
    response_model=RecoveryPacketDetail,
    operation_id="getRecoveryPacket",
)
async def get_recovery_packet(
    candidate_id: UUID, context: AuthedContext, session: DbSession
) -> RecoveryPacketDetail:
    service = RecoveryPacketService(session)
    packet = await service.get_for_candidate(context, candidate_id)
    return _packet_detail(packet, service.current_version(packet))


@packets_router.post(
    "/{packet_id}/versions/{version_id}/review",
    response_model=RecoveryPacketVersionOut,
    summary="Human decision on a packet version: confirm | reject | request_info | edit",
    operation_id="reviewRecoveryPacketVersion",
)
async def review_recovery_packet_version(
    packet_id: UUID,
    version_id: UUID,
    payload: PacketReviewRequest,
    context: AuthedContext,
    session: DbSession,
) -> RecoveryPacketVersionOut:
    version = await RecoveryPacketService(session).review_version(
        context,
        packet_id,
        version_id,
        PacketReview(
            decision=payload.decision,
            reason=payload.reason,
            statement_key=payload.statement_key,
            value=payload.value,
        ),
    )
    return _packet_version_out(version)


@packets_router.get(
    "/{packet_id}/versions/{version_id}/html",
    response_class=HTMLResponse,
    summary="The rendered packet HTML (for printing / archiving)",
    operation_id="getRecoveryPacketHtml",
)
async def get_recovery_packet_html(
    packet_id: UUID, version_id: UUID, context: AuthedContext, session: DbSession
) -> HTMLResponse:
    version = await RecoveryPacketService(session).version_html(context, version_id)
    return HTMLResponse(
        content=version.rendered_html or "<!doctype html><title>Empty packet</title>",
        headers={"Cache-Control": "private, no-store"},
    )


# --- recovery notice ----------------------------------------------


def _notice_out(notice: RecoveryNotice) -> RecoveryNoticeOut:
    return RecoveryNoticeOut(
        id=notice.id,
        recovery_candidate_id=notice.recovery_candidate_id,
        kind=notice.kind,
        status=notice.status,
        recipient=dict(notice.recipient),
        subject=notice.subject,
        body_markdown=notice.body_markdown,
        key_figures=dict(notice.key_figures),
        caveats=list(notice.caveats),
        used_only_provided_facts=notice.used_only_provided_facts,
        notes_for_reviewer=notice.notes_for_reviewer,
        context=dict(notice.context),
        agent_run_id=notice.agent_run_id,
        recovery_packet_version_id=notice.recovery_packet_version_id,
        review_note=notice.review_note,
        approved_at=notice.approved_at,
        superseded=notice.superseded_at is not None,
        created_at=notice.created_at,
    )


@router.post(
    "/{candidate_id}/notices",
    response_model=RecoveryCandidateOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue the notice drafter (whitelist of approved facts in; draft out; never sent)",
    operation_id="draftRecoveryNotice",
)
async def draft_recovery_notice(
    candidate_id: UUID,
    payload: DraftNoticeRequest,
    context: AuthedContext,
    session: DbSession,
    settings: AppSettings,
    enqueue: Annotated[NoticeEnqueuer, Depends(get_notice_enqueuer)],
) -> RecoveryCandidateOut:
    if not settings.ai_enabled:
        raise ConflictError("AI is disabled in this environment")
    candidate = await RecoveryCandidateService(session).get_candidate(context, candidate_id)
    if candidate.status.value not in ("confirmed", "notice_drafted"):
        raise ConflictError("confirm the recovery candidate before drafting a notice")
    await enqueue(
        context.organization.id,
        candidate.id,
        kind=payload.kind.value,
        recipient=payload.recipient.model_dump(),
        actor_id=context.user.id,
    )
    return _candidate_out(candidate)


@router.get(
    "/{candidate_id}/notices",
    response_model=RecoveryNoticeList,
    operation_id="listRecoveryNotices",
)
async def list_recovery_notices(
    candidate_id: UUID, context: AuthedContext, session: DbSession, settings: AppSettings
) -> RecoveryNoticeList:
    notices = await NoticeService(session, settings).list_for_candidate(context, candidate_id)
    return RecoveryNoticeList(notices=[_notice_out(n) for n in notices])


@notices_router.get(
    "/{notice_id}", response_model=RecoveryNoticeOut, operation_id="getRecoveryNotice"
)
async def get_recovery_notice(
    notice_id: UUID, context: AuthedContext, session: DbSession, settings: AppSettings
) -> RecoveryNoticeOut:
    notice = await NoticeService(session, settings).get_notice(context, notice_id)
    return _notice_out(notice)


@notices_router.post(
    "/{notice_id}/review",
    response_model=RecoveryNoticeOut,
    summary="Human decision on a draft notice: confirm | reject | request_info | edit",
    operation_id="reviewRecoveryNotice",
)
async def review_recovery_notice(
    notice_id: UUID,
    payload: NoticeReviewRequest,
    context: AuthedContext,
    session: DbSession,
    settings: AppSettings,
) -> RecoveryNoticeOut:
    notice = await NoticeService(session, settings).review(
        context,
        notice_id,
        NoticeReview(
            decision=payload.decision,
            subject=payload.subject,
            body_markdown=payload.body_markdown,
            recipient=payload.recipient.model_dump() if payload.recipient else None,
            reason=payload.reason,
        ),
    )
    return _notice_out(notice)


# --- collection tracking (ADR-0024) ------------------------------------------


def _recoverable_out(r: Recoverable, *, as_of: dt.date) -> RecoverableOut:
    overdue = days_overdue(r.due_date, as_of)
    entered = entered_status_on(
        r.status,
        created_at=r.created_at,
        notified_at=r.notified_at,
        agreed_at=r.agreed_at,
        billed_at=r.billed_at,
        settled_at=r.settled_at,
        updated_at=r.updated_at,
    )
    days_in_status = max((as_of - entered.date()).days, 0)
    hint = recommend_chase(status=r.status, days_in_status=days_in_status, days_overdue=overdue)
    return RecoverableOut(
        id=r.id,
        recovery_candidate_id=r.recovery_candidate_id,
        reinsurer_id=r.reinsurer_id,
        reinsurer_name=r.reinsurer.name,
        currency=r.currency,
        status=r.status,
        expected_amount=r.expected_amount,
        agreed_amount=r.agreed_amount,
        billed_amount=r.billed_amount,
        collected_amount=r.collected_amount,
        outstanding=outstanding(
            status=r.status,
            expected_amount=r.expected_amount,
            agreed_amount=r.agreed_amount,
            collected_amount=r.collected_amount,
        ),
        due_date=r.due_date,
        days_overdue=overdue,
        aging_bucket=aging_bucket(r.due_date, as_of).value,
        notified_at=r.notified_at,
        agreed_at=r.agreed_at,
        billed_at=r.billed_at,
        settled_at=r.settled_at,
        note=r.note,
        days_in_status=days_in_status,
        next_action=hint.action.value,
        next_action_text=hint.text,
        next_action_urgent=hint.urgent,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.post(
    "/{candidate_id}/recoverables",
    response_model=RecoverableList,
    summary="Start collection tracking — one recoverable per reinsurer (idempotent)",
    operation_id="materializeRecoverables",
)
async def materialize_recoverables(
    candidate_id: UUID, context: AuthedContext, session: DbSession
) -> RecoverableList:
    items = await CollectionService(session).materialize(context, candidate_id)
    today = dt.datetime.now(tz=dt.UTC).date()
    return RecoverableList(recoverables=[_recoverable_out(r, as_of=today) for r in items])


@router.get(
    "/{candidate_id}/recoverables",
    response_model=RecoverableList,
    operation_id="listRecoverablesForCandidate",
)
async def list_recoverables_for_candidate(
    candidate_id: UUID, context: AuthedContext, session: DbSession
) -> RecoverableList:
    items = await CollectionService(session).list_for_candidate(context, candidate_id)
    today = dt.datetime.now(tz=dt.UTC).date()
    return RecoverableList(recoverables=[_recoverable_out(r, as_of=today) for r in items])


@recoverables_router.get("", response_model=RecoverableList, operation_id="listRecoverables")
async def list_recoverables(
    context: AuthedContext,
    session: DbSession,
    status_filter: Annotated[RecoverableStatus | None, Query(alias="status")] = None,
) -> RecoverableList:
    items = await CollectionService(session).portfolio(context, status=status_filter)
    today = dt.datetime.now(tz=dt.UTC).date()
    return RecoverableList(recoverables=[_recoverable_out(r, as_of=today) for r in items])


@recoverables_router.get(
    "/summary", response_model=RecoverableSummaryOut, operation_id="getRecoverablesSummary"
)
async def get_recoverables_summary(
    context: AuthedContext, session: DbSession
) -> RecoverableSummaryOut:
    s = await CollectionService(session).summary(context)
    return RecoverableSummaryOut(
        currency=s.currency,
        count=s.count,
        total_expected=s.total_expected,
        total_collected=s.total_collected,
        total_outstanding=s.total_outstanding,
        overdue_count=s.overdue_count,
        overdue_outstanding=s.overdue_outstanding,
        by_status=[
            RecoverableStatusTotalOut(status=t.status, count=t.count, outstanding=t.outstanding)
            for t in s.by_status
        ],
        by_aging=s.by_aging,
    )


@recoverables_router.post(
    "/{recoverable_id}",
    response_model=RecoverableOut,
    summary="Human update: status, agreed/billed figures, a collection, due date, a note",
    operation_id="updateRecoverable",
)
async def update_recoverable(
    recoverable_id: UUID,
    payload: RecoverableUpdateRequest,
    context: AuthedContext,
    session: DbSession,
) -> RecoverableOut:
    r = await CollectionService(session).update(
        context,
        recoverable_id,
        status=payload.status,
        agreed_amount=payload.agreed_amount,
        billed_amount=payload.billed_amount,
        collect=payload.collect,
        due_date=payload.due_date,
        clear_due_date=payload.clear_due_date,
        note=payload.note,
    )
    return _recoverable_out(r, as_of=dt.datetime.now(tz=dt.UTC).date())
