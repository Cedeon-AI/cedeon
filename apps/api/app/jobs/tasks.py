"""Job definitions.

- ``ping`` — proves the API → queue → worker path.
- ``parse_document`` — fetch blob, parse, persist pages + chunks (Phase 2).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger
from app.jobs.app import procrastinate_app
from app.jobs.context import job_session
from app.parsing import build_parser
from app.services.document_pipeline import DocumentPipeline
from app.storage import build_object_store

log = get_logger(__name__)


@procrastinate_app.task(name="ping")
async def ping(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    log.info("job.ping", payload=payload or {})
    return {"pong": True, "echo": payload or {}}


@procrastinate_app.task(name="parse_document", queue="documents", pass_context=False)
async def parse_document(*, organization_id: str, document_id: str) -> dict[str, Any]:
    settings = get_settings()
    async with job_session() as session:
        pipeline = DocumentPipeline(
            session,
            build_object_store(settings),
            build_parser(settings),
        )
        parse = await pipeline.run(UUID(organization_id), UUID(document_id))
    return {"parse_id": str(parse.id), "status": parse.status.value}


async def enqueue_parse_document(organization_id: UUID, document_id: UUID) -> None:
    await parse_document.defer_async(
        organization_id=str(organization_id), document_id=str(document_id)
    )
