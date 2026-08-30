"""Run the parse pipeline inline, standing in for the Procrastinate worker."""

from __future__ import annotations

from uuid import UUID

from app.parsing import PyMuPDFParser
from app.services.document_pipeline import DocumentPipeline
from app.storage.base import ObjectStore


async def run_parse(session: object, store: ObjectStore, org_id: UUID, document_id: UUID) -> object:
    pipeline = DocumentPipeline(session, store, PyMuPDFParser())  # type: ignore[arg-type]
    return await pipeline.run(org_id, document_id)
