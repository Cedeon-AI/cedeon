"""Recovery candidates and the immutable calculation snapshots they carry.

A ``recovery_candidate`` is the mutable review object for one
``(treaty_version, treaty_layer, loss_event)`` triple. Every run of the
deterministic engine writes a new immutable ``recovery_calculations`` row (plus
its ``recovery_allocations``); ``current_calculation_id`` points at the live one
(docs/DATA_MODEL.md §2, ADR-0010/0012)."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.ai import ApplicabilityAssessment, FindingKind, InvestigationStatus
from app.domain.recoveries import (
    NoticeKind,
    NoticeStatus,
    PacketVersionStatus,
    RecoverableStatus,
    RecoveryCandidateStatus,
)

_candidate_status = SAEnum(
    RecoveryCandidateStatus,
    native_enum=False,
    length=20,
    create_constraint=False,
    name="recovery_candidate_status",
)
_investigation_status = SAEnum(
    InvestigationStatus,
    native_enum=False,
    length=12,
    create_constraint=False,
    name="recovery_investigation_status",
)
_applicability = SAEnum(
    ApplicabilityAssessment,
    native_enum=False,
    length=24,
    create_constraint=False,
    name="applicability_assessment",
)
_finding_kind = SAEnum(
    FindingKind, native_enum=False, length=24, create_constraint=False, name="finding_kind"
)
_packet_version_status = SAEnum(
    PacketVersionStatus,
    native_enum=False,
    length=12,
    create_constraint=False,
    name="recovery_packet_version_status",
)
_notice_kind = SAEnum(
    NoticeKind, native_enum=False, length=32, create_constraint=False, name="recovery_notice_kind"
)
_notice_status = SAEnum(
    NoticeStatus,
    native_enum=False,
    length=12,
    create_constraint=False,
    name="recovery_notice_status",
)
_recoverable_status = SAEnum(
    RecoverableStatus,
    native_enum=False,
    length=16,
    create_constraint=False,
    name="recoverable_status",
)

MONEY = Numeric(20, 2)
SHARE = Numeric(9, 6)


class RecoveryCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recovery_candidates"
    __table_args__ = (
        UniqueConstraint(
            "treaty_version_id",
            "treaty_layer_id",
            "loss_event_id",
            name="uq_recovery_candidates_version_layer_event",
        ),
        Index("ix_recovery_candidates_org_status", "organization_id", "status"),
        Index("ix_recovery_candidates_loss_event_id", "loss_event_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    treaty_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaties.id", ondelete="RESTRICT"), nullable=False
    )
    treaty_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaty_versions.id", ondelete="RESTRICT"), nullable=False
    )
    treaty_layer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaty_layers.id", ondelete="RESTRICT"), nullable=False
    )
    loss_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loss_events.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[RecoveryCandidateStatus] = mapped_column(
        _candidate_status, nullable=False, default=RecoveryCandidateStatus.NEEDS_REVIEW
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    gross_event_incurred: Mapped[Any] = mapped_column(MONEY, nullable=False)
    currency_mismatch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The analyst's stated "date the cedent knew a loss was likely to involve this
    # treaty" — the reference date for a knowledge-triggered notice deadline.
    knowledge_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    # Set when a claims import moves the recovery figure without a human in the
    # loop (auto-recalc on loss commit). Cleared on the next human review.
    drifted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pre_drift_recovery: Mapped[Any | None] = mapped_column(MONEY, nullable=True)
    current_calculation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recovery_calculations.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    calculations: Mapped[list[RecoveryCalculation]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        foreign_keys="RecoveryCalculation.recovery_candidate_id",
        order_by="RecoveryCalculation.created_at",
    )


class RecoveryCalculation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Immutable. One run of the deterministic XOL engine (ADR-0010)."""

    __tablename__ = "recovery_calculations"
    __table_args__ = (
        Index("ix_recovery_calculations_candidate_id", "recovery_candidate_id"),
        Index("ix_recovery_calculations_input_hash", "input_hash"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    recovery_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_candidates.id", ondelete="CASCADE"), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    treaty_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaty_versions.id", ondelete="RESTRICT"), nullable=False
    )
    treaty_layer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaty_layers.id", ondelete="RESTRICT"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    gross_loss: Mapped[Any] = mapped_column(MONEY, nullable=False)
    attachment: Mapped[Any] = mapped_column(MONEY, nullable=False)
    amount_above_attachment: Mapped[Any] = mapped_column(MONEY, nullable=False)
    layer_limit: Mapped[Any] = mapped_column(MONEY, nullable=False)
    layer_recovery: Mapped[Any] = mapped_column(MONEY, nullable=False)
    cedent_retention: Mapped[Any] = mapped_column(MONEY, nullable=False)
    total_ceded: Mapped[Any] = mapped_column(MONEY, nullable=False)
    trace: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    candidate: Mapped[RecoveryCandidate] = relationship(
        back_populates="calculations", foreign_keys=[recovery_candidate_id]
    )
    allocations: Mapped[list[RecoveryAllocation]] = relationship(
        back_populates="calculation",
        cascade="all, delete-orphan",
        order_by="RecoveryAllocation.created_at",
    )


class RecoveryInvestigation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Immutable output of one Recovery Investigator run (docs/AI_ARCHITECTURE.md §2b).

    Re-investigating writes a new row; the newest non-superseded one is current.
    The agent never computes the recovery — that stays in ``recovery_calculations``.
    """

    __tablename__ = "recovery_investigations"
    __table_args__ = (
        Index("ix_recovery_investigations_candidate", "recovery_candidate_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    recovery_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_candidates.id", ondelete="CASCADE"), nullable=False
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[InvestigationStatus] = mapped_column(_investigation_status, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicability_assessment: Mapped[ApplicabilityAssessment | None] = mapped_column(
        _applicability, nullable=True
    )
    confidence: Mapped[Any | None] = mapped_column(Numeric(4, 3), nullable=True)
    out_of_scope: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suspected_prompt_injection: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unresolved_questions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    findings: Mapped[list[RecoveryInvestigationFinding]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="RecoveryInvestigationFinding.ordinal",
    )


class RecoveryInvestigationFinding(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Immutable. One normalised finding, optionally citation-backed."""

    __tablename__ = "recovery_investigation_findings"
    __table_args__ = (
        UniqueConstraint(
            "investigation_id", "ordinal", name="uq_recovery_investigation_findings_ordinal"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_investigations.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[FindingKind] = mapped_column(_finding_kind, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Any | None] = mapped_column(Numeric(4, 3), nullable=True)
    citation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("citations.id", ondelete="SET NULL"), nullable=True
    )

    investigation: Mapped[RecoveryInvestigation] = relationship(back_populates="findings")
    citation: Mapped[Any | None] = relationship("Citation")


class RecoveryPacket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One audit-friendly artifact per recovery candidate. Mutable only for
    `current_version_id` and `human_overrides`; the versions themselves are frozen."""

    __tablename__ = "recovery_packets"
    __table_args__ = (
        UniqueConstraint("recovery_candidate_id", name="uq_recovery_packets_candidate"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    recovery_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_candidates.id", ondelete="CASCADE"), nullable=False
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recovery_packet_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    human_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    versions: Mapped[list[RecoveryPacketVersion]] = relationship(
        back_populates="packet",
        cascade="all, delete-orphan",
        foreign_keys="RecoveryPacketVersion.recovery_packet_id",
        order_by="RecoveryPacketVersion.version_no",
    )


class RecoveryPacketVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Immutable. Regenerating a packet writes a new version and supersedes the rest."""

    __tablename__ = "recovery_packet_versions"
    __table_args__ = (
        UniqueConstraint("recovery_packet_id", "version_no", name="uq_recovery_packet_versions_no"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    recovery_packet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_packets.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PacketVersionStatus] = mapped_column(
        _packet_version_status, nullable=False, default=PacketVersionStatus.DRAFT
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rendered_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_calculations.id", ondelete="RESTRICT"), nullable=False
    )
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recovery_investigations.id", ondelete="SET NULL"), nullable=True
    )
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    packet: Mapped[RecoveryPacket] = relationship(
        back_populates="versions", foreign_keys=[recovery_packet_id]
    )


class RecoveryAllocation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Immutable. One participant's penny-exact share of a calculation's layer recovery."""

    __tablename__ = "recovery_allocations"
    __table_args__ = (
        UniqueConstraint(
            "recovery_calculation_id",
            "reinsurer_id",
            name="uq_recovery_allocations_calculation_reinsurer",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    recovery_calculation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_calculations.id", ondelete="CASCADE"), nullable=False
    )
    reinsurer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reinsurers.id", ondelete="RESTRICT"), nullable=False
    )
    participation_share: Mapped[Any] = mapped_column(SHARE, nullable=False)
    allocated_recovery: Mapped[Any] = mapped_column(MONEY, nullable=False)

    calculation: Mapped[RecoveryCalculation] = relationship(back_populates="allocations")
    reinsurer: Mapped[Any] = relationship("Reinsurer")


class RecoveryNotice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A drafted notice for one recovery candidate. Mutable while DRAFT (a human
    edits the prose); frozen on APPROVE. Re-drafting supersedes the prior notice of
    the same kind. Cedeon never sends it — there is no send action (AI_ARCH §2c)."""

    __tablename__ = "recovery_notices"
    __table_args__ = (
        Index("ix_recovery_notices_candidate", "recovery_candidate_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    recovery_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_candidates.id", ondelete="CASCADE"), nullable=False
    )
    recovery_packet_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recovery_packet_versions.id", ondelete="SET NULL"), nullable=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[NoticeKind] = mapped_column(_notice_kind, nullable=False)
    status: Mapped[NoticeStatus] = mapped_column(
        _notice_status, nullable=False, default=NoticeStatus.DRAFT
    )
    recipient: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    key_figures: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    caveats: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    used_only_provided_facts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes_for_reviewer: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Recoverable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One reinsurer's leg of a confirmed recovery, tracked from notified to cash
    collected (docs/DECISIONS.md ADR-0024). ``expected_amount`` is a fact carried
    from the immutable calculation; ``agreed`` / ``billed`` / ``collected`` are
    human-entered facts, corrected over time — every change is audited. No AI."""

    __tablename__ = "recoverables"
    __table_args__ = (
        UniqueConstraint(
            "recovery_candidate_id",
            "reinsurer_id",
            name="uq_recoverables_candidate_reinsurer",
        ),
        CheckConstraint("expected_amount >= 0", name="expected_nonneg"),
        CheckConstraint("collected_amount >= 0", name="collected_nonneg"),
        Index("ix_recoverables_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    recovery_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_candidates.id", ondelete="RESTRICT"), nullable=False
    )
    recovery_calculation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_calculations.id", ondelete="RESTRICT"), nullable=False
    )
    reinsurer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reinsurers.id", ondelete="RESTRICT"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[RecoverableStatus] = mapped_column(
        _recoverable_status, nullable=False, default=RecoverableStatus.PENDING
    )
    expected_amount: Mapped[Any] = mapped_column(MONEY, nullable=False)
    agreed_amount: Mapped[Any | None] = mapped_column(MONEY, nullable=True)
    billed_amount: Mapped[Any | None] = mapped_column(MONEY, nullable=True)
    collected_amount: Mapped[Any] = mapped_column(MONEY, nullable=False, server_default=text("0"))
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    notified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agreed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    reinsurer: Mapped[Any] = relationship("Reinsurer")


class ReinsurerStatement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A batch of figures a reinsurer stated (agreed / paid), reconciled line by
    line against what Cedeon holds. The lines are supplied directly — a file
    importer for real bordereau formats is a later addition."""

    __tablename__ = "reinsurer_statements"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    statement_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list[ReinsurerStatementLine]] = relationship(
        back_populates="statement",
        cascade="all, delete-orphan",
        order_by="ReinsurerStatementLine.row_number",
    )


class ReinsurerStatementLine(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "reinsurer_statement_lines"
    __table_args__ = (
        UniqueConstraint("statement_id", "row_number", name="uq_reinsurer_statement_lines_row"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    statement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reinsurer_statements.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reinsurer_name: Mapped[str] = mapped_column(String(300), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    their_agreed: Mapped[Any | None] = mapped_column(MONEY, nullable=True)
    their_paid: Mapped[Any | None] = mapped_column(MONEY, nullable=True)
    matched_recoverable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recoverables.id", ondelete="SET NULL"), nullable=True
    )
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    statement: Mapped[ReinsurerStatement] = relationship(back_populates="lines")
