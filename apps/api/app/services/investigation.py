"""Run the Recovery Investigator and persist its output + telemetry.

Runnable directly (tests inject a fake runner) or from the
``investigate_recovery_candidate`` Procrastinate task. The agent is bounded and
read-only; it never computes the recovery — that stays deterministic (ADR-0010).
Every finding that should be evidenced is checked against real page text before it
is stored (ADR-0011)."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.investigator import InvestigationResult, InvestigatorDeps, run_investigator
from app.ai.investigator.schema import Finding
from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models.extraction import AgentRun, Citation, ToolCall
from app.db.models.recoveries import RecoveryInvestigation, RecoveryInvestigationFinding
from app.domain.ai import (
    AgentRunStatus,
    AgentType,
    ApplicabilityAssessment,
    FindingKind,
    InvestigationStatus,
)
from app.domain.audit import ActorType, AuditRecord
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.extraction import AgentRunRepository, ToolCallRepository
from app.repositories.recoveries import (
    RecoveryCandidateRepository,
    RecoveryInvestigationRepository,
)
from app.repositories.reinsurance import TreatyVersionRepository
from app.services.ai_budget import AiBudgetService
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError

log = get_logger(__name__)

InvestigatorRunner = Callable[..., Awaitable[InvestigationResult]]

_CITE_KINDS = {
    FindingKind.RELEVANT_CLAUSE,
    FindingKind.SUPPORTING_EVIDENCE,
    FindingKind.NOTICE_OBLIGATION,
    FindingKind.INCONSISTENCY,
}


class InvestigationInputError(Exception):
    pass


class InvestigationService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        runner: InvestigatorRunner = run_investigator,
    ) -> None:
        self._session = session
        self._settings = settings
        self._runner = runner
        self._candidates = RecoveryCandidateRepository(session)
        self._investigations = RecoveryInvestigationRepository(session)
        self._versions = TreatyVersionRepository(session)
        self._documents = DocumentRepository(session)
        self._runs = AgentRunRepository(session)
        self._tool_calls = ToolCallRepository(session)
        self._audit = AuditRepository(session)

    # --- reading -------------------------------------------------

    async def list_for_candidate(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> list[RecoveryInvestigation]:
        return await self._investigations.list_for_candidate(context.organization.id, candidate_id)

    async def tool_calls(self, context: AuthenticatedContext, agent_run_id: UUID) -> list[ToolCall]:
        return await self._tool_calls.list_for_run(context.organization.id, agent_run_id)

    # --- running ------------------------------------------------

    async def investigate(
        self, organization_id: UUID, candidate_id: UUID, *, actor_id: UUID | None = None
    ) -> RecoveryInvestigation:
        await AiBudgetService(self._session, self._settings).enforce(organization_id)

        candidate = await self._candidates.get(organization_id, candidate_id)
        if candidate is None:
            raise NotFoundError("recovery candidate not found")
        calc = next(
            (c for c in candidate.calculations if c.id == candidate.current_calculation_id), None
        )
        if calc is None:
            raise ConflictError("the candidate has no calculation to investigate")

        version = await self._versions.get(organization_id, candidate.treaty_version_id)
        if version is None or version.source_document_id is None:
            raise InvestigationInputError("the treaty version has no source document")
        document_id = version.source_document_id

        if await self._runs.has_active_run(
            organization_id, AgentType.RECOVERY_INVESTIGATOR, candidate.id
        ):
            raise ConflictError("an investigation is already running for this candidate")

        spec = self._settings.recovery_investigator_model
        started = dt.datetime.now(dt.UTC)
        run = AgentRun(
            organization_id=organization_id,
            agent_type=AgentType.RECOVERY_INVESTIGATOR,
            subject_type="recovery_candidate",
            subject_id=candidate.id,
            provider=spec.split(":", 1)[0],
            model=spec,
            status=AgentRunStatus.RUNNING,
            input_ref={
                "recovery_candidate_id": str(candidate.id),
                "recovery_calculation_id": str(calc.id),
            },
            started_at=started,
        )
        self._runs.add(run)
        investigation = RecoveryInvestigation(
            organization_id=organization_id,
            recovery_candidate_id=candidate.id,
            status=InvestigationStatus.RUNNING,
        )
        self._investigations.add(investigation)
        await self._session.flush()
        investigation.agent_run_id = run.id

        deps = InvestigatorDeps(
            session=self._session,
            organization_id=organization_id,
            candidate_id=candidate.id,
        )
        prompt_context = {
            "candidate_id": str(candidate.id),
            "layer_recovery": str(calc.layer_recovery),
            "currency": calc.currency,
            "engine_version": calc.engine_version,
            "gross_event_incurred": str(candidate.gross_event_incurred),
            "currency_mismatch": str(candidate.currency_mismatch),
        }

        try:
            result = await self._runner(
                deps=deps, prompt_context=prompt_context, settings=self._settings
            )
        except Exception as exc:
            run.status = AgentRunStatus.FAILED
            run.error = str(exc)[:2000]
            run.finished_at = dt.datetime.now(dt.UTC)
            investigation.status = InvestigationStatus.FAILED
            investigation.error = str(exc)[:2000]
            self._audit.record(
                AuditRecord(
                    organization_id=organization_id,
                    actor_type=ActorType.SYSTEM,
                    action="recovery_candidate.investigation_failed",
                    entity_type="recovery_candidate",
                    entity_id=candidate.id,
                    summary=f"recovery investigation failed: {type(exc).__name__}",
                    payload={"agent_run_id": str(run.id), "error": str(exc)[:500]},
                )
            )
            await self._session.commit()
            log.warning("recovery.investigation_failed", error_type=type(exc).__name__)
            raise

        # Persist tool-call telemetry.
        for entry in result.tool_calls:
            self._tool_calls.add(
                ToolCall(
                    organization_id=organization_id,
                    agent_run_id=run.id,
                    ordinal=entry.ordinal,
                    tool_name=entry.tool_name,
                    arguments=entry.arguments,
                    result_summary=entry.result_summary,
                    status=entry.status,
                )
            )

        # Grounding gate: a finding that should cite must quote real page text.
        page_text = await self._page_text(organization_id, document_id)
        findings = _ground_findings(result.investigation.findings, page_text)

        for ordinal, finding in enumerate(findings):
            citation_row: Citation | None = None
            if finding.citation is not None:
                citation_row = Citation(
                    organization_id=organization_id,
                    document_id=document_id,
                    page_number=finding.citation.page_number,
                    section=finding.citation.section,
                    quoted_text=finding.citation.quoted_text,
                )
                self._session.add(citation_row)
            self._session.add(
                RecoveryInvestigationFinding(
                    organization_id=organization_id,
                    investigation_id=investigation.id,
                    ordinal=ordinal,
                    kind=FindingKind(finding.kind.value),
                    text=finding.text,
                    confidence=_as_confidence(finding.confidence),
                    citation=citation_row,
                )
            )

        inv = result.investigation
        investigation.status = InvestigationStatus.COMPLETED
        investigation.summary = inv.summary
        investigation.applicability_assessment = ApplicabilityAssessment(
            inv.applicability_assessment.value
        )
        investigation.confidence = _as_confidence(inv.overall_confidence)
        investigation.out_of_scope = inv.out_of_scope
        investigation.suspected_prompt_injection = inv.suspected_prompt_injection
        investigation.unresolved_questions = list(inv.unresolved_questions)
        investigation.output = result.output

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

        # Newest completed investigation supersedes the rest.
        now = dt.datetime.now(dt.UTC)
        for prior in await self._investigations.active_for_candidate(organization_id, candidate.id):
            if prior.id != investigation.id:
                prior.superseded_at = now

        self._audit.record(
            AuditRecord(
                organization_id=organization_id,
                actor_type=ActorType.AGENT,
                actor_id=actor_id,
                action="recovery_candidate.investigated",
                entity_type="recovery_candidate",
                entity_id=candidate.id,
                summary=(
                    f"recovery investigation: {inv.applicability_assessment.value}, "
                    f"{len(findings)} findings"
                    + (" (flagged possible injection)" if inv.suspected_prompt_injection else "")
                ),
                payload={
                    "agent_run_id": str(run.id),
                    "investigation_id": str(investigation.id),
                    "model": result.model,
                    "applicability": inv.applicability_assessment.value,
                    "tool_calls": len(result.tool_calls),
                    "recomputed_a_different_number": inv.recomputed_a_different_number,
                    "suspected_injection": inv.suspected_prompt_injection,
                },
            )
        )
        await self._session.commit()
        log.info(
            "recovery.investigation_completed",
            recovery_candidate_id=str(candidate.id),
            findings=len(findings),
            applicability=inv.applicability_assessment.value,
        )
        refreshed = await self._investigations.list_for_candidate(organization_id, candidate.id)
        return refreshed[0]

    # --- helpers -----------------------------------------------

    async def _page_text(self, organization_id: UUID, document_id: UUID) -> dict[int, str]:
        parse = await self._documents.current_parse(organization_id, document_id)
        if parse is None:
            return {}
        pages = await self._documents.list_pages(organization_id, parse.id)
        return {p.page_number: p.text for p in pages}


_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def _ground_findings(findings: list[Finding], page_text: dict[int, str]) -> list[Finding]:
    """Drop a citation whose quote is not actually on the cited page; a finding that
    then has no citation but needed one is downgraded to an ambiguity."""
    grounded: list[Finding] = []
    for finding in findings:
        citation = finding.citation
        if citation is not None:
            haystack = _norm(page_text.get(citation.page_number, ""))
            if not haystack or _norm(citation.quoted_text) not in haystack:
                finding = finding.model_copy(update={"citation": None})
        if finding.citation is None and finding.kind in _CITE_KINDS:
            finding = finding.model_copy(
                update={
                    "kind": FindingKind.AMBIGUITY,
                    "text": f"[unverified] {finding.text}",
                }
            )
        grounded.append(finding)
    return grounded


def _as_confidence(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(1.0, value)), 3)
