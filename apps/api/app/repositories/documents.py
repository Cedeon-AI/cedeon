"""Repositories for the document pipeline. Every query is organization-scoped."""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.documents import Document, DocumentChunk, DocumentPage, DocumentParse
from app.domain.documents import ParseStatus


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID, document_id: UUID) -> Document | None:
        result = await self._session.execute(
            select(Document).where(
                Document.id == document_id, Document.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sha256(self, organization_id: UUID, sha256: str) -> Document | None:
        result = await self._session.execute(
            select(Document).where(
                Document.organization_id == organization_id, Document.sha256 == sha256
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: UUID) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .where(Document.organization_id == organization_id)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    def add(self, document: Document) -> None:
        self._session.add(document)

    # --- parses / pages / chunks ---------------------------------------

    def add_parse(self, parse: DocumentParse) -> None:
        self._session.add(parse)

    async def current_parse(self, organization_id: UUID, document_id: UUID) -> DocumentParse | None:
        result = await self._session.execute(
            select(DocumentParse)
            .where(
                DocumentParse.organization_id == organization_id,
                DocumentParse.document_id == document_id,
                DocumentParse.status == ParseStatus.SUCCEEDED,
                DocumentParse.superseded_at.is_(None),
            )
            .order_by(DocumentParse.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def supersede_other_parses(
        self, document_id: UUID, keep_parse_id: UUID, *, at: dt.datetime
    ) -> None:
        parses = (
            await self._session.execute(
                select(DocumentParse).where(
                    DocumentParse.document_id == document_id,
                    DocumentParse.id != keep_parse_id,
                    DocumentParse.superseded_at.is_(None),
                )
            )
        ).scalars()
        for parse in parses:
            parse.superseded_at = at

    async def list_pages(self, organization_id: UUID, parse_id: UUID) -> list[DocumentPage]:
        result = await self._session.execute(
            select(DocumentPage)
            .where(
                DocumentPage.organization_id == organization_id,
                DocumentPage.parse_id == parse_id,
            )
            .order_by(DocumentPage.page_number)
        )
        return list(result.scalars().all())

    async def list_chunks(self, organization_id: UUID, parse_id: UUID) -> list[DocumentChunk]:
        result = await self._session.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.organization_id == organization_id,
                DocumentChunk.parse_id == parse_id,
            )
            .order_by(DocumentChunk.ordinal)
        )
        return list(result.scalars().all())
