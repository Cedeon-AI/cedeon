from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel
from app.domain.losses import LossImportStatus, LossRowStatus


class CanonicalFieldOut(ApiModel):
    field: str
    label: str
    kind: str
    required: bool
    hint: str


class CanonicalFieldList(ApiModel):
    fields: list[CanonicalFieldOut]


class RowIssueOut(ApiModel):
    row_number: int
    level: str
    field: str | None
    message: str


class ImportRowOut(ApiModel):
    row_number: int
    status: LossRowStatus
    raw: dict[str, str]
    parsed: dict[str, str] | None
    issues: list[RowIssueOut]


class ImportReportOut(ApiModel):
    total_rows: int
    ok: int
    warnings: int
    errors: int
    committable: int
    currencies: list[str]
    distinct_events: list[str]
    gross_incurred_by_currency: dict[str, str]
    issues: list[RowIssueOut]


class LossImportOut(ApiModel):
    id: UUID
    original_filename: str
    content_type: str
    row_count: int
    status: LossImportStatus
    header_columns: list[str]
    column_mapping: dict[str, str]
    report: ImportReportOut | None
    created_at: dt.datetime
    committed_at: dt.datetime | None


class LossImportList(ApiModel):
    imports: list[LossImportOut]


class LossImportDetail(ApiModel):
    loss_import: LossImportOut
    rows: list[ImportRowOut]


class ColumnMappingIn(ApiModel):
    # canonical field name -> CSV header column
    mapping: dict[str, str]


class CommitImportIn(ApiModel):
    loss_event_id: UUID | None = None
    event_name: str | None = Field(default=None, max_length=300)


class CommitResultOut(ApiModel):
    committed: int
    skipped: int
    events_created: int
    loss_event_ids: list[UUID]
    recoveries_drifted: int = 0


class LossEventCurrencyTotal(ApiModel):
    currency: str
    claim_count: int
    gross_incurred: str


class LossEventOut(ApiModel):
    id: UUID
    name: str
    event_identifier: str | None
    catastrophe_code: str | None
    currency: str | None
    date_of_loss_from: dt.date | None
    date_of_loss_to: dt.date | None
    description: str | None
    peril: str | None
    hours_clause_hours: int | None
    created_at: dt.datetime
    totals: list[LossEventCurrencyTotal]


class LossEventList(ApiModel):
    events: list[LossEventOut]


class LossEventCreate(ApiModel):
    name: str = Field(min_length=1, max_length=300)
    catastrophe_code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    peril: str | None = Field(default=None, max_length=80, description="e.g. Named windstorm")
    hours_clause_hours: int | None = Field(default=None, ge=1, le=2000)


class UnderlyingLossOut(ApiModel):
    id: UUID
    claim_id: str
    date_of_loss: dt.date
    reported_date: dt.date | None
    gross_incurred: Decimal
    gross_paid: Decimal | None
    gross_case_reserve: Decimal | None
    currency: str
    status: str | None
    cause_of_loss: str | None
    location: str | None
    description: str | None
    loss_import_id: UUID


class LossEventDetail(ApiModel):
    event: LossEventOut
    losses: list[UnderlyingLossOut]
