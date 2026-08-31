from __future__ import annotations

from decimal import Decimal

from app.api.schemas import ApiModel
from app.domain.worklist import WorklistKind


class UrgencyTermOut(ApiModel):
    label: str
    points: int


class WorklistItemOut(ApiModel):
    kind: WorklistKind
    key: str
    title: str
    detail: str
    href: str
    amount: Decimal | None
    currency: str | None
    due_in_days: int | None
    age_days: int | None
    urgency: int
    urgency_terms: list[UrgencyTermOut]


class WorklistSummaryOut(ApiModel):
    open_count: int
    currency: str
    open_recoverable: Decimal
    overdue_outstanding: Decimal
    largest_open_recovery: Decimal | None


class WorklistResponse(ApiModel):
    items: list[WorklistItemOut]
    summary: WorklistSummaryOut
