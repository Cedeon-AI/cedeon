"""Draft a recovery notice, then let a human edit and approve it.

The drafter (docs/AI_ARCHITECTURE.md §2c) is a single structured-output call with
**no tools**. It runs only after the recovery candidate is CONFIRMED and receives
a whitelist of approved facts — no raw document text. Its output is a DRAFT. There
is deliberately **no send action** anywhere: a notice's terminal state is APPROVED
and a human takes it from there."""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.notice import NoticeDraftResult, draft_notice
from app.core.config import Settings
from app.core.logging import get_correlation_id, get_logger
from app.db.models.extraction import AgentRun, Review
from app.db.models.recoveries import RecoveryCalculation, RecoveryCandidate, RecoveryNotice
from app.domain.ai import AgentRunStatus, AgentType
from app.domain.audit import ActorType, AuditRecord
from app.domain.recoveries import (
    NoticeContext,
    NoticeInputs,
    NoticeKind,
    NoticeParticipant,
    NoticeRecipient,
    NoticeStatus,
    RecoveryCandidateStatus,
    build_notice_context,
)
from app.domain.reviews import ReviewDecision, ReviewSubjectType
from app.repositories.audit import AuditRepository
from app.repositories.extraction import AgentRunRepository
from app.repositories.losses import LossEventRepository
from app.repositories.recoveries import (
    RecoveryCandidateRepository,
    RecoveryNoticeRepository,
    RecoveryPacketRepository,
)
from app.repositories.reinsurance import TreatyRepository, TreatyVersionRepository
from app.services.auth import AuthenticatedContext
from app.services.errors import ConflictError, NotFoundError, ValidationError

log = get_logger(__name__)

NoticeDrafter = Callable[..., Awaitable[NoticeDraftResult]]

_NOTICE_DECISIONS = (
    ReviewDecision.CONFIRM,
    ReviewDecision.REJECT,
    ReviewDecision.REQUEST_INFO,
    ReviewDecision.EDIT,
)


class NoticeInputError(Exception):
    pass


@dataclass(slots=True)
class NoticeReview:
    decision: ReviewDecision
    subject: str | None = None
    body_markdown: str | None = None
    recipient: dict[str, str] | None = None
    reason: str | None = None


class NoticeService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        drafter: NoticeDrafter = draft_notice,
    ) -> None:
        self._session = session
        self._settings = settings
        self._drafter = drafter
        self._notices = RecoveryNoticeRepository(session)
        self._candidates = RecoveryCandidateRepository(session)
        self._packets = RecoveryPacketRepository(session)
        self._versions = TreatyVersionRepository(session)
        self._treaties = TreatyRepository(session)
        self._events = LossEventRepository(session)
        self._runs = AgentRunRepository(session)
        self._audit = AuditRepository(session)

    # --- reading -------------------------------------------------

    async def list_for_candidate(
        self, context: AuthenticatedContext, candidate_id: UUID
    ) -> list[RecoveryNotice]:
        return await self._notices.list_for_candidate(context.organization.id, candidate_id)

    async def get_notice(self, context: AuthenticatedContext, notice_id: UUID) -> RecoveryNotice:
        notice = await self._notices.get(context.organization.id, notice_id)
        if notice is None:
            raise NotFoundError("recovery notice not found")
        return notice

    # --- drafting ----------------------------------------------

    async def draft(
        self,
        organization_id: UUID,
        candidate_id: UUID,
        *,
        kind: NoticeKind,
        recipient: dict[str, str],
        actor_id: UUID | None = None,
    ) -> RecoveryNotice:
        if not self._settings.ai_enabled:
            raise ConflictError("AI is disabled in this environment")

        candidate = await self._candidates.get(organization_id, candidate_id)
        if candidate is None:
            raise NotFoundError("recovery candidate not found")
        if candidate.status not in (
            RecoveryCandidateStatus.CONFIRMED,
            RecoveryCandidateStatus.NOTICE_DRAFTED,
        ):
            raise ConflictError("confirm the recovery candidate before drafting a notice")
        calc = next(
            (c for c in candidate.calculations if c.id == candidate.current_calculation_id), None
        )
        if calc is None:
            raise ConflictError("the candidate has no calculation")

        recipient_vo = NoticeRecipient(
            name=str(recipient.get("name", "")).strip(),
            organisation=str(recipient.get("organisation", "")).strip(),
            role=str(recipient.get("role", "")).strip(),
            email=str(recipient.get("email", "")).strip(),
        )
        if not recipient_vo.name or not recipient_vo.organisation:
            raise ValidationError("the notice recipient needs a name and an organisation")

        if await self._runs.has_active_run(organization_id, AgentType.NOTICE_DRAFTER, candidate.id):
            raise ConflictError("a notice draft is already running for this candidate")

        context = await self._build_context(organization_id, candidate, calc, kind, recipient_vo)

        spec = self._settings.notice_drafter_model
        started = dt.datetime.now(dt.UTC)
        run = AgentRun(
            organization_id=organization_id,
            agent_type=AgentType.NOTICE_DRAFTER,
            subject_type="recovery_candidate",
            subject_id=candidate.id,
            provider=spec.split(":", 1)[0],
            model=spec,
            status=AgentRunStatus.RUNNING,
            input_ref={"recovery_candidate_id": str(candidate.id), "kind": kind.value},
            started_at=started,
        )
        self._runs.add(run)
        await self._session.flush()

        try:
            result = await self._drafter(notice_context=context, settings=self._settings)
        except Exception as exc:
            run.status = AgentRunStatus.FAILED
            run.error = str(exc)[:2000]
            run.finished_at = dt.datetime.now(dt.UTC)
            self._audit.record(
                AuditRecord(
                    organization_id=organization_id,
                    actor_type=ActorType.SYSTEM,
                    action="recovery_candidate.notice_draft_failed",
                    entity_type="recovery_candidate",
                    entity_id=candidate.id,
                    summary=f"notice draft failed: {type(exc).__name__}",
                    payload={"agent_run_id": str(run.id), "error": str(exc)[:500]},
                )
            )
            await self._session.commit()
            log.warning("recovery.notice_draft_failed", error_type=type(exc).__name__)
            raise

        draft = result.draft
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

        packet_version_id = await self._approved_packet_version_id(organization_id, candidate.id)
        notice = RecoveryNotice(
            organization_id=organization_id,
            recovery_candidate_id=candidate.id,
            recovery_packet_version_id=packet_version_id,
            agent_run_id=run.id,
            kind=kind,
            status=NoticeStatus.DRAFT,
            recipient=recipient_vo.to_dict(),
            subject=draft.subject[:300],
            body_markdown=draft.body_markdown,
            context=context.to_dict(),
            key_figures=dict(draft.key_figures),
            caveats=list(draft.caveats),
            used_only_provided_facts=draft.used_only_provided_facts,
            notes_for_reviewer=draft.notes_for_reviewer or None,
            generated_by=actor_id,
        )
        self._notices.add(notice)

        now = dt.datetime.now(dt.UTC)
        for prior in await self._notices.active_of_kind(organization_id, candidate.id, kind):
            prior.superseded_at = now
            if prior.status is NoticeStatus.DRAFT:
                prior.status = NoticeStatus.SUPERSEDED

        if candidate.status is RecoveryCandidateStatus.CONFIRMED:
            candidate.status = RecoveryCandidateStatus.NOTICE_DRAFTED

        self._audit.record(
            AuditRecord(
                organization_id=organization_id,
                actor_type=ActorType.AGENT,
                actor_id=actor_id,
                action="recovery_candidate.notice_drafted",
                entity_type="recovery_candidate",
                entity_id=candidate.id,
                summary=(
                    f"drafted a {kind.value.replace('_', ' ')} to "
                    f"{recipient_vo.organisation} (review before sending)"
                ),
                payload={
                    "agent_run_id": str(run.id),
                    "kind": kind.value,
                    "used_only_provided_facts": draft.used_only_provided_facts,
                    "model": result.model,
                },
            )
        )
        await self._session.commit()
        refreshed = await self._notices.get(organization_id, notice.id)
        assert refreshed is not None
        log.info(
            "recovery.notice_drafted", recovery_candidate_id=str(candidate.id), kind=kind.value
        )
        return refreshed

    # --- review ----------------------------------------------

    async def review(
        self, context: AuthenticatedContext, notice_id: UUID, review: NoticeReview
    ) -> RecoveryNotice:
        if review.decision not in _NOTICE_DECISIONS:
            raise ValidationError(f"unsupported notice decision {review.decision.value!r}")
        notice = await self.get_notice(context, notice_id)
        if notice.status is not NoticeStatus.DRAFT:
            raise ConflictError(f"this notice is already {notice.status.value}")

        org_id = context.organization.id
        before: dict[str, object] = {"status": notice.status.value}
        after: dict[str, object] = {"decision": review.decision.value}

        if review.decision is ReviewDecision.EDIT:
            before |= {
                "subject": notice.subject,
                "body_markdown": notice.body_markdown,
                "recipient": dict(notice.recipient),
            }
            if review.subject is not None:
                notice.subject = review.subject[:300]
            if review.body_markdown is not None:
                notice.body_markdown = review.body_markdown
            if review.recipient is not None:
                merged = dict(notice.recipient)
                merged.update({k: v for k, v in review.recipient.items() if v is not None})
                notice.recipient = merged
            after |= {
                "subject": notice.subject,
                "body_markdown": notice.body_markdown,
                "recipient": dict(notice.recipient),
            }
        elif review.decision is ReviewDecision.CONFIRM:
            notice.status = NoticeStatus.APPROVED
            notice.approved_by = context.user.id
            notice.approved_at = dt.datetime.now(dt.UTC)
            after["status"] = notice.status.value
        elif review.decision is ReviewDecision.REJECT:
            notice.status = NoticeStatus.REJECTED
            after["status"] = notice.status.value
        else:  # REQUEST_INFO
            notice.review_note = review.reason

        review_row = Review(
            organization_id=org_id,
            subject_type=ReviewSubjectType.RECOVERY_NOTICE,
            subject_id=notice.id,
            reviewer_id=context.user.id,
            decision=review.decision,
            value_before=before,
            value_after=after,
            reason=review.reason,
        )
        self._session.add(review_row)
        self._audit.record(
            AuditRecord(
                organization_id=org_id,
                actor_type=ActorType.USER,
                actor_id=context.user.id,
                action="recovery_notice.reviewed",
                entity_type="recovery_candidate",
                entity_id=notice.recovery_candidate_id,
                summary=(
                    f"{context.user.email} {review.decision.value} the "
                    f"{notice.kind.value.replace('_', ' ')} notice"
                ),
                payload={
                    "recovery_notice_id": str(notice.id),
                    "decision": review.decision.value,
                    "status": notice.status.value,
                },
                correlation_id=get_correlation_id(),
            )
        )
        await self._session.commit()
        refreshed = await self._notices.get(org_id, notice.id)
        assert refreshed is not None
        return refreshed

    # --- helpers ---------------------------------------------

    async def _approved_packet_version_id(
        self, organization_id: UUID, candidate_id: UUID
    ) -> UUID | None:
        packet = await self._packets.for_candidate(organization_id, candidate_id)
        if packet is None:
            return None
        approved = [v for v in packet.versions if v.status.value == "approved"]
        if approved:
            return max(approved, key=lambda v: v.version_no).id
        return None

    async def _build_context(
        self,
        organization_id: UUID,
        candidate: RecoveryCandidate,
        calc: RecoveryCalculation,
        kind: NoticeKind,
        recipient: NoticeRecipient,
    ) -> NoticeContext:
        version = await self._versions.get(organization_id, candidate.treaty_version_id)
        assert version is not None
        treaty = await self._treaties.get(organization_id, candidate.treaty_id)
        assert treaty is not None
        layer = next((x for x in version.layers if x.id == candidate.treaty_layer_id), None)
        assert layer is not None
        event = await self._events.get(organization_id, candidate.loss_event_id)
        assert event is not None

        notice_provision = next(
            (
                str(t.value.get("value", t.value))
                for t in version.terms
                if t.key == "notice_provision"
            ),
            None,
        )
        participants = [
            NoticeParticipant(
                name=a.reinsurer.name,
                share_percent=f"{Decimal(a.participation_share) * 100:g}%",
                allocated_recovery=str(a.allocated_recovery),
            )
            for a in calc.allocations
        ]
        packet_approved = (
            await self._approved_packet_version_id(organization_id, candidate.id)
        ) is not None

        return build_notice_context(
            NoticeInputs(
                kind=kind,
                recipient=recipient,
                cedent_name=treaty.program.cedent.name,
                treaty_name=treaty.name,
                program_name=treaty.program.name,
                currency=layer.currency,
                attachment=str(layer.attachment),
                limit=str(layer.limit),
                loss_event_name=event.name,
                catastrophe_code=event.catastrophe_code,
                date_of_loss_from=(
                    event.date_of_loss_from.isoformat() if event.date_of_loss_from else None
                ),
                date_of_loss_to=(
                    event.date_of_loss_to.isoformat() if event.date_of_loss_to else None
                ),
                gross_event_incurred=str(candidate.gross_event_incurred),
                layer_recovery=str(calc.layer_recovery),
                engine_version=str(calc.engine_version),
                participants=participants,
                notice_provision=notice_provision,
                packet_approved=packet_approved,
                generated_on=dt.date.today().isoformat(),
            )
        )
