"""Document upload, listing, parse output, and content streaming."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.context import (
    AuthedContext,
    DocumentServiceDep,
    require_write_role,
)
from app.api.schemas.documents import (
    ChunkList,
    ChunkOut,
    DocumentDetail,
    DocumentList,
    DocumentOut,
    PageList,
    PageOut,
    ParseInfo,
)
from app.db.models.documents import Document, DocumentParse
from app.domain.documents import DocumentKind

router = APIRouter(
    prefix="/documents", tags=["documents"], dependencies=[Depends(require_write_role)]
)


def _doc_out(document: Document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        kind=document.kind,
        original_filename=document.original_filename,
        content_type=document.content_type,
        byte_size=document.byte_size,
        status=document.status,
        created_at=document.created_at,
    )


def _parse_info(parse: DocumentParse | None) -> ParseInfo | None:
    if parse is None:
        return None
    return ParseInfo(
        id=parse.id,
        parser_name=parse.parser_name,
        parser_version=parse.parser_version,
        status=parse.status,
        page_count=parse.page_count,
        ocr_used=parse.ocr_used,
        error=parse.error,
        started_at=parse.started_at,
        finished_at=parse.finished_at,
    )


@router.post(
    "",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document (PDF); parsing is enqueued",
    operation_id="uploadDocument",
)
async def upload_document(
    context: AuthedContext,
    service: DocumentServiceDep,
    file: Annotated[UploadFile, File()],
    kind: Annotated[DocumentKind, Form()] = DocumentKind.TREATY,
) -> DocumentOut:
    data = await file.read()
    document = await service.upload(
        context,
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "application/pdf",
        data=data,
        kind=kind,
    )
    return _doc_out(document)


@router.get("", response_model=DocumentList, operation_id="listDocuments")
async def list_documents(context: AuthedContext, service: DocumentServiceDep) -> DocumentList:
    documents = await service.list_documents(context)
    return DocumentList(documents=[_doc_out(d) for d in documents])


@router.get("/{document_id}", response_model=DocumentDetail, operation_id="getDocument")
async def get_document(
    document_id: UUID, context: AuthedContext, service: DocumentServiceDep
) -> DocumentDetail:
    document = await service.get(context, document_id)
    parse = await service.current_parse(context, document_id)
    return DocumentDetail(document=_doc_out(document), current_parse=_parse_info(parse))


@router.get("/{document_id}/pages", response_model=PageList, operation_id="getDocumentPages")
async def get_document_pages(
    document_id: UUID, context: AuthedContext, service: DocumentServiceDep
) -> PageList:
    pages = await service.pages(context, document_id)
    return PageList(
        pages=[
            PageOut(page_number=p.page_number, width=p.width, height=p.height, text=p.text)
            for p in pages
        ]
    )


@router.get("/{document_id}/chunks", response_model=ChunkList, operation_id="getDocumentChunks")
async def get_document_chunks(
    document_id: UUID, context: AuthedContext, service: DocumentServiceDep
) -> ChunkList:
    chunks = await service.chunks(context, document_id)
    return ChunkList(
        chunks=[
            ChunkOut(
                ordinal=c.ordinal,
                page_from=c.page_from,
                page_to=c.page_to,
                section_path=c.section_path,
                heading=c.heading,
                text=c.text,
                char_start=c.char_start,
                char_end=c.char_end,
            )
            for c in chunks
        ]
    )


@router.get(
    "/{document_id}/content",
    summary="Stream the original file (auth-checked)",
    operation_id="getDocumentContent",
    response_class=StreamingResponse,
)
async def get_document_content(
    document_id: UUID, context: AuthedContext, service: DocumentServiceDep
) -> StreamingResponse:
    document, stream = await service.stream_content(context, document_id)
    return StreamingResponse(
        stream,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{document.original_filename}"',
            "Cache-Control": "private, no-store",
        },
    )
