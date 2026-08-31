"""Loss imports: the raw file, the mapping used, every raw row, and the
immutable ``underlying_losses`` snapshot they commit to (docs/PRODUCT.md §10-12)."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
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
from app.domain.losses import LossImportStatus, LossRowStatus

_import_status = SAEnum(
    LossImportStatus,
    native_enum=False,
    length=16,
    create_constraint=False,
    name="loss_import_status",
)
_row_status = SAEnum(
    LossRowStatus, native_enum=False, length=12, create_constraint=False, name="loss_row_status"
)
MONEY = Numeric(20, 2)


class LossImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "loss_imports"
    __table_args__ = (Index("ix_loss_imports_org_created", "organization_id", "created_at"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    header_columns: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    column_mapping: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[LossImportStatus] = mapped_column(
        _import_status, nullable=False, default=LossImportStatus.UPLOADED
    )
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    committed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rows: Mapped[list[LossImportRow]] = relationship(
        back_populates="loss_import", cascade="all, delete-orphan"
    )


class LossImportRow(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "loss_import_rows"
    __table_args__ = (
        UniqueConstraint("loss_import_id", "row_number", name="uq_loss_import_rows_import_row"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    loss_import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loss_imports.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parsed: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[LossRowStatus] = mapped_column(
        _row_status, nullable=False, default=LossRowStatus.OK
    )
    issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    loss_import: Mapped[LossImport] = relationship(back_populates="rows")


class LossEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "loss_events"
    __table_args__ = (Index("ix_loss_events_org", "organization_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reinsurance_programs.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    event_identifier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    catastrophe_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    date_of_loss_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    date_of_loss_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The analyst's stated occurrence basis (UX_STUDY finding 8). Informational for
    # now — the deterministic engine does not yet apply an hours clause.
    peril: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hours_clause_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)

    losses: Mapped[list[UnderlyingLoss]] = relationship(back_populates="loss_event")


class UnderlyingLoss(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Immutable snapshot of one committed import row (docs/DATA_MODEL.md §2)."""

    __tablename__ = "underlying_losses"
    __table_args__ = (
        UniqueConstraint("loss_import_row_id", name="uq_underlying_losses_import_row"),
        CheckConstraint("gross_incurred >= 0", name="gross_incurred_non_negative"),
        Index("ix_underlying_losses_event", "loss_event_id"),
        Index("ix_underlying_losses_org", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    loss_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("loss_events.id", ondelete="SET NULL"), nullable=True
    )
    loss_import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loss_imports.id", ondelete="RESTRICT"), nullable=False
    )
    loss_import_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loss_import_rows.id", ondelete="RESTRICT"), nullable=False
    )
    claim_id: Mapped[str] = mapped_column(String(200), nullable=False)
    date_of_loss: Mapped[dt.date] = mapped_column(Date, nullable=False)
    reported_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    gross_incurred: Mapped[Any] = mapped_column(MONEY, nullable=False)
    gross_paid: Mapped[Any | None] = mapped_column(MONEY, nullable=True)
    gross_case_reserve: Mapped[Any | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cause_of_loss: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    loss_event: Mapped[LossEvent | None] = relationship(back_populates="losses")
