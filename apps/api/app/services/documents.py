"""Document use-cases: upload (→ enqueue parse), list, read, stream content."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id
from app.db.models.documents import Document, DocumentChunk, DocumentPage, DocumentParse
from app.domain.audit import ActorType, AuditRecord
from app.domain.documents import DocumentKind, DocumentStatus
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import NotFoundError, ValidationError
from app.storage.base import ObjectNotFoundError, ObjectStore

# (organization_id, document_id) -> None
ParseEnqueuer = Callable[[UUID, UUID], Awaitable[None]]

_ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        store: ObjectStore,
        *,
        enqueue_parse: ParseEnqueuer,
        max_upload_bytes: int,
    ) -> None:
        self._session = session
        self._store = store
        self._enqueue_parse = enqueue_parse
        self._max_upload_bytes = max_upload_bytes
        self._documents = DocumentRepository(session)
        self._audit = AuditRepository(session)

    async def upload(
        self,
        context: AuthenticatedContext,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        kind: DocumentKind,
    ) -> Document:
        if not data:
            raise ValidationError("the uploaded file is empty")
        if len(data) > self._max_upload_bytes:
            raise ValidationError(
                f"file exceeds the {self._max_upload_bytes // (1024 * 1024)} MB limit"
            )
        if content_type not in _ALLOWED_CONTENT_TYPES and not filename.lower().endswith(".pdf"):
            raise ValidationError("only PDF documents are supported in this phase")

        org_id = context.organization.id
        sha256 = hashlib.sha256(data).hexdigest()

        existing = await self._documents.get_by_sha256(org_id, sha256)
        if existing is not None:
            return existing

        document = Document(
            organization_id=org_id,
            kind=kind,
            original_filename=filename[:500],
            content_type=content_type or "application/pdf",
            byte_size=len(data),
            sha256=sha256,
            storage_key="",
            status=DocumentStatus.UPLOADED,
            uploaded_by=context.user.id,
        )
        self._documents.add(document)
        await self._session.flush()

        document.storage_key = f"org/{org_id}/documents/{document.id}/{sha256}"
        await self._store.put(document.storage_key, data, content_type=document.content_type)

        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="document.uploaded",
                entity_type="document",
                entity_id=document.id,
                summary=f"{context.user.email} uploaded {filename!r} ({kind.value})",
                payload={"kind": kind.value, "byte_size": len(data), "sha256": sha256},
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        await self._enqueue_parse(org_id, document.id)
        return document

    async def list_documents(self, context: AuthenticatedContext) -> list[Document]:
        return await self._documents.list_for_org(context.organization.id)

    async def get(self, context: AuthenticatedContext, document_id: UUID) -> Document:
        document = await self._documents.get(context.organization.id, document_id)
        if document is None:
            raise NotFoundError("document not found")
        return document

    async def current_parse(
        self, context: AuthenticatedContext, document_id: UUID
    ) -> DocumentParse | None:
        await self.get(context, document_id)
        return await self._documents.current_parse(context.organization.id, document_id)

    async def pages(self, context: AuthenticatedContext, document_id: UUID) -> list[DocumentPage]:
        parse = await self.current_parse(context, document_id)
        if parse is None:
            return []
        return await self._documents.list_pages(context.organization.id, parse.id)

    async def chunks(self, context: AuthenticatedContext, document_id: UUID) -> list[DocumentChunk]:
        parse = await self.current_parse(context, document_id)
        if parse is None:
            return []
        return await self._documents.list_chunks(context.organization.id, parse.id)

    async def stream_content(
        self, context: AuthenticatedContext, document_id: UUID
    ) -> tuple[Document, AsyncIterator[bytes]]:
        document = await self.get(context, document_id)
        try:
            return document, self._store.stream(document.storage_key)
        except ObjectNotFoundError as exc:
            raise NotFoundError("document content is missing from storage") from exc
