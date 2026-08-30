"""Recovery candidates: turn a validated treaty + a loss event into a reviewable,
deterministically-calculated recovery. No AI in this module (ADR-0010)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies.context import AuthedContext, DbSession
from app.api.schemas.recoveries import (
    CalcStepOut,
    CalculationAllocationOut,
    CreateRecoveryCandidateRequest,
    RecoveryCalculationOut,
    RecoveryCandidateDetail,
    RecoveryCandidateList,
    RecoveryCandidateOut,
    RecoveryReviewOut,
    ReviewRecoveryCandidateRequest,
)
from app.db.models.extraction import Review
from app.db.models.recoveries import RecoveryCalculation, RecoveryCandidate
from app.domain.recoveries import RecoveryCandidateStatus
from app.services.recoveries import RecoveryCandidateService

router = APIRouter(prefix="/recovery-candidates", tags=["recovery-candidates"])


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
        created_at=candidate.created_at,
        reviewed_at=candidate.reviewed_at,
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


@router.post(
    "",
    response_model=RecoveryCandidateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a recovery candidate (validated treaty + loss event → deterministic calc)",
    operation_id="createRecoveryCandidate",
)
async def create_recovery_candidate(
    payload: CreateRecoveryCandidateRequest, context: AuthedContext, session: DbSession
) -> RecoveryCandidateOut:
    candidate = await RecoveryCandidateService(session).create(
        context, treaty_id=payload.treaty_id, loss_event_id=payload.loss_event_id
    )
    return _candidate_out(candidate)


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
    "/{candidate_id}", response_model=RecoveryCandidateDetail, operation_id="getRecoveryCandidate"
)
async def get_recovery_candidate(
    candidate_id: UUID, context: AuthedContext, session: DbSession
) -> RecoveryCandidateDetail:
    service = RecoveryCandidateService(session)
    candidate = await service.get_candidate(context, candidate_id)
    reviews = await service.candidate_reviews(context, candidate_id)
    current = service.current_calculation(candidate)
    return RecoveryCandidateDetail(
        candidate=_candidate_out(candidate),
        current_calculation=_calculation_out(current) if current else None,
        calculations=[
            _calculation_out(c)
            for c in sorted(candidate.calculations, key=lambda x: x.created_at, reverse=True)
        ],
        reviews=[_review_out(r) for r in reviews],
    )


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
