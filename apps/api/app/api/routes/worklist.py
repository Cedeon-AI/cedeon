"""The recovery desk's worklist — one prioritised list of what needs a human,
across every stage of the pipeline. Read-only, no AI."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies.context import AuthedContext, DbSession
from app.api.schemas.worklist import (
    UrgencyTermOut,
    WorklistItemOut,
    WorklistResponse,
    WorklistSummaryOut,
)
from app.domain.worklist import WorklistItem
from app.services.worklist import WorklistService

router = APIRouter(prefix="/worklist", tags=["worklist"])


def _item_out(item: WorklistItem) -> WorklistItemOut:
    return WorklistItemOut(
        kind=item.kind,
        key=item.key,
        title=item.title,
        detail=item.detail,
        href=item.href,
        amount=item.amount,
        currency=item.currency,
        due_in_days=item.due_in_days,
        age_days=item.age_days,
        urgency=item.urgency,
        urgency_terms=[UrgencyTermOut(label=t.label, points=t.points) for t in item.urgency_terms],
    )


@router.get("", response_model=WorklistResponse, operation_id="getWorklist")
async def get_worklist(context: AuthedContext, session: DbSession) -> WorklistResponse:
    worklist = await WorklistService(session).build(context)
    s = worklist.summary
    return WorklistResponse(
        items=[_item_out(i) for i in worklist.items],
        summary=WorklistSummaryOut(
            open_count=s.open_count,
            currency=s.currency,
            open_recoverable=s.open_recoverable,
            overdue_outstanding=s.overdue_outstanding,
            largest_open_recovery=s.largest_open_recovery,
        ),
    )
