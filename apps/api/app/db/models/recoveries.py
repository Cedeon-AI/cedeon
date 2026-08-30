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
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.recoveries import RecoveryCandidateStatus

_candidate_status = SAEnum(
    RecoveryCandidateStatus,
    native_enum=False,
    length=20,
    create_constraint=False,
    name="recovery_candidate_status",
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
