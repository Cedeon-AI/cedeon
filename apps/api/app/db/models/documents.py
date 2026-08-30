"""Document pipeline: immutable uploads, parse runs, and their pages/chunks.

Re-parsing creates a new ``document_parses`` row; older parses (and their
pages/chunks) are retained and marked ``superseded_at``."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.documents import DocumentKind, DocumentStatus, ParseStatus

_kind_enum = SAEnum(
    DocumentKind, native_enum=False, length=24, create_constraint=False, name="document_kind"
)
_doc_status_enum = SAEnum(
    DocumentStatus, native_enum=False, length=16, create_constraint=False, name="document_status"
)
_parse_status_enum = SAEnum(
    ParseStatus, native_enum=False, length=16, create_constraint=False, name="parse_status"
)


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "sha256", name="uq_documents_org_sha256"),
        Index("ix_documents_org_created", "organization_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[DocumentKind] = mapped_column(_kind_enum, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        _doc_status_enum, nullable=False, default=DocumentStatus.UPLOADED
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    parses: Mapped[list[DocumentParse]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentParse(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "document_parses"
    __table_args__ = (Index("ix_document_parses_document_id", "document_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    parser_name: Mapped[str] = mapped_column(String(50), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[ParseStatus] = mapped_column(_parse_status_enum, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    document: Mapped[Document] = relationship(back_populates="parses")
    pages: Mapped[list[DocumentPage]] = relationship(
        back_populates="parse", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="parse", cascade="all, delete-orphan"
    )


class DocumentPage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("parse_id", "page_number", name="uq_document_pages_parse_page"),
        Index("ix_document_pages_document_id", "document_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    parse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_parses.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    parse: Mapped[DocumentParse] = relationship(back_populates="pages")


class DocumentChunk(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("parse_id", "ordinal", name="uq_document_chunks_parse_ordinal"),
        Index("ix_document_chunks_document_id", "document_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    parse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_parses.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    page_from: Mapped[int] = mapped_column(Integer, nullable=False)
    page_to: Mapped[int] = mapped_column(Integer, nullable=False)
    section_path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    parse: Mapped[DocumentParse] = relationship(back_populates="chunks")
