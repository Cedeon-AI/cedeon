"""Treaties, their versions, and the extraction → validation workspace."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies.context import AuthedContext, DbSession, TreatyServiceDep
from app.api.schemas.recoveries import (
    AllocationOut,
    CalcStepOut,
    RecoveryPreviewRequest,
    RecoveryPreviewResponse,
)
from app.api.schemas.reinsurance import (
    LayerOut,
    ParticipationOut,
    TermOut,
    TreatyCreate,
    TreatyDetail,
    TreatyList,
    TreatyOut,
    TreatyVersionOut,
    TreatyVersionSummary,
)
from app.api.schemas.validation import (
    CitationOut,
    DocumentPageOut,
    ReviewRequest,
    SetLayersRequest,
    SetNoticeTermRequest,
    TermCandidateOut,
    TermCandidatesResponse,
)
from app.db.models.extraction import TreatyTermCandidate
from app.db.models.reinsurance import Treaty, TreatyVersion
from app.domain.recoveries import NoticeTermSpec, NoticeTrigger
from app.services.errors import ValidationError
from app.services.obligations import ObligationService
from app.services.recoveries import RecoveryPreviewService
from app.services.validation import CandidateReview, ValidationService

router = APIRouter(prefix="/treaties", tags=["treaties"])


def _treaty_out(treaty: Treaty) -> TreatyOut:
    current = next((v for v in treaty.versions if v.id == treaty.current_version_id), None)
    return TreatyOut(
        id=treaty.id,
        name=treaty.name,
        treaty_type=treaty.treaty_type,
        program_id=treaty.program_id,
        program_name=treaty.program.name,
        cedent_name=treaty.program.cedent.name,
        created_at=treaty.created_at,
        current_version=(
            TreatyVersionSummary(
                id=current.id,
                version_no=current.version_no,
                status=current.status,
                source_document_id=current.source_document_id,
            )
            if current
            else None
        ),
    )


def _version_out(version: TreatyVersion) -> TreatyVersionOut:
    return TreatyVersionOut(
        id=version.id,
        version_no=version.version_no,
        status=version.status,
        effective_date=version.effective_date,
        expiration_date=version.expiration_date,
        currency=version.currency,
        source_document_id=version.source_document_id,
        validated_at=version.validated_at,
        layers=[
            LayerOut(
                layer_no=layer.layer_no,
                attachment=layer.attachment,
                limit=layer.limit,
                currency=layer.currency,
                reinstatements=layer.reinstatements,
                description=layer.description,
            )
            for layer in sorted(version.layers, key=lambda x: x.layer_no)
        ],
        participations=[
            ParticipationOut(
                reinsurer_id=p.reinsurer_id,
                reinsurer_name=p.reinsurer.name,
                placed_share=p.placed_share,
                signed_share=p.signed_share,
                broker_name=p.broker_name,
            )
            for p in version.participations
        ],
        terms=[TermOut(key=t.key, value=t.value, status=t.status.value) for t in version.terms],
    )


def _candidate_out(candidate: TreatyTermCandidate) -> TermCandidateOut:
    return TermCandidateOut(
        id=candidate.id,
        key=candidate.key,
        status=candidate.status.value,
        raw_value=candidate.raw_value,
        normalized_value=candidate.normalized_value,
        currency=candidate.currency,
        confidence=float(candidate.confidence) if candidate.confidence is not None else None,
        reasoning=candidate.reasoning,
        resolution=candidate.resolution,
        citation=(
            CitationOut(
                document_id=candidate.citation.document_id,
                page_number=candidate.citation.page_number,
                section=candidate.citation.section,
                quoted_text=candidate.citation.quoted_text,
            )
            if candidate.citation
            else None
        ),
    )


@router.get("", response_model=TreatyList, operation_id="listTreaties")
async def list_treaties(context: AuthedContext, service: TreatyServiceDep) -> TreatyList:
    treaties = await service.list_treaties(context)
    return TreatyList(treaties=[_treaty_out(t) for t in treaties])


@router.post(
    "",
    response_model=TreatyOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="createTreaty",
)
async def create_treaty(
    payload: TreatyCreate, context: AuthedContext, service: TreatyServiceDep
) -> TreatyOut:
    treaty = await service.create_treaty(
        context,
        program_id=payload.program_id,
        name=payload.name,
        source_document_id=payload.source_document_id,
    )
    return _treaty_out(treaty)


@router.get("/{treaty_id}", response_model=TreatyDetail, operation_id="getTreaty")
async def get_treaty(
    treaty_id: UUID, context: AuthedContext, service: TreatyServiceDep
) -> TreatyDetail:
    treaty = await service.get_treaty(context, treaty_id)
    current = await service.get_current_version(context, treaty)
    return TreatyDetail(
        treaty=_treaty_out(treaty),
        current_version=_version_out(current) if current else None,
    )


@router.post(
    "/{treaty_id}/extract",
    response_model=TreatyOut,
    operation_id="rerunTreatyExtraction",
)
async def rerun_extraction(
    treaty_id: UUID, context: AuthedContext, service: TreatyServiceDep
) -> TreatyOut:
    treaty = await service.rerun_extraction(context, treaty_id)
    return _treaty_out(treaty)


@router.get(
    "/{treaty_id}/versions/{version_id}/term-candidates",
    response_model=TermCandidatesResponse,
    operation_id="listTermCandidates",
)
async def list_term_candidates(
    treaty_id: UUID,
    version_id: UUID,
    context: AuthedContext,
    session: DbSession,
) -> TermCandidatesResponse:
    version, candidates, pages = await ValidationService(session).list_candidates(
        context, version_id
    )
    return TermCandidatesResponse(
        treaty_version_id=version.id,
        status=version.status,
        currency=version.currency,
        source_document_id=version.source_document_id,
        candidates=[_candidate_out(c) for c in candidates],
        pages=[DocumentPageOut(page_number=p.page_number, text=p.text) for p in pages],
    )


@router.post(
    "/{treaty_id}/versions/{version_id}/term-candidates/{candidate_id}/review",
    response_model=TermCandidateOut,
    operation_id="reviewTermCandidate",
)
async def review_term_candidate(
    treaty_id: UUID,
    version_id: UUID,
    candidate_id: UUID,
    payload: ReviewRequest,
    context: AuthedContext,
    session: DbSession,
) -> TermCandidateOut:
    candidate = await ValidationService(session).review_candidate(
        context,
        version_id,
        candidate_id,
        CandidateReview(
            decision=payload.decision,
            value=payload.value,
            currency=payload.currency,
            reason=payload.reason,
        ),
    )
    return _candidate_out(candidate)


@router.put(
    "/{treaty_id}/versions/{version_id}/layers",
    response_model=TreatyDetail,
    summary="Set the full stack of executable XOL layers (before the version is validated)",
    operation_id="setTreatyLayers",
)
async def set_treaty_layers(
    treaty_id: UUID,
    version_id: UUID,
    payload: SetLayersRequest,
    context: AuthedContext,
    session: DbSession,
    treaty_service: TreatyServiceDep,
) -> TreatyDetail:
    try:
        specs = [(Decimal(s.attachment), Decimal(s.limit)) for s in payload.layers]
    except InvalidOperation as exc:
        raise ValidationError("layer amounts must be numeric") from exc
    await ValidationService(session).set_layers(
        context, version_id, specs, currency=payload.currency
    )
    treaty = await treaty_service.get_treaty(context, treaty_id)
    current = await treaty_service.get_current_version(context, treaty)
    return TreatyDetail(
        treaty=_treaty_out(treaty),
        current_version=_version_out(current) if current else None,
    )


@router.put(
    "/{treaty_id}/versions/{version_id}/notice-term",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set the notice provision — free text plus, where stated, a structured deadline",
    operation_id="setTreatyNoticeTerm",
)
async def set_treaty_notice_term(
    treaty_id: UUID,
    version_id: UUID,
    payload: SetNoticeTermRequest,
    context: AuthedContext,
    session: DbSession,
) -> None:
    spec: NoticeTermSpec | None = None
    if payload.period_days is not None and payload.trigger is not None:
        spec = NoticeTermSpec(
            days=payload.period_days,
            trigger=NoticeTrigger(payload.trigger),
            basis=payload.basis,
        )
    await ObligationService(session).set_notice_term(
        context, version_id, provision_text=payload.provision_text, spec=spec
    )


@router.post(
    "/{treaty_id}/versions/{version_id}/validate",
    response_model=TreatyVersionOut,
    operation_id="validateTreatyVersion",
)
async def validate_treaty_version(
    treaty_id: UUID,
    version_id: UUID,
    context: AuthedContext,
    session: DbSession,
) -> TreatyVersionOut:
    version = await ValidationService(session).validate_version(context, version_id)
    return _version_out(version)


@router.post(
    "/{treaty_id}/recovery-preview",
    response_model=RecoveryPreviewResponse,
    summary="Deterministic 'what would this treaty recover' — read-only, not persisted",
    operation_id="previewRecovery",
)
async def preview_recovery(
    treaty_id: UUID,
    payload: RecoveryPreviewRequest,
    context: AuthedContext,
    session: DbSession,
) -> RecoveryPreviewResponse:
    calc = await RecoveryPreviewService(session).preview(
        context, treaty_id, gross_loss_amount=payload.gross_loss
    )
    return RecoveryPreviewResponse(
        engine_version=calc.engine_version,
        currency=calc.xol.currency,
        gross_loss=calc.xol.gross_loss.amount,
        attachment=calc.xol.attachment.amount,
        limit=calc.xol.limit.amount,
        amount_above_attachment=calc.xol.amount_above_attachment.amount,
        layer_recovery=calc.layer_recovery.amount,
        cedent_retention=calc.cedent_retention.amount,
        allocations=[
            AllocationOut(
                reinsurer_id=a.key,
                reinsurer_name=a.label,
                share=a.share,
                amount=a.amount.amount,
            )
            for a in calc.allocations
        ],
        trace=[
            CalcStepOut(label=s.label, expression=s.expression, result=s.result)
            for s in calc.xol.trace
        ],
    )
