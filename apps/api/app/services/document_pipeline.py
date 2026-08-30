"""The parse pipeline: fetch blob → parse → persist pages → chunk → persist chunks.

Runnable directly (tests) or from the ``parse_document`` Procrastinate task. One
transaction per run; on parser failure the parse row and document are marked
failed and the error re-raised for the job runner to retry.
"""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.documents import Document, DocumentChunk, DocumentPage, DocumentParse
from app.domain.audit import ActorType, AuditRecord
from app.domain.documents import DocumentStatus, ParseStatus, chunk_document
from app.domain.documents.parsed import ParsedDocument
from app.parsing.base import DocumentParser
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.storage.base import ObjectStore

log = get_logger(__name__)


class DocumentNotFoundError(Exception):
    pass


class DocumentPipeline:
    def __init__(self, session: AsyncSession, store: ObjectStore, parser: DocumentParser) -> None:
        self._session = session
        self._store = store
        self._parser = parser
        self._documents = DocumentRepository(session)
        self._audit = AuditRepository(session)

    async def run(self, organization_id: UUID, document_id: UUID) -> DocumentParse:
        document = await self._documents.get(organization_id, document_id)
        if document is None:
            raise DocumentNotFoundError(
                f"document {document_id} not found in org {organization_id}"
            )

        now = dt.datetime.now(dt.UTC)
        document.status = DocumentStatus.PARSING
        parse = DocumentParse(
            organization_id=organization_id,
            document_id=document.id,
            parser_name=self._parser.name,
            parser_version=self._parser.version,
            status=ParseStatus.RUNNING,
            started_at=now,
            ocr_used=False,
        )
        self._documents.add_parse(parse)
        await self._session.flush()

        try:
            data = await self._store.get_bytes(document.storage_key)
            parsed = await self._parser.parse(
                data,
                filename=document.original_filename,
                content_type=document.content_type,
            )
        except Exception as exc:
            await self._fail(document, parse, exc, organization_id)
            raise

        self._persist_pages(organization_id, document, parse, parsed)
        chunk_count = self._persist_chunks(organization_id, document, parse, parsed)

        parse.status = ParseStatus.SUCCEEDED
        parse.page_count = parsed.page_count
        parse.ocr_used = parsed.ocr_used
        parse.finished_at = dt.datetime.now(dt.UTC)
        document.status = DocumentStatus.PARSED

        await self._documents.supersede_other_parses(
            document.id, parse.id, at=dt.datetime.now(dt.UTC)
        )
        self._audit.record(
            AuditRecord(
                organization_id=organization_id,
                actor_type=ActorType.SYSTEM,
                action="document.parsed",
                entity_type="document",
                entity_id=document.id,
                summary=(
                    f"parsed {document.original_filename!r} with {self._parser.name} "
                    f"→ {parsed.page_count} pages, {chunk_count} chunks"
                ),
                payload={
                    "parse_id": str(parse.id),
                    "parser": self._parser.name,
                    "parser_version": self._parser.version,
                    "pages": parsed.page_count,
                    "chunks": chunk_count,
                },
            )
        )
        await self._session.commit()
        log.info(
            "document.parsed",
            document_id=str(document.id),
            pages=parsed.page_count,
            chunks=chunk_count,
        )
        return parse

    async def _fail(
        self,
        document: Document,
        parse: DocumentParse,
        exc: Exception,
        organization_id: UUID,
    ) -> None:
        parse.status = ParseStatus.FAILED
        parse.error = str(exc)[:2000]
        parse.finished_at = dt.datetime.now(dt.UTC)
        document.status = DocumentStatus.PARSE_FAILED
        self._audit.record(
            AuditRecord(
                organization_id=organization_id,
                actor_type=ActorType.SYSTEM,
                action="document.parse_failed",
                entity_type="document",
                entity_id=document.id,
                summary=f"parse of {document.original_filename!r} failed: {type(exc).__name__}",
                payload={"parse_id": str(parse.id), "error": str(exc)[:500]},
            )
        )
        await self._session.commit()
        log.warning(
            "document.parse_failed",
            document_id=str(document.id),
            error_type=type(exc).__name__,
        )

    def _persist_pages(
        self,
        organization_id: UUID,
        document: Document,
        parse: DocumentParse,
        parsed: ParsedDocument,
    ) -> None:
        for page in parsed.pages:
            self._session.add(
                DocumentPage(
                    organization_id=organization_id,
                    document_id=document.id,
                    parse_id=parse.id,
                    page_number=page.page_number,
                    width=page.width,
                    height=page.height,
                    text=page.text,
                )
            )

    def _persist_chunks(
        self,
        organization_id: UUID,
        document: Document,
        parse: DocumentParse,
        parsed: ParsedDocument,
    ) -> int:
        chunks = chunk_document(parsed)
        for chunk in chunks:
            self._session.add(
                DocumentChunk(
                    organization_id=organization_id,
                    document_id=document.id,
                    parse_id=parse.id,
                    ordinal=chunk.ordinal,
                    page_from=chunk.page_from,
                    page_to=chunk.page_to,
                    section_path=chunk.section_path,
                    heading=chunk.heading,
                    text=chunk.text,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                )
            )
        return len(chunks)
