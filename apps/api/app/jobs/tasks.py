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


@procrastinate_app.task(name="extract_treaty", queue="ai", pass_context=False)
async def extract_treaty(*, organization_id: str, treaty_version_id: str) -> dict[str, Any]:
    settings = get_settings()
    async with job_session() as session:
        from app.services.extraction import TreatyExtractionService

        service = TreatyExtractionService(session, settings)
        run = await service.run(UUID(organization_id), UUID(treaty_version_id))
    return {"agent_run_id": str(run.id), "status": run.status.value}


async def enqueue_extract_treaty(organization_id: UUID, treaty_version_id: UUID) -> None:
    await extract_treaty.defer_async(
        organization_id=str(organization_id), treaty_version_id=str(treaty_version_id)
    )


@procrastinate_app.task(name="investigate_recovery_candidate", queue="ai", pass_context=False)
async def investigate_recovery_candidate(
    *, organization_id: str, candidate_id: str, actor_id: str | None = None
) -> dict[str, Any]:
    settings = get_settings()
    async with job_session() as session:
        from app.services.investigation import InvestigationService

        service = InvestigationService(session, settings)
        investigation = await service.investigate(
            UUID(organization_id),
            UUID(candidate_id),
            actor_id=UUID(actor_id) if actor_id else None,
        )
    return {"investigation_id": str(investigation.id), "status": investigation.status.value}


async def enqueue_investigate_recovery(
    organization_id: UUID, candidate_id: UUID, actor_id: UUID | None = None
) -> None:
    await investigate_recovery_candidate.defer_async(
        organization_id=str(organization_id),
        candidate_id=str(candidate_id),
        actor_id=str(actor_id) if actor_id else None,
    )


@procrastinate_app.task(name="draft_recovery_notice", queue="ai", pass_context=False)
async def draft_recovery_notice(
    *,
    organization_id: str,
    candidate_id: str,
    kind: str,
    recipient: dict[str, Any],
    actor_id: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    async with job_session() as session:
        from app.domain.recoveries import NoticeKind
        from app.services.notice import NoticeService

        notice = await NoticeService(session, settings).draft(
            UUID(organization_id),
            UUID(candidate_id),
            kind=NoticeKind(kind),
            recipient={k: str(v) for k, v in recipient.items()},
            actor_id=UUID(actor_id) if actor_id else None,
        )
    return {"recovery_notice_id": str(notice.id), "status": notice.status.value}


async def enqueue_draft_notice(
    organization_id: UUID,
    candidate_id: UUID,
    *,
    kind: str,
    recipient: dict[str, str],
    actor_id: UUID | None = None,
) -> None:
    await draft_recovery_notice.defer_async(
        organization_id=str(organization_id),
        candidate_id=str(candidate_id),
        kind=kind,
        recipient=recipient,
        actor_id=str(actor_id) if actor_id else None,
    )
