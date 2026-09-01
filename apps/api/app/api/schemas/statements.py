from __future__ import annotations

import datetime as dt
from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel


class StatementLineIn(ApiModel):
    reinsurer_name: str = Field(min_length=1, max_length=300)
    reference: str | None = Field(default=None, max_length=300)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    their_agreed: str | None = None
    their_paid: str | None = None


class CreateStatementRequest(ApiModel):
    label: str = Field(min_length=1, max_length=200)
    currency: str = Field(min_length=3, max_length=3)
    statement_date: dt.date | None = None
    lines: list[StatementLineIn] = Field(min_length=1)


class StatementFindingOut(ApiModel):
    kind: str
    text: str
    ours: str | None
    theirs: str | None


class StatementLineOut(ApiModel):
    row_number: int
    reinsurer_name: str
    reference: str | None
    currency: str
    their_agreed: str | None
    their_paid: str | None
    matched_recoverable_id: UUID | None
    findings: list[StatementFindingOut]
    resolved: bool


class StatementOut(ApiModel):
    id: UUID
    label: str
    currency: str
    statement_date: dt.date | None
    created_at: dt.datetime
    line_count: int
    open_discrepancies: int
    lines: list[StatementLineOut]


class StatementSummary(ApiModel):
    id: UUID
    label: str
    currency: str
    statement_date: dt.date | None
    created_at: dt.datetime
    line_count: int
    open_discrepancies: int


class StatementList(ApiModel):
    statements: list[StatementSummary]
