from __future__ import annotations

import datetime as dt
from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel
from app.domain.recoveries import DeadlineBasis, NoticeTrigger
from app.domain.reviews import ReviewDecision
from app.domain.treaties import TreatyVersionStatus


class CitationOut(ApiModel):
    document_id: UUID
    page_number: int
    section: str | None
    quoted_text: str


class TermCandidateOut(ApiModel):
    id: UUID
    key: str
    status: str
    raw_value: str | None
    normalized_value: dict | None
    currency: str | None
    confidence: float | None
    reasoning: str | None
    resolution: str | None
    citation: CitationOut | None


class DocumentPageOut(ApiModel):
    page_number: int
    text: str


class TermCandidatesResponse(ApiModel):
    treaty_version_id: UUID
    status: TreatyVersionStatus
    currency: str | None
    source_document_id: UUID | None
    candidates: list[TermCandidateOut]
    pages: list[DocumentPageOut]


class TermDiffEntryOut(ApiModel):
    key: str
    carried_value: str | None
    extracted_value: str | None
    extracted_candidate_id: UUID | None
    change: str  # unchanged | changed | new | not_extracted


class TermDiffResponse(ApiModel):
    treaty_version_id: UUID
    entries: list[TermDiffEntryOut]


class ReviewRequest(ApiModel):
    decision: ReviewDecision
    value: str | None = Field(default=None, max_length=2000)
    currency: str | None = Field(default=None, max_length=3)
    reason: str | None = Field(default=None, max_length=2000)


class ReviewOut(ApiModel):
    id: UUID
    decision: ReviewDecision
    reason: str | None
    created_at: dt.datetime


class SetNoticeTermRequest(ApiModel):
    """The notice provision as free text, plus — where the analyst can state it —
    the structured deadline that drives reminders."""

    provision_text: str = Field(min_length=1, max_length=2000)
    period_days: int | None = Field(default=None, ge=1, le=1000)
    trigger: NoticeTrigger | None = None
    basis: DeadlineBasis = DeadlineBasis.CALENDAR


class LayerSpecIn(ApiModel):
    attachment: str = Field(min_length=1, max_length=40)
    limit: str = Field(min_length=1, max_length=40)


class SetLayersRequest(ApiModel):
    """The full stack of executable XOL layers for a treaty version. Replaces
    whatever is there. Editable only before the version is validated."""

    currency: str | None = Field(default=None, min_length=3, max_length=3)
    layers: list[LayerSpecIn] = Field(min_length=1, max_length=12)
