"""AI extraction + human validation: agent runs, prompt versions, citations,
treaty term candidates, and the append-only review log."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.domain.ai import AgentRunStatus, AgentType, ExtractedTermStatus
from app.domain.reviews import ReviewDecision, ReviewSubjectType

_agent_type = SAEnum(
    AgentType, native_enum=False, length=32, create_constraint=False, name="agent_type"
)
_run_status = SAEnum(
    AgentRunStatus, native_enum=False, length=16, create_constraint=False, name="agent_run_status"
)
_candidate_status = SAEnum(
    ExtractedTermStatus,
    native_enum=False,
    length=16,
    create_constraint=False,
    name="candidate_status",
)
_review_subject = SAEnum(
    ReviewSubjectType,
    native_enum=False,
    length=32,
    create_constraint=False,
    name="review_subject_type",
)
_review_decision = SAEnum(
    ReviewDecision, native_enum=False, length=24, create_constraint=False, name="review_decision"
)


class PromptVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_prompt_versions_name_version"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)


class AgentRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One model call. Immutable telemetry (docs/AI_ARCHITECTURE.md §7)."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_subject", "subject_type", "subject_id"),
        Index("ix_agent_runs_org_created", "organization_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    agent_type: Mapped[AgentType] = mapped_column(_agent_type, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[AgentRunStatus] = mapped_column(_run_status, nullable=False)
    input_ref: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Any | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Citation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A resolvable pointer to supporting text. The backbone of auditability."""

    __tablename__ = "citations"
    __table_args__ = (Index("ix_citations_document_id", "document_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quoted_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )


class TreatyTermCandidate(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Immutable AI output. Never feeds executable state — a human validates it."""

    __tablename__ = "treaty_term_candidates"
    __table_args__ = (Index("ix_treaty_term_candidates_version", "treaty_version_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    treaty_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaty_versions.id", ondelete="CASCADE"), nullable=False
    )
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ExtractedTermStatus] = mapped_column(_candidate_status, nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    confidence: Mapped[Any | None] = mapped_column(Numeric(4, 3), nullable=True)
    citation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("citations.id", ondelete="SET NULL"), nullable=True
    )
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Filled by the review flow: which term/decision this candidate resolved to.
    resolution: Mapped[str | None] = mapped_column(String(24), nullable=True)

    citation: Mapped[Citation | None] = relationship()


class Review(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only record of a human decision on a reviewable subject."""

    __tablename__ = "reviews"
    __table_args__ = (Index("ix_reviews_subject", "subject_type", "subject_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    subject_type: Mapped[ReviewSubjectType] = mapped_column(_review_subject, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[ReviewDecision] = mapped_column(_review_decision, nullable=False)
    value_before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    value_after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
