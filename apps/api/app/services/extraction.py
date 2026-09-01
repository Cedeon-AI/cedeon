"""Run treaty extraction and persist candidates + AI-run telemetry.

Runnable directly (tests inject a fake extractor) or from the ``extract_treaty``
Procrastinate task. One model call, then everything is a candidate a human must
validate (docs/DECISIONS.md ADR-0011)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.extraction import ExtractionResult, extract_treaty_terms
from app.ai.extraction.schema import Provenance, TermCandidateStatus
from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models.extraction import AgentRun, Citation, TreatyTermCandidate
from app.domain.ai import AgentRunStatus, AgentType, ExtractedTermStatus
from app.domain.audit import ActorType, AuditRecord
from app.domain.treaties import TreatyVersionStatus
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.extraction import (
    AgentRunRepository,
    CitationRepository,
    TermCandidateRepository,
)
from app.repositories.reinsurance import TreatyVersionRepository
from app.services.ai_budget import AiBudgetService
from app.services.errors import ConflictError

log = get_logger(__name__)

# (document_blocks, settings) -> ExtractionResult
Extractor = Callable[..., Awaitable[ExtractionResult]]

_MATERIAL_KEYS = frozenset({"attachment", "limit"})


class ExtractionInputError(Exception):
    pass


class TreatyExtractionService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        extractor: Extractor = extract_treaty_terms,
    ) -> None:
        self._session = session
        self._settings = settings
        self._extractor = extractor
        self._versions = TreatyVersionRepository(session)
        self._documents = DocumentRepository(session)
        self._runs = AgentRunRepository(session)
        self._citations = CitationRepository(session)
        self._candidates = TermCandidateRepository(session)
        self._audit = AuditRepository(session)

    async def run(self, organization_id: UUID, treaty_version_id: UUID) -> AgentRun:
        await AiBudgetService(self._session, self._settings).enforce(organization_id)

        version = await self._versions.get(organization_id, treaty_version_id)
        if version is None:
            raise ExtractionInputError(f"treaty version {treaty_version_id} not found")
        if version.source_document_id is None:
            raise ExtractionInputError("treaty version has no source document")

        document = await self._documents.get(organization_id, version.source_document_id)
        if document is None:
            raise ExtractionInputError("source document not found")
        parse = await self._documents.current_parse(organization_id, document.id)
        if parse is None:
            raise ExtractionInputError("source document has not been parsed yet")
        chunks = await self._documents.list_chunks(organization_id, parse.id)
        if not chunks:
            raise ExtractionInputError("source document produced no chunks")

        blocks = [
            f"[page {c.page_from}] {c.section_path or c.heading or ''}\n{c.text}".strip()
            for c in chunks
        ]

        if await self._runs.has_active_run(
            organization_id, AgentType.TREATY_EXTRACTION, version.id
        ):
            raise ConflictError("an extraction is already running for this treaty version")

        version.status = TreatyVersionStatus.EXTRACTING
        started = dt.datetime.now(dt.UTC)
        run = AgentRun(
            organization_id=organization_id,
            agent_type=AgentType.TREATY_EXTRACTION,
            subject_type="treaty_version",
            subject_id=version.id,
            provider=self._settings.treaty_extraction_model.split(":", 1)[0],
            model=self._settings.treaty_extraction_model,
            status=AgentRunStatus.RUNNING,
            input_ref={"document_id": str(document.id), "chunks": len(chunks)},
            started_at=started,
        )
        self._runs.add(run)
        await self._session.flush()

        try:
            result = await self._extractor(document_blocks=blocks, settings=self._settings)
        except Exception as exc:
            run.status = AgentRunStatus.FAILED
            run.error = str(exc)[:2000]
            run.finished_at = dt.datetime.now(dt.UTC)
            version.status = TreatyVersionStatus.DRAFT
            self._audit.record(
                AuditRecord(
                    organization_id=organization_id,
                    actor_type=ActorType.SYSTEM,
                    action="treaty.extraction_failed",
                    entity_type="treaty_version",
                    entity_id=version.id,
                    summary=f"treaty extraction failed: {type(exc).__name__}",
                    payload={"agent_run_id": str(run.id), "error": str(exc)[:500]},
                )
            )
            await self._session.commit()
            log.warning("treaty.extraction_failed", error_type=type(exc).__name__)
            raise

        await self._candidates.delete_for_version(version.id)
        await self._session.flush()

        candidate_count = self._persist_candidates(
            organization_id, version.id, document.id, run.id, result
        )

        run.status = AgentRunStatus.SUCCEEDED
        run.prompt_version = result.prompt_version
        run.provider = result.provider
        run.model = result.model
        run.output = result.output
        run.input_tokens = result.input_tokens
        run.output_tokens = result.output_tokens
        run.cost_usd = result.cost_usd
        run.latency_ms = result.latency_ms
        run.finished_at = dt.datetime.now(dt.UTC)

        if result.extraction.currency and not version.currency:
            version.currency = result.extraction.currency.upper()[:3]
        version.status = TreatyVersionStatus.NEEDS_VALIDATION

        self._audit.record(
            AuditRecord(
                organization_id=organization_id,
                actor_type=ActorType.AGENT,
                action="treaty.extraction_completed",
                entity_type="treaty_version",
                entity_id=version.id,
                summary=(
                    f"extracted {candidate_count} term candidates "
                    f"({len(result.extraction.participations)} participations); "
                    f"needs human validation"
                ),
                payload={
                    "agent_run_id": str(run.id),
                    "model": result.model,
                    "candidates": candidate_count,
                    "suspected_injection": result.extraction.suspected_prompt_injection,
                },
            )
        )
        await self._session.commit()
        log.info(
            "treaty.extraction_completed",
            treaty_version_id=str(version.id),
            candidates=candidate_count,
        )
        return run

    def _persist_candidates(
        self,
        organization_id: UUID,
        treaty_version_id: UUID,
        document_id: UUID,
        agent_run_id: UUID,
        result: ExtractionResult,
    ) -> int:
        count = 0
        for term in result.extraction.terms:
            self._candidates.add(
                TreatyTermCandidate(
                    organization_id=organization_id,
                    treaty_version_id=treaty_version_id,
                    agent_run_id=agent_run_id,
                    key=term.key,
                    status=ExtractedTermStatus(term.status.value),
                    raw_value=term.value,
                    normalized_value={"value": term.value} if term.value is not None else None,
                    currency=(term.currency.upper()[:3] if term.currency else None),
                    confidence=_as_confidence(term.confidence),
                    citation=self._make_citation(organization_id, document_id, term.provenance),
                    reasoning=term.reasoning,
                )
            )
            count += 1

        for participation in result.extraction.participations:
            self._candidates.add(
                TreatyTermCandidate(
                    organization_id=organization_id,
                    treaty_version_id=treaty_version_id,
                    agent_run_id=agent_run_id,
                    key="participation",
                    status=ExtractedTermStatus.EXTRACTED,
                    raw_value=(
                        f"{participation.reinsurer_name}: {participation.placed_share_percent}%"
                    ),
                    normalized_value={
                        "reinsurer_name": participation.reinsurer_name,
                        "placed_share_percent": participation.placed_share_percent,
                    },
                    confidence=_as_confidence(participation.confidence),
                    citation=self._make_citation(
                        organization_id, document_id, participation.provenance
                    ),
                    reasoning="",
                )
            )
            count += 1
        return count

    def _make_citation(
        self, organization_id: UUID, document_id: UUID, provenance: Provenance | None
    ) -> Citation | None:
        if provenance is None:
            return None
        citation = Citation(
            organization_id=organization_id,
            document_id=document_id,
            page_number=provenance.page_number,
            section=provenance.section,
            quoted_text=provenance.quoted_text[:4000],
        )
        self._citations.add(citation)
        return citation


def _as_confidence(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(max(0.0, min(1.0, value)), 3)))


__all__ = ["ExtractionInputError", "Extractor", "TermCandidateStatus", "TreatyExtractionService"]
