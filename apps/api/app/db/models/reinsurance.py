"""Reinsurance structure: cedents, programs, reinsurers, treaties, versions,
layers, participations, and validated scalar terms.

`treaty_versions` is the immutable executable unit. Layers / participations /
terms belong to a version and freeze with it (see docs/DATA_MODEL.md §2)."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Date,
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

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.treaties import TermStatus, TreatyType, TreatyVersionStatus

_treaty_type = SAEnum(
    TreatyType, native_enum=False, length=32, create_constraint=False, name="treaty_type"
)
_version_status = SAEnum(
    TreatyVersionStatus,
    native_enum=False,
    length=24,
    create_constraint=False,
    name="treaty_version_status",
)
_term_status = SAEnum(
    TermStatus, native_enum=False, length=16, create_constraint=False, name="treaty_term_status"
)

MONEY = Numeric(20, 2)
SHARE = Numeric(9, 6)


class Cedent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cedents"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_cedents_org_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)


class Reinsurer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reinsurers"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_reinsurers_org_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)


class ReinsuranceProgram(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reinsurance_programs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "cedent_id", "name", name="uq_programs_org_cedent_name"
        ),
        Index("ix_reinsurance_programs_cedent_id", "cedent_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    cedent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cedents.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    treaty_year: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    cedent: Mapped[Cedent] = relationship()


class Treaty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "treaties"
    __table_args__ = (Index("ix_treaties_program_id", "program_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reinsurance_programs.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    treaty_type: Mapped[TreatyType] = mapped_column(
        _treaty_type, nullable=False, default=TreatyType.PER_OCCURRENCE_XOL
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("treaty_versions.id", ondelete="SET NULL", use_alter=True), nullable=True
    )

    program: Mapped[ReinsuranceProgram] = relationship()
    versions: Mapped[list[TreatyVersion]] = relationship(
        back_populates="treaty",
        cascade="all, delete-orphan",
        foreign_keys="TreatyVersion.treaty_id",
    )


class TreatyVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "treaty_versions"
    __table_args__ = (
        UniqueConstraint("treaty_id", "version_no", name="uq_treaty_versions_treaty_version_no"),
        Index("ix_treaty_versions_treaty_id", "treaty_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    treaty_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaties.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[TreatyVersionStatus] = mapped_column(
        _version_status, nullable=False, default=TreatyVersionStatus.DRAFT
    )
    effective_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    validated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    treaty: Mapped[Treaty] = relationship(back_populates="versions", foreign_keys=[treaty_id])
    layers: Mapped[list[TreatyLayer]] = relationship(
        back_populates="treaty_version", cascade="all, delete-orphan"
    )
    participations: Mapped[list[TreatyParticipation]] = relationship(
        back_populates="treaty_version", cascade="all, delete-orphan"
    )
    terms: Mapped[list[TreatyTerm]] = relationship(
        back_populates="treaty_version", cascade="all, delete-orphan"
    )


class TreatyLayer(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "treaty_layers"
    __table_args__ = (
        UniqueConstraint("treaty_version_id", "layer_no", name="uq_treaty_layers_version_layer_no"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    treaty_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaty_versions.id", ondelete="CASCADE"), nullable=False
    )
    layer_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attachment: Mapped[Any] = mapped_column(MONEY, nullable=False)
    limit: Mapped[Any] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reinstatements: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    treaty_version: Mapped[TreatyVersion] = relationship(back_populates="layers")


class TreatyParticipation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "treaty_participations"
    __table_args__ = (
        UniqueConstraint(
            "treaty_version_id", "reinsurer_id", name="uq_treaty_participations_version_reinsurer"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    treaty_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaty_versions.id", ondelete="CASCADE"), nullable=False
    )
    reinsurer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reinsurers.id", ondelete="RESTRICT"), nullable=False
    )
    placed_share: Mapped[Any] = mapped_column(SHARE, nullable=False)
    signed_share: Mapped[Any | None] = mapped_column(SHARE, nullable=True)
    broker_name: Mapped[str | None] = mapped_column(String(300), nullable=True)

    treaty_version: Mapped[TreatyVersion] = relationship(back_populates="participations")
    reinsurer: Mapped[Reinsurer] = relationship()


class TreatyTerm(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A human-validated scalar term. Only rows here feed downstream logic."""

    __tablename__ = "treaty_terms"
    __table_args__ = (
        UniqueConstraint("treaty_version_id", "key", name="uq_treaty_terms_version_key"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    treaty_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("treaty_versions.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[TermStatus] = mapped_column(
        _term_status, nullable=False, default=TermStatus.CONFIRMED
    )
    derived_from_candidate_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    review_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    treaty_version: Mapped[TreatyVersion] = relationship(back_populates="terms")
